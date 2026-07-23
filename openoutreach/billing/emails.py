"""
Billing-related email notifications for subscription lifecycle events.
Supports Resend, AWS SES, and SMTP backends.
"""
import logging
from datetime import datetime
from typing import Optional
from abc import ABC, abstractmethod

from openoutreach.mongodb.models_user import User
from openoutreach.config import Settings

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
    """Format datetime for email display."""
    if not dt:
        return "N/A"
    return dt.strftime("%B %d, %Y at %I:%M %p UTC")


def _send_billing_email(user: User, subject: str, html: str, text: str) -> bool:
    """Send a billing email to a user. Returns True on success."""
    if not user.email:
        logger.warning(f"User {user._id} has no email address")
        return False

    settings = Settings()
    provider = _get_email_provider(settings)

    if not provider:
        logger.warning("No email provider configured")
        return False

    return provider.send(user.email, subject, html, text)


def _settings_ctx() -> tuple[str, str, str, str]:
    """Return (brand_name, app_url, support_email, docs_url) from settings."""
    s = Settings()
    brand = s.EMAIL_FROM_NAME or "Lengrowth"
    app_url = s.APP_URL or "http://localhost:3000"
    support = s.SUPPORT_EMAIL or f"support@{brand.lower().replace(' ', '')}.com"
    docs_url = f"https://docs.{brand.lower().replace(' ', '')}.com"
    return brand, app_url, support, docs_url


def send_welcome_email(user: User) -> bool:
    """Send welcome email on signup with trial info."""
    s = Settings()
    trial_days = s.TRIAL_DURATION_DAYS
    brand, app_url, support, _ = _settings_ctx()

    html = f"""
<html>
  <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
      <h1 style="color: #0066cc; margin-bottom: 20px;">Welcome to {brand}!</h1>

      <p>Hi {user.full_name or 'there'},</p>

      <p>Your free trial has started! You now have <strong>{trial_days} days</strong> of full access to {brand} Pro.</p>

      <h3>Your trial includes:</h3>
      <ul>
        <li>Up to 1 LinkedIn account</li>
        <li>Unlimited campaigns</li>
        <li>AI-powered messaging</li>
        <li>Voice notes</li>
        <li>Sales Navigator access</li>
        <li>Full API access</li>
      </ul>

      <p><strong>No credit card will be charged during your trial.</strong> When your trial ends, you'll need to choose a plan to continue using {brand}.</p>

      <p><a href="{app_url}/settings/billing" style="display: inline-block; background-color: #0066cc; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; margin-top: 10px;">View Your Trial</a></p>

      <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">

      <p style="color: #666; font-size: 12px;">
        If you have any questions, reply to this email or contact us at {support}
      </p>
    </div>
  </body>
</html>
"""

    text = f"""Welcome to {brand}!

Hi {user.full_name or 'there'},

Your free trial has started! You now have {trial_days} days of full access to {brand} Pro.

Your trial includes:
- Up to 1 LinkedIn account
- Unlimited campaigns
- AI-powered messaging
- Voice notes
- Sales Navigator access
- Full API access

No credit card will be charged during your trial. When your trial ends, you'll need to choose a plan to continue using {brand}.

View your trial: {app_url}/settings/billing

If you have any questions, reply to this email or contact us at {support}
"""

    return _send_billing_email(user, f"Welcome to {brand}! Your trial has started.", html, text)


def send_trial_expiry_warning(user: User, days_remaining: int) -> bool:
    """Send trial expiry warning email (1 day before expiry)."""
    brand, app_url, support, _ = _settings_ctx()

    html = f"""
<html>
  <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
      <h1 style="color: #ff6600; margin-bottom: 20px;">Your Trial Ends Tomorrow</h1>

      <p>Hi {user.full_name or 'there'},</p>

      <p>Your {brand} trial ends <strong>tomorrow</strong>. After that, your campaigns will pause and you won't be able to run new automations.</p>

      <h3>Choose a plan to keep going:</h3>
      <ul>
        <li><strong>Starter - $19/month</strong>: 1 LinkedIn account, 3 campaigns</li>
        <li><strong>Pro - $49/month</strong>: 1 LinkedIn account, unlimited campaigns, voice notes, API access</li>
        <li><strong>Business - $99/month</strong>: 3 LinkedIn accounts, team members, priority support</li>
        <li><strong>Agency - $249/month</strong>: 10 LinkedIn accounts, white-label branding, unlimited team members</li>
        <li><strong>Cloud - $299/month</strong>: Fully managed cloud execution + AI on Sonnet, priority support included</li>
      </ul>

      <p><a href="{app_url}/settings/plan" style="display: inline-block; background-color: #ff6600; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; margin-top: 10px;">Choose a Plan</a></p>

      <p style="color: #666; margin-top: 20px; font-size: 14px;">
        Questions? Our team is here to help. Reply to this email or contact {support}
      </p>

      <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">

      <p style="color: #999; font-size: 12px;">
        This is an automated message. Please don't reply with sensitive information.
      </p>
    </div>
  </body>
</html>
"""

    text = f"""Your Trial Ends Tomorrow

Hi {user.full_name or 'there'},

Your {brand} trial ends tomorrow. After that, your campaigns will pause and you won't be able to run new automations.

Choose a plan to keep going:
- Starter - $19/month: 1 LinkedIn account, 3 campaigns
- Pro - $49/month: 1 LinkedIn account, unlimited campaigns, voice notes, API access
- Business - $99/month: 3 LinkedIn accounts, team members, priority support
- Agency - $249/month: 10 LinkedIn accounts, white-label branding, unlimited team members

Choose a plan: {app_url}/settings/plan

Questions? Reply to this email or contact {support}
"""

    return _send_billing_email(user, f"Your {brand} trial ends tomorrow", html, text)


def send_trial_expired(user: User) -> bool:
    """Send trial expired notification."""
    brand, app_url, support, _ = _settings_ctx()

    html = f"""
<html>
  <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
      <h1 style="color: #cc0000; margin-bottom: 20px;">Your Trial Has Ended</h1>

      <p>Hi {user.full_name or 'there'},</p>

      <p>Your {brand} trial has ended. Your campaigns are now paused and automations have been stopped.</p>

      <h3>Ready to continue?</h3>
      <p>Choose a plan to reactivate your campaigns and get back to work.</p>

      <p><a href="{app_url}/settings/plan" style="display: inline-block; background-color: #0066cc; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; margin-top: 10px;">Subscribe Now</a></p>

      <h3>Still deciding?</h3>
      <p>Our team is here to answer questions about plans and help you choose the right option. <a href="mailto:{support}">Get in touch</a>.</p>

      <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">

      <p style="color: #999; font-size: 12px;">
        Your data will be preserved for 30 days. After that, it will be permanently deleted.
      </p>
    </div>
  </body>
</html>
"""

    text = f"""Your Trial Has Ended

Hi {user.full_name or 'there'},

Your {brand} trial has ended. Your campaigns are now paused and automations have been stopped.

Ready to continue?

Choose a plan to reactivate your campaigns and get back to work.

Subscribe now: {app_url}/settings/plan

Still deciding?

Our team is here to answer questions about plans. Get in touch: {support}

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

    html = f"""
<html>
  <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
      <h1 style="color: #0066cc; margin-bottom: 20px;">Welcome to the {plan_names.get(new_plan, new_plan)} Plan!</h1>

      <p>Hi {user.full_name or 'there'},</p>

      <p>Your upgrade from <strong>{plan_names.get(old_plan, old_plan)}</strong> to <strong>{plan_names.get(new_plan, new_plan)}</strong> is now active.</p>

      <h3>Your new limits:</h3>
      <ul>
        <li>LinkedIn accounts: {user.linkedin_account_limit}</li>
        <li>Campaigns: {user.campaign_limit if user.campaign_limit else "Unlimited"}</li>
      </ul>

      <p>The prorated charge for this upgrade has been applied to your account. Any questions about your billing? <a href="{app_url}/settings/billing">View your invoice</a>.</p>

      <p><a href="{app_url}" style="display: inline-block; background-color: #0066cc; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; margin-top: 10px;">Back to Dashboard</a></p>

      <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">

      <p style="color: #666; font-size: 12px;">
        If you have any questions, reply to this email or contact us at {support}
      </p>
    </div>
  </body>
</html>
"""

    text = f"""Welcome to the {plan_names.get(new_plan, new_plan)} Plan!

Hi {user.full_name or 'there'},

Your upgrade from {plan_names.get(old_plan, old_plan)} to {plan_names.get(new_plan, new_plan)} is now active.

Your new limits:
- LinkedIn accounts: {user.linkedin_account_limit}
- Campaigns: {user.campaign_limit if user.campaign_limit else "Unlimited"}

The prorated charge for this upgrade has been applied to your account. View your invoice: {app_url}/settings/billing

Back to dashboard: {app_url}

If you have any questions, reply to this email or contact us at {support}
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

    html = f"""
<html>
  <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
      <h1 style="color: #666; margin-bottom: 20px;">Your Plan Change</h1>

      <p>Hi {user.full_name or 'there'},</p>

      <p>We've received your request to downgrade from <strong>{plan_names.get(old_plan, old_plan)}</strong> to <strong>{plan_names.get(new_plan, new_plan)}</strong>.</p>

      <h3>When does it take effect?</h3>
      <p>Your new plan will activate on <strong>{date_str}</strong> at the end of your current billing period.</p>

      <h3>Your new limits (starting {date_str}):</h3>
      <ul>
        <li>LinkedIn accounts: {user.linkedin_account_limit}</li>
        <li>Campaigns: {user.campaign_limit if user.campaign_limit else "Unlimited"}</li>
      </ul>

      <p style="background-color: #fff3cd; padding: 10px; border-radius: 5px; margin-top: 20px;">
        <strong>Note:</strong> If you currently have more LinkedIn accounts or campaigns than your new plan allows, we'll deactivate the excess profiles starting on {date_str}. You'll receive another email letting you know which profiles were deactivated.
      </p>

      <p style="margin-top: 20px;"><a href="{app_url}/settings/billing" style="display: inline-block; background-color: #0066cc; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">View Your Subscription</a></p>

      <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">

      <p style="color: #666; font-size: 12px;">
        Changed your mind? You can upgrade anytime from your billing settings.
      </p>
    </div>
  </body>
</html>
"""

    text = f"""Your Plan Change

Hi {user.full_name or 'there'},

We've received your request to downgrade from {plan_names.get(old_plan, old_plan)} to {plan_names.get(new_plan, new_plan)}.

When does it take effect?

Your new plan will activate on {date_str} at the end of your current billing period.

Your new limits (starting {date_str}):
- LinkedIn accounts: {user.linkedin_account_limit}
- Campaigns: {user.campaign_limit if user.campaign_limit else "Unlimited"}

Note: If you currently have more LinkedIn accounts or campaigns than your new plan allows, we'll deactivate the excess profiles starting on {date_str}. You'll receive another email letting you know which profiles were deactivated.

View your subscription: {app_url}/settings/billing

Changed your mind? You can upgrade anytime from your billing settings.
"""

    return _send_billing_email(user, f"Your plan change to {plan_names.get(new_plan, new_plan)}", html, text)


def send_payment_failed(user: User, retry_count: int = 1) -> bool:
    """Send payment failed notification with retry information."""
    brand, app_url, support, _ = _settings_ctx()

    html = f"""
<html>
  <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
      <h1 style="color: #cc0000; margin-bottom: 20px;">Payment Failed</h1>

      <p>Hi {user.full_name or 'there'},</p>

      <p>We attempted to charge your payment method for your subscription, but it was declined.</p>

      <h3>What happens next?</h3>
      <p>We'll retry charging your card up to 3 times over the next few days. If all attempts fail, your account will be downgraded to the free tier and your campaigns will be paused.</p>

      <h3>Fix it now</h3>
      <p>Update your payment method to avoid service interruption.</p>

      <p><a href="{app_url}/settings/billing" style="display: inline-block; background-color: #0066cc; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; margin-top: 10px;">Update Payment Method</a></p>

      <p style="margin-top: 20px; color: #666; font-size: 14px;">
        <strong>Common reasons for payment failures:</strong>
      </p>
      <ul style="color: #666; font-size: 14px;">
        <li>Card has expired</li>
        <li>Insufficient funds</li>
        <li>Card issuer declined the transaction</li>
        <li>Billing address mismatch</li>
      </ul>

      <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">

      <p style="color: #666; font-size: 12px;">
        Need help? Reply to this email or contact us at {support}
      </p>
    </div>
  </body>
</html>
"""

    text = f"""Payment Failed

Hi {user.full_name or 'there'},

We attempted to charge your payment method for your subscription, but it was declined.

What happens next?

We'll retry charging your card up to 3 times over the next few days. If all attempts fail, your account will be downgraded to the free tier and your campaigns will be paused.

Fix it now

Update your payment method to avoid service interruption.

Update payment method: {app_url}/settings/billing

Common reasons for payment failures:
- Card has expired
- Insufficient funds
- Card issuer declined the transaction
- Billing address mismatch

Need help? Reply to this email or contact us at {support}
"""

    return _send_billing_email(user, f"Payment failed for your {brand} subscription", html, text)


def send_account_blocked(user: User, reason: str = "violation of our terms of service") -> bool:
    """Send account blocked notification."""
    brand, _, support, _ = _settings_ctx()

    html = f"""
<html>
  <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
      <h1 style="color: #cc0000; margin-bottom: 20px;">Your Account Has Been Suspended</h1>

      <p>Hi {user.full_name or 'there'},</p>

      <p>Your {brand} account has been suspended due to: <strong>{reason}</strong></p>

      <p>You will no longer be able to log in or run automations.</p>

      <h3>What now?</h3>
      <p>If you believe this is a mistake or have questions about this decision, please reply to this email or contact our support team at {support} with your account email and a brief explanation.</p>

      <p>Our team will review your account within 24 hours.</p>

      <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">

      <p style="color: #999; font-size: 12px;">
        This is an automated message. Please don't reply with sensitive information.
      </p>
    </div>
  </body>
</html>
"""

    text = f"""Your Account Has Been Suspended

Hi {user.full_name or 'there'},

Your {brand} account has been suspended due to: {reason}

You will no longer be able to log in or run automations.

What now?

If you believe this is a mistake or have questions about this decision, please reply to this email or contact our support team at {support} with your account email and a brief explanation.

Our team will review your account within 24 hours.
"""

    return _send_billing_email(user, f"Your {brand} account has been suspended", html, text)


def send_lifetime_deal_purchase(user: User) -> bool:
    """Send lifetime deal purchase confirmation email."""
    brand, app_url, support, docs_url = _settings_ctx()

    html = f"""
<html>
  <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
      <h1 style="color: #0066cc; margin-bottom: 20px;">Lifetime Deal Activated!</h1>

      <p>Hi {user.full_name or 'there'},</p>

      <p>Thank you for your purchase! You've activated the {brand} Lifetime Deal with Pro-equivalent access <strong>forever</strong>.</p>

      <h3>What's included:</h3>
      <ul>
        <li>1 LinkedIn account</li>
        <li>Unlimited campaigns</li>
        <li>AI-powered messaging (requires your own LLM API key)</li>
        <li>Voice notes</li>
        <li>Sales Navigator access</li>
        <li>Full API access</li>
        <li>Desktop daemon execution (runs on your machine)</li>
        <li><strong>No recurring charges — ever</strong></li>
      </ul>

      <p style="color: #666; font-size: 14px;">
        <strong>Note:</strong> The lifetime deal uses the desktop daemon for campaign execution — automation runs on your computer using your own residential IP. The Cloud tier ($299/month) is not included. To set up your desktop daemon, download the app from the dashboard.
      </p>

      <p>You're all set. Your campaigns are ready to launch!</p>

      <p><a href="{app_url}" style="display: inline-block; background-color: #0066cc; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; margin-top: 10px;">Go to Dashboard</a></p>

      <h3>Need help getting started?</h3>
      <p>Check out our <a href="{docs_url}">documentation</a> or reach out to {support} if you have any questions.</p>

      <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">

      <p style="color: #666; font-size: 12px;">
        Your receipt has been sent to your email. If you didn't receive it, reply to this email.
      </p>
    </div>
  </body>
</html>
"""

    text = f"""Lifetime Deal Activated!

Hi {user.full_name or 'there'},

Thank you for your purchase! You've activated the {brand} Lifetime Deal with Pro-equivalent access forever.

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

You're all set. Your campaigns are ready to launch!

Go to dashboard: {app_url}

Need help getting started?

Check out our documentation: {docs_url}

Or reach out to {support} if you have any questions.

Your receipt has been sent to your email. If you didn't receive it, reply to this email.
"""

    return _send_billing_email(user, f"Your {brand} Lifetime Deal is active!", html, text)


def send_email_verification(user: User, verification_url: str) -> bool:
    """Send email verification link to new user."""
    brand, _, _, _ = _settings_ctx()

    html = f"""
<html>
  <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
      <h1 style="color: #0066cc; margin-bottom: 20px;">Verify Your Email</h1>

      <p>Hi {user.full_name or 'there'},</p>

      <p>Thanks for signing up for {brand}! Please verify your email address to start your trial.</p>

      <p><a href="{verification_url}" style="display: inline-block; background-color: #0066cc; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; margin-top: 10px;">Verify Email Address</a></p>

      <p style="margin-top: 20px; color: #666; font-size: 14px;">
        Or copy and paste this link into your browser:<br>
        <a href="{verification_url}" style="color: #0066cc; word-break: break-all;">{verification_url}</a>
      </p>

      <p style="margin-top: 20px; color: #666; font-size: 14px;">
        This link will expire in 24 hours.
      </p>

      <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">

      <p style="color: #666; font-size: 12px;">
        If you didn't create an account, you can safely ignore this email.
      </p>
    </div>
  </body>
</html>
"""

    text = f"""Verify Your Email

Hi {user.full_name or 'there'},

Thanks for signing up for {brand}! Please verify your email address to start your trial.

Verify your email: {verification_url}

This link will expire in 24 hours.

If you didn't create an account, you can safely ignore this email.
"""

    return _send_billing_email(user, f"Verify your {brand} email address", html, text)


def send_password_reset(user: User, reset_url: str) -> bool:
    """Send password reset link to user."""
    brand, _, _, _ = _settings_ctx()

    html = f"""
<html>
  <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
      <h1 style="color: #0066cc; margin-bottom: 20px;">Reset Your Password</h1>

      <p>Hi {user.full_name or 'there'},</p>

      <p>We received a request to reset your {brand} password. Click the button below to create a new password:</p>

      <p><a href="{reset_url}" style="display: inline-block; background-color: #0066cc; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; margin-top: 10px;">Reset Password</a></p>

      <p style="margin-top: 20px; color: #666; font-size: 14px;">
        Or copy and paste this link into your browser:<br>
        <a href="{reset_url}" style="color: #0066cc; word-break: break-all;">{reset_url}</a>
      </p>

      <p style="margin-top: 20px; color: #666; font-size: 14px;">
        This link will expire in 24 hours.
      </p>

      <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">

      <p style="color: #666; font-size: 12px;">
        If you didn't request a password reset, you can safely ignore this email. Your password will remain unchanged.
      </p>
    </div>
  </body>
</html>
"""

    text = f"""Reset Your Password

Hi {user.full_name or 'there'},

We received a request to reset your {brand} password. Click the link below to create a new password:

{reset_url}

This link will expire in 24 hours.

If you didn't request a password reset, you can safely ignore this email. Your password will remain unchanged.
"""

    return _send_billing_email(user, f"Reset your {brand} password", html, text)
