"""LLM model factory + sync boundary for pydantic-ai.

Two public entry points:

- `get_llm_model()` - builds a `pydantic_ai.Model` from `SiteConfig`,
  routing to the right provider.
- `run_agent_sync(coro)` - drives a pydantic-ai coroutine to completion
  from sync code, on a dedicated worker thread with a long-lived event
  loop. Used everywhere instead of `Agent.run_sync`.

Why a persistent worker thread (not `Agent.run_sync`, not `asyncio.run`):

- `Agent.run_sync` uses an anyio portal that leaves the caller thread's
  running-loop slot populated. Subsequent sync Playwright calls on the
  daemon thread then raise
  `"using Playwright Sync API inside the asyncio loop"`.
- `asyncio.run` per call closes its loop on exit. The openai / anthropic
  SDKs wrap `httpx.AsyncClient` in a subclass whose `__del__` does
  `get_running_loop().create_task(self.aclose())`. If GC fires the
  wrapper from call N during call N+1's loop, the cleanup task tries to
  close a transport bound to call N's now-closed loop →
  `RuntimeError: Event loop is closed`.

A single long-lived loop on a dedicated thread eliminates both: all HTTP
clients live on the same loop forever, and the runner thread's asyncio
slot stays inside this module - the caller thread is never touched.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from contextlib import asynccontextmanager
from typing import Awaitable, Callable, TypeVar

from pydantic_ai.models import Model
from pydantic_ai.models.openai import OpenAIChatModel

_T = TypeVar("_T")

# Override the SDK default of 2. Each retry uses the SDK's built-in jittered
# exponential backoff and honors `Retry-After`, so 8 attempts ride through
# typical 429/529 capacity blips (~1–2 minutes) instead of failing in ~1.5s.
_MAX_RETRIES = 8
logger = logging.getLogger(__name__)


# ── Async runner ─────────────────────────────────────────────────────


class _AgentRunner:
    """Owns one persistent asyncio loop on a dedicated daemon thread.

    Construct lazily via `_get_runner()` so importing this module is free.
    The thread is a daemon, so no explicit shutdown is needed - it ends
    with the process.
    """

    def __init__(self):
        self._loop = asyncio.new_event_loop()
        ready = threading.Event()
        threading.Thread(
            target=self._serve,
            args=(ready,),
            daemon=True,
            name="llm-runner",
        ).start()
        ready.wait()

    def _serve(self, ready: threading.Event) -> None:
        asyncio.set_event_loop(self._loop)
        ready.set()
        self._loop.run_forever()

    def run(self, coro: Awaitable[_T]) -> _T:
        """Submit *coro* to the runner loop; block until it completes."""

        # Convert Awaitable to Coroutine for run_coroutine_threadsafe
        async def _ensure_coroutine() -> _T:
            return await coro

        return asyncio.run_coroutine_threadsafe(
            _ensure_coroutine(), self._loop
        ).result()


_runner: _AgentRunner | None = None
_runner_lock = threading.Lock()


def _get_runner() -> _AgentRunner:
    """Return the process-wide runner, creating it on first call."""
    global _runner
    if _runner is None:
        with _runner_lock:
            if _runner is None:
                _runner = _AgentRunner()
    return _runner


def run_agent_sync(coro: Awaitable[_T]) -> _T:
    """Drive *coro* on the dedicated LLM runner thread + loop."""
    return _get_runner().run(coro)


# ── Per-provider builders ────────────────────────────────────────────


def _build_openai(cfg):
    from openai import AsyncOpenAI
    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.providers.openai import OpenAIProvider

    client = AsyncOpenAI(api_key=cfg.llm_api_key, max_retries=_MAX_RETRIES)
    return OpenAIChatModel(cfg.ai_model, provider=OpenAIProvider(openai_client=client))


def _build_anthropic(cfg):
    from anthropic import AsyncAnthropic
    from pydantic_ai.models.anthropic import AnthropicModel
    from pydantic_ai.providers.anthropic import AnthropicProvider

    client = AsyncAnthropic(api_key=cfg.llm_api_key, max_retries=_MAX_RETRIES)
    return AnthropicModel(
        cfg.ai_model, provider=AnthropicProvider(anthropic_client=client)
    )


def _build_google(cfg):
    from pydantic_ai.models.google import GoogleModel
    from pydantic_ai.providers.google import GoogleProvider

    return GoogleModel(cfg.ai_model, provider=GoogleProvider(api_key=cfg.llm_api_key))


def _build_groq(cfg):
    from groq import AsyncGroq
    from pydantic_ai.models.groq import GroqModel
    from pydantic_ai.providers.groq import GroqProvider

    client = AsyncGroq(api_key=cfg.llm_api_key, max_retries=_MAX_RETRIES)
    return GroqModel(cfg.ai_model, provider=GroqProvider(groq_client=client))


def _build_mistral(cfg):
    from pydantic_ai.models.mistral import MistralModel
    from pydantic_ai.providers.mistral import MistralProvider

    return MistralModel(cfg.ai_model, provider=MistralProvider(api_key=cfg.llm_api_key))


def _build_cohere(cfg):
    from pydantic_ai.models.cohere import CohereModel
    from pydantic_ai.providers.cohere import CohereProvider

    return CohereModel(cfg.ai_model, provider=CohereProvider(api_key=cfg.llm_api_key))


def _build_openai_compatible(cfg):
    if not cfg.llm_api_base:
        raise ValueError("LLM_API_BASE is required for the openai_compatible provider.")
    from openai import AsyncOpenAI
    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.providers.openai import OpenAIProvider

    client = AsyncOpenAI(
        base_url=cfg.llm_api_base,
        api_key=cfg.llm_api_key,
        max_retries=_MAX_RETRIES,
    )
    return OpenAIChatModel(cfg.ai_model, provider=OpenAIProvider(openai_client=client))


def _build_cloudflare_workers_ai(cfg):
    """Build an OpenAI-compatible model backed by Cloudflare Workers AI."""
    from openai import AsyncOpenAI
    from pydantic_ai.providers.openai import OpenAIProvider
    from openoutreach.config import settings

    account_id = settings.CLOUDFLARE_ACCOUNT_ID.strip()
    # Prefer the deployment secret, but allow an encrypted per-user token from
    # SiteConfig for installations that configure providers in the Settings UI.
    api_token = (settings.CLOUDFLARE_API_TOKEN or cfg.llm_api_key).strip()
    if not account_id:
        raise ValueError("CLOUDFLARE_ACCOUNT_ID is required for cloudflare_workers_ai.")
    if not api_token:
        raise ValueError("CLOUDFLARE_API_TOKEN is required for cloudflare_workers_ai.")

    def build_model(model_name: str):
        client = AsyncOpenAI(
            base_url=f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/v1",
            api_key=api_token,
            max_retries=_MAX_RETRIES,
        )
        return OpenAIChatModel(model_name, provider=OpenAIProvider(openai_client=client))

    models = [build_model(cfg.ai_model)]
    fallback_names = getattr(settings, "AI_MODEL_FALLBACKS", "")
    for model_name in fallback_names.split(","):
        model_name = model_name.strip()
        if model_name and model_name not in {cfg.ai_model, *(m.model_name for m in models)}:
            models.append(build_model(model_name))
    return _FallbackModel(models) if len(models) > 1 else models[0]


def _is_transient_model_error(error: Exception) -> bool:
    """Return whether a model error is safe to retry on another model."""
    status_code = getattr(error, "status_code", None)
    if status_code in {408, 409, 429} or (isinstance(status_code, int) and status_code >= 500):
        return True
    return any(
        marker in type(error).__name__.lower()
        for marker in ("timeout", "connection", "rate_limit", "internalserver")
    )


class _FallbackModel(Model):
    """Try configured models in order when a provider has a transient failure."""

    def __init__(self, models: list[Model]):
        super().__init__(profile=models[0].profile)
        self._models = models

    @property
    def model_name(self) -> str:
        return self._models[0].model_name

    @property
    def system(self) -> str:
        return self._models[0].system

    @property
    def provider(self):
        return self._models[0].provider

    @property
    def base_url(self) -> str | None:
        return self._models[0].base_url

    async def request(self, messages, model_settings, model_request_parameters):
        last_error = None
        for index, model in enumerate(self._models):
            try:
                return await model.request(messages, model_settings, model_request_parameters)
            except Exception as error:
                last_error = error
                if not _is_transient_model_error(error) or index == len(self._models) - 1:
                    raise
                logger.warning(
                    "LLM model failed transiently; trying fallback %s/%s (%s)",
                    index + 1,
                    len(self._models),
                    type(error).__name__,
                )
        raise last_error  # pragma: no cover

    @asynccontextmanager
    async def request_stream(self, messages, model_settings, model_request_parameters, run_context=None):
        last_error = None
        for index, model in enumerate(self._models):
            try:
                async with model.request_stream(
                    messages, model_settings, model_request_parameters, run_context
                ) as stream:
                    yield stream
                return
            except Exception as error:
                last_error = error
                if not _is_transient_model_error(error) or index == len(self._models) - 1:
                    raise
                logger.warning(
                    "LLM streaming model failed transiently; trying fallback %s/%s (%s)",
                    index + 1,
                    len(self._models),
                    type(error).__name__,
                )
        raise last_error  # pragma: no cover


_PROVIDER_BUILDERS: dict[str, Callable] = {
    "openai": _build_openai,
    "anthropic": _build_anthropic,
    "google": _build_google,
    "groq": _build_groq,
    "mistral": _build_mistral,
    "cohere": _build_cohere,
    "openai_compatible": _build_openai_compatible,
    "cloudflare_workers_ai": _build_cloudflare_workers_ai,
}


# ── Model factory ────────────────────────────────────────────────────


def _validated_site_config(user_id: str | None = None):
    """Load `SiteConfig` and assert the required LLM fields are populated.

    Falls back to .env values (via settings) when the user hasn't configured
    LLM settings in the database - allows a platform-level default key.
    """
    from openoutreach.core.models import SiteConfig
    from openoutreach.config import settings

    cfg = SiteConfig.load(user_id=user_id)

    if not cfg.llm_api_key:
        # Lifetime plan users must supply their own key - they are not entitled to the
        # platform-managed LLM key.
        if user_id:
            from openoutreach.mongodb.models_user import User
            user = User.get(user_id)
            if user and user.plan == "lifetime":
                raise ValueError(
                    "Lifetime plan requires your own LLM API key. "
                    "Add it in Settings → LLM / AI Settings."
                )

        # No custom key - use the full platform LLM config (key, provider, model, base).
        # Always override provider here: core/models.py defaults it to "openai" even when
        # the DB has no value, so `not cfg.llm_provider` would never be true.
        cfg.llm_api_key = (
            settings.CLOUDFLARE_API_TOKEN
            if settings.LLM_PROVIDER == "cloudflare_workers_ai"
            else settings.LLM_API_KEY
        )
        cfg.llm_provider = settings.LLM_PROVIDER
        cfg.ai_model = cfg.ai_model or settings.AI_MODEL
        cfg.llm_api_base = cfg.llm_api_base or settings.LLM_API_BASE or ""
    else:
        # Custom key set - fill in any missing fields from platform defaults
        if not cfg.ai_model and settings.AI_MODEL:
            cfg.ai_model = settings.AI_MODEL
        if not cfg.llm_api_base and settings.LLM_API_BASE:
            cfg.llm_api_base = settings.LLM_API_BASE

    if not cfg.llm_api_key:
        raise ValueError("LLM_API_KEY is not set in Site Configuration or .env")
    if not cfg.ai_model:
        raise ValueError("AI_MODEL is not set in Site Configuration or .env")
    return cfg


def get_llm_model(user_id: str | None = None):
    """Return a configured pydantic-ai `Model` for the current `SiteConfig`."""
    cfg = _validated_site_config(user_id=user_id)
    builder = _PROVIDER_BUILDERS.get(cfg.llm_provider)
    if builder is None:
        raise ValueError(f"Unknown LLM provider: {cfg.llm_provider!r}")
    return builder(cfg)
