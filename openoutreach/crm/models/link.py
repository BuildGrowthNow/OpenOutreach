# Link tracking models for UTM tracking and analytics

from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone
from django.urls import reverse

if TYPE_CHECKING:
    from .deal import Deal
    from openoutreach.core.models import Campaign


class TrackedLink(models.Model):
    """
    Model for tracking marketing links with UTM parameters.
    Generates short, unique URLs for tracking clicks and conversions.
    """
    
    class Meta:
        verbose_name = "Tracked Link"
        verbose_name_plural = "Tracked Links"
        indexes = [
            models.Index(fields=['short_code'], name='trackedlink_shortcode_idx'),
            models.Index(fields=['campaign'], name='trackedlink_campaign_idx'),
            models.Index(fields=['created_at'], name='trackedlink_created_idx'),
        ]
    
    # Link identification
    campaign: models.ForeignKey[Campaign, Campaign] = models.ForeignKey(
        Campaign, on_delete=models.CASCADE, related_name='tracked_links', null=True, blank=True
    )
    original_url: models.URLField = models.URLField(max_length=1000, help_text="Original destination URL")
    short_code: models.CharField = models.CharField(
        max_length=50, unique=True, help_text="Short unique identifier for the link"
    )
    is_active: models.BooleanField = models.BooleanField(default=True, help_text="Whether this link is active")
    
    # UTM parameters for source tracking
    utm_source: models.CharField = models.CharField(max_length=100, blank=True, help_text="UTM source parameter")
    utm_medium: models.CharField = models.CharField(max_length=100, blank=True, help_text="UTM medium parameter")
    utm_campaign: models.CharField = models.CharField(max_length=100, blank=True, help_text="UTM campaign parameter")
    utm_term: models.CharField = models.CharField(max_length=100, blank=True, help_text="UTM term parameter")
    utm_content: models.CharField = models.CharField(max_length=100, blank=True, help_text="UTM content parameter")
    
    # Statistics
    total_clicks: models.PositiveIntegerField = models.PositiveIntegerField(default=0)
    unique_clicks: models.PositiveIntegerField = models.PositiveIntegerField(default=0)
    created_at: models.DateTimeField = models.DateTimeField(auto_now_add=True)
    last_clicked_at: models.DateTimeField = models.DateTimeField(null=True, blank=True)
    
    # Tracking details
    last_ip: models.GenericIPAddressField | None = models.GenericIPAddressField(null=True, blank=True)
    last_user_agent: models.CharField = models.CharField(max_length=500, blank=True)
    
    def __str__(self):
        campaign_name = self.campaign.name if self.campaign else "General"
        return f"{campaign_name}: {self.short_code}"
    
    def get_short_url(self, request=None):
        """Get the short tracked URL."""
        if request:
            return request.build_absolute_uri(
                reverse('link_redirect', kwargs={'short_code': self.short_code})
            )
        return f"https://yourdomain.com/l/{self.short_code}"
    
    def record_click(self, ip_address: str | None = None, user_agent: str | None = None):
        """Record a click on this link."""
        self.total_clicks += 1
        self.last_clicked_at = timezone.now()
        
        # Track last IP and user agent for analytics
        if ip_address:
            self.last_ip = ip_address
        if user_agent:
            self.last_user_agent = user_agent[:500]  # Limit length
        
        self.save(update_fields=[
            'total_clicks', 'last_clicked_at', 'last_ip', 'last_user_agent'
        ])
    
    @property
    def conversion_rate(self):
        """Calculate conversion rate based on linked deals."""
        if self.total_clicks == 0:
            return 0.0
        return round(self.deal_links.count() / self.total_clicks * 100, 2)


class LinkClick(models.Model):
    """
    Individual click record for detailed analytics.
    Stores IP, user agent, timestamp, and referrer for each click.
    """
    
    class Meta:
        verbose_name = "Link Click"
        verbose_name_plural = "Link Clicks"
        indexes = [
            models.Index(fields=['link', 'clicked_at'], name='linkclick_link_time_idx'),
            models.Index(fields=['ip_address'], name='linkclick_ip_idx'),
        ]
    
    link: models.ForeignKey[TrackedLink, TrackedLink] = models.ForeignKey(
        TrackedLink, on_delete=models.CASCADE, related_name='clicks'
    )
    ip_address: models.GenericIPAddressField | None = models.GenericIPAddressField(null=True, blank=True)
    user_agent: models.CharField = models.CharField(max_length=500, blank=True)
    referrer: models.CharField = models.CharField(max_length=500, blank=True)
    clicked_at: models.DateTimeField = models.DateTimeField(auto_now_add=True)
    device_type: models.CharField = models.CharField(
        max_length=20, 
        choices=[
            ('desktop', 'Desktop'),
            ('mobile', 'Mobile'),
            ('tablet', 'Tablet'),
        ],
        blank=True
    )
    country: models.CharField = models.CharField(max_length=100, blank=True)
    
    def __str__(self):
        return f"Click on {self.link.short_code} at {self.clicked_at}"
    
    def detect_device(self):
        """Detect device type from user agent."""
        if not self.user_agent:
            return None
        
        ua_lower = self.user_agent.lower()
        
        if 'mobile' in ua_lower or 'android' in ua_lower or 'iphone' in ua_lower:
            self.device_type = 'mobile'
        elif 'ipad' in ua_lower or 'tablet' in ua_lower:
            self.device_type = 'tablet'
        else:
            self.device_type = 'desktop'
        
        self.save(update_fields=['device_type'])
        return self.device_type


class LinkDealConversion(models.Model):
    """
    Model linking link clicks to actual deal conversions.
    Tracks which links led to which deals.
    """
    
    class Meta:
        verbose_name = "Link Conversion"
        verbose_name_plural = "Link Conversions"
        indexes = [
            models.Index(fields=['link'], name='linkconv_link_idx'),
            models.Index(fields=['deal'], name='linkconv_deal_idx'),
        ]
    
    link: models.ForeignKey[TrackedLink, TrackedLink] = models.ForeignKey(
        TrackedLink, on_delete=models.CASCADE, related_name='deal_links'
    )
    click: models.ForeignKey[LinkClick, LinkClick] | None = models.ForeignKey(
        LinkClick, on_delete=models.SET_NULL, null=True, blank=True
    )
    deal: models.ForeignKey[Deal, Deal] = models.ForeignKey(
        Deal, on_delete=models.CASCADE, related_name='link_conversions'
    )
    converted_at: models.DateTimeField = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Conversion: {self.link.short_code} -> Deal {self.deal.id}"