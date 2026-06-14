# Autonomous Campaign A/B Testing Framework

A self-optimizing system that automatically runs A/B tests on messages, connection requests, and follow-up sequences. The AI agent learns from outcomes in real-time and dynamically adjusts messaging strategy using reinforcement learning — continuously improving conversion rates without manual intervention.

---

## Overview

The system creates a closed-loop optimization engine that:
1. **Generates multiple message variants** for each outreach sequence
2. **Distributes leads across variants** using intelligent allocation
3. **Tracks performance metrics** per variant (acceptance, response, conversion)
4. **Autonomously shifts traffic** to better-performing variants
5. **Creates new variants** using LLM-generated variations when performance plateaus

This is a fully autonomous system that operates alongside the existing campaign infrastructure.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         A/B Testing Engine                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌────────────┐     ┌──────────────┐     ┌───────────────────────┐   │
│  │ Test Store │────▶│ Decision     │────▶│ Traffic Router      │   │
│  └────────────┘     │ Engine       │     └───────────────────────┘   │
│        ▲            └──────────────┘           │                      │
│        │                                       │ tracks               │
│        │ performance                           │ metrics              │
│        │ data                                  ▼                      │
│  ┌────────────┐                           ┌─────────────┐           │
│  │ LLM        │◀──────────────────────────│ Performance │           │
│  │ Variant    │     feedback loop         │ Dashboard   │           │
│  │ Generator  │     (RL optimization)     └─────────────┘           │
│  └────────────┘                                                       │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Campaign Infrastructure                           │
│                                                                       │
│  Leads → Qualification → [A/BVariant] → follow-up → Outcome         │
│                                       ↑    │                         │
│                                       └────┘                          │
│                              (performance tracking)                   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Implementation Plan

### 1. Core Models (`linkedin/models/ab_test.py`)

```python
from django.db import models
from django.utils import timezone
import json


class ABTest(models.Model):
    """An A/B test configuration for a campaign."""
    
    CAMPAIGN_SCOPE = 'campaign'
    INDIVIDUAL_SCOPE = 'individual'
    
    SCOPES = [
        (CAMPAIGN_SCOPE, 'Campaign-wide'),  # All leads in campaign
        (INDIVIDUAL_SCOPE, 'Per-lead'),     # Each lead gets unique test
    ]
    
    campaign = models.ForeignKey('Campaign', on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    scope = models.CharField(max_length=20, choices=SCOPES, default=CAMPAIGN_SCOPE)
    
    # Variant allocation (weights sum to 1.0)
    variants = models.JSONField(default=list)  # List of {name, weight, message_template}
    
    # Configuration
    min_impressions = models.PositiveIntegerField(default=5)  # Min views before stats
    exploration_rate = models.FloatField(default=0.1)  # 10% exploration (multi-armed bandit)
    update_interval_hours = models.PositiveIntegerField(default=24)
    
    # Status
    active = models.BooleanField(default=True)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Metrics (aggregated)
    total_impressions = models.PositiveIntegerField(default=0)
    total_conversions = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['-started_at']
    
    def __str__(self):
        return f"{self.name} ({self.campaign.name})"


class A/BVariant(models.Model):
    """Individual variant within an A/B test."""
    
    test = models.ForeignKey(ABTest, on_delete=models.CASCADE, related_name='variants')
    name = models.CharField(max_length=100)
    
    # Message template with Jinja2 variables
    message_template = models.TextField()
    
    # Allocation weight
    weight = models.FloatField(default=1.0)
    
    # Metrics
    impressions = models.PositiveIntegerField(default=0)
    responses = models.PositiveIntegerField(default=0)
    conversions = models.PositiveIntegerField(default=0)
    
    # Statistics
    last_impression_at = models.DateTimeField(null=True, blank=True)
    last_response_at = models.DateTimeField(null=True, blank=True)
    last_conversion_at = models.DateTimeField(null=True, blank=True)
    
    # Calculated metrics
    response_rate = models.FloatField(default=0.0)
    conversion_rate = models.FloatField(default=0.0)
    
    class Meta:
        unique_together = ('test', 'name')
    
    def __str__(self):
        return f"{self.test.name}: {self.name}"
    
    def update_metrics(self, action: str, value: int = 1):
        """Update metrics for an action."""
        if action == 'impression':
            self.impressions += value
            self.last_impression_at = timezone.now()
        elif action == 'response':
            self.responses += value
            self.last_response_at = timezone.now()
        elif action == 'conversion':
            self.conversions += value
            self.last_conversion_at = timezone.now()
        
        self.save()
        self._recalculate_rates()
        self.test._recalculate_aggregates()
    
    def _recalculate_rates(self):
        """Recalculate response and conversion rates."""
        if self.impressions > 0:
            self.response_rate = self.responses / self.impressions
            self.conversion_rate = self.conversions / self.impressions
        else:
            self.response_rate = 0.0
            self.conversion_rate = 0.0
        self.save(update_fields=['response_rate', 'conversion_rate'])


class A/BTestAssignment(models.Model):
    """Tracks which variant was assigned to a deal."""
    
    deal = models.ForeignKey('Deal', on_delete=models.CASCADE)
    test = models.ForeignKey(ABTest, on_delete=models.CASCADE)
    variant = models.ForeignKey(ABVariant, on_delete=models.CASCADE)
    
    assigned_at = models.DateTimeField(auto_now_add=True)
    impression_count = models.PositiveIntegerField(default=0)
    
    class Meta:
        unique_together = ('deal', 'test')
    
    def record_impression(self):
        """Record that the variant was shown."""
        self.impression_count += 1
        self.save()
        self.variant.update_metrics('impression')


class ABTestResult(models.Model):
    """Historical result record for A/B tests."""
    
    test = models.ForeignKey(ABTest, on_delete=models.CASCADE)
    variant = models.ForeignKey(ABVariant, on_delete=models.CASCADE)
    
    impressions = models.PositiveIntegerField()
    responses = models.PositiveIntegerField()
    conversions = models.PositiveIntegerField()
    
    response_rate = models.FloatField()
    conversion_rate = models.FloatField()
    
    recorded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name_plural = "AB test results"
        ordering = ['-recorded_at']
```

### 2. Multi-Armed Bandit Decision Engine (`linkedin/agents/ab_test.py`)

```python
import random
import math
from typing import Optional
from datetime import datetime, timedelta

from pydantic import BaseModel, Field


class VariantStats(BaseModel):
    """Statistics for a single variant."""
    name: str
    impressions: int
    responses: int
    conversions: int
    response_rate: float
    conversion_rate: float


class ABTestAgent:
    """
    Multi-armed bandit decision engine for A/B testing.
    
    Supports:
    - UCB1 (Upper Confidence Bound)
    - Thompson Sampling (Bayesian)
    - Epsilon-Greedy with decay
    - Dynamic allocation based on performance
    """
    
    def __init__(self, test, exploration_rate: float = 0.1):
        self.test = test
        self.variants = list(test.variants.all())
        self.exploration_rate = exploration_rate
        
        #_ucb1 = C * sqrt(ln(n_total) / n_variant)
        self.ucb_constant = 1.0  # Exploration bonus weight
    
    def get_variant_stats(self) -> list[VariantStats]:
        """Get current statistics for all variants."""
        stats = []
        for v in self.variants:
            stats.append(VariantStats(
                name=v.name,
                impressions=v.impressions,
                responses=v.responses,
                conversions=v.conversions,
                response_rate=v.response_rate,
                conversion_rate=v.conversion_rate,
            ))
        return stats
    
    def select_variant_ucb1(self) -> str:
        """
        Select variant using UCB1 algorithm.
        
        UCB1 = average_reward + C * sqrt(ln(total_visits) / variant_visits)
        
        This balances exploration (trying less-tested variants) 
        with exploitation ( favouring high-performing variants).
        """
        total_visits = sum(v.impressions for v in self.variants)
        
        if total_visits == 0 or any(v.impressions == 0 for v in self.variants):
            # Initial exploration phase: try each variant at least once
            for v in self.variants:
                if v.impressions == 0:
                    return v.name
            
            # If all have been tried, proceed normally
            total_visits = sum(v.impressions for v in self.variants)
        
        scores = []
        for v in self.variants:
            avg_reward = v.conversions / v.impressions if v.impressions > 0 else 0
            exploration_bonus = self.ucb_constant * math.sqrt(math.log(total_visits + 1) / (v.impressions + 1))
            score = avg_reward + exploration_bonus
            scores.append((v.name, score))
        
        return max(scores, key=lambda x: x[1])[0]
    
    def select_variant_thompson(self) -> str:
        """
        Select variant using Thompson Sampling (Bayesian).
        
        Samples from Beta distributions of conversion rates and
        picks the variant with highest sampled value.
        """
        samples = []
        for v in self.variants:
            # Beta(a, b) where a = successes + 1, b = failures + 1
            a = v.conversions + 1
            b = v.impressions - v.conversions + 1
            sample = random.betavariate(a, b)
            samples.append((v.name, sample))
        
        return max(samples, key=lambda x: x[1])[0]
    
    def select_variant_eps_greedy(self) -> str:
        """
        Select variant using epsilon-greedy with exploration decay.
        
        With probability epsilon: explore (random variant)
        With probability 1-epsilon: exploit (best performing variant)
        """
        if random.random() < self.exploration_rate:
            # Explore: random variant
            return random.choice([v.name for v in self.variants])
        else:
            # Exploit: highest conversion rate
            best = max(self.variants, key=lambda v: v.conversion_rate or 0)
            return best.name
    
    def decay_exploration(self, decay_rate: float = 0.99, min_rate: float = 0.01):
        """Gradually reduce exploration rate over time."""
        self.exploration_rate = max(min_rate, self.exploration_rate * decay_rate)


def select_variant_for_deal(deal, test_type: str = 'connnect') -> str:
    """Select the best variant for a given deal."""
    from linkedin.models import ABTest
    
    # Find active tests for this campaign
    tests = ABTest.objects.filter(
        campaign=deal.campaign,
        active=True,
    )
    
    if not tests.exists():
        return 'control'  # Default variant
    
    # For now, select the best test and use it
    # In production, you might combine results from multiple tests
    
    test = tests.first()
    agent = ABTestAgent(test)
    
    # Use Thompson sampling for best results with sparse data
    selected = agent.select_variant_thompson()
    
    # Record assignment
    ABTestAssignment.objects.create(
        deal=deal,
        test=test,
        variant=test.variants.get(name=selected),
    )
    
    return selected
```

### 3. Prompt Template for LLM Variant Generation (`generate_ab_variant.j2`)

```
Generate a new A/B test variant for LinkedIn outreach.

## CURRENT TEST
Campaign: {{ campaign.name }}
Name: {{ test.name }}
Objective: {{ campaign.campaign_objective }}

## CURRENT VARIANTS
{% for variant in variants %}
### {{ variant.name }}
Message: {{ variant.message_template | truncatechars:200 }}
Responses: {{ variant.responses }} / {{ variant.impressions }} ({{ variant.response_rate * 100|format_int }}%)
Conversions: {{ variant.conversions }} ({{ variant.conversion_rate * 100|format_int }}%)

{% endfor %}

## PERFORMANCE SUMMARY
Best performing: {{ best_variant.name }} ({{ best_variant.conversion_rate * 100 }}% conversion)

## INSTRUCTIONS
Analyze the current variants and create a NEW variant that:
1. Addresses weaknesses in current performance
2. Uses different psychological triggers if underperforming
3. Maintains alignment with campaign objective
4. Provides clear value proposition

Generate a NEW message template using these Jinja2 variables:
- {{ first_name }} - Lead's first name
- {{ company }} - Lead's company
- {{ headline }} - Lead's headline
- {{ product_name }} - Our product name

Respond with JSON:
{
  "name": "variant_{{ next_number }}",
  "message_template": "..."
}
```

### 4. Integration with Follow-Up Agent

Update `linkedin/agents/follow_up.py` to use A/B test variants:

```python
def run_follow_up_agent(deal, session) -> FollowUpDecision:
    """Run follow-up agent with A/B test support."""
    from linkedin.models import ABTestAssignment
    
    # Get AB test assignment for this lead
    assignment = ABTestAssignment.objects.filter(
        deal=deal,
        test__active=True,
    ).select_related('variant').first()
    
    variant = assignment.variant if assignment else None
    
    # ... existing context building ...
    
    # Add variant info to prompt if available
    context['ab_test_variant'] = variant.name if variant else None
    context['ab_test_message'] = variant.message_template if variant else None
    
    # ... rest of agent execution ...


def handle_follow_up(task, session, qualifiers):
    """Handle follow-up task with A/B test recording."""
    # ... existing code ...
    
    # Send message (variant is already selected)
    agent = Agent(get_llm_model(), ...)
    result = run_agent_sync(agent.run(...))
    
    if result.output.action == 'send_message':
        # Send the message
        sent = send_raw_message(session, deal, result.output.message)
        
        # Record impression and response
        if sent:
            # Get or create assignment
            assignment, _ = ABTestAssignment.objects.get_or_create(
                deal=deal,
                test=test,
                defaults={'variant': variant},
            )
            assignment.record_impression()
            variant.update_metrics('response')
    
    # ... rest of handler ...
```

### 5. Automatic Test Creation and Optimization

```python
def optimize_campaign_tests(campaign_id):
    """Analyze current tests and create new variants if needed."""
    from linkedin.models import ABTest, ABVariant
    
    campaigns = ABTest.objects.filter(campaign_id=campaign_id, active=True)
    
    for test in campaigns:
        # Check if any test has plateaued
        variants = test.variants.all()
        best = max(variants, key=lambda v: v.conversion_rate or 0)
        
        # If best has significantly outperformed others for 48+ hours
        time_threshold = timezone.now() - timedelta(hours=48)
        
        if best.last_conversion_at and best.last_conversion_at < time_threshold:
            # Check if test has enough data
            total_conversions = sum(v.conversions for v in variants)
            
            if total_conversions >= 20:
                # Create new variant using LLM
                new_variant = _generate_new_variant_via_llm(test)
                
                # Update test with new variant
                ABVariant.objects.create(
                    test=test,
                    name=f"variant_{len(variants) + 1}",
                    message_template=new_variant['message_template'],
                    weight=1.0,
                )
                
                # Reset exploration rate
                test.exploration_rate = 0.2
                test.save()
                
                logger.info(f"Created new variant for test: {test.name}")


def _generate_new_variant_via_llm(test):
    """Use LLM to generate a new variant based on current performance."""
    from openoutreach.core.llm import get_llm_model, run_agent_sync
    from pydantic import BaseModel
    
    class VariantCreationOutput(BaseModel):
        name: str
        message_template: str
    
    variants = list(test.variants.all())
    best = max(variants, key=lambda v: v.conversion_rate or 0)
    
    prompt = f"""
    Current test: {test.name}
    Best variant: {best.name} ({best.conversion_rate * 100:.1f}% conversion)
    
    Generate a NEW variant that:
    1. Improves on the best variant
    2. Uses different psychological triggers
    3. Maintains campaign objective
    
    Campaign objective: {test.campaign.campaign_objective}
    """
    
    agent = Agent(get_llm_model(), output_type=VariantCreationOutput)
    result = run_agent_sync(agent.run(prompt))
    
    return result.output
```

### 6. Frontend Dashboard (`frontend/src/components/ab-test/Dashboard.tsx`)

```typescript
interface ABTestVariant {
  name: string;
  impressions: number;
  responses: number;
  conversions: number;
  responseRate: number;
  conversionRate: number;
}

interface ABTestResult {
  test: {
    id: string;
    name: string;
    active: boolean;
  };
  variants: ABTestVariant[];
  bestVariant: ABTestVariant;
  improvementPercent: number;
}

export function ABTestDashboard() {
  const [tests, setTests] = useState<ABTestResult[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchAbTests().then(setTests).finally(() => setLoading(false));
  }, []);

  if (loading) return <LoadingSpinner />;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold">Autonomous A/B Testing</h2>
        <button className="btn-primary">Start New Test</button>
      </div>

      {tests.map(test => (
        <ABTestCard key={test.test.id} test={test} />
      ))}
    </div>
  );
}

function ABTestCard({ test }: { test: ABTestResult }) {
  return (
    <div className="bg-white rounded-lg border p-6">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="font-semibold">{test.test.name}</h3>
          <span className={`text-xs px-2 py-1 rounded-full ${
            test.test.active ? 'bg-green-100 text-green-800' : 'bg-gray-100'
          }`}>
            {test.test.active ? 'Active' : 'Paused'}
          </span>
        </div>
        <div className="text-right">
          <div className="text-sm text-gray-500">Best Conversion</div>
          <div className={`text-lg font-bold ${test.bestVariant.conversionRate >= 0.1 ? 'text-green-600' : ''}`}>
            {test.bestVariant.conversionRate * 100:.1f}%
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        {test.variants.map(variant => (
          <VariantMetric key={variant.name} variant={variant} isBest={variant === test.bestVariant} />
        ))}
      </div>
    </div>
  );
}
```

---

## Migration Plan

1. Create database migration for new models
2. Create initial A/B test for first campaign
3. Update follow-up agent to use variants
4. Build frontend dashboard
5. Implement automatic variant generation

---

## Benefits

| Feature | Current State | With AB Testing |
|---------|---------------|-----------------|
| Testing | Manual A/B (manual code changes) | Fully automatic |
| Optimization | Fixed messages | RL-optimized |
| Variant Generation | Manual copy/paste | LLM-generated |
| Performance | Static | Continuously improving |

---

## Expected Impact

A well-tuned A/B testing system can:
- Increase connection acceptance rates by 15-25%
- Improve response rates by 20-35%  
- Boost conversion rates by 30-50%
- Reduce average message count needed per conversion

The autonomous nature means these improvements happen continuously without manual intervention.