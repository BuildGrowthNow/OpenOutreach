"""
Billing-related email notifications for subscription lifecycle events.
Supports Resend, AWS SES, and SMTP backends.
"""
import logging
from datetime import datetime
from typing import Optional
from abc import ABC, abstractmethod

from openoutreach.mongodb.models_user import User
from openoutreach.config import Settings, settings as _settings

logger = logging.getLogger(__name__)


class EmailProvider(ABC):
    """Abstract base class for email providers."""

    @abstractmethod
    def send(self, to: str, subject: str, html: str, text: str) -> bool:
        """Send email. Returns True on success."""
        pass


class ResendProvider(EmailProvider):
    """Resend email provider."""

    def __init__(self, api_key: str, from_address: str, from_name: str):
        self.api_key = api_key
        self.from_address = from_address
        self.from_name = from_name
        try:
            import resend  # type: ignore
            self.resend = resend
            self.resend.api_key = api_key
        except ImportError:
            logger.error("resend package not installed")
            self.resend = None

    def send(self, to: str, subject: str, html: str, text: str) -> bool:
        """Send email via Resend."""
        if not self.resend:
            logger.error("Resend not available")
            return False

        try:
            self.resend.Emails.send(
                {
                    "from": f"{self.from_name} <{self.from_address}>",
                    "to": to,
                    "subject": subject,
                    "html": html,
                    "text": text,
                }
            )
            logger.info(f"Email sent to {to} via Resend")
            return True
        except Exception as e:
            logger.error(f"Failed to send email via Resend: {e}")
            return False


class SMTPProvider(EmailProvider):
    """SMTP email provider."""

    def __init__(
        self,
        host: Optional[str],
        port: int,
        username: Optional[str],
        password: Optional[str],
        from_address: str,
        from_name: str,
    ):
        self.host = host or ""
        self.port = port
        self.username = username or ""
        self.password = password or ""
        self.from_address = from_address
        self.from_name = from_name

    def send(self, to: str, subject: str, html: str, text: str) -> bool:
        """Send email via SMTP."""
        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart

            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{self.from_name} <{self.from_address}>"
            msg["To"] = to

            msg.attach(MIMEText(text, "plain"))
            msg.attach(MIMEText(html, "html"))

            with smtplib.SMTP(self.host, self.port, timeout=30) as smtp:
                smtp.starttls()
                smtp.login(self.username, self.password)
                smtp.send_message(msg)

            logger.info(f"Email sent to {to} via SMTP")
            return True
        except Exception as e:
            logger.error(f"Failed to send email via SMTP: {e}")
            return False


class SESProvider(EmailProvider):
    """AWS SES email provider."""

    def __init__(self, from_address: str, from_name: str):
        self.from_address = from_address
        self.from_name = from_name
        try:
            import boto3
            self.ses_client = boto3.client("ses")
        except Exception as e:
            logger.error(f"Failed to initialize SES client: {e}")
            self.ses_client = None

    def send(self, to: str, subject: str, html: str, text: str) -> bool:
        """Send email via AWS SES."""
        if not self.ses_client:
            logger.error("SES not available")
            return False

        try:
            self.ses_client.send_email(
                Source=f"{self.from_name} <{self.from_address}>",
                Destination={"ToAddresses": [to]},
                Message={
                    "Subject": {"Data": subject},
                    "Body": {
                        "Text": {"Data": text},
                        "Html": {"Data": html},
                    },
                },
            )
            logger.info(f"Email sent to {to} via SES")
            return True
        except Exception as e:
            logger.error(f"Failed to send email via SES: {e}")
            return False


def _get_email_provider(settings: Settings) -> Optional[EmailProvider]:
    """Get configured email provider."""
    provider_type = settings.EMAIL_PROVIDER.lower()

    if provider_type == "resend":
        if not settings.RESEND_API_KEY:
            logger.warning("Resend provider selected but RESEND_API_KEY not set")
            return None
        return ResendProvider(
            settings.RESEND_API_KEY,
            settings.EMAIL_FROM_ADDRESS,
            settings.EMAIL_FROM_NAME,
        )
    elif provider_type == "smtp":
        if not all([settings.SMTP_HOST, settings.SMTP_USERNAME, settings.SMTP_PASSWORD]):
            logger.warning("SMTP provider selected but credentials not set")
            return None
        return SMTPProvider(
            settings.SMTP_HOST,
            settings.SMTP_PORT,
            settings.SMTP_USERNAME,
            settings.SMTP_PASSWORD,
            settings.EMAIL_FROM_ADDRESS,
            settings.EMAIL_FROM_NAME,
        )
    elif provider_type == "ses":
        return SESProvider(
            settings.EMAIL_FROM_ADDRESS,
            settings.EMAIL_FROM_NAME,
        )
    else:
        logger.warning(f"Unknown email provider: {provider_type}")
        return None


def _format_date(dt: Optional[datetime]) -> str:
    if not dt:
        return "N/A"
    return dt.strftime("%B %d, %Y at %I:%M %p UTC")


def _send_billing_email(user: User, subject: str, html: str, text: str) -> bool:
    """Send a billing email to a user. Returns True on success."""
    if not user.email:
        logger.warning(f"User {user._id} has no email address")
        return False

    settings = _settings
    provider = _get_email_provider(settings)

    if not provider:
        logger.warning("No email provider configured")
        return False

    return provider.send(user.email, subject, html, text)


def _settings_ctx() -> tuple[str, str, str, str]:
    """Return (brand_name, app_url, support_email, docs_url) from settings."""
    s = _settings
    brand = s.EMAIL_FROM_NAME or "Lengrowth Outreach"
    app_url = s.APP_URL or "http://localhost:3000"
    support = s.SUPPORT_EMAIL or "support@lengrowth.com"
    docs_url = f"https://docs.{brand.lower().replace(' ', '')}.com"
    return brand, app_url, support, docs_url


# ---------------------------------------------------------------------------
# Shared HTML layout helpers
# ---------------------------------------------------------------------------

def _html_wrap(brand: str, support: str, body_content: str) -> str:
    """Wrap email body in the dark/emerald branded shell."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{brand}</title>
</head>
<body style="margin:0;padding:0;background-color:#09090b;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#09090b;padding:40px 0;">
    <tr>
      <td align="center">
        <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;">

          <!-- Header -->
          <tr>
            <td style="padding:0 0 32px 0;">
              <span style="font-size:20px;font-weight:700;color:#10b981;letter-spacing:-0.5px;">{brand}</span>
            </td>
          </tr>

          <!-- Card -->
          <tr>
            <td style="background-color:#18181b;border:1px solid #27272a;border-radius:12px;padding:40px;">
              {body_content}
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="padding:32px 0 0 0;text-align:center;">
              <p style="margin:0;font-size:12px;color:#52525b;">
                &copy; {datetime.now().year} {brand}. All rights reserved.
              </p>
              <p style="margin:8px 0 0 0;font-size:12px;color:#52525b;">
                Questions? <a href="mailto:{support}" style="color:#10b981;text-decoration:none;">{support}</a>
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def _btn(url: str, label: str) -> str:
    return (
        f'<a href="{url}" style="display:inline-block;background-color:#10b981;color:#ffffff;'
        f'font-weight:600;font-size:14px;padding:12px 24px;text-decoration:none;border-radius:8px;'
        f'margin-top:8px;">{label}</a>'
    )


def _h1(text: str) -> str:
    return f'<h1 style="margin:0 0 24px 0;font-size:24px;font-weight:700;color:#f4f4f5;">{text}</h1>'


def _p(text: str, extra_style: str = "") -> str:
    return f'<p style="margin:0 0 16px 0;font-size:15px;line-height:1.6;color:#a1a1aa;{extra_style}">{text}</p>'


def _ul(items: list[str]) -> str:
    lis = "".join(
        f'<li style="margin:0 0 8px 0;font-size:15px;color:#a1a1aa;">{item}</li>'
        for item in items
    )
    return f'<ul style="margin:0 0 24px 0;padding-left:20px;">{lis}</ul>'


def _section_heading(text: str) -> str:
    return f'<p style="margin:24px 0 12px 0;font-size:13px;font-weight:600;color:#71717a;text-transform:uppercase;letter-spacing:0.08em;">{text}</p>'


def _divider() -> str:
    return '<hr style="border:none;border-top:1px solid #27272a;margin:32px 0;">'


def _note(text: str) -> str:
    return (
        f'<p style="margin:16px 0;font-size:13px;line-height:1.6;color:#71717a;'
        f'background-color:#09090b;border:1px solid #27272a;border-radius:8px;padding:12px 16px;">{text}</p>'
    )


# ---------------------------------------------------------------------------
# Email senders
# ---------------------------------------------------------------------------

def send_welcome_email(user: User) -> bool:
    """Send welcome email on signup with trial info."""
    s = _settings
    trial_days = s.TRIAL_DURATION_DAYS
    brand, app_url, support, _ = _settings_ctx()

    body = (
        _h1(f"Welcome to {brand}!")
        + _p(f"Hi {user.full_name or 'there'},")
        + _p(f"Your free {trial_days}-day trial has started. You have full access to {brand} Pro — no credit card required.")
        + _section_heading("Your trial includes")
        + _ul([
            "Up to 1 LinkedIn account",
            "Unlimited campaigns",
            "AI-powered messaging",
            "Voice notes",
            "Sales Navigator access",
            "Full API access",
        ])
        + _p("When your trial ends, choose a plan to keep your campaigns running.")
        + _btn(f"{app_url}/settings/billing", "View Your Trial")
        + _divider()
        + _p(f'Questions? Reply to this email or reach us at <a href="mailto:{support}" style="color:#10b981;text-decoration:none;">{support}</a>', "font-size:13px;color:#71717a;")
    )

    html = _html_wrap(brand, support, body)

    text = f"""Welcome to {brand}!

Hi {user.full_name or 'there'},

Your free {trial_days}-day trial has started. You have full access to {brand} Pro — no credit card required.

Your trial includes:
- Up to 1 LinkedIn account
- Unlimited campaigns
- AI-powered messaging
- Voice notes
- Sales Navigator access
- Full API access

When your trial ends, choose a plan to keep your campaigns running.

View your trial: {app_url}/settings/billing

Questions? Reply to this email or contact us at {support}
"""

    return _send_billing_email(user, f"Welcome to {brand}! Your trial has started.", html, text)


def send_trial_expiry_warning(user: User, days_remaining: int) -> bool:
    """Send trial expiry warning email (1 day before expiry)."""
    brand, app_url, support, _ = _settings_ctx()

    body = (
        _h1("Your trial ends tomorrow")
        + _p(f"Hi {user.full_name or 'there'},")
        + _p(f"Your {brand} trial expires <strong style=\"color:#f4f4f5;\">tomorrow</strong>. After that, your campaigns will pause.")
        + _section_heading("Available plans")
        + _ul([
            "<strong style=\"color:#f4f4f5;\">Starter — $19/month:</strong> 1 LinkedIn account, 3 campaigns",
            "<strong style=\"color:#f4f4f5;\">Pro — $49/month:</strong> 1 LinkedIn account, unlimited campaigns, voice notes, API access",
            "<strong style=\"color:#f4f4f5;\">Business — $99/month:</strong> 3 LinkedIn accounts, team members, priority support",
            "<strong style=\"color:#f4f4f5;\">Agency — $249/month:</strong> 10 LinkedIn accounts, white-label branding, unlimited team members",
        ])
        + _btn(f"{app_url}/settings/plan", "Choose a Plan")
        + _divider()
        + _p(f'Questions? Reply to this email or contact <a href="mailto:{support}" style="color:#10b981;text-decoration:none;">{support}</a>', "font-size:13px;color:#71717a;")
    )

    html = _html_wrap(brand, support, body)

    text = f"""Your trial ends tomorrow

Hi {user.full_name or 'there'},

Your {brand} trial expires tomorrow. After that, your campaigns will pause.

Available plans:
- Starter — $19/month: 1 LinkedIn account, 3 campaigns
- Pro — $49/month: 1 LinkedIn account, unlimited campaigns, voice notes, API access
- Business — $99/month: 3 LinkedIn accounts, team members, priority support
- Agency — $249/month: 10 LinkedIn accounts, white-label branding, unlimited team members

Choose a plan: {app_url}/settings/plan

Questions? Reply to this email or contact {support}
"""

    return _send_billing_email(user, f"Your {brand} trial ends tomorrow", html, text)


def send_trial_expired(user: User) -> bool:
    """Send trial expired notification."""
    brand, app_url, support, _ = _settings_ctx()

    body = (
        _h1("Your trial has ended")
        + _p(f"Hi {user.full_name or 'there'},")
        + _p(f"Your {brand} trial has ended. Your campaigns are now paused.")
        + _p("Subscribe to a plan to reactivate your campaigns and get back to work.")
        + _btn(f"{app_url}/settings/plan", "Subscribe Now")
        + _divider()
        + _p(f'Still deciding? Our team can help — <a href="mailto:{support}" style="color:#10b981;text-decoration:none;">get in touch</a>.', "font-size:13px;color:#71717a;")
        + _note("Your data will be preserved for 30 days. After that, it will be permanently deleted.")
    )

    html = _html_wrap(brand, support, body)

    text = f"""Your trial has ended

Hi {user.full_name or 'there'},

Your {brand} trial has ended. Your campaigns are now paused.

Subscribe to a plan to reactivate your campaigns and get back to work.

Subscribe now: {app_url}/settings/plan

Still deciding? Our team can help: {support}

Your data will be preserved for 30 days. After that, it will be permanently deleted.
"""

    return _send_billing_email(user, f"Your {brand} trial has ended", html, text)


def send_plan_upgraded(user: User, old_plan: str, new_plan: str) -> bool:
    """Send plan upgrade confirmation email."""
    brand, app_url, support, _ = _settings_ctx()
    plan_names = {
        "starter": "Starter",
        "pro": "Pro",
        "business": "Business",
        "agency": "Agency",
    }

    body = (
        _h1(f"You're on the {plan_names.get(new_plan, new_plan)} plan")
        + _p(f"Hi {user.full_name or 'there'},")
        + _p(f"Your upgrade from <strong style=\"color:#f4f4f5;\">{plan_names.get(old_plan, old_plan)}</strong> to <strong style=\"color:#f4f4f5;\">{plan_names.get(new_plan, new_plan)}</strong> is now active.")
        + _section_heading("Your new limits")
        + _ul([
            f"LinkedIn accounts: {user.linkedin_account_limit}",
            f"Campaigns: {user.campaign_limit if user.campaign_limit else 'Unlimited'}",
        ])
        + _p(f'The prorated charge has been applied. <a href="{app_url}/settings/billing" style="color:#10b981;text-decoration:none;">View your invoice</a>.')
        + _btn(app_url, "Go to Dashboard")
        + _divider()
        + _p(f'Questions? <a href="mailto:{support}" style="color:#10b981;text-decoration:none;">{support}</a>', "font-size:13px;color:#71717a;")
    )

    html = _html_wrap(brand, support, body)

    text = f"""You're on the {plan_names.get(new_plan, new_plan)} plan

Hi {user.full_name or 'there'},

Your upgrade from {plan_names.get(old_plan, old_plan)} to {plan_names.get(new_plan, new_plan)} is now active.

Your new limits:
- LinkedIn accounts: {user.linkedin_account_limit}
- Campaigns: {user.campaign_limit if user.campaign_limit else "Unlimited"}

The prorated charge has been applied. View your invoice: {app_url}/settings/billing

Go to dashboard: {app_url}

Questions? {support}
"""

    return _send_billing_email(user, f"You've upgraded to {plan_names.get(new_plan, new_plan)}!", html, text)


def send_plan_downgraded(user: User, old_plan: str, new_plan: str, effective_date: datetime) -> bool:
    """Send plan downgrade notification email."""
    brand, app_url, support, _ = _settings_ctx()
    plan_names = {
        "starter": "Starter",
        "pro": "Pro",
        "business": "Business",
        "agency": "Agency",
    }

    date_str = effective_date.strftime("%B %d, %Y")

    body = (
        _h1("Your plan change")
        + _p(f"Hi {user.full_name or 'there'},")
        + _p(f"Your request to downgrade from <strong style=\"color:#f4f4f5;\">{plan_names.get(old_plan, old_plan)}</strong> to <strong style=\"color:#f4f4f5;\">{plan_names.get(new_plan, new_plan)}</strong> has been received.")
        + _p(f"Your new plan activates on <strong style=\"color:#f4f4f5;\">{date_str}</strong> at the end of your current billing period.")
        + _section_heading(f"New limits starting {date_str}")
        + _ul([
            f"LinkedIn accounts: {user.linkedin_account_limit}",
            f"Campaigns: {user.campaign_limit if user.campaign_limit else 'Unlimited'}",
        ])
        + _note(f"If you currently exceed your new plan's limits, excess profiles will be deactivated on {date_str}. You'll receive a separate email listing which profiles were affected.")
        + _btn(f"{app_url}/settings/billing", "View Your Subscription")
        + _divider()
        + _p("Changed your mind? You can upgrade anytime from your billing settings.", "font-size:13px;color:#71717a;")
    )

    html = _html_wrap(brand, support, body)

    text = f"""Your plan change

Hi {user.full_name or 'there'},

Your request to downgrade from {plan_names.get(old_plan, old_plan)} to {plan_names.get(new_plan, new_plan)} has been received.

Your new plan activates on {date_str} at the end of your current billing period.

New limits starting {date_str}:
- LinkedIn accounts: {user.linkedin_account_limit}
- Campaigns: {user.campaign_limit if user.campaign_limit else "Unlimited"}

Note: If you currently exceed your new plan's limits, excess profiles will be deactivated on {date_str}.

View your subscription: {app_url}/settings/billing

Changed your mind? You can upgrade anytime from your billing settings.
"""

    return _send_billing_email(user, f"Your plan change to {plan_names.get(new_plan, new_plan)}", html, text)


def send_payment_failed(user: User, retry_count: int = 1) -> bool:
    """Send payment failed notification with retry information."""
    brand, app_url, support, _ = _settings_ctx()

    body = (
        _h1("Payment failed")
        + _p(f"Hi {user.full_name or 'there'},")
        + _p("We attempted to charge your payment method for your subscription, but it was declined.")
        + _p("We'll retry up to 3 times over the next few days. If all attempts fail, your account will be downgraded and campaigns paused.")
        + _p("Update your payment method now to avoid any interruption.")
        + _btn(f"{app_url}/settings/billing", "Update Payment Method")
        + _section_heading("Common reasons")
        + _ul([
            "Card has expired",
            "Insufficient funds",
            "Card issuer declined the transaction",
            "Billing address mismatch",
        ])
        + _divider()
        + _p(f'Need help? <a href="mailto:{support}" style="color:#10b981;text-decoration:none;">{support}</a>', "font-size:13px;color:#71717a;")
    )

    html = _html_wrap(brand, support, body)

    text = f"""Payment failed

Hi {user.full_name or 'there'},

We attempted to charge your payment method for your subscription, but it was declined.

We'll retry up to 3 times over the next few days. If all attempts fail, your account will be downgraded and campaigns paused.

Update your payment method: {app_url}/settings/billing

Common reasons:
- Card has expired
- Insufficient funds
- Card issuer declined the transaction
- Billing address mismatch

Need help? {support}
"""

    return _send_billing_email(user, f"Payment failed for your {brand} subscription", html, text)


def send_account_blocked(user: User, reason: str = "violation of our terms of service") -> bool:
    """Send account blocked notification."""
    brand, _, support, _ = _settings_ctx()

    body = (
        _h1("Your account has been suspended")
        + _p(f"Hi {user.full_name or 'there'},")
        + _p(f"Your {brand} account has been suspended due to: <strong style=\"color:#f4f4f5;\">{reason}</strong>")
        + _p("You will no longer be able to log in or run automations.")
        + _p(f'If you believe this is a mistake, reply to this email or contact <a href="mailto:{support}" style="color:#10b981;text-decoration:none;">{support}</a> with your account email and a brief explanation. Our team will review within 24 hours.')
        + _divider()
        + _p("This is an automated message. Please do not reply with sensitive information.", "font-size:13px;color:#71717a;")
    )

    html = _html_wrap(brand, support, body)

    text = f"""Your account has been suspended

Hi {user.full_name or 'there'},

Your {brand} account has been suspended due to: {reason}

You will no longer be able to log in or run automations.

If you believe this is a mistake, contact {support} with your account email and a brief explanation. Our team will review within 24 hours.
"""

    return _send_billing_email(user, f"Your {brand} account has been suspended", html, text)


def send_lifetime_deal_purchase(user: User) -> bool:
    """Send lifetime deal purchase confirmation email."""
    brand, app_url, support, docs_url = _settings_ctx()

    body = (
        _h1("Lifetime Deal activated!")
        + _p(f"Hi {user.full_name or 'there'},")
        + _p(f"Thank you for your purchase! You've activated the {brand} Lifetime Deal — Pro-equivalent access <strong style=\"color:#f4f4f5;\">forever</strong>.")
        + _section_heading("What's included")
        + _ul([
            "1 LinkedIn account",
            "Unlimited campaigns",
            "AI-powered messaging (requires your own LLM API key)",
            "Voice notes",
            "Sales Navigator access",
            "Full API access",
            "Desktop daemon execution (runs on your machine)",
            "<strong style=\"color:#f4f4f5;\">No recurring charges — ever</strong>",
        ])
        + _note("The lifetime deal uses the desktop daemon for campaign execution — automation runs on your computer using your own residential IP. The Cloud tier ($299/month) is not included. Download the desktop app from the dashboard to get started.")
        + _btn(app_url, "Go to Dashboard")
        + _divider()
        + _p(f'Need help? Check our <a href="{docs_url}" style="color:#10b981;text-decoration:none;">documentation</a> or reach out to <a href="mailto:{support}" style="color:#10b981;text-decoration:none;">{support}</a>.', "font-size:13px;color:#71717a;")
        + _p("Your receipt has been sent to your email. If you didn't receive it, reply to this email.", "font-size:13px;color:#71717a;")
    )

    html = _html_wrap(brand, support, body)

    text = f"""Lifetime Deal activated!

Hi {user.full_name or 'there'},

Thank you for your purchase! You've activated the {brand} Lifetime Deal — Pro-equivalent access forever.

What's included:
- 1 LinkedIn account
- Unlimited campaigns
- AI-powered messaging (requires your own LLM API key)
- Voice notes
- Sales Navigator access
- Full API access
- Desktop daemon execution (runs on your machine)
- No recurring charges — ever

Note: The lifetime deal uses the desktop daemon for execution. The Cloud tier ($299/month) is not included.

Go to dashboard: {app_url}

Need help? {docs_url} or {support}

Your receipt has been sent to your email. If you didn't receive it, reply to this email.
"""

    return _send_billing_email(user, f"Your {brand} Lifetime Deal is active!", html, text)


def send_email_verification(user: User, verification_url: str) -> bool:
    """Send email verification link to new user."""
    brand, _, support, _ = _settings_ctx()

    body = (
        _h1("Verify your email")
        + _p(f"Hi {user.full_name or 'there'},")
        + _p(f"Thanks for signing up for {brand}! Verify your email address to start your trial.")
        + _btn(verification_url, "Verify Email Address")
        + _divider()
        + _p(f'Or copy this link into your browser:<br><a href="{verification_url}" style="color:#10b981;text-decoration:none;word-break:break-all;font-size:13px;">{verification_url}</a>', "font-size:13px;color:#71717a;")
        + _p("This link expires in 24 hours.", "font-size:13px;color:#71717a;")
        + _p("If you didn't create an account, you can safely ignore this email.", "font-size:13px;color:#71717a;")
    )

    html = _html_wrap(brand, support, body)

    text = f"""Verify your email

Hi {user.full_name or 'there'},

Thanks for signing up for {brand}! Verify your email address to start your trial.

Verify your email: {verification_url}

This link expires in 24 hours.

If you didn't create an account, you can safely ignore this email.
"""

    return _send_billing_email(user, f"Verify your {brand} email address", html, text)


def send_password_reset(user: User, reset_url: str) -> bool:
    """Send password reset link to user."""
    brand, _, support, _ = _settings_ctx()

    body = (
        _h1("Reset your password")
        + _p(f"Hi {user.full_name or 'there'},")
        + _p(f"We received a request to reset your {brand} password.")
        + _btn(reset_url, "Reset Password")
        + _divider()
        + _p(f'Or copy this link into your browser:<br><a href="{reset_url}" style="color:#10b981;text-decoration:none;word-break:break-all;font-size:13px;">{reset_url}</a>', "font-size:13px;color:#71717a;")
        + _p("This link expires in 24 hours.", "font-size:13px;color:#71717a;")
        + _p("If you didn't request a password reset, you can safely ignore this email. Your password will remain unchanged.", "font-size:13px;color:#71717a;")
    )

    html = _html_wrap(brand, support, body)

    text = f"""Reset your password

Hi {user.full_name or 'there'},

We received a request to reset your {brand} password.

Reset your password: {reset_url}

This link expires in 24 hours.

If you didn't request a password reset, you can safely ignore this email. Your password will remain unchanged.
"""

    return _send_billing_email(user, f"Reset your {brand} password", html, text)
