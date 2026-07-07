# openoutreach/crm/models/linkedin_credentials.py
"""LinkedIn Credentials Management with Secure Encryption."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from openoutreach.core.models import Campaign
from openoutreach.linkedin.models import LinkedInProfile

logger = logging.getLogger(__name__)


def _derive_key_from_settings() -> bytes:
    """Derive encryption key from Django settings.

    Uses the SECRET_KEY as the basis for encryption, combined with a salt.
    This ensures keys are tied to the specific deployment.
    """
    secret = settings.SECRET_KEY.encode()
    salt = b"openoutreach_linkedin_credentials"  # Fixed salt for this deployment

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    return base64.urlsafe_b64encode(kdf.derive(secret))


def _get_fernet() -> Fernet:
    """Get a Fernet cipher instance for encryption/decryption."""
    try:
        key = _derive_key_from_settings()
        return Fernet(key)
    except Exception as e:
        logger.error("Failed to create Fernet cipher: %s", e)
        raise


class LinkedInCredentials(models.Model):
    """
    Securely stored LinkedIn credentials with encryption at rest.

    Credentials are encrypted using AES-256-GCM via Fernet.
    The encryption key is derived from Django's SECRET_KEY using PBKDF2.

    Features:
    - AES-256 encrypted storage of email and password
    - Automatic credential verification tracking
    - Usage monitoring and rate limit enforcement
    - Backup and recovery support
    """

    # Verification states - progress from stored to verified
    STATUS_STORED = "stored"  # Credential saved but not tested
    STATUS_TESTED = "tested"  # Attempted login but needs verification
    STATUS_ACTIVE = "active"  # Successfully verified and working
    STATUS_INVALID = "invalid"  # Verification failed
    STATUS_EXPIRED = "expired"  # Needs rotation
    STATUS_LOCKED = "locked"  # Temporarily disabled (checkpoint/Challenge)
    STATUS_BACKUP = "backup"  # Backup credential

    STATUS_CHOICES = [
        (STATUS_STORED, _("Stored - not yet verified")),
        (STATUS_TESTED, _("Tested - login attempted")),
        (STATUS_ACTIVE, _("Active - verified and working")),
        (STATUS_INVALID, _("Invalid - verification failed")),
        (STATUS_EXPIRED, _("Expired - needs rotation")),
        (STATUS_LOCKED, _("Locked - checkpoint/challenge detected")),
        (STATUS_BACKUP, _("Backup credential")),
    ]

    # Credential owner - linked to a specific LinkedIn profile
    linkedin_profile: models.OneToOneField[LinkedInProfile | None, LinkedInProfile] = (
        models.OneToOneField(
            LinkedInProfile,
            on_delete=models.CASCADE,
            related_name="credentials",
            null=True,
            blank=True,
            help_text=_("The LinkedIn profile this credential belongs to"),
        )
    )

    # Encrypted credential data
    email_encrypted: models.BinaryField = models.BinaryField(
        max_length=500, help_text=_("Encrypted LinkedIn email")
    )
    password_encrypted: models.BinaryField = models.BinaryField(
        max_length=500, help_text=_("Encrypted LinkedIn password")
    )

    # Display information (not encrypted)
    username: models.CharField = models.CharField(
        max_length=200,
        blank=True,
        help_text=_("Display name/username for this credential"),
    )

    # Status and verification
    status: models.CharField = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_STORED,
        help_text=_("Credential status and validity"),
    )  # type: ignore[var-annotated]

    last_verified: models.DateTimeField = models.DateTimeField(
        null=True, blank=True, help_text=_("When credentials were last verified")
    )
    verification_failed_at: models.DateTimeField = models.DateTimeField(
        null=True, blank=True, help_text=_("When last verification failed")
    )
    verification_failures: models.PositiveIntegerField = models.PositiveIntegerField(
        default=0, help_text=_("Number of consecutive verification failures")
    )

    # Usage tracking
    usage_count: models.PositiveIntegerField = models.PositiveIntegerField(
        default=0,
        help_text=_("Total number of actions performed with these credentials"),
    )
    last_used: models.DateTimeField = models.DateTimeField(
        null=True, blank=True, help_text=_("When these credentials were last used")
    )
    campaign: models.ForeignKey[Campaign, Campaign] = models.ForeignKey(
        Campaign,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="linkedin_credentials",
        help_text=_("Campaign using these credentials"),
    )

    # Rotation and expiration
    created_at: models.DateTimeField = models.DateTimeField(auto_now_add=True)
    updated_at: models.DateTimeField = models.DateTimeField(auto_now=True)
    expires_at: models.DateTimeField = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_("When these credentials expire (for rotation)"),
    )
    rotated_at: models.DateTimeField = models.DateTimeField(
        null=True, blank=True, help_text=_("When these credentials were last rotated")
    )
    rotation_required_days: models.PositiveIntegerField = models.PositiveIntegerField(
        default=90, help_text=_("Days after which credentials should be rotated")
    )

    # Backup and sharing
    is_primary: models.BooleanField = models.BooleanField(
        default=True,
        help_text=_("Whether this is the primary credential for the profile"),
    )
    is_backup: models.BooleanField = models.BooleanField(
        default=False, help_text=_("Whether this is a backup credential")
    )

    # Backup tracking
    backup_of: models.ForeignKey[
        LinkedInCredentials | None, LinkedInCredentials
    ] = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="backup_credentials",
        help_text=_("Original credential this is backed up from"),
    )  # type: ignore[var-annotated]

    # Security alerts
    security_alert_sent_at: models.DateTimeField = models.DateTimeField(
        null=True, blank=True, help_text=_("When last security alert was sent")
    )

    class Meta:
        verbose_name = _("LinkedIn Credential")
        verbose_name_plural = _("LinkedIn Credentials")
        ordering = ["-is_primary", "-updated_at"]
        indexes = [
            models.Index(fields=["status", "expires_at"]),
            models.Index(fields=["campaign", "status"]),
        ]

    def __str__(self):
        return f"LinkedInCredential #{self.pk} ({self.get_public_email()})"

    # ==================== Encryption Methods ====================

    @classmethod
    def encrypt(cls, plaintext: str) -> bytes:
        """Encrypt a string using Fernet AES encryption."""
        fernet = _get_fernet()
        return fernet.encrypt(plaintext.encode("utf-8"))

    @classmethod
    def decrypt(cls, ciphertext: bytes) -> str:
        """Decrypt a string using Fernet AES decryption."""
        fernet = _get_fernet()
        try:
            return fernet.decrypt(ciphertext).decode("utf-8")
        except InvalidToken:
            raise ValueError("Invalid or corrupted encrypted data")

    # ==================== Credential Access Methods ====================

    def get_email(self) -> str:
        """Get the decrypted email address."""
        return self.decrypt(self.email_encrypted)

    def set_email(self, email: str) -> None:
        """Set and encrypt the email address."""
        self.email_encrypted = self.encrypt(email)

    def get_password(self) -> str:
        """Get the decrypted password."""
        return self.decrypt(self.password_encrypted)

    def set_password(self, password: str) -> None:
        """Set and encrypt the password."""
        self.password_encrypted = self.encrypt(password)

    def get_public_email(self) -> str:
        """Get a masked version of the email for display."""
        try:
            email = self.get_email()
            if "@" in email:
                local, domain = email.rsplit("@", 1)
                if len(local) > 2:
                    return f"{local[0]}***@{domain}"
                return f"***@{domain}"
            return "***@***"
        except Exception:
            return "***@***"

    # ==================== Status Methods ====================

    def mark_as_invalid(self, reason: str = "") -> None:
        """Mark credentials as invalid."""
        self.status = self.STATUS_INVALID
        self.verification_failed_at = timezone.now()
        self.verification_failures += 1
        if reason:
            self._save_verification_log("invalid", reason)
        self.save(
            update_fields=["status", "verification_failed_at", "verification_failures"]
        )

    def mark_as_active(self) -> None:
        """Mark credentials as active."""
        self.status = self.STATUS_ACTIVE
        self.save(update_fields=["status"])

    def mark_as_expired(self) -> None:
        """Mark credentials as expired."""
        self.status = self.STATUS_EXPIRED
        self.save(update_fields=["status"])

    def mark_as_locked(self, reason: str = "") -> None:
        """Temporarily lock credentials."""
        self.status = self.STATUS_LOCKED
        if reason:
            self._save_verification_log("locked", reason)
        self.save(update_fields=["status"])

    def unlock(self) -> None:
        """Unlock locked credentials."""
        if self.status == self.STATUS_LOCKED:
            self.status = self.STATUS_ACTIVE
            self.save(update_fields=["status"])

    # ==================== Verification Methods ====================

    def verify_credentials(
        self, session, mark_as_active: bool = True, mark_as_stored: bool = False
    ) -> tuple[bool, dict]:
        """Verify credentials via browser automation.

        On checkpoint/challenge, the browser is kept alive (visible via VNC)
        so the user can complete the challenge interactively.  The caller
        should then invoke ``confirm_challenge(session)`` once the user
        signals completion from the frontend.

        Returns:
            (success, details) — details always contains ``error_type``.
            When error_type is ``"awaiting_challenge"`` the browser is still
            running and the session is usable for ``confirm_challenge``.
        """
        from linkedin_cli.browser.login import launch_browser, submit_login_form  # type: ignore[import-untyped]
        from linkedin_cli.page_state import classify_page, PageState  # type: ignore[import-untyped]

        logger.info(
            "Starting LinkedIn credential verification for %s", self.get_public_email()
        )

        try:
            # Launch browser
            session.page, session.context, session.browser, session.playwright = launch_browser()

            # Stamp credentials on session so submit_login_form can read them
            session.username = self.get_email()
            session.password = self.get_password()

            # Use linkedin_cli's login form handler (handles goto, stealth typing, etc.)
            submit_login_form(session, session.username, session.password)

            # Check where we ended up
            page_state = classify_page(session.page)
            logger.info("Post-login page state: %s (%s)", page_state, session.page.url)

            if page_state == PageState.FEED:
                return self._mark_verified(session, mark_as_active)

            # Checkpoint/challenge or still on login — keep browser alive for VNC
            logger.warning(
                "Challenge detected for %s (state=%s, url=%s) — browser kept alive for VNC",
                self.get_public_email(), page_state, session.page.url,
            )
            try:
                self.status = self.STATUS_LOCKED
                self.save(update_fields=["status"])
            except Exception:
                pass
            try:
                LinkedInCredentialLog.objects.create(
                    credentials=self,
                    action="locked",
                    details={
                        "error_type": "awaiting_challenge",
                        "page_state": str(page_state),
                        "checkpoint_url": session.page.url,
                    },
                )
            except Exception:
                logger.debug("Could not write audit log for challenge")

            # Browser intentionally NOT closed — VNC exposes it
            return False, {
                "verified_at": None,
                "failures": self.verification_failures,
                "status": self.STATUS_LOCKED,
                "message": "LinkedIn requires verification. Complete the challenge in the browser viewer, then confirm.",
                "error_type": "awaiting_challenge",
            }

        except Exception as e:
            error_msg = str(e)[:500]
            is_timeout = "timeout" in error_msg.lower()
            logger.error("Credential verification failed for %s: %s", self.get_public_email(), error_msg)

            try:
                LinkedInCredentialLog.objects.create(
                    credentials=self,
                    action="failed",
                    details={
                        "error_type": "timeout" if is_timeout else "verification_error",
                        "error_message": error_msg,
                    },
                )
            except Exception:
                pass
            if mark_as_stored:
                self.status = self.STATUS_STORED
                self.save(update_fields=["status"])
            else:
                self.mark_as_invalid(reason=error_msg)

            return False, {
                "verified_at": None,
                "failures": self.verification_failures,
                "status": self.status,
                "message": f"Verification {'timed out' if is_timeout else 'error'}: {error_msg}",
                "error_type": "timeout" if is_timeout else "verification_error",
            }

    def confirm_challenge(self, session) -> tuple[bool, dict]:
        """Check if the user resolved the challenge in VNC and finalize auth.

        Call this after ``verify_credentials`` returned ``awaiting_challenge``.
        The browser must still be open on the session (VNC interaction happened
        in the same X display).
        """
        from linkedin_cli.page_state import classify_page, PageState  # type: ignore[import-untyped]

        if not session.page or session.page.is_closed():
            return False, {
                "verified_at": None,
                "status": self.status,
                "message": "Browser session expired. Please try again.",
                "error_type": "session_expired",
            }

        try:
            session.page.wait_for_load_state("domcontentloaded", timeout=10000)
            page_state = classify_page(session.page)

            if page_state == PageState.FEED:
                return self._mark_verified(session, mark_as_active=True)

            return False, {
                "verified_at": None,
                "status": self.STATUS_LOCKED,
                "message": "Challenge not yet completed. Finish the verification in the browser viewer and try again.",
                "error_type": "challenge_incomplete",
            }
        except Exception as e:
            return False, {
                "verified_at": None,
                "status": self.status,
                "message": f"Error checking challenge status: {str(e)[:200]}",
                "error_type": "verification_error",
            }

    def _mark_verified(self, session, mark_as_active: bool) -> tuple[bool, dict]:
        """Common path: mark credential active, save cookies, discover username."""
        from openoutreach.linkedin.browser.launch import _save_cookies

        self._discover_username(session)
        _save_cookies(session)

        self.last_verified = timezone.now()
        self.verification_failures = 0
        self.status = self.STATUS_ACTIVE if mark_as_active else self.STATUS_TESTED
        self.save(update_fields=["last_verified", "verification_failures", "status", "username"])

        LinkedInCredentialLog.objects.create(
            credentials=self,
            action="verified",
            details={"verified_by": "browser_automation", "status": self.status},
        )
        logger.info("Credential verified successfully for %s", self.get_public_email())

        return True, {
            "verified_at": self.last_verified.isoformat(),
            "failures": 0,
            "status": self.status,
            "message": "LinkedIn credentials verified successfully",
            "error_type": None,
        }

    def _discover_username(self, session) -> None:
        """Extract the LinkedIn username from the current authenticated page."""
        try:
            # Try the /in/username link in the nav
            me_link = session.page.query_selector("a[href*='/in/']")
            if me_link:
                href = me_link.get_attribute("href") or ""
                # Extract username from /in/username or /in/username/
                parts = [p for p in href.split("/") if p]
                if "in" in parts:
                    idx = parts.index("in")
                    if idx + 1 < len(parts):
                        username = parts[idx + 1]
                        if username and username != "me":
                            self.username = username
                            return

            # Fallback: check URL after navigating to /me/
            session.page.goto("https://www.linkedin.com/in/me/", timeout=10000)
            session.page.wait_for_load_state("domcontentloaded", timeout=5000)
            url = session.page.url
            if "/in/" in url:
                parts = [p for p in url.split("/") if p]
                if "in" in parts:
                    idx = parts.index("in")
                    if idx + 1 < len(parts):
                        username = parts[idx + 1]
                        if username and username != "me":
                            self.username = username
        except Exception as e:
            logger.debug("Could not discover username: %s", e)

    def check_checkpoint_challenge(self, session) -> tuple[bool, str]:
        """
        Check if LinkedIn is presenting a checkpoint/challenge (2FA, security check).

        Returns:
            Tuple of (is_checkpoint: bool, description: str)
        """

        try:
            current_url = session.page.url

            # Check for checkpoint URLs
            checkpoint_patterns = [
                "checkpoint",
                "challenge",
                "secondary",
                "sms",
                "email",
                "security",
                "2fa",
                "verify",
            ]

            for pattern in checkpoint_patterns:
                if pattern in current_url.lower():
                    return True, f"Checkpoint detected: {current_url}"

            # Check for checkpoint-related elements
            checkpoint_selectors = [
                "h1:has-text('check')",
                "h1:has-text('Security')",
                "h1:has-text('Confirm')",
                "h1:has-text('Verify')",
                "h1:has-text('Challenge')",
                "[class*='checkpoint']",
                "[class*='challenge']",
            ]

            for selector in checkpoint_selectors:
                elements = session.page.query_selector_all(selector)
                if elements:
                    return True, f"Checkpoint element detected: {selector}"

            return False, "No checkpoint detected"

        except Exception as e:
            logger.debug(f"Error checking for checkpoint: {e}")
            return False, str(e)

    def record_usage(
        self, campaign: Optional[Campaign] = None, action_type: str = ""
    ) -> None:
        """Record that these credentials were used for an action."""
        self.usage_count += 1
        self.last_used = timezone.now()

        if campaign and self.campaign != campaign:
            self.campaign = campaign

        self.save(update_fields=["usage_count", "last_used", "campaign"])

    # ==================== Rotation Methods ====================

    def needs_rotation(self) -> bool:
        """Check if credentials need rotation."""
        if self.status != self.STATUS_ACTIVE:
            return False
        if self.expires_at is None:
            return False
        return timezone.now() >= self.expires_at

    def rotate_credentials(
        self, new_email: Optional[str] = None, new_password: Optional[str] = None
    ) -> None:
        """Rotate credentials to new values."""
        if new_email:
            self.set_email(new_email)
        if new_password:
            self.set_password(new_password)

        self.rotated_at = timezone.now()
        self.expires_at = timezone.now() + timedelta(days=self.rotation_required_days)
        self.is_primary = False
        self.is_backup = True

        self.save(
            update_fields=[
                "email_encrypted",
                "password_encrypted",
                "rotated_at",
                "expires_at",
                "is_primary",
                "is_backup",
            ]
        )

    # ==================== Backup Methods ====================

    def create_backup(
        self, email: Optional[str] = None, password: Optional[str] = None
    ) -> "LinkedInCredentials":
        """Create a backup copy of these credentials."""
        backup = LinkedInCredentials.objects.create(
            username=f"Backup of {self.username or 'credential'}",
            email_encrypted=(
                self.email_encrypted if email is None else self.encrypt(email)
            ),
            password_encrypted=(
                self.password_encrypted if password is None else self.encrypt(password)
            ),
            status=self.STATUS_BACKUP,
            is_primary=False,
            is_backup=True,
            backup_of=self,
            created_at=timezone.now(),
            expires_at=self.expires_at,
            rotation_required_days=self.rotation_required_days,
        )
        return backup

    # ==================== Alert Methods ====================

    def send_security_alert(self, alert_type: str) -> None:
        """Send a security alert notification."""
        from django.core.mail import send_mail

        utcnow = timezone.now()
        if (
            self.security_alert_sent_at
            and (utcnow - self.security_alert_sent_at).days < 1
        ):
            return  # Don't send more than one alert per day

        subject = f"LinkedIn Security Alert: {alert_type}"
        status_display = getattr(self, "get_status_display")()
        message = f"""
        Security alert for LinkedIn credentials #{self.pk}
        
        Alert Type: {alert_type}
        Public Email: {self.get_public_email()}
        Status: {status_display}
        
        If this was not you, please contact support immediately.
        """

        try:
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [settings.ADMINS[0][1]] if settings.ADMINS else [],
                fail_silently=True,
            )
            self.security_alert_sent_at = utcnow
            self.save(update_fields=["security_alert_sent_at"])
        except Exception as e:
            logger.error("Failed to send security alert: %s", e)

    def _save_verification_log(self, action: str, reason: str) -> None:
        """Save a verification log entry."""
        LinkedInCredentialLog.objects.create(
            credentials=self,
            action=action,
            details={"reason": reason},
        )

    # ==================== Health Status Methods ====================

    def get_health_status(self) -> Dict[str, Any]:
        """Get a comprehensive health status for these credentials."""
        now = timezone.now()
        days_since_rotation = 0
        if self.rotated_at:
            days_since_rotation = (now - self.rotated_at).days

        days_until_expiry = None
        if self.expires_at:
            days_until_expiry = (self.expires_at - now).days

        return {
            "id": self.pk,
            "username": self.username or "",
            "public_email": self.get_public_email(),
            "status": self.status,
            "is_primary": self.is_primary,
            "is_backup": self.is_backup,
            "usage_count": self.usage_count,
            "days_since_rotation": days_since_rotation,
            "days_until_expiry": days_until_expiry,
            "verification_failures": self.verification_failures,
            "last_verified": (
                self.last_verified.isoformat() if self.last_verified else None
            ),
            "last_used": self.last_used.isoformat() if self.last_used else None,
            "health_score": self._calculate_health_score(),
        }

    def _calculate_health_score(self) -> int:
        """Calculate a health score (0-100) for these credentials."""
        score = 100

        # Deduct for status issues
        if self.status == self.STATUS_INVALID:
            score -= 50
        elif self.status == self.STATUS_LOCKED:
            score -= 30
        elif self.status == self.STATUS_EXPIRED:
            score -= 20

        # Deduct for old credentials
        if self.rotated_at:
            days_old = (timezone.now() - self.rotated_at).days
            if days_old > self.rotation_required_days:
                score -= 20

        # Deduct for verification failures
        score -= self.verification_failures * 5

        return max(0, min(100, score))


class LinkedInCredentialLog(models.Model):
    """
    Audit log for LinkedIn credential actions.

    Tracks all verification, usage, and security events for compliance
    and troubleshooting purposes.
    """

    ACTION_VERIFIED = "verified"
    ACTION_FAILED = "failed"
    ACTION_LOCKED = "locked"
    ACTION_UNLOCKED = "unlocked"
    ACTION_ROTATED = "rotated"
    ACTION_BACKUP = "backup"
    ACTION_USAGE = "usage"

    ACTION_CHOICES = [
        (ACTION_VERIFIED, "Verified"),
        (ACTION_FAILED, "Failed"),
        (ACTION_LOCKED, "Locked"),
        (ACTION_UNLOCKED, "Unlocked"),
        (ACTION_ROTATED, "Rotated"),
        (ACTION_BACKUP, "Backup Created"),
        (ACTION_USAGE, "Usage Recorded"),
    ]

    credentials: models.ForeignKey[LinkedInCredentials, LinkedInCredentials] = (
        models.ForeignKey(
            LinkedInCredentials,
            on_delete=models.CASCADE,
            related_name="logs",
        )
    )

    action: models.CharField = models.CharField(
        max_length=20,
        choices=ACTION_CHOICES,
    )

    details: models.JSONField = models.JSONField(default=dict, blank=True)

    ip_address: models.GenericIPAddressField | None = models.GenericIPAddressField(
        null=True, blank=True
    )
    user_agent: models.CharField = models.CharField(max_length=500, blank=True)

    created_at: models.DateTimeField = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "LinkedIn Credential Log"
        verbose_name_plural = "LinkedIn Credential Logs"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["credentials", "created_at"]),
        ]

    def __str__(self):
        return f"{self.credentials} - {self.action} at {self.created_at}"
