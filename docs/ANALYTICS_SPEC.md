# Analytics & Data Spec

Complete reference for every number, chart, and table shown across the platform.
For each component: what it displays, the exact calculation, and which backend query produces it.

---

## Collections Referenced

| Collection | Key Fields |
|---|---|
| `campaigns` | `_id`, `user_id`, `team_member_ids`, `status`, `is_paused`, `name` |
| `deals` | `_id`, `lead_id`, `campaign_id`, `state` (DealState), `outcome`, `creation_date` |
| `leads` | `_id`, `user_id`, `public_identifier`, `full_name`, `headline`, `disqualified`, `cached_profile`, `api_email`, `contact_info`, `connection_degree` |
| `action_logs` | `_id`, `campaign_id`, `linkedin_profile_id`, `action_type`, `status`, `created_at`, `details` |
| `chat_messages` | `_id`, `deal_id`, `is_outgoing`, `content`, `creation_date`, `sender_name` |
| `tasks` | `_id`, `payload.campaign_id`, `task_type`, `status`, `scheduled_at` |

### DealState values

`Discovered` → `Qualified` → `ReadyToConnect` → `Pending` → `Connected` → `Completed` / `Failed` / `NoEmail`

---

## 1. Dashboard (`/dashboard`)

**Endpoints called:** `GET /api/analytics/overview?period=30d`, `GET /api/campaigns?status=active`, `GET /api/analytics/activity`

### 1.1 Stat Cards (top row, 4 cards)

| Card | Value | Formula |
|---|---|---|
| Active Campaigns | `campaigns.length` | Count of campaign docs returned by `GET /api/campaigns` filtered to `status=active`. Frontend count, not a DB aggregate. |
| Total Leads | `totals.leads` | `leads.count_documents({user_id})` - all lead docs owned by user regardless of state or campaign. |
| Connected | `totals.connected` | `deals.count_documents({campaign_id: {$in: user_campaign_ids}, state: "Connected"})` - all CONNECTED deals across all campaigns, not time-filtered. |
| Messages Sent | `stats.messagesSent` | `action_logs.count_documents({campaign_id: {$in: …}, action_type: "follow_up", status: {$nin: ["failed","error"]}, created_at: {$gte: now-30d}})` |

Sub-text on Connected card: `"X% accept rate (30d)"` where `X = (stats.connectionsAccepted / stats.connectionsSent) * 100`. Computed on frontend. Shows `—` when `connectionsSent = 0`.

Sub-text on Messages Sent card: `"Reply rate Y%"` where `Y = (stats.messagesReplied / stats.messagesSent) * 100`. Computed on frontend.

### 1.2 Quick Stats Panel (6 items)

| Label | Value | Formula |
|---|---|---|
| Accept Rate | `X%` or `—` | Frontend: `(stats.connectionsAccepted / stats.connectionsSent) * 100`. Shows `—` when denominator is 0. |
| Reply Rate | `Y%` or `—` | Frontend: `(stats.messagesReplied / stats.messagesSent) * 100`. |
| Connections Accepted | count | `stats.connectionsAccepted` - 30-day window. Sub: `"X% accept rate"`. |
| Active Campaigns | count | `campaigns.length` (fetched list of active campaigns). |
| Total Leads | count | `totals.leads` from overview response. |
| Connections Sent | count | `stats.connectionsSent` - 30-day action log count. |

### 1.3 30-Day Metrics Row (4 values)

| Label | Value |
|---|---|
| Connections Sent | `stats.connectionsSent` |
| Accept Rate | Frontend: `stats.connectionsAccepted / stats.connectionsSent * 100` |
| Reply Rate | Frontend: `stats.messagesReplied / stats.messagesSent * 100` |
| Connections Accepted | `stats.connectionsAccepted` - raw count (time-consistent with other 30d columns) |

### 1.4 Recent Activity Feed

- Source: `GET /api/analytics/activity?limit=10`
- Backend: `action_logs.find({campaign_id: {$in: user_campaign_ids}}).sort(created_at, -1).limit(10)`
- Each row shows: action type label, lead name (from `details.lead_name` or `details.public_identifier` → leads lookup), campaign name, timestamp (relative), status badge (success/pending/failed).
- Types rendered: `connect`, `follow_up`, `check_pending`, `lead_discovered`, `lead_qualified`, `lead_disqualified`, `campaign_started`, `campaign_paused`.

---

## 2. Analytics Overview (`/analytics`)

**Endpoint:** `GET /api/analytics/overview?campaign_id={id}&period={7d|30d|90d}`

All time-filtered metrics use `since = now() - period_days`. Pipeline counts (DISCOVERED/QUALIFIED/etc.) are **not** time-filtered - they reflect current state.

### 2.1 Progress Cards (top row, 4 cards)

| Card | Value | Backend field | Formula |
|---|---|---|---|
| Connection Accept Rate | `X%` | `stats.connectionAcceptRate` | `round((connections_accepted / connections_sent) * 100, 2)`. Zero-safe. |
| Response Rate | `Y%` | `stats.responseRate` | `round((distinct_deals_with_reply / distinct_deals_messaged) * 100, 2)`. Zero-safe. Both are distinct deal counts. |
| Conversion Rate | `Z%` | `stats.conversionRate` | `round((conversions / connections_accepted) * 100, 2)`. Zero-safe. |
| Total Leads | count | `totals.leads` | When `campaign_id` param is set: `deals.count_documents({campaign_id: {$in: campaign_ids}})`. Without filter: `leads.count_documents({user_id})` - all user leads. |

**connections_accepted** excludes 1st-degree leads. Pipeline:
```
deals.aggregate([
  {$match: {campaign_id, state: "Connected"}},
  {$lookup: {from:"leads", localField:"lead_id", foreignField:"_id", as:"lead"}},
  {$unwind: {path:"$lead", preserveNullAndEmptyArrays:true}},
  {$match: {$or: [
    {lead.connection_degree: {$exists:false}},
    {lead.connection_degree: null},
    {lead.connection_degree: {$ne: 1}}
  ]}},
  {$count: "total"}
])
```

**messages_replied** = distinct deals with ≥1 inbound message in the period:
```
chat_messages.aggregate([
  {$match: {is_outgoing: false, creation_date: {$gte: since}}},
  {$lookup: {from:"deals", localField:"deal_id", foreignField:"_id", as:"deal"}},
  {$unwind: "$deal"},
  {$match: {"deal.campaign_id": {$in: campaign_ids}}},
  {$group: {_id: "$deal_id"}},
  {$count: "total"}
])
```

**conversions** = `deals.count_documents({campaign_id, state:"Completed", creation_date:{$gte:since}})` - time-filtered completions.

### 2.2 Lead Pipeline Donut Chart

7 segments. Each = `deals.count_documents({campaign_id:{$in:…}, state:X})` - NOT time-filtered.

| Segment | State value | Color |
|---|---|---|
| Qualified | `Qualified` | Blue |
| Ready to Connect | `ReadyToConnect` | Amber |
| Pending | `Pending` | Orange |
| Connected | `Connected` | Green |
| Completed | `Completed` | Purple |
| Failed | `Failed` | Red |
| No Email | `NoEmail` | Gray |

Note: `Discovered` state not shown in donut (leads start here, not shown in active pipeline).

### 2.3 Conversion Rates Bar Chart

3 horizontal bars (capped at 100%):
- Connection Accept Rate = `stats.connectionAcceptRate`
- Response Rate = `stats.responseRate`
- Conversion Rate = `stats.conversionRate`

### 2.4 Per-Campaign Metrics Table (when "All Campaigns" selected)

One row per campaign. Columns:

| Column | Source | Formula |
|---|---|---|
| Campaign Name | `campaign.name` | Direct |
| Status | `campaign.status` | Badge: active=green, paused=amber, draft=gray |
| Total Leads | `stats.totalLeads` | `deals.count_documents({campaign_id})` - all deals for campaign |
| In-Funnel Leads | `stats.activeLeads` | `qualified + ready_to_connect + pending + connected` deal counts - leads that have entered the funnel but not yet completed/failed |
| Accept Rate | `stats.connectionAcceptRate` | Same formula as 2.1, scoped to campaign |
| Response Rate | `stats.responseRate` | Same formula as 2.1, scoped to campaign |
| Conversion Rate | `stats.conversionRate` | Same formula as 2.1, scoped to campaign |

---

## 3. Leads Page (`/leads`)

**Endpoint:** `GET /api/leads?state={filter}&search={term}&disqualified={bool}&limit=50&offset={n}`

### 3.1 Leads Table

Source: deals joined to leads. One row per deal (a lead appearing in N campaigns = N rows).

Columns:

| Column | Source field | Notes |
|---|---|---|
| Name | `lead.full_name` or parsed from `cached_profile.firstName + lastName` | |
| Title | `lead.headline` or `cached_profile.profile.headline` | |
| Company | Parsed from headline: text after first `" at "` | |
| State badge | `deal.state` | Color-coded by DealState |
| Outcome | `deal.outcome` | Shown when present: `converted`, `not_interested`, `wrong_fit`, etc. |
| Campaign | `campaign_names[deal.campaign_id]` | Batch-fetched campaign name lookup |
| Email | `lead.api_email` (enrichment waterfall) or `lead.contact_info.email` (LinkedIn overlay) | Prefers api_email |
| Disqualified | `lead.disqualified` | Boolean flag - shown as badge when true |
| Created | `lead.creation_date` | |

**Filters:**
- `state`: exact DealState value match
- `search`: case-insensitive substring match on `full_name`, `headline`, `public_identifier`, `api_email`, `contact_info.email`
- `disqualified`: boolean filter on `lead.disqualified`

**Pagination:** server-side. Total = count of all matching deals after applying filters. Page size 50.

### 3.2 Lead Detail Modal / Page

Opens on row click. Additional fields exposed:

| Field | Source |
|---|---|
| Experience | `lead.cached_profile.positions[]` → `{title, company_name, date_range}` |
| Education | `lead.cached_profile.educations[]` → `{school_name, degree_name, year}` |
| Connection degree | `lead.connection_degree` (1/2/3) |
| Notes | `lead.notes` |
| All deals | All campaigns where this lead appears, with state per campaign |
| Messages | Routed via `GET /api/leads/{id}/messages` |

### 3.3 CSV Export

`GET /api/leads/export?campaign_id={id}&state={filter}`

Columns: Name, Email, Phone Numbers, LinkedIn URL, Company, Title, State, Outcome, Campaign, Created Date, Disqualified.
Email resolution: `api_email` (enrichment waterfall) falling back to `contact_info.email` (LinkedIn overlay).

---

## 4. Messages Page (`/messages`)

**Endpoints:**
- `GET /api/messages/stats?campaign_id={id}` - stat cards
- `GET /api/messages?campaign_id={id}&deal_id={id}&limit=50&offset={n}` - message list
- `GET /api/messages/deals/{deal_id}/messages?sync=true` - thread view (also syncs from LinkedIn)

### 4.1 Stat Cards (4 cards)

| Card | Value | Backend field | Formula |
|---|---|---|---|
| Total Sent | count | `totalSent` | `chat_messages.count_documents({deal_id: {$in: accessible_deal_ids}, is_outgoing: true})` |
| Total Received | count | `totalReceived` | `chat_messages.count_documents({deal_id: {$in: …}, is_outgoing: false})` |
| Response Rate | `%` | `responseRate` | `round((distinct_deal_ids_with_reply / distinct_deal_ids_messaged) * 100)`. Both are distinct deal ID counts - `chat_messages.distinct("deal_id", {is_outgoing:false})` / `chat_messages.distinct("deal_id", {is_outgoing:true})`. Returns 0 when no deals messaged. |
| Campaigns with Messages | count | `activeCampaigns` | Count of distinct `deal.campaign_id` values from deals that have at least one message. |

Note: "Campaigns with Messages" = campaigns with at least one sent or received message (not campaigns with `status=active`).

### 4.2 Message List

One row per message, sorted by `creation_date` descending.

| Field | Source |
|---|---|
| Direction badge | `message.isOutgoing` - outgoing=blue, incoming=gray |
| Recipient Name | `lead.full_name` via deal→lead lookup |
| Campaign Name | `campaign.name` via deal→campaign lookup |
| Content (clipped) | `message.content` |
| Timestamp | `message.creationDate` - rendered relative ("2h ago") |
| `sender` field | `"me"` if outgoing, `"them"` if incoming |

**Filters (frontend-driven):**
- Campaign dropdown - passes `campaign_id` query param
- Search - client-side filter on rendered name/content
- Date range: all/today/7d/30d/90d - passed as additional query params or client-filtered
- Response status: all/with response/without response - client-filtered on whether deal has any `is_outgoing=false` message

### 4.3 Thread View (Modal)

- `GET /api/messages/deals/{deal_id}/messages?sync=true` - triggers live LinkedIn conversation sync before returning stored messages
- Displays all messages for the deal sorted by `creation_date` ascending
- Outgoing: right-aligned blue; Incoming: left-aligned gray
- Reply field: 1000-character limit, enqueues a daemon task

---

## 5. Campaigns List (`/campaigns`)

**Endpoint:** `GET /api/campaigns?skip=0&limit=100`

### 5.1 Status Tabs

| Tab | Count |
|---|---|
| All | `pagination.total` |
| Active | Frontend: `campaigns.filter(c => c.status === "active").length` |
| Paused | Frontend: `campaigns.filter(c => c.status === "paused").length` |
| Draft | Frontend: `campaigns.filter(c => c.status === "draft").length` |

Counts are derived client-side from the full response list (up to 100 campaigns per fetch).

### 5.2 Campaign Card

Per-campaign stats are batch-aggregated in the list endpoint:

| Metric | Source | Formula |
|---|---|---|
| Total Leads | `stats.totalLeads` | `deals.aggregate($group by campaign_id, $sum:1)` - count of all deals for campaign regardless of state |
| Connections Sent | `stats.connected` | `action_logs.aggregate({action_type:"connect", status:{$nin:["failed","error"]}} → $group by campaign_id, $sum:1)` - all-time, no time filter |
| Completed | `stats.completed` | `deals.aggregate($group, $sum if state=="Completed")` |

Note: `messagesSent` and `messagesReplied` are **not** included in the list endpoint's `CampaignStats`. Those appear on the campaign detail and analytics tabs.

---

## 6. Campaign Detail - Overview Tab (`/campaigns/{id}`)

**Endpoints:**
- `GET /api/campaigns/{id}` - campaign doc
- `GET /api/campaigns/{id}/analytics?period=30d` - stats
- `GET /api/campaigns/{id}/activity` - activity log + next task

### 6.1 Analytics Stats Card (8 metrics)

| Metric | Field | Formula |
|---|---|---|
| Connections Sent | `stats.connections_sent` | `action_logs.count({campaign_id, action_type:"connect", status:{$nin:[…]}, created_at:{$gte:since}})` |
| Connections Accepted | `stats.connections_accepted` | CONNECTED deals excluding 1st-degree (same pipeline as §2.1) - **not** time-filtered in campaign analytics endpoint |
| Connection Accept Rate | `stats.connection_accept_rate` | `round(accepted / sent * 100, 2)`. Zero-safe. |
| Messages Sent | `stats.messages_sent` | `action_logs.count({campaign_id, action_type:"follow_up", status:{$nin:[…]}, created_at:{$gte:since}})` |
| Messages Replied | `stats.messages_replied` | Distinct deals with inbound messages in period (same pipeline as §2.1) |
| Response Rate | `stats.response_rate` | `round(replied / sent * 100, 2)`. Zero-safe. |
| Conversions | `stats.conversions` | `deals.count({campaign_id, state:"Completed"})` - **not** time-filtered in this endpoint |
| Conversion Rate | `stats.conversion_rate` | `round(conversions / accepted * 100, 2)`. Zero-safe. |
| Errors | `stats.errors` | `action_logs.count({campaign_id, status:{$in:["failed","error"]}, created_at:{$gte:since}})` |

### 6.2 Activity Log

Source: `GET /api/campaigns/{id}/activity?page=1&limit=20`
- Lists `action_logs` for campaign, sorted `created_at` descending, paginated
- `lead_name` enriched from `leads.find({public_identifier:…})` for logs missing `details.lead_name`
- Each row: type, status, timestamp, lead name, duration_ms

**Next Task card:**
- `tasks.find_one({payload.campaign_id, status:"pending"}).sort(scheduled_at,1)` - the earliest pending task
- Shows: task type, `scheduled_at` timestamp, ETA in seconds

**Pending Count:** `tasks.count_documents({payload.campaign_id, status:"pending"})`

---

## 7. Campaign Detail - Analytics Tab (`/campaigns/{id}/analytics`)

**Endpoint:** `GET /api/campaigns/{id}/analytics?period={7d|30d|90d|all}`

When `period=all`, `since = datetime(2000,1,1)` (effectively all-time).

### 7.1 KPI Cards (4 cards)

| Card | Value | Source |
|---|---|---|
| Connections Sent | count | `stats.connections_sent` |
| Connections Accepted | count | `stats.connections_accepted` |
| Messages Sent | count | `stats.messages_sent` |
| Replies | count | `stats.messages_replied` (= `stats.responses`) |

### 7.2 Outreach Funnel Bar Chart (5 bars)

Bars represent the funnel stages, each bar shorter than the last:

| Bar | Value |
|---|---|
| Sent | `stats.connections_sent` |
| Accepted | `stats.connections_accepted` |
| Messaged | `stats.messages_sent` |
| Replied | `stats.messages_replied` |
| Completed | `stats.conversions` |

### 7.3 Conversion Rates (3 badges)

| Label | Formula |
|---|---|
| Connection Accept Rate | `accepted / sent * 100%` |
| Message Response Rate | `replied / messages_sent * 100%` |
| Overall Conversion Rate | `conversions / accepted * 100%` |

### 7.4 Lead Pipeline Breakdown (Donut)

Same as §2.2, filtered to campaign. Source: `pipeline` object in response - one key per DealState, each = `deals.count_documents({campaign_id, state:X})`.

---

## 8. Campaign Leads Tab (`/campaigns/{id}/leads`)

**Endpoint:** `GET /api/campaigns/{id}/leads?state={filter}&limit=50&offset={n}`

### 8.1 Summary Stats (4 cards, server-side counts)

| Card | Formula |
|---|---|
| Total Leads | Sum of all `pipelineCounts` values returned in response envelope |
| Qualified | `pipelineCounts.qualified` |
| Completed | `pipelineCounts.completed` |
| Failed | `pipelineCounts.failed` |

Server returns `pipelineCounts` in the pagination envelope via a `$group` aggregation over all deals for the campaign (not page-scoped):
```
deals.aggregate([
  {$match: {campaign_id}},
  {$group: {_id: "$state", count: {$sum: 1}}}
])
```
Keys: `discovered`, `qualified`, `readyToConnect`, `pending`, `connected`, `completed`, `failed`, `noEmail`.

### 8.2 Lead Status Distribution (7 bars)

Each bar = count of deals in that state. Source: `pipelineCounts` from response envelope (server-side aggregates - NOT client-side filtered):
- Bar width = `(pipelineCounts[key] / totalPipelineCount) * 100%`
- States shown: Discovered, Qualified, Pending, Connected, Completed, Failed, No Email

### 8.3 Leads Table

Same column set as §3.1, scoped to this campaign.

---

## Key Math Formulas Summary

| Metric | Formula | Zero-safe |
|---|---|---|
| Connection Accept Rate | `connected_non_1st_degree / connections_sent * 100` | Returns 0.0 when sent=0 |
| Response Rate (all endpoints) | `distinct_deals_with_reply / distinct_deals_messaged * 100` | Returns 0.0 when messaged=0; both are deal-level distinct counts |
| Conversion Rate | `completed_deals / connections_accepted * 100` | Returns 0.0 when accepted=0 |
| Accept Rate (dashboard) | `connections_accepted / connections_sent * 100` | Shows `—` on frontend when sent=0 |
| Reply Rate (dashboard) | `messages_replied / messages_sent * 100` | Shows `—` on frontend when 0 |
| In-Funnel Leads (analytics) | `qualified + ready_to_connect + pending + connected` deal counts | |

---

## Important Distinctions

**connections_accepted ≠ deals with state=Connected**
The acceptance count excludes 1st-degree connections (they auto-transition to CONNECTED without a request being sent). A CONNECTED deal where `lead.connection_degree == 1` does NOT count as "accepted" for rate calculations.

**messages_replied = distinct deals, not message count**
If a lead sends 3 replies, that still counts as 1 in `messages_replied`. The metric represents "how many conversations got a response", not total inbound message volume.

**conversions in analytics vs. overview**
- Analytics overview (`/api/analytics/overview`): `conversions` = COMPLETED deals with `creation_date >= since` (time-filtered)
- Campaign analytics (`/api/campaigns/{id}/analytics`): `conversions` = ALL COMPLETED deals for campaign (not time-filtered)

**Period filtering**
- `connections_sent`, `messages_sent`, `messages_replied`, `conversions` (in overview): time-filtered by `created_at >= since`
- Pipeline stage counts (QUALIFIED, PENDING, CONNECTED, etc.): always current state, never time-filtered
- `connections_accepted` in campaign analytics: not time-filtered (all CONNECTED non-1st-degree deals ever)

---

## 9. Lead Detail Page (`/leads/{id}`)

**Endpoint:** `GET /api/leads/{id}`

Full page with 4 tabs (Overview / Profile / Messages / Campaigns) plus right sidebar.

### 9.1 Overview Tab

**Lead Status card:**

| Field | Source |
|---|---|
| Current State badge | `lead.state` (DealState from first accessible deal) |
| Active / Disqualified badge | `lead.disqualified` boolean |
| LinkedIn URL | `lead.linkedinUrl` |
| Created | `lead.creationDate` (relative, e.g. "3 days ago") |
| Last Updated | `lead.updateDate` (relative) |

**Contact Information card:**

| Field | Source | Notes |
|---|---|---|
| Enrichment email | `lead.contactInfo.apiEmail` | `lead.api_email` from enrichment waterfall |
| LinkedIn overlay email | `lead.contactInfo.overlayEmail` | `lead.contact_info.email` from 1st-degree contact-info scrape |
| Phone numbers | `lead.contactInfo.phoneNumbers[]` | `lead.contact_info.phone_numbers` array |

Only shown when at least one contact field is non-null.

### 9.2 Profile Tab

Source: `lead.profile` object built from `lead.cached_profile` (Voyager JSON).

| Field | Source path |
|---|---|
| Headline | `lead.profile.headline` |
| Location | `lead.profile.location` |
| Summary | `lead.profile.summary` |
| Experience list | `lead.profile.experience[]` → `{title, company, duration}`. Duration formatted as `"M/YYYY - M/YYYY"` or `"M/YYYY - Present"` |
| Education list | `lead.profile.education[]` → `{school, degree, year}` |

### 9.3 Messages Tab

- Source: `GET /api/leads/{id}/messages` - all messages across all accessible deals for this lead
- Polled every 10 seconds while tab is active
- Displayed via `MessageThread` component: chronological, outgoing right-aligned blue, incoming left-aligned gray
- Reply sends `POST /api/leads/{id}/messages` → creates `Message` record + enqueues `SEND_MANUAL_MESSAGE` daemon task

### 9.4 Campaigns Tab

Source: `lead.deals[]` from the detail response - all campaigns where this lead appears and user has access.

| Column | Source |
|---|---|
| Campaign name | `deal.campaignName` |
| State badge | `deal.state` |
| Outcome badge | `deal.outcome` (if present) |

### 9.5 Sidebar - Metadata card

| Field | Source | Notes |
|---|---|---|
| Public ID | `lead.publicIdentifier` | LinkedIn username/slug |
| LinkedIn URN | Last path segment of `lead.linkedinUrl` | Parsed client-side |
| Messages | `lead.messagesCount` | Count of all `chat_messages` across all accessible deals for this lead |
| Last Message | `lead.lastMessageAt` | ISO timestamp of most recent message across all deals; `null` if no messages |

`messagesCount`: `chat_messages.count_documents({deal_id: {$in: accessible_deal_ids}})`.
`lastMessageAt`: `chat_messages.find_one({deal_id: {$in: …}}, sort=[("creation_date", -1)]).creation_date.isoformat()`.

### 9.6 Notes

- Stored in `lead.notes` (free text)
- Save: `PATCH /api/leads/{id}` with `{notes: "..."}` - updates `leads.notes` field

---

## 10. Campaign Logs Page (`/campaigns/{id}/logs`)

Full-page version of the activity log from Campaign Overview tab §6.2.

**Endpoint:** `GET /api/campaigns/{id}/activity?page={n}&limit=20`

Same data as §6.2 but `compact=false` - shows more detail per row. No additional metrics beyond what §6.2 documents.

---

## 11. System Health Page (`/health`)

**Endpoint:** `GET /api/health` (via `useDashboard` hook)

### 11.1 Overall Status Badge

| Value | Condition |
|---|---|
| `operational` | `healthStatus.status === "operational"` |
| `degraded` | Any other value |

### 11.2 Service Timeline (2 services)

| Service | Status source | Latency source |
|---|---|---|
| Database | `healthStatus.services.database` mapped: `"operational"` → `connected`, `"degraded"` → `degraded`, other → `disconnected` | `healthStatus.database.latency_ms` measured around the MongoDB probe |
| API | `healthStatus.status === "operational"` → `connected`, else `degraded` | `healthStatus.api.latency_ms` measured for the health request |

### 11.3 Database Status card

| Field | Value |
|---|---|
| Database Type | Hard-coded string `"MongoDB"` |
| Connection Status | `healthStatus.services.database === "operational"` → `"Connected"` with pulsing green dot, else `"Disconnected"` with red dot |

The generic health endpoint reports LinkedIn as `unknown` because it does not
perform a provider API probe. Provider/profile health must come from the
authenticated LinkedIn profile health endpoint.

Latency values are measured by the health endpoint for each request. They are
diagnostic probe timings, not an externally observed request-duration SLI.

---

## 12. Settings Page (`/settings`)

**Endpoints:** `GET /api/settings`, `GET /api/settings/daily-usage`

### 12.1 Summary Cards (3 cards, always visible)

| Card | Value | Source |
|---|---|---|
| LinkedIn profile | `@{username}` or `"Not connected yet"` | `settings.linkedinProfile.username` from `LinkedInProfile.linkedin_username` - empty if unresolved (login email, not yet scraped) |
| Daily sending profile | `{N} connect / {M} follow-up` | `settings.rateLimits.dailyConnectionLimit` / `settings.rateLimits.dailyFollowUpLimit` from `SiteConfig` |
| LLM configuration | Provider name or `"Lengrowth AI"` | `settings.llm.provider` - shows `"Lengrowth AI"` when no API key configured (platform default) |

Sub-text on sending card: `"Velocity {V}/hour"` from `settings.rateLimits.velocity`.

Sub-text on LLM card: badge row - shows `Style`, `Prefer`, `Avoid` badges if those guardrail fields are non-empty; otherwise `"Defaults only"`.

### 12.2 Rate Limits Tab - Daily Usage Cards (3 cards)

Source: `GET /api/settings/daily-usage`

| Card | Field | Formula |
|---|---|---|
| Connections sent today | `daily_connections_sent` | `action_logs.count({linkedin_profile_id: {$in: active_profile_ids}, action_type:"connect", status:{$nin:["failed","error"]}, created_at:{$gte:day_start, $lt:day_end}})` |
| Effective limit | `effective_limit` | `SiteConfig.daily_connection_limit` (= base limit; smart multipliers not applied here) |
| Remaining | `remaining` | `max(0, connect_limit - connect_count) + max(0, follow_up_limit - follow_up_count)` |
| Rate limit status | `rate_limit_status` | Thresholds based on `connect_pct = connect_count / connect_limit * 100`: `normal` (<60%), `caution` (60-79%), `warning` (80-99%), `exceeded` (≥100%) |

Day boundaries use user's `SiteConfig.active_timezone` (default UTC).

### 12.3 Rate Limits Tab - Form Fields

Reads/writes `SiteConfig` via `PATCH /api/settings`:

| Field | SiteConfig key | Type |
|---|---|---|
| Daily connection limit | `daily_connection_limit` | int |
| Daily follow-up limit | `daily_follow_up_limit` | int |
| Velocity (actions/hr) | `velocity` | int |
| Cooldown minutes | `cooldown_minutes` | int |
| Enable smart rate limiting | `enable_smart_rate_limiting` | bool |
| Aggressiveness preset | `aggressiveness_preset` | enum: `very_slow/slow/average/aggressive/very_aggressive` |

### 12.4 LLM / AI Settings Tab - Form Fields

| Field | SiteConfig key | Purpose |
|---|---|---|
| Provider | `llm_provider` | `openai/anthropic/google/groq/mistral/cohere/openai_compatible` |
| API Key | `llm_api_key` | Provider key |
| Model | `ai_model` | Model ID string |
| API Base | `llm_api_base` | Only used when provider = `openai_compatible` |
| Writing Style | `ai_writing_style` | Tone/style instruction injected into follow-up agent system prompt |
| Say Rules | `ai_say_rules` | Phrases/topics to emphasize |
| Avoid Rules | `ai_avoid_rules` | Phrases/topics to avoid |

### 12.5 Active Hours Tab - Form Fields

| Field | SiteConfig key | Type |
|---|---|---|
| Enable active hours | `enable_active_hours` | bool |
| Start hour | `active_start_hour` | int 0-23 |
| End hour | `active_end_hour` | int 0-23 |
| Timezone | `active_timezone` | IANA timezone string |
| Active days | `active_days` | comma-separated int string e.g. `"1,2,3,4,5"` (Mon=1, Sun=7) |

---

## 13. Settings / Billing Page (`/settings/billing`)

**Endpoints:** `GET /api/billing/status`, `GET /api/billing/plans`, `GET /api/billing/invoices`, `GET /api/billing/usage`, `GET /api/billing/lifetime-deal`

### 13.1 Trial Banner

Shown when `billingStatus.subscription_status === "trialing"`.
Displays `billingStatus.trial_ends_at` - absolute date from Stripe subscription.

### 13.2 Billing Status Card

| Field | Source |
|---|---|
| Current plan display name | `plans.find(p => p.name === billingStatus.plan).display_name` |
| Subscription status | `billingStatus.subscription_status` (Stripe status: `active/trialing/past_due/canceled`) |
| Next billing date | `billingStatus.current_period_end` (from Stripe) |

### 13.3 Plan Limits Card (usage bars)

Source: `GET /api/billing/usage`

| Bar | Used | Limit |
|---|---|---|
| LinkedIn Accounts | `usage.linkedin_accounts_used` | `billingStatus.linkedin_account_limit` |
| Campaigns | `usage.campaigns_used` | `billingStatus.campaign_limit` |

`UsageIndicator` component renders a progress bar: `width = (used / limit) * 100%`.

### 13.4 Invoices Table

Source: `GET /api/billing/invoices` (Stripe invoices).

| Column | Source | Notes |
|---|---|---|
| Invoice number | `invoice.number` or `"Invoice " + id.slice(0,8)` | |
| Date | `invoice.created * 1000` (Unix ms → date format `"MMM d, yyyy"`) | |
| Status badge | `invoice.status` | green when `invoice.paid === true` |
| Amount | `invoice.amount_paid / 100` formatted as `"$X.XX"` | Stripe stores cents |
| Download | `invoice.pdf_url` | Link to Stripe-hosted PDF |

---

## 14. Settings / Plan Page (`/settings/plan`)

**Endpoints:** `GET /api/billing/status`, `GET /api/billing/plans`, `GET /api/billing/lifetime-deal`

### 14.1 Plan Cards (4 regular plans)

`cloud_addon` plan is always filtered out of display. Plans rendered: `starter/pro/business/agency`.

| Field | Source |
|---|---|
| Price (monthly) | `plan.monthly_price` |
| Price (annual) | `plan.annual_price` (toggle `isAnnual` switches display) |
| Savings label | Hard-coded `"Save 17%"` on annual toggle |
| Feature list | `plan.features[]` |
| Current plan highlight | `billingStatus.plan === plan.name` |

### 14.2 Lifetime Deal Banner

Only shown when `isLifetimeDealActive === true` (from `GET /api/billing/lifetime-deal`). Price: `$149 once`. Features from `lifetimePlan.features[]`.

### 14.3 Plan Comparison Table

`PlanComparison` component: renders all plans × all feature rows. Source: `plans[]` with feature flags.

---

## 15. Campaign Health API (backend only, no dedicated UI page)

Endpoint group at `GET /api/campaigns/{id}/health`, `/health/metrics`, `/health/alerts`, `/health/recovery-actions`. Not linked from navigation - backend infrastructure only.

### Health Score formula

```
score = 100
score -= min(errors_total * 5, 30)          # each error costs 5pts, capped at -30
if connection_accept_rate < 0.20: score -= 20
if response_rate < 0.10: score -= 20
score -= int(detectability_score * 0.3)
score = max(0, score)

status: healthy (≥80), degraded (50-79), critical (<50)
```

Source collections: `campaign_health_metrics`, `health_alerts`, `recovery_actions`.

---

## Gaps & Known Issues

| Page | Issue |
|---|---|
| Health page (`/health`) | Latency values always 0 - health endpoint does not measure real latency |
| Campaigns list (§5.1) | Tab counts (Active/Paused/Draft) are client-side from first 100 campaigns - if user has >100 campaigns, counts are wrong |
