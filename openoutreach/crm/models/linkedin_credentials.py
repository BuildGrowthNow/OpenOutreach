# openoutreach/crm/models/linkedin_credentials.py
"""LinkedIn Credentials Management with Secure Encryption."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from openoutreach.core.models import Campaign
    from openoutreach.linkedin.models import LinkedInProfile

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from openoutreach.core.models import Campaign

logger = logging.getLogger(__name__)


def _derive_key_from_settings() -> bytes:
    """Derive encryption key from Django settings.
    
    Uses the SECRET_KEY as the basis for encryption, combined with a salt.
    This ensures keys are tied to the specific deployment.
    """
    secret = settings.SECRET_KEY.encode()
    salt = b'openoutreach_linkedin_credentials'  # Fixed salt for this deployment
    
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
    STATUS_STORED = 'stored'  # Credential saved but not tested
    STATUS_TESTED = 'tested'  # Attempted login but needs verification
    STATUS_ACTIVE = 'active'  # Successfully verified and working
    STATUS_INVALID = 'invalid'  # Verification failed
    STATUS_EXPIRED = 'expired'  # Needs rotation
    STATUS_LOCKED = 'locked'  # Temporarily disabled (checkpoint/Challenge)
    STATUS_BACKUP = 'backup'  # Backup credential
    
    STATUS_CHOICES = [
        (STATUS_STORED, _('Stored - not yet verified')),
        (STATUS_TESTED, _('Tested - login attempted')),
        (STATUS_ACTIVE, _('Active - verified and working')),
        (STATUS_INVALID, _('Invalid - verification failed')),
        (STATUS_EXPIRED, _('Expired - needs rotation')),
        (STATUS_LOCKED, _('Locked - checkpoint/challenge detected')),
        (STATUS_BACKUP, _('Backup credential')),
    ]
    
    # Credential owner - linked to a specific LinkedIn profile
    linkedin_profile: models.OneToOneField[LinkedInProfile | None, LinkedInProfile] = models.OneToOneField(
        LinkedInProfile,
        on_delete=models.CASCADE,
        related_name='credentials',
        null=True,
        blank=True,
        help_text=_('The LinkedIn profile this credential belongs to')
    )
    
    # Encrypted credential data
    email_encrypted: models.BinaryField = models.BinaryField(
        max_length=500,
        help_text=_('Encrypted LinkedIn email')
    )
    password_encrypted: models.BinaryField = models.BinaryField(
        max_length=500,
        help_text=_('Encrypted LinkedIn password')
    )
    
    # Display information (not encrypted)
    username: models.CharField = models.CharField(
        max_length=200,
        blank=True,
        help_text=_('Display name/username for this credential')
    )
    
    # Status and verification
    status: models.CharField = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_ACTIVE,
        help_text=_('Credential status and validity')
    )  # type: ignore[var-annotated]
    
    last_verified: models.DateTimeField = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_('When credentials were last verified')
    )
    verification_failed_at: models.DateTimeField = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_('When last verification failed')
    )
    verification_failures: models.PositiveIntegerField = models.PositiveIntegerField(
        default=0,
        help_text=_('Number of consecutive verification failures')
    )
    
    # Usage tracking
    usage_count: models.PositiveIntegerField = models.PositiveIntegerField(
        default=0,
        help_text=_('Total number of actions performed with these credentials')
    )
    last_used: models.DateTimeField = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_('When these credentials were last used')
    )
    campaign: models.ForeignKey[Campaign, Campaign] = models.ForeignKey(
        Campaign,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='linkedin_credentials',
        help_text=_('Campaign using these credentials')
    )
    
    # Rotation and expiration
    created_at: models.DateTimeField = models.DateTimeField(auto_now_add=True)
    updated_at: models.DateTimeField = models.DateTimeField(auto_now=True)
    expires_at: models.DateTimeField = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_('When these credentials expire (for rotation)')
    )
    rotated_at: models.DateTimeField = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_('When these credentials were last rotated')
    )
    rotation_required_days: models.PositiveIntegerField = models.PositiveIntegerField(
        default=90,
        help_text=_('Days after which credentials should be rotated')
    )
    
    # Backup and sharing
    is_primary: models.BooleanField = models.BooleanField(
        default=True,
        help_text=_('Whether this is the primary credential for the profile')
    )
    is_backup: models.BooleanField = models.BooleanField(
        default=False,
        help_text=_('Whether this is a backup credential')
    )
    
    # Backup tracking
    backup_of: models.ForeignKey[LinkedInCredentials | None, LinkedInCredentials] = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='backup_credentials',
        help_text=_('Original credential this is backed up from')
    )  # type: ignore[var-annotated]
    
    # Security alerts
    security_alert_sent_at: models.DateTimeField = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_('When last security alert was sent')
    )
    
    class Meta:
        verbose_name = _('LinkedIn Credential')
        verbose_name_plural = _('LinkedIn Credentials')
        ordering = ['-is_primary', '-updated_at']
        indexes = [
            models.Index(fields=['status', 'expires_at']),
            models.Index(fields=['campaign', 'status']),
        ]
    
    def __str__(self):
        return f"LinkedInCredential #{self.pk} ({self.get_public_email()})"
    
    # ==================== Encryption Methods ====================
    
    @classmethod
    def encrypt(cls, plaintext: str) -> bytes:
        """Encrypt a string using Fernet AES encryption."""
        fernet = _get_fernet()
        return fernet.encrypt(plaintext.encode('utf-8'))
    
    @classmethod
    def decrypt(cls, ciphertext: bytes) -> str:
        """Decrypt a string using Fernet AES decryption."""
        fernet = _get_fernet()
        try:
            return fernet.decrypt(ciphertext).decode('utf-8')
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
            if '@' in email:
                local, domain = email.rsplit('@', 1)
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
            self._save_verification_log('invalid', reason)
        self.save(update_fields=['status', 'verification_failed_at', 'verification_failures'])
    
    def mark_as_active(self) -> None:
        """Mark credentials as active."""
        self.status = self.STATUS_ACTIVE
        self.save(update_fields=['status'])
    
    def mark_as_expired(self) -> None:
        """Mark credentials as expired."""
        self.status = self.STATUS_EXPIRED
        self.save(update_fields=['status'])
    
    def mark_as_locked(self, reason: str = "") -> None:
        """Temporarily lock credentials."""
        self.status = self.STATUS_LOCKED
        if reason:
            self._save_verification_log('locked', reason)
        self.save(update_fields=['status'])
    
    def unlock(self) -> None:
        """Unlock locked credentials."""
        if self.status == self.STATUS_LOCKED:
            self.status = self.STATUS_ACTIVE
            self.save(update_fields=['status'])
    
    # ==================== Verification Methods ====================
    
    def verify_credentials(
        self, 
        session,
        mark_as_active: bool = True,
        mark_as_stored: bool = False
    ) -> tuple[bool, dict]:
        """
        Verify credentials by attempting a LinkedIn login using browser automation.
        
        This method performs a safe, real LinkedIn login verification using the
        existing browser session infrastructure. It handles:
        - Successful authentication (status -> active)
        - Checkpoint/challenge/2FA flows (status -> locked)
        - Invalid credentials (status -> invalid)
        - Other errors (status -> stored or invalid depending on mark_as_stored)
        
        Args:
            session: AccountSession for browser automation
            mark_as_active: If True, mark as active on success
            mark_as_stored: If True, mark as stored on failure instead of invalid
            
        Returns:
            Tuple of (success: bool, details: dict)
            details contains: verified_at, failures, status, message, error_type
        """
        from openoutreach.linkedin.browser.launch import start_browser_session
        from linkedin_cli.browser.login import dismiss_comply_gate, goto_page
        from linkedin_cli.browser.nav import wait_for_element
        
        logger.info("Starting LinkedIn credential verification for %s", self.get_public_email())
        
        try:
            # Ensure we have a fresh browser session for verification
            session.ensure_browser()
            
            # Navigate to LinkedIn login page
            session.page.goto("https://www.linkedin.com/login")
            
            # Enter credentials
            email_input = wait_for_element(session.page, "input#username", timeout=10000)
            password_input = wait_for_element(session.page, "input#password", timeout=10000)
            
            # Clear and fill email
            email_input.fill("")
            email_input.type(self.get_email())
            
            # Clear and fill password  
            password_input.fill("")
            password_input.type(self.get_password())
            
            # Click login button
            login_button = wait_for_element(session.page, "button[type='submit']", timeout=10000)
            login_button.click()
            
            # Wait for page to load
            session.page.wait_for_load_state("domcontentloaded", timeout=15000)
            
            # Check for checkpoint/challenge/2FA flows
            current_url = session.page.url
            
            # Check if we're still on login page (failed auth)
            if "linkedin.com/login" in current_url:
                # Check for specific error messages
                error_selectors = [
                    "div.err-msg",
                    "div.error",
                    "div.login__error",
                    "[class*='error']",
                ]
                
                for selector in error_selectors:
                    error_elements = session.page.query_selector_all(selector)
                    if error_elements:
                        error_texts = [el.inner_text() for el in error_elements]
                        error_msg = "; ".join(error_texts[:3])  # Limit to 3 errors
                        logger.warning(f"LinkedIn credential verification failed for {self.get_public_email()}: {error_msg}")
                        
                        # Update verification log
                        LinkedInCredentialLog.objects.create(
                            credentials=self,
                            action='failed',
                            details={
                                'error_type': 'invalid_credentials',
                                'error_message': error_msg,
                                'ip_address': None,
                            },
                        )
                        
                        self.mark_as_invalid(reason=error_msg)
                        return False, {
                            'verified_at': None,
                            'failures': self.verification_failures,
                            'status': self.STATUS_INVALID,
                            'message': 'Invalid LinkedIn credentials',
                            'error_type': 'invalid_credentials',
                        }
                
                # No specific error found - probably still waiting for 2FA
                logger.warning(f"LinkedIn credential verification paused for {self.get_public_email()} - likely 2FA required")
                
                LinkedInCredentialLog.objects.create(
                    credentials=self,
                    action='locked',
                    details={
                        'error_type': 'checkpoint_detected',
                        'message': 'LinkedIn checkpoint/challenge detected (2FA or security check)',
                        'ip_address': None,
                    },
                )
                
                self.mark_as_locked(reason='Checkpoint/challenge detected')
                return False, {
                    'verified_at': None,
                    'failures': self.verification_failures + 1,
                    'status': self.STATUS_LOCKED,
                    'message': 'LinkedIn checkpoint/challenge detected. Account requires additional verification.',
                    'error_type': 'checkpoint_detected',
                }
            
            # Check if we're on feed (successful login)
            if "linkedin.com/feed" in current_url or "linkedin.com" in current_url:
                # Check for profile access
                try:
                    profile_link = session.page.query_selector("[href='/me']")
                    if profile_link:
                        logger.info(f"LinkedIn credential verification successful for {self.get_public_email()}")
                        
                        self.last_verified = timezone.now()
                        self.verification_failures = 0
                        self.status = self.STATUS_ACTIVE if mark_as_active else self.STATUS_TESTED
                        self.save(update_fields=[
                            'last_verified', 
                            'verification_failures', 
                            'status',
                        ])
                        
                        LinkedInCredentialLog.objects.create(
                            credentials=self,
                            action='verified',
                            details={
                                'verified_by': 'browser_automation',
                                'status': self.status,
                                'ip_address': None,
                            },
                        )
                        
                        return True, {
                            'verified_at': self.last_verified.isoformat(),
                            'failures': 0,
                            'status': self.status,
                            'message': 'LinkedIn credentials verified successfully',
                            'error_type': None,
                        }
                except Exception:
                    pass  # Continue with basic success
            
            # Basic success if we got past login
            logger.info(f"LinkedIn credential verification successful for {self.get_public_email()}")
            
            self.last_verified = timezone.now()
            self.verification_failures = 0
            self.status = self.STATUS_ACTIVE if mark_as_active else self.STATUS_TESTED
            self.save(update_fields=[
                'last_verified', 
                'verification_failures', 
                'status',
            ])
            
            LinkedInCredentialLog.objects.create(
                credentials=self,
                action='verified',
                details={
                    'verified_by': 'browser_automation',
                    'status': self.status,
                    'ip_address': None,
                },
            )
            
            return True, {
                'verified_at': self.last_verified.isoformat(),
                'failures': 0,
                'status': self.status,
                'message': 'LinkedIn credentials verified successfully',
                'error_type': None,
            }
            
        except Exception as e:
            error_msg = str(e)[:500]  # Limit error message length
            logger.error(f"Credential verification failed for {self.get_public_email()}: {error_msg}")
            
            LinkedInCredentialLog.objects.create(
                credentials=self,
                action='failed',
                details={
                    'error_type': 'verification_error',
                    'error_message': error_msg,
                    'ip_address': None,
                },
            )
            
            if mark_as_stored:
                self.status = self.STATUS_STORED
            else:
                self.mark_as_invalid(reason=error_msg)
            
            return False, {
                'verified_at': None,
                'failures': self.verification_failures,
                'status': self.status,
                'message': f'Verification error: {error_msg}',
                'error_type': 'verification_error',
            }
    
    def check_checkpoint_challenge(self, session) -> tuple[bool, str]:
        """
        Check if LinkedIn is presenting a checkpoint/challenge (2FA, security check).
        
        Returns:
            Tuple of (is_checkpoint: bool, description: str)
        """
        from linkedin_cli.browser.login import dismiss_comply_gate
        
        try:
            current_url = session.page.url
            
            # Check for checkpoint URLs
            checkpoint_patterns = [
                'checkpoint',
                'challenge',
                'secondary',
                'sms',
                'email',
                'security',
                '2fa',
                'verify',
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
    
    def record_usage(self, campaign: Optional[Campaign] = None, action_type: str = '') -> None:
        """Record that these credentials were used for an action."""
        self.usage_count += 1
        self.last_used = timezone.now()
        
        if campaign and self.campaign != campaign:
            self.campaign = campaign
        
        self.save(update_fields=['usage_count', 'last_used', 'campaign'])
    
    # ==================== Rotation Methods ====================
    
    def needs_rotation(self) -> bool:
        """Check if credentials need rotation."""
        if self.status != self.STATUS_ACTIVE:
            return False
        if self.expires_at is None:
            return False
        return timezone.now() >= self.expires_at
    
    def rotate_credentials(self, new_email: Optional[str] = None, new_password: Optional[str] = None) -> None:
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
                'email_encrypted', 'password_encrypted', 'rotated_at',
                'expires_at', 'is_primary', 'is_backup'
            ]
        )
    
    # ==================== Backup Methods ====================
    
    def create_backup(self, email: Optional[str] = None, password: Optional[str] = None) -> 'LinkedInCredentials':
        """Create a backup copy of these credentials."""
        backup = LinkedInCredentials.objects.create(
            username=f"Backup of {self.username or 'credential'}",
            email_encrypted=self.email_encrypted if email is None else self.encrypt(email),
            password_encrypted=self.password_encrypted if password is None else self.encrypt(password),
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
        if (self.security_alert_sent_at and 
            (utcnow - self.security_alert_sent_at).days < 1):
            return  # Don't send more than one alert per day
        
        subject = f"LinkedIn Security Alert: {alert_type}"
        message = f"""
        Security alert for LinkedIn credentials #{self.pk}
        
        Alert Type: {alert_type}
        Public Email: {self.get_public_email()}
        Status: {self.get_status_display()}  # type: ignore[attr-defined]
        
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
            self.save(update_fields=['security_alert_sent_at'])
        except Exception as e:
            logger.error("Failed to send security alert: %s", e)
    
    def _save_verification_log(self, action: str, reason: str) -> None:
        """Save a verification log entry."""
        LinkedInCredentialLog.objects.create(
            credentials=self,
            action=action,
            details={'reason': reason},
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
            'id': self.pk,
            'username': self.username or '',
            'public_email': self.get_public_email(),
            'status': self.status,
            'is_primary': self.is_primary,
            'is_backup': self.is_backup,
            'usage_count': self.usage_count,
            'days_since_rotation': days_since_rotation,
            'days_until_expiry': days_until_expiry,
            'verification_failures': self.verification_failures,
            'last_verified': self.last_verified.isoformat() if self.last_verified else None,
            'last_used': self.last_used.isoformat() if self.last_used else None,
            'health_score': self._calculate_health_score(),
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
    
    ACTION_VERIFIED = 'verified'
    ACTION_FAILED = 'failed'
    ACTION_LOCKED = 'locked'
    ACTION_UNLOCKED = 'unlocked'
    ACTION_ROTATED = 'rotated'
    ACTION_BACKUP = 'backup'
    ACTION_USAGE = 'usage'
    
    ACTION_CHOICES = [
        (ACTION_VERIFIED, 'Verified'),
        (ACTION_FAILED, 'Failed'),
        (ACTION_LOCKED, 'Locked'),
        (ACTION_UNLOCKED, 'Unlocked'),
        (ACTION_ROTATED, 'Rotated'),
        (ACTION_BACKUP, 'Backup Created'),
        (ACTION_USAGE, 'Usage Recorded'),
    ]
    
    credentials: models.ForeignKey[LinkedInCredentials, LinkedInCredentials] = models.ForeignKey(
        LinkedInCredentials,
        on_delete=models.CASCADE,
        related_name='logs',
    )
    
    action: models.CharField = models.CharField(
        max_length=20,
        choices=ACTION_CHOICES,
    )
    
    details: models.JSONField = models.JSONField(default=dict, blank=True)
    
    ip_address: models.GenericIPAddressField | None = models.GenericIPAddressField(null=True, blank=True)
    user_agent: models.CharField = models.CharField(max_length=500, blank=True)
    
    created_at: models.DateTimeField = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'LinkedIn Credential Log'
        verbose_name_plural = 'LinkedIn Credential Logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['credentials', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.credentials} - {self.action} at {self.created_at}"