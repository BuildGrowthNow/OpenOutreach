import logging
import os
import sys

from django.core.management import call_command
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Run the OpenOutreach daemon (onboard, validate, start task queue)."

    def handle(self, *args, **options):
        self._configure_logging(verbose=options["verbosity"] >= 2)
        self._ensure_db()
        self._ensure_onboarded()
        session = self._create_session()
        self._ensure_newsletter(session)

        from openoutreach.core.daemon import run_daemon
        run_daemon(session)

    # -- Steps ---------------------------------------------------------------

    def _configure_logging(self, verbose: bool = False):
        from openoutreach.core.logging import configure_logging, print_banner

        level = logging.DEBUG if verbose else logging.INFO
        configure_logging(level=level)
        print_banner()

    def _ensure_db(self):
        call_command("migrate", "--no-input")

        from openoutreach.core.management.setup_crm import setup_crm
        setup_crm()

    def _ensure_onboarded(self):
        from openoutreach.core.onboarding import apply, collect_from_wizard, missing_keys
        from openoutreach.core.models import SiteConfig, Campaign
        from openoutreach.linkedin.models import LinkedInProfile

        # If onboarding is complete, skip
        if not missing_keys():
            return

        # In container mode, auto-configure from environment variables
        if os.environ.get("DOCKER_ENV") == "true":
            from openoutreach.core.onboarding import OnboardConfig

            config = OnboardConfig()

            # LLM Configuration from env
            if llm_key := os.environ.get("LLM_API_KEY"):
                config.llm_api_key = llm_key
            if llm_base := os.environ.get("LLM_API_BASE"):
                config.llm_api_base = llm_base
            if ai_model := os.environ.get("AI_MODEL"):
                config.ai_model = ai_model
            # Default LLM provider based on API base
            if "bedrock" in (llm_base or ""):
                config.llm_provider = "openai_compatible"
            else:
                config.llm_provider = os.environ.get("LLM_PROVIDER", "openai")

            # LinkedIn Configuration from env
            if linkedin_email := os.environ.get("LINKEDIN_USERNAME"):
                config.linkedin_email = linkedin_email
            if linkedin_password := os.environ.get("LINKEDIN_PASSWORD"):
                config.linkedin_password = linkedin_password

            # Apply the configuration
            apply(config)
            self.stderr.write("[INFO] Auto-configured from environment variables.\n")
            return

        if sys.stdin.isatty():
            apply(collect_from_wizard())
        else:
            missing = missing_keys()
            self.stderr.write(
                f"[ERROR] Onboarding incomplete and no TTY available.\n"
                f"[ERROR] Missing: {', '.join(sorted(missing))}\n"
                f"[ERROR] Run with an interactive terminal to complete onboarding."
            )
            sys.exit(1)

    def _create_session(self):
        from openoutreach.linkedin.browser.registry import get_first_active_profile, get_or_create_session
        from openoutreach.core.models import SiteConfig

        if not SiteConfig.load().llm_api_key:
            logger.error("LLM_API_KEY is required. Set it in Site Configuration (Django Admin).")
            sys.exit(1)

        profile = get_first_active_profile()
        if profile is None:
            logger.error("No active LinkedIn profiles found.")
            sys.exit(1)

        session = get_or_create_session(profile)

        if not session.campaigns:
            logger.error("No campaigns found for this user.")
            sys.exit(1)
        campaign = next(
            (c for c in session.campaigns if not c.is_freemium), None,
        ) or session.campaigns[0]
        session.campaign = campaign

        return session

    def _ensure_newsletter(self, session):
        if session.linkedin_profile.newsletter_processed:
            return

        from openoutreach.linkedin.api.newsletter import ensure_newsletter_subscription
        from openoutreach.linkedin.setup.gdpr import apply_gdpr_newsletter_override
        from linkedin_cli.url_utils import public_id_to_url

        profile = session.self_profile
        country_code = profile.get("country_code")
        apply_gdpr_newsletter_override(session, country_code)
        linkedin_url = public_id_to_url(profile["public_identifier"])
        ensure_newsletter_subscription(session, linkedin_url=linkedin_url)
        session.linkedin_profile.newsletter_processed = True
        session.linkedin_profile.save(update_fields=["newsletter_processed"])
