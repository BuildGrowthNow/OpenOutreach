# Personal Knowledge Graph for Campaigns

A semantic knowledge base that learns from each campaign's interactions, storing rich relationships between leads, companies, industries, and outreach patterns to enable deeper insights and better personalization.

---

## Overview

The Knowledge Graph creates a persistent memory of your outreach:
- **Entities**: Leads, companies, industries, job titles, skills, tech stacks
- **Relationships**: Works at, interested in, connects to, similar to, qualified for
- **Attributes**: Company size, industry, recent funding, engagement level

The graph enables:
- **Cross-campaign learning**: Insights from one campaign improve others
- **Rich personalization**: Context-aware messaging based on company knowledge
- **Pattern discovery**: Find which approaches work best for specific segments
- **Predictive scoring**: Score leads based on graph-based features

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       Knowledge Graph Engine                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌────────────┐     ┌─────────────────┐     ┌───────────────────────┐   │
│  │ Entity     │────▶│  Graph Database │────▶│  Relationship Engine  │   │
│  │ Extractor  │     │  (Neo4j/TigerDB)│     │  (Cypher/SPARQL)      │   │
│  └────────────┘     └─────────────────┘     └───────────────────────┘   │
│         │                    │                    │                     │
│         ▼                    ▼                    ▼                     │
│  ┌────────────┐     ┌─────────────────┐     ┌───────────────────────┐   │
│  │ LLM        │◀────│  Pattern Learner│◀────│  Campaign Insights  │   │
│  │ Analyzer   │     │  (Graph Neural  │     │  (Aggregations)     │   │
│  └────────────┘     │  Networks)      │     └───────────────────────┘   │
│                     └─────────────────┘                                 │
│                                                                           │
└─────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         Applied Use Cases                               │
│                                                                           │
│  • Hyper-personalized outreach (company-specific context)              │
│  • Pattern-based lead scoring                                          │
│  • Campaign optimization recommendations                               │
│  • Competitor intelligence (unofficial)                                │
│  • Cross-campaign insight sharing                                      │
│                                                                           │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Implementation Plan

### 1. Knowledge Graph Models (`linkedin/models/graph.py`)

```python
from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey


class Entity(models.Model):
    """Represents a named entity in the knowledge graph."""
    
    TYPE_LEAD = 'lead'
    TYPE_COMPANY = 'company'
    TYPE_INDUSTRY = 'industry'
    TYPE_JOB_TITLE = 'job_title'
    TYPE_SKILL = 'skill'
    TYPE_TECH_STACK = 'tech_stack'
    TYPE_VALUE = 'value'
    TYPE_PAIN_POINT = 'pain_point'
    TYPE_GOAL = 'goal'
    TYPE_SIGNAL = 'signal'
    
    TYPE_CHOICES = [
        (TYPE_LEAD, 'Lead'),
        (TYPE_COMPANY, 'Company'),
        (TYPE_INDUSTRY, 'Industry'),
        (TYPE_JOB_TITLE, 'Job Title'),
        (TYPE_SKILL, 'Skill'),
        (TYPE_TECH_STACK, 'Tech Stack'),
        (TYPE_VALUE, 'Value'),
        (TYPE_PAIN_POINT, 'Pain Point'),
        (TYPE_GOAL, 'Goal'),
        (TYPE_SIGNAL, 'Signal'),
    ]
    
    name = models.CharField(max_length=255)
    entity_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    
    # External reference
    external_id = models.CharField(max_length=255, blank=True)
    source_url = models.URLField(blank=True)
    
    # Attributes
    description = models.TextField(blank=True)
    metadata = models.JSONField(default=dict)
    
    # Aggregation
    relevance_score = models.FloatField(default=0.5)
    occurrence_count = models.PositiveIntegerField(default=1)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('name', 'entity_type')
        indexes = [
            models.Index(fields=['entity_type']),
            models.Index(fields=['relevance_score']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.entity_type})"


class Relationship(models.Model):
    """Represents a relationship between entities."""
    
    TYPE_WORKS_AT = 'works_at'
    TYPE_INTERESTED_IN = 'interested_in'
    TYPE_QUALIFIED_FOR = 'qualified_for'
    TYPE_SIMILAR_TO = 'similar_to'
    TYPE_CAME_FROM = 'came_from'
    TYPE_OFFERS = 'offers'
    TYPE_NEEDS = 'needs'
    TYPE_TECHNOLOGY_USED = 'technology_used'
    TYPE_HAS_PAIN_POINT = 'has_pain_point'
    TYPE_HAS_GOAL = 'has_goal'
    
    TYPE_CHOICES = [
        (TYPE_WORKS_AT, 'Works at'),
        (TYPE_INTERESTED_IN, 'Interested in'),
        (TYPE_QUALIFIED_FOR, 'Qualified for'),
        (TYPE_SIMILAR_TO, 'Similar to'),
        (TYPE_CAME_FROM, 'Came from'),
        (TYPE_OFFERS, 'Offers'),
        (TYPE_NEEDS, 'Needs'),
        (TYPE_TECHNOLOGY_USED, 'Technology used'),
        (TYPE_HAS_PAIN_POINT, 'Has pain point'),
        (TYPE_HAS_GOAL, 'Has goal'),
    ]
    
    source = models.ForeignKey(Entity, on_delete=models.CASCADE, related_name='outgoing')
    relationship_type = models.CharField(max_length=30, choices=TYPE_CHOICES)
    target = models.ForeignKey(Entity, on_delete=models.CASCADE, related_name='incoming')
    
    # Strength and confidence
    strength = models.FloatField(default=1.0)  # 0-1
    confidence = models.FloatField(default=0.8)  # 0-1
    weight = models.FloatField(default=1.0)  # For path finding
    
    # Metadata
    metadata = models.JSONField(default=dict)
    source_evidence = models.TextField(blank=True)
    
    # Counts
    occurrence_count = models.PositiveIntegerField(default=1)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('source', 'relationship_type', 'target')
        indexes = [
            models.Index(fields=['source', 'relationship_type']),
            models.Index(fields=['target', 'relationship_type']),
            models.Index(fields=['strength']),
        ]
    
    def __str__(self):
        return f"{self.source.name} {self.relationship_type} {self.target.name}"


class CampaignKnowledgeStats(models.Model):
    """Aggregated knowledge stats per campaign."""
    
    campaign = models.ForeignKey('Campaign', on_delete=models.CASCADE)
    
    entity_counts = models.JSONField(default=dict)  # {entity_type: count}
    relationship_counts = models.JSONField(default=dict)  # {relationship_type: count}
    
    top_industries = models.JSONField(default=list)
    top_job_titles = models.JSONField(default=list)
    top_pain_points = models.JSONField(default=list)
    top_tech_stacks = models.JSONField(default=list)
    
    # Quality metrics
    average_confidence = models.FloatField(default=0.5)
    knowledge_coverage = models.FloatField(default=0.0)
    
    calculated_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-calculated_at']
        verbose_name_plural = "Campaign knowledge stats"
```

### 2. Entity Extraction Service (`linkedin/services/knowledge_graph.py`)

```python
from typing import List, Dict, Optional
from datetime import datetime

from django.db import transaction

from linkedin.models import Entity, Relationship, CampaignKnowledgeStats


class KnowledgeGraphService:
    """Service for building and querying the knowledge graph."""
    
    def __init__(self):
        pass
    
    @transaction.atomic
    def extract_entities_from_profile(self, profile: Dict, campaign_id: str) -> List[Entity]:
        """Extract entities from a LinkedIn profile."""
        entities = []
        
        # Extract company
        company_name = profile.get('company')
        if company_name:
            company, _ = Entity.objects.get_or_create(
                name=company_name,
                entity_type=Entity.TYPE_COMPANY,
                defaults={'description': profile.get('company_description', '')}
            )
            entities.append(company)
        
        # Extract job title
        job_title = profile.get('job_title')
        if job_title:
            title, _ = Entity.objects.get_or_create(
                name=job_title,
                entity_type=Entity.TYPE_JOB_TITLE,
            )
            entities.append(title)
        
        # Extract skills
        skills = profile.get('skills', [])
        for skill in skills:
            skill_entity, _ = Entity.objects.get_or_create(
                name=skill,
                entity_type=Entity.TYPE_SKILL,
            )
            entities.append(skill_entity)
        
        # Extract industries
        industries = profile.get('industries', [])
        for industry in industries:
            industry_entity, _ = Entity.objects.get_or_create(
                name=industry,
                entity_type=Entity.TYPE_INDUSTRY,
            )
            entities.append(industry_entity)
        
        return entities
    
    @transaction.atomic
    def build_relationships(self, lead_entity: Entity, profile_entities: List[Entity], campaign_id: str):
        """Build relationships for a lead."""
        
        # Works at relationships
        for entity in profile_entities:
            if entity.entity_type == Entity.TYPE_COMPANY:
                Relationship.objects.get_or_create(
                    source=lead_entity,
                    relationship_type=Relationship.TYPE_WORKS_AT,
                    target=entity,
                    defaults={'strength': 1.0, 'confidence': 0.95, 'weight': 1.0}
                )
            
            elif entity.entity_type == Entity.TYPE_JOB_TITLE:
                Relationship.objects.get_or_create(
                    source=lead_entity,
                    relationship_type=Relationship.TYPE_HAS_TITLE,
                    target=entity,
                    defaults={'strength': 1.0, 'confidence': 0.9, 'weight': 1.0}
                )
            
            elif entity.entity_type == Entity.TYPE_SKILL:
                Relationship.objects.get_or_create(
                    source=lead_entity,
                    relationship_type=Relationship.TYPE_HAS_SKILL,
                    target=entity,
                    defaults={'strength': 0.8, 'confidence': 0.85, 'weight': 0.8}
                )
    
    def find_similar_leads(self, lead_entity: Entity, limit: int = 10) -> List[Entity]:
        """Find leads with similar profile characteristics."""
        cypher = """
        MATCH (l1:Lead {name: $lead_name})-[:HAS_SKILL]->(skill:Skill),
              (l2:Lead)-[:HAS_SKILL]->(skill)
        WHERE l1 <> l2
        WITH l2, count(skill) as skill_count
        MATCH (l2)-[:WORKS_AT]->(company:Company)
        RETURN l2, skill_count, company.name as company
        ORDER BY skill_count DESC
        LIMIT $limit
        """
        
        # Use Django's raw query if using Neo4j, or implement equivalent
        # For simplicity, return queryset-based approach
        pass
    
    def calculate_leads_for_company(self, company_entity: Entity) -> List[Dict]:
        """Calculate which leads would be good for a specific company."""
        cypher = """
        MATCH (c:Company {name: $company_name})<-[:WORKS_AT]-(l:Lead)
        WHERE NOT EXISTS((l)-[:QUALIFIED_FOR]->(c))
        RETURN l, count(*) as score
        ORDER BY score DESC
        """
    
    def calculate_campaign_insights(self, campaign_id: str) -> CampaignKnowledgeStats:
        """Calculate knowledge insights for a campaign."""
        # Get all entities and relationships for campaign
        from openoutreach.crm.models import Deal
        
        deals = Deal.objects.filter(campaign_id=campaign_id)
        
        entity_counts = {}
        relationship_counts = {}
        
        for deal in deals:
            lead = deal.lead
            
            # Count entities
            for entity_type in [Entity.TYPE_JOB_TITLE, Entity.TYPE_INDUSTRY, Entity.TYPE_SKILL]:
                count = Entity.objects.filter(
                    id__in=lead.entities.filter(entity_type=entity_type).values_list('id', flat=True)
                ).count()
                entity_counts[entity_type] = entity_counts.get(entity_type, 0) + count
            
            # Count relationships
            for rel_type in [Relationship.TYPE_WORKS_AT, Relationship.TYPE_HAS_SKILL]:
                count = Relationship.objects.filter(
                    source__id__in=lead.entities.values_list('id', flat=True),
                    relationship_type=rel_type
                ).count()
                relationship_counts[rel_type] = relationship_counts.get(rel_type, 0) + count
        
        # Calculate top industries
        top_industries = Entity.objects.filter(
            id__in=Relationship.objects.filter(
                source__id__in=Deal.objects.filter(campaign_id=campaign_id)
                .values_list('lead__entities', flat=True)
            ).values_list('target', flat=True),
            entity_type=Entity.TYPE_INDUSTRY
        ).annotate(occur=Count('id')).order_by('-occur')[:10]
        
        return CampaignKnowledgeStats.objects.create(
            campaign_id=campaign_id,
            entity_counts=entity_counts,
            relationship_counts=relationship_counts,
            top_industries=[i.name for i in top_industries],
            calculated_at=datetime.now(),
        )
```

### 3. LLM-Augmented Analysis (`linkedin/agents/knowledge_graph.py`)

```python
import jinja2
from pydantic import BaseModel
from pydantic_ai import Agent

from openoutreach.core.llm import get_llm_model, run_agent_sync


class LeadAnalysisOutput(BaseModel):
    """Output from lead analysis."""
    
    inferred_pain_points: list[str]
    inferred_goals: list[str]
    inferred_tech_stack: list[str]
    inferred_industry_challenges: list[str]
    engagement_signals: list[dict]
    personalization_suggestions: list[str]


def analyze_lead_with_graph(context: Dict) -> LeadAnalysisOutput:
    """Use LLM to analyze lead and update knowledge graph."""
    from openoutreach.core.llm import get_llm_model, run_agent_sync
    from openoutreach.core.conf import PROMPTS_DIR
    
    # Render prompt with context
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(PROMPTS_DIR)))
    template = env.get_template("analyze_lead.j2")
    prompt = template.render(**context)
    
    # Call LLM
    agent = Agent(
        get_llm_model(),
        output_type=LeadAnalysisOutput,
        model_settings={"temperature": 0.7, "timeout": 60},
    )
    
    result = run_agent_sync(agent.run(prompt))
    
    return result.output or LeadAnalysisOutput(
        inferred_pain_points=[],
        inferred_goals=[],
        inferred_tech_stack=[],
        inferred_industry_challenges=[],
        engagement_signals=[],
        personalization_suggestions=[],
    )


def enrich_lead_graph(lead_entity: Entity, profile: Dict, campaign_id: str):
    """Enrich a lead's graph representation using LLM analysis."""
    from linkedoutreach.linkedin.models import Entity, Relationship
    
    # Build context
    context = {
        'profile': profile,
        'campaign_objective': profile.get('campaign_objective'),
        'product_docs': profile.get('product_docs'),
    }
    
    # Run LLM analysis
    analysis = analyze_lead_with_graph(context)
    
    # Store inferred entities and relations
    for pain_point in analysis.inferred_pain_points:
        entity, _ = Entity.objects.get_or_create(
            name=pain_point,
            entity_type=Entity.TYPE_PAIN_POINT,
        )
        Relationship.objects.get_or_create(
            source=lead_entity,
            relationship_type=Relationship.TYPE_HAS_PAIN_POINT,
            target=entity,
            defaults={'strength': analysis.inferred_goals.index(pain_point) / len(analysis.inferred_goals),
                     'confidence': 0.7}
        )
    
    for goal in analysis.inferred_goals:
        entity, _ = Entity.objects.get_or_create(
            name=goal,
            entity_type=Entity.TYPE_GOAL,
        )
        Relationship.objects.get_or_create(
            source=lead_entity,
            relationship_type=Relationship.TYPE_HAS_GOAL,
            target=entity,
            defaults={'strength': 1.0, 'confidence': 0.8}
        )
```

### 4. Graph-Based Personalization Engine

```python
def get_personalization_context(lead_entity: Entity) -> Dict:
    """Get personalization context from knowledge graph."""
    
    # Get company context
    company = Entity.objects.filter(
        id__in=Relationship.objects.filter(
            source=lead_entity,
            relationship_type=Relationship.TYPE_WORKS_AT
        ).values_list('target', flat=True)
    ).first()
    
    # Get industry context
    industry = Entity.objects.filter(
        id__in=Relationship.objects.filter(
            source=lead_entity,
            relationship_type=Relationship.TYPE_INDUSTRY_WORKS
        ).values_list('target', flat=True)
    ).first()
    
    # Get pain points
    pain_points = Entity.objects.filter(
        id__in=Relationship.objects.filter(
            source=lead_entity,
            relationship_type=Relationship.TYPE_HAS_PAIN_POINT
        ).values_list('target', flat=True)
    ).order_by('-relevance_score')[:3]
    
    # Get goals
    goals = Entity.objects.filter(
        id__in=Relationship.objects.filter(
            source=lead_entity,
            relationship_type=Relationship.TYPE_HAS_GOAL
        ).values_list('target', flat=True)
    ).order_by('-relevance_score')[:3]
    
    return {
        'company': company.name if company else '',
        'industry': industry.name if industry else '',
        'pain_points': [p.name for p in pain_points],
        'goals': [g.name for g in goals],
    }


def generate_hyper_personalized_message(lead_entity: Entity, campaign_context: Dict) -> str:
    """Generate a message personalized using graph context."""
    from openoutreach.core.llm import get_llm_model, run_agent_sync
    
    # Get graph context
    context = get_personalization_context(lead_entity)
    
    # Add campaign context
    context.update(campaign_context)
    
    # Render prompt
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(PROMPTS_DIR)))
    template = env.get_template("personalized_message.j2")
    prompt = template.render(**context)
    
    # Call LLM
    agent = Agent(get_llm_model(), model_settings={"temperature": 0.8, "timeout": 30})
    result = run_agent_sync(agent.run(prompt))
    
    return result.output or ""
```

### 5. Integration with Campaign Setup

Update onboarding to initialize knowledge graph:

```python
# linkedin/setup/knowledge_graph.py

def initialize_campaign_graph(campaign):
    """Initialize knowledge graph for a new campaign."""
    from linkedoutreach.linkedin.services.knowledge_graph import KnowledgeGraphService
    
    service = KnowledgeGraphService()
    
    # Process existing seed leads
    for lead in campaign.seeds.all():
        profile = lead.get_profile()
        
        # Extract entities
        entities = service.extract_entities_from_profile(profile, campaign.id)
        
        # Build relationships
        for entity in entities:
            if entity.entity_type == Entity.TYPE_JOB_TITLE:
                Relationship.objects.get_or_create(
                    source=lead.entity,
                    relationship_type=Relationship.TYPE_HAS_TITLE,
                    target=entity,
                )
            elif entity.entity_type == Entity.TYPE_COMPANY:
                Relationship.objects.get_or_create(
                    source=lead.entity,
                    relationship_type=Relationship.TYPE_WORKS_AT,
                    target=entity,
                )
    
    # Calculate initial insights
    service.calculate_campaign_insights(campaign.id)
```

### 6. Frontend Visualization

```typescript
interface KnowledgeGraph {
  nodes: GraphNode[];
  links: GraphLink[];
}

interface GraphNode {
  id: string;
  label: string;
  type: string;
  size: number;
  color: string;
  count: number;
}

interface GraphLink {
  source: string;
  target: string;
  type: string;
  strength: number;
}

export function KnowledgeGraphVisualization({ campaignId }: { campaignId: string }) {
  const [graph, setGraph] = useState<KnowledgeGraph | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`/api/knowledge-graph/${campaignId}/`)
      .then(r => r.json())
      .then(setGraph)
      .finally(() => setLoading(false));
  }, [campaignId]);

  if (loading) return <LoadingSpinner />;

  return (
    <div className="space-y-6">
      <div className="flex gap-4">
        <select className="p-2 border rounded">
          <option>Industries</option>
          <option>Job Titles</option>
          <option>Skills</option>
          <option>Pain Points</option>
        </select>
      </div>
      
      <div className="bg-white rounded-lg border p-4">
        <h3 className="font-semibold mb-4">Top Industries</h3>
        <div className="space-y-2">
          {graph?.nodes.filter(n => n.type === 'industry').slice(0, 10).map(node => (
            <div key={node.id} className="flex items-center gap-2">
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div 
                  className="bg-blue-600 h-2 rounded-full" 
                  style={{ width: `${(node.count / 100) * 100}%` }}
                />
              </div>
              <span className="text-sm">{node.label} ({node.count})</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
```

---

## Migration Plan

1. Create Entity and Relationship models
2. Run migration
3. Build initial extraction service
4. Create LLM analysis integration
5. Implement personalization engine
6. Build frontend visualization

---

## Benefits

| Feature | Before | After |
|---------|--------|-------|
| Context | Flat profile fields | Rich graph connections |
| Learning | Stale per-campaign | Persistent across campaigns |
| Personalization | Static templates | Dynamic, context-aware |
| Insights | Count metrics only | Relationship-based patterns |
| Scalability | One campaign at a time | Cross-campaign leverage |

The knowledge graph enables true learning from outreach campaigns, turning each interaction into persistent knowledge that improves future campaigns.