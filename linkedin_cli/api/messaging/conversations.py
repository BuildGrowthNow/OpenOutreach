# linkedin/api/messaging/conversations.py
"""Retrieve conversations and messages via Voyager Messaging GraphQL API.

Query-ID resilience
-------------------
LinkedIn periodically rotates the opaque hash in GraphQL query IDs like
``messengerConversations.0d5e6781bbee71c3e51c8843c6519f48``.  When a rotation
happens every request using the stale ID returns HTTP 400, breaking message
sync silently.

Mitigation - two-layer approach:

1. **Passive capture**: ``install_query_id_listener(session)`` attaches a
   context-level request listener that watches *every* outgoing
   ``voyagerMessagingGraphQL/graphql`` request the browser makes (including
   LinkedIn's own frontend requests) and caches the queryId it finds.  The
   cache is module-global so it survives across multiple API instances.

2. **400 invalidation + retry**: When a fetch call gets HTTP 400 (the stale-ID
   signal), it clears the cached ID and logs a warning.  Tenacity's retry
   decorator then re-invokes the function; the resolver returns the fallback
   hard-coded ID (or a freshly-captured one if the listener fired in the
   meantime).  After three retries the IOError propagates normally.

Both hard-coded IDs are kept as ``_FALLBACK_*`` constants.  They are used when
no live ID has been captured yet and as the last-resort value after a cached ID
is invalidated.
"""
import logging
import re
import weakref

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from linkedin_cli.api.client import PlaywrightLinkedinAPI
from linkedin_cli.api.messaging.utils import encode_urn, check_response

logger = logging.getLogger(__name__)

_GRAPHQL_BASE = "https://www.linkedin.com/voyager/api/voyagerMessagingGraphQL/graphql"
_GRAPHQL_PATH = "/voyager/api/voyagerMessagingGraphQL/graphql"

# Last-known-good query IDs.  Used when no live ID has been captured yet and as
# the fallback after a stale cached ID is invalidated.
_FALLBACK_CONVERSATIONS_QUERY_ID = "messengerConversations.0d5e6781bbee71c3e51c8843c6519f48"
_FALLBACK_MESSAGES_QUERY_ID = "messengerMessages.5846eeb71c981f11e0134cb6626cc314"

# queryId=messengerConversations.{hash}  or  queryId=messengerMessages.{hash}
_QUERY_ID_RE = re.compile(r"[?&]queryId=(messengerConversations\.[^&\s]+|messengerMessages\.[^&\s]+)")

# Module-global cache: {"messengerConversations": "…full id…", "messengerMessages": "…"}
_id_cache: dict[str, str] = {}

# Contexts that already have the passive listener installed (WeakSet so closed
# contexts are GC'd without holding a reference here).
_instrumented: weakref.WeakSet = weakref.WeakSet()


# ── Passive query-ID capture ───────────────────────────────────────────────────

def _on_graphql_request(request) -> None:
    """Request event handler - extracts query IDs from messengerGraphQL URLs.

    Runs in the Playwright event loop for every browser request; must not block.
    """
    url = request.url
    if _GRAPHQL_PATH not in url:
        return
    m = _QUERY_ID_RE.search(url)
    if not m:
        return
    full_id = m.group(1)                    # e.g. "messengerConversations.abc123"
    name = full_id.split(".", 1)[0]         # e.g. "messengerConversations"
    if _id_cache.get(name) != full_id:
        logger.info("Captured fresh queryId for %s: %s", name, full_id)
        _id_cache[name] = full_id


def install_query_id_listener(session) -> None:
    """Attach a request listener on *session.context* to capture live query IDs.

    Idempotent - safe to call on every messaging operation; the listener is
    installed at most once per browser context (tracked via WeakSet so closed
    contexts are cleaned up automatically).
    """
    ctx = getattr(session, "context", None)
    if ctx is None:
        return
    if ctx in _instrumented:
        return
    try:
        ctx.on("request", _on_graphql_request)
        _instrumented.add(ctx)
        logger.debug("Installed messengerGraphQL query-ID listener on context")
    except Exception as exc:
        # Context may already be closing; log and move on.
        logger.debug("Could not install query-ID listener: %s", exc)


# ── ID resolvers (live-captured → fallback) ────────────────────────────────────

def _conversations_query_id() -> str:
    """Return the best available conversations query ID."""
    return _id_cache.get("messengerConversations") or _FALLBACK_CONVERSATIONS_QUERY_ID


def _messages_query_id() -> str:
    """Return the best available messages query ID."""
    return _id_cache.get("messengerMessages") or _FALLBACK_MESSAGES_QUERY_ID


# ── HTTP layer ─────────────────────────────────────────────────────────────────

def _graphql_headers(api: PlaywrightLinkedinAPI) -> dict:
    headers = {**api.headers}
    headers["accept"] = "application/graphql"
    return headers


def _handle_graphql_400(res, cache_key: str, query_id: str, context: str) -> None:
    """Log a clear warning and invalidate the cached ID on HTTP 400.

    Tenacity will retry the outer function; the resolver will then return the
    fallback hard-coded ID (or a freshly-captured one).
    """
    was_cached = _id_cache.pop(cache_key, None) is not None
    body_snippet = res.text()[:300]
    if was_cached:
        logger.warning(
            "%s: queryId '%s' returned HTTP 400 - cached ID invalidated, "
            "next retry will use fallback. Response body: %s",
            context, query_id, body_snippet,
        )
    else:
        logger.warning(
            "%s: fallback queryId '%s' also returned HTTP 400 - "
            "LinkedIn may have rotated all known IDs. "
            "The passive listener will capture a fresh ID on the next "
            "LinkedIn messaging page load. Response body: %s",
            context, query_id, body_snippet,
        )


# ── Public API ─────────────────────────────────────────────────────────────────

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    retry=retry_if_exception_type(IOError),
    reraise=True,
)
def fetch_conversations(api: PlaywrightLinkedinAPI, mailbox_urn: str) -> dict:
    """Fetch recent conversations list. Returns raw API response."""
    install_query_id_listener(api.session)

    qid = _conversations_query_id()
    url = (
        f"{_GRAPHQL_BASE}"
        f"?queryId={qid}"
        f"&variables=(mailboxUrn:{encode_urn(mailbox_urn)})"
    )
    res = api.get(url, headers=_graphql_headers(api))

    if res.status == 400:
        _handle_graphql_400(res, "messengerConversations", qid, "fetch_conversations")

    check_response(res, "fetch_conversations")
    return res.json()


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    retry=retry_if_exception_type(IOError),
    reraise=True,
)
def fetch_messages(api: PlaywrightLinkedinAPI, conversation_urn: str) -> dict:
    """Fetch messages for a conversation. Returns raw API response."""
    install_query_id_listener(api.session)

    qid = _messages_query_id()
    url = (
        f"{_GRAPHQL_BASE}"
        f"?queryId={qid}"
        f"&variables=(conversationUrn:{encode_urn(conversation_urn)})"
    )
    res = api.get(url, headers=_graphql_headers(api))

    if res.status == 400:
        _handle_graphql_400(res, "messengerMessages", qid, "fetch_messages")

    check_response(res, "fetch_messages")
    return res.json()
