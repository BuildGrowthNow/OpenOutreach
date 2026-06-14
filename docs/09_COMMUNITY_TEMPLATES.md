# Community Campaign Templates

A marketplace of pre-built campaign templates created and shared by the OpenOutreach community, allowing users to get started quickly with proven strategies for different industries and use cases.

---

## Overview

The Community Templates system enables:
- **Template marketplace**: Browse and download campaigns created by other users
- **Industry-specific templates**: Ready-to-use strategies for different verticals
- **Template customization**: Fork and modify existing templates for your needs
- **Template sharing**: Share your successful campaigns with the community
- **Template ratings**: Discover high-quality templates through user feedback

This enables users to:
- Launch campaigns in minutes instead of building from scratch
- Learn from proven strategies used by successful practitioners
- Adapt industry-specific approaches rather than发明ing new ones
- Contribute their own successful templates back to the community

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      Community Templates System                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌──────────────┐     ┌──────────────────┐     ┌──────────────────────┐  │
│  │  Template    │────▶│  Template        │────▶│  Campaign Loader     │  │
│  │  Marketplace │     │  Registry        │     │  (Import/Export)     │  │
│  └──────────────┘     └──────────────────┘     └──────────────────────┘  │
│         │                     │                        │                │
│         ▼                     ▼                        ▼                │
│  ┌──────────────┐     ┌──────────────────┐     ┌──────────────────────┐  │
│  │ Template     │     │  Community       │     │  Template Builder    │  │
│  │ Registry     │     │  Contribution    │     │  (Fork/Customize)    │  │
│  └──────────────┘     └──────────────────┘     └──────────────────────┘  │
│                                                                           │
└─────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        Template Categories                              │
│                                                                           │
│  • SaaS / B2B Technology                                                │
│  • Marketing Agencies                                                   │
│  • Professional Services                                                │
│  • E-commerce Brands                                                    │
│  • Recruitment / HR Tech                                                │
│  • Fundraising / VC                                                     │
│  • Education / E-learning                                               │
│  • Content Creators / Influencers                                       │
│                                                                           │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Implementation Plan

### 1. Template Models (`linkedin/models/templates.py`)

```python
from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey


class TemplateCategory(models.Model):
    """Category for campaign templates."""
    
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    
    # Metadata
    icon = models.CharField(max_length=20, blank=True)
    color = models.CharField(max_length=20, blank=True)
    
    # Ordering
    order = models.PositiveIntegerField(default=0)
    
    # Status
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['order', 'name']
        verbose_name_plural = "Template categories"


class Template(models.Model):
    """A campaign template created by the community."""
    
    STATUS_DRAFT = 'draft'
    STATUS_PRIVATE = 'private'
    STATUS_REVIEWING = 'reviewing'
    STATUS_PUBLISHED = 'published'
    STATUS_ARCHIVED = 'archived'
    
    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draft'),
        (STATUS_PRIVATE, 'Private'),
        (STATUS_REVIEWING, 'Reviewing'),
        (STATUS_PUBLISHED, 'Published'),
        (STATUS_ARCHIVED, 'Archived'),
    ]
    
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    
    # Creator
    created_by = models.ForeignKey('User', on_delete=models.SET_NULL, null=True, related_name='templates')
    created_by_name = models.CharField(max_length=100, blank=True)  # For anonymous creators
    
    # Content
    description = models.TextField()
    long_description = models.TextField(blank=True)
    
    # Campaign data (stored as JSON for flexibility)
    template_data = models.JSONField(default=dict)
    # {
    #   'product_docs': str,
    #   'campaign_objective': str,
    #   'booking_link': str,
    #   'seed_urls': list,
    #   'search_keywords': list,
    # }
    
    # Categories
    categories = models.ManyToManyField(TemplateCategory, blank=True)
    
    # Statistics
    views = models.PositiveIntegerField(default=0)
    downloads = models.PositiveIntegerField(default=0)
    forks = models.PositiveIntegerField(default=0)
    rating = models.FloatField(default=0.0)
    ratings_count = models.PositiveIntegerField(default=0)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey('User', on_delete=models.SET_NULL, null=True, related_name='reviewed_templates')
    
    # Tags
    tags = models.JSONField(default=list)
    
    # Creation
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['rating']),
            models.Index(fields=['downloads']),
        ]
    
    def __str__(self):
        return self.title
    
    def get_rating_display(self):
        return f"{self.rating:.1f} ({self.ratings_count} reviews)"


class TemplateRating(models.Model):
    """Rating for a template."""
    
    template = models.ForeignKey(Template, on_delete=models.CASCADE, related_name='ratings')
    user = models.ForeignKey('User', on_delete=models.SET_NULL, null=True)
    rating = models.PositiveSmallIntegerField(choices=list(zip(range(1, 6), range(1, 6))))
    comment = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('template', 'user')
        ordering = ['-created_at']


class TemplateDownload(models.Model):
    """Record template downloads."""
    
    template = models.ForeignKey(Template, on_delete=models.CASCADE, related_name='downloads')
    user = models.ForeignKey('User', on_delete=models.SET_NULL, null=True)
    campaign = models.ForeignKey('Campaign', on_delete=models.SET_NULL, null=True, related_name='template_imports')
    
    download_type = models.CharField(max_length=20, choices=[
        ('direct', 'Direct download'),
        ('fork', 'Forked template'),
        ('import', 'Imported template'),
    ])
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = "Template downloads"
```

### 2. Template Service (`linkedin/services/templates.py`)

```python
from typing import Dict, List, Optional
from datetime import datetime
import json

from linkedoutreach.linkedin.models import Template, TemplateCategory, TemplateRating, TemplateDownload
from openoutreach.core.models import Campaign


class TemplateService:
    """Service for managing campaign templates."""
    
    def __init__(self):
        pass
    
    def get_templates(
        self,
        category_id: Optional[str] = None,
        search: Optional[str] = None,
        status: str = 'published',
        page: int = 1,
        page_size: int = 20,
    ) -> Dict:
        """Get paginated templates."""
        templates = Template.objects.filter(status=status)
        
        if category_id:
            templates = templates.filter(categories__id=category_id)
        
        if search:
            templates = templates.filter(
                models.Q(title__icontains=search) |
                models.Q(description__icontains=search) |
                models.Q(tags__contains=search)
            )
        
        total = templates.count()
        start = (page - 1) * page_size
        end = start + page_size
        templates = templates[start:end]
        
        return {
            'templates': [
                {
                    'id': t.id,
                    'title': t.title,
                    'slug': t.slug,
                    'description': t.description,
                    'created_by': t.created_by_name or t.created_by.username,
                    'categories': list(t.categories.values('id', 'name')),
                    'stats': {
                        'views': t.views,
                        'downloads': t.downloads,
                        'forks': t.forks,
                        'rating': t.rating,
                        'ratings_count': t.ratings_count,
                    },
                    'tags': t.tags,
                    'created_at': t.created_at.isoformat(),
                }
                for t in templates
            ],
            'page': page,
            'page_size': page_size,
            'total': total,
            'total_pages': (total + page_size - 1) // page_size,
        }
    
    def get_template(self, slug: str) -> Optional[Dict]:
        """Get a single template by slug."""
        try:
            template = Template.objects.get(slug=slug, status='published')
            
            # Increment views
            template.views += 1
            template.save()
            
            return {
                'id': template.id,
                'title': template.title,
                'slug': template.slug,
                'description': template.description,
                'long_description': template.long_description,
                'template_data': template.template_data,
                'created_by': template.created_by_name or template.created_by.username,
                'categories': list(template.categories.values('id', 'name')),
                'stats': {
                    'views': template.views,
                    'downloads': template.downloads,
                    'forks': template.forks,
                    'rating': template.rating,
                    'ratings_count': template.ratings_count,
                },
                'tags': template.tags,
                'created_at': template.created_at.isoformat(),
            }
        except Template.DoesNotExist:
            return None
    
    def create_template(
        self,
        user,
        title: str,
        description: str,
        template_data: Dict,
        categories: List[int] = None,
        tags: List[str] = None,
    ) -> Template:
        """Create a new template."""
        template = Template.objects.create(
            title=title,
            slug=self._generate_slug(title),
            description=description,
            template_data=template_data,
            created_by=user,
            created_by_name=user.get_full_name() or user.username,
            status='private',  # Must be reviewed before publishing
        )
        
        if categories:
            template.categories.set(categories)
        
        if tags:
            template.tags = tags
        
        return template
    
    def fork_template(self, template: Template, user, new_title: str = None) -> Template:
        """Create a copy of a template."""
        fork = Template.objects.create(
            title=new_title or f'Duplicate of {template.title}',
            slug=self._generate_slug(template.slug, 'fork'),
            description=f'Duplicate of {template.title} - forked from community template',
            template_data=template.template_data,
            created_by=user,
            created_by_name=user.get_full_name() or user.username,
            status='draft',
        )
        
        fork.categories.set(template.categories.all())
        fork.tags = template.tags.copy()
        
        # Increment fork count
        template.forks += 1
        template.save()
        
        return fork
    
    def import_template(self, template: Template, user, campaign_name: str = None) -> Campaign:
        """Import a template into a new campaign."""
        # Create campaign from template
        campaign = Campaign.objects.create(
            name=campaign_name or template.title,
            product_docs=template.template_data.get('product_docs', ''),
            campaign_objective=template.template_data.get('campaign_objective', ''),
            booking_link=template.template_data.get('booking_link', ''),
            seed_public_ids=template.template_data.get('seed_urls', []),
            is_archived=False,
        )
        
        # Add search keywords
        for keyword in template.template_data.get('search_keywords', []):
            from linkedoutreach.linkedin.models import SearchKeyword
            SearchKeyword.objects.get_or_create(
                campaign=campaign,
                keyword=keyword['keyword'],
                defaults={'used': keyword.get('used', 0)},
            )
        
        # Record import
        TemplateDownload.objects.create(
            template=template,
            user=user,
            campaign=campaign,
            download_type='import',
        )
        
        # Increment download count
        template.downloads += 1
        template.save()
        
        return campaign
    
    def rate_template(self, template: Template, user, rating: int, comment: str = None) -> TemplateRating:
        """Rate a template."""
        template_rating, created = TemplateRating.objects.get_or_create(
            template=template,
            user=user,
            defaults={
                'rating': rating,
                'comment': comment,
            }
        )
        
        if not created:
            template_rating.rating = rating
            template_rating.comment = comment
            template_rating.save()
        
        # Recalculate template rating
        ratings = TemplateRating.objects.filter(template=template)
        template.ratings_count = ratings.count()
        template.rating = ratings.aggregate(models.Avg('rating'))['rating__avg'] or 0.0
        template.save()
        
        return template_rating
    
    def _generate_slug(self, title: str, suffix: str = None) -> str:
        """Generate a URL-safe slug from title."""
        import re
        slug = re.sub(r'[^\w\s-]', '', title.lower())
        slug = re.sub(r'[\s_-]+', '-', slug).strip('-')
        
        if suffix:
            slug = f"{slug}-{suffix}"
        
        return slug


# Convenience function
template_service = TemplateService()
```

### 3. Template Marketplace Dashboard

```typescript
interface Template {
  id: number;
  title: string;
  slug: string;
  description: string;
  created_by: string;
  categories: { id: number; name: string }[];
  stats: {
    views: number;
    downloads: number;
    forks: number;
    rating: number;
    ratings_count: number;
  };
  tags: string[];
  created_at: string;
}

export function TemplateMarketplace() {
  const [templates, setTemplates] = useState<Template[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState<number | null>(null);
  const [page, setPage] = useState(1);
  
  useEffect(() => {
    fetchTemplates();
  }, [search, category, page]);

  const fetchTemplates = async () => {
    setLoading(true);
    const params = new URLSearchParams();
    if (search) params.append('search', search);
    if (category) params.append('category', category.toString());
    params.append('page', page.toString());
    
    const res = await fetch(`/api/templates/?${params.toString()}`);
    const data = await res.json();
    setTemplates(data.templates);
    setLoading(false);
  };

  return (
    <div className="space-y-6">
      {/* Search and Filter */}
      <div className="flex gap-4">
        <input
          type="text"
          placeholder="Search templates..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="flex-1 p-2 border rounded"
        />
        <select
          value={category || ''}
          onChange={(e) => setCategory(e.target.value ? Number(e.target.value) : null)}
          className="p-2 border rounded"
        >
          <option value="">All Categories</option>
          <option value="1">SaaS & B2B Technology</option>
          <option value="2">Marketing Agencies</option>
          <option value="3">Professional Services</option>
          <option value="4">E-commerce</option>
        </select>
      </div>

      {/* Template Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {templates.map(template => (
          <TemplateCard key={template.id} template={template} />
        ))}
      </div>

      {/* Pagination */}
      <Pagination page={page} totalPages={10} onPageChange={setPage} />
    </div>
  );
}

function TemplateCard({ template }: { template: Template }) {
  return (
    <div className="bg-white border rounded-lg p-5 hover:shadow-lg transition-shadow">
      <div className="flex items-start justify-between">
        <h3 className="font-semibold text-lg">{template.title}</h3>
        <div className="flex items-center gap-1 text-yellow-500">
          <span>★</span>
          <span className="font-semibold">{template.stats.rating.toFixed(1)}</span>
          <span className="text-gray-400 text-sm">({template.stats.ratings_count})</span>
        </div>
      </div>
      
      <p className="text-gray-600 mt-2">{template.description}</p>
      
      <div className="mt-4 flex flex-wrap gap-2">
        {template.categories.map(cat => (
          <span key={cat.id} className="px-2 py-1 bg-blue-100 text-blue-800 text-xs rounded">
            {cat.name}
          </span>
        ))}
      </div>
      
      <div className="mt-4 flex items-center justify-between text-sm text-gray-500">
        <span>by {template.created_by}</span>
        <span>{template.stats.downloads} downloads</span>
      </div>
      
      <div className="mt-4 flex gap-2">
        <button className="flex-1 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700">
          Use Template
        </button>
        <button className="flex-1 px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700">
          Fork Template
        </button>
        <button className="px-4 py-2 bg-gray-600 text-white rounded hover:bg-gray-700">
          View Details
        </button>
      </div>
    </div>
  );
}
```

### 4. Template Creation UI

```typescript
export function TemplateBuilder({ campaignId }: { campaignId: string }) {
  const [formData, setFormData] = useState({
    title: '',
    description: '',
    longDescription: '',
    productDocs: '',
    campaignObjective: '',
    bookingLink: '',
    seedUrls: [],
    searchKeywords: [],
  });

  const fetchCampaignData = async () => {
    const res = await fetch(`/api/campaigns/${campaignId}/`);
    const data = await res.json();
    
    setFormData({
      title: data.name,
      description: data.description || '',
      longDescription: '',
      productDocs: data.product_docs,
      campaignObjective: data.campaign_objective,
      bookingLink: data.booking_link,
      seedUrls: '',
      searchKeywords: '',
    });
  };

  const saveAsTemplate = async () => {
    const res = await fetch('/api/templates/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        title: formData.title,
        description: formData.description,
        long_description: formData.longDescription,
        template_data: {
          product_docs: formData.productDocs,
          campaign_objective: formData.campaignObjective,
          booking_link: formData.bookingLink,
          seed_urls: formData.seedUrls,
          search_keywords: formData.searchKeywords,
        },
        categories: [],
        tags: [],
      }),
    });
    
    if (res.ok) {
      alert('Template saved! It will be reviewed before being published.');
    }
  };

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Save Campaign as Template</h2>
      
      <div className="space-y-4">
        <TextInput
          label="Template Title"
          value={formData.title}
          onChange={(v) => setFormData({ ...formData, title: v })}
          placeholder="e.g., SaaS Growth Outreach - Startup Edition"
        />
        
        <TextArea
          label="Short Description"
          value={formData.description}
          onChange={(v) => setFormData({ ...formData, description: v })}
          placeholder="Brief overview of what this template does..."
          rows={3}
        />
        
        <TextArea
          label="Detailed Description"
          value={formData.longDescription}
          onChange={(v) => setFormData({ ...formData, longDescription: v })}
          placeholder="Full explanation for users considering this template..."
          rows={6}
        />
      </div>

      <div className="bg-gray-50 p-4 rounded">
        <h3 className="font-semibold mb-2">Campaign Data (Auto-filled)</h3>
        
        <TextArea
          label="Product Description"
          value={formData.productDocs}
          onChange={(v) => setFormData({ ...formData, productDocs: v })}
          rows={8}
          readOnly
        />
        
        <TextArea
          label="Campaign Objective"
          value={formData.campaignObjective}
          onChange={(v) => setFormData({ ...formData, campaignObjective: v })}
          rows={6}
          readOnly
        />
        
        <TextInput
          label="Booking Link"
          value={formData.bookingLink}
          onChange={(v) => setFormData({ ...formData, bookingLink: v })}
        />
      </div>

      <div className="flex gap-4">
        <button className="flex-1 px-6 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 font-semibold">
          Save as Template
        </button>
        <button className="flex-1 px-6 py-3 bg-gray-600 text-white rounded-lg hover:bg-gray-700">
          Cancel
        </button>
      </div>
    </div>
  );
}
```

### 5. Template Import Integration

Update onboarding to suggest templates:

```python
# core/onboarding.py

def suggest_templates_for_campaign(campaign: Campaign) -> List[Dict]:
    """Suggest templates that might fit this campaign."""
    from linkedoutreach.linkedin.models import Template
    
    # Get user's campaign information
    product_docs = campaign.product_docs
    objective = campaign.campaign_objective
    
    # Simple keyword matching to find relevant templates
    keywords = [
        'SaaS', 'B2B', 'tech', 'marketing', 'agencies', 'consulting', 
        'startups', 'founders', 'growth', 'digital'
    ]
    
    queries = []
    for keyword in keywords:
        if keyword in product_docs.lower() or keyword in objective.lower():
            queries.append(models.Q(title__icontains=keyword) | models.Q(tags__contains=keyword))
    
    if not queries:
        # No specific matches, suggest popular templates
        queries.append(models.Q(status='published'))
    
    templates = Template.objects.filter(
        models.Q(*queries, operator='OR'),
        status='published',
    ).order_by('-rating', '-downloads')[:5]
    
    return [
        {
            'id': t.id,
            'title': t.title,
            'description': t.description,
            'rating': t.rating,
            'downloads': t.downloads,
        }
        for t in templates
    ]


# Update onboarding flow to include template selection
def collect_from_wizard() -> OnboardConfig:
    """Collect onboarding config via interactive wizard."""
    import questionary
    
    config = OnboardConfig()
    
    # Existing questions...
    config.campaign_name = questionary.text("Campaign Name:").ask()
    config.product_docs = questionary.text("Product Description:", multiline=True).ask()
    config.campaign_objective = questionary.text("Campaign Objective:", multiline=True).ask()
    config.booking_link = questionary.text("Booking Link:").ask()
    
    # NEW: Template suggestion
    if config.campaign_name:
        campaign = Campaign(name=config.campaign_name)
        
        templates = suggest_templates_for_campaign(campaign)
        
        if templates:
            template_names = [f"{t['title']} ({t['rating']}★, {t['downloads']} downloads)" for t in templates]
            use_template = questionary.confirm(
                f"Found {len(templates)} relevant templates. Would you like to use one as a starting point?",
                default=True,
            ).ask()
            
            if use_template:
                selected = questionary.select(
                    "Select a template:",
                    choices=template_names,
                ).ask()
                
                template_index = template_names.index(selected)
                template = templates[template_index]
                
                # Load template data
                from linkedoutreach.linkedin.models import Template
                loaded_template = Template.objects.get(id=template['id'])
                template_data = loaded_template.template_data
                
                # Update config with template data
                if 'product_docs' in template_data:
                    config.product_docs = template_data['product_docs']
                if 'campaign_objective' in template_data:
                    config.campaign_objective = template_data['campaign_objective']
                if 'booking_link' in template_data:
                    config.booking_link = template_data['booking_link']
    
    return config
```

---

## Migration Plan

1. Create Template models and database tables
2. Build Template service
3. Create marketplace frontend
4. Add template import to campaign builder
5. Implement template rating system
6. Add template export functionality

---

## Benefits

| Feature | Before | After |
|---------|--------|-------|
| Setup time | Hours/days | Minutes |
| Learning curve | Steep | Guided by examples |
| Industry knowledge | Generic | Proven strategies |
| Innovation | One-off | Community-driven |
| Quality | Variable | Curated by community |

The community templates system accelerates campaign launch by providing proven strategies for different industries and use cases, while enabling users to contribute their own successful approaches back to the community.