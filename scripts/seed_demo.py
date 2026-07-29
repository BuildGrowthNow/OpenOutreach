"""
Demo seed script for video recording.

Creates a fully-populated fake campaign for fern2gue@gmail.com with realistic
leads, deals spread across all funnel stages, chat conversations, and activity
logs. Nothing is queued to run — the campaign shows as active but is frozen.

Usage:
    python scripts/seed_demo.py

Safe to re-run: skips creation if the demo campaign already exists.
"""

from __future__ import annotations

import random
import sys
import uuid
from datetime import datetime, timedelta, timezone

# Bootstrap settings / MongoDB before importing models
import os
from pathlib import Path

# Load .env manually first so MONGODB_ATLAS_URI (the name used in .env) is
# available. Pydantic-settings reads MONGODB_URI; if it's blank but
# MONGODB_ATLAS_URI is set, alias it before the module is imported.
_project_root = Path(__file__).resolve().parent.parent
_env_file = _project_root / ".env"
if _env_file.exists():
    for _line in _env_file.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line.startswith("#") or "=" not in _line:
            continue
        _k, _, _v = _line.partition("=")
        _k = _k.strip()
        _v = _v.strip().strip('"').strip("'")
        os.environ.setdefault(_k, _v)

# Alias MONGODB_ATLAS_URI → MONGODB_URI if needed
if not os.environ.get("MONGODB_URI") and os.environ.get("MONGODB_ATLAS_URI"):
    os.environ["MONGODB_URI"] = os.environ["MONGODB_ATLAS_URI"]

sys.path.insert(0, str(_project_root))

from openoutreach.mongodb.connection import get_mongodb_collection

UTC = timezone.utc
NOW = datetime.now(UTC)

TARGET_EMAIL = "fern2gue@gmail.com"
DEMO_CAMPAIGN_NAME = "B2B SaaS Outreach - Demo"

# ── Fake people ───────────────────────────────────────────────────────────────

LEADS_DATA = [
    {
        "first_name": "Marcus", "last_name": "Reidel",
        "headline": "VP of Sales @ Synapse CRM | SaaS Revenue Leader",
        "location_name": "Austin, Texas",
        "company": "Synapse CRM", "title": "VP of Sales",
        "email": "marcus.reidel@synapsecrm.com",
    },
    {
        "first_name": "Priya", "last_name": "Nair",
        "headline": "Head of Business Development | B2B Growth",
        "location_name": "San Francisco, California",
        "company": "Growthly", "title": "Head of Business Development",
        "email": "p.nair@growthly.io",
    },
    {
        "first_name": "James", "last_name": "Whitmore",
        "headline": "Director of Sales Operations | RevOps",
        "location_name": "New York, New York",
        "company": "Stackline", "title": "Director of Sales Operations",
        "email": None,
    },
    {
        "first_name": "Sofia", "last_name": "Alvarez",
        "headline": "Enterprise Account Executive | Fintech",
        "location_name": "Miami, Florida",
        "company": "Fintara", "title": "Enterprise Account Executive",
        "email": "s.alvarez@fintara.com",
    },
    {
        "first_name": "Liam", "last_name": "Chen",
        "headline": "Founder & CEO @ LeadMagnet — B2B Prospecting",
        "location_name": "Seattle, Washington",
        "company": "LeadMagnet", "title": "Founder & CEO",
        "email": "liam@leadmagnet.app",
    },
    {
        "first_name": "Amara", "last_name": "Okonkwo",
        "headline": "Sales Manager | SaaS | Team of 12",
        "location_name": "Toronto, Ontario",
        "company": "Cloudify", "title": "Sales Manager",
        "email": None,
    },
    {
        "first_name": "Tobias", "last_name": "Gruber",
        "headline": "Chief Revenue Officer | Series B | €40M ARR",
        "location_name": "Berlin, Germany",
        "company": "Konvect", "title": "Chief Revenue Officer",
        "email": "tgruber@konvect.de",
    },
    {
        "first_name": "Rachel", "last_name": "Huang",
        "headline": "Account Executive → Sr. AE @ Databricks",
        "location_name": "San Francisco, California",
        "company": "Databricks", "title": "Senior Account Executive",
        "email": None,
    },
    {
        "first_name": "Nathan", "last_name": "Calloway",
        "headline": "Business Development Representative | SDR Leader",
        "location_name": "Denver, Colorado",
        "company": "Salesloft", "title": "Senior BDR",
        "email": "n.calloway@salesloft.com",
    },
    {
        "first_name": "Isabela", "last_name": "Ferreira",
        "headline": "Sales Director LATAM | Outbound Expert",
        "location_name": "São Paulo, Brazil",
        "company": "Nexion", "title": "Sales Director LATAM",
        "email": "isabela@nexion.com.br",
    },
    {
        "first_name": "Derek", "last_name": "Morrison",
        "headline": "VP Growth | PLG | SaaS Veteran",
        "location_name": "Chicago, Illinois",
        "company": "Pulsar Analytics", "title": "VP Growth",
        "email": "derek.morrison@pulsaranalytics.com",
    },
    {
        "first_name": "Yuki", "last_name": "Tanaka",
        "headline": "Regional Sales Manager | APAC | B2B Tech",
        "location_name": "Tokyo, Japan",
        "company": "TechBridge", "title": "Regional Sales Manager",
        "email": None,
    },
    {
        "first_name": "Connor", "last_name": "Walsh",
        "headline": "Co-Founder @ Remofly | Remote Team Sales",
        "location_name": "Dublin, Ireland",
        "company": "Remofly", "title": "Co-Founder",
        "email": "connor@remofly.io",
    },
    {
        "first_name": "Fatima", "last_name": "El Mourabit",
        "headline": "Sales Enablement Lead | CRM & Automation",
        "location_name": "Paris, France",
        "company": "Saleshift", "title": "Sales Enablement Lead",
        "email": None,
    },
    {
        "first_name": "Andre", "last_name": "Santos",
        "headline": "Inside Sales Manager | 50-rep team | SaaS",
        "location_name": "Lisbon, Portugal",
        "company": "Optivend", "title": "Inside Sales Manager",
        "email": "andre@optivend.pt",
    },
    {
        "first_name": "Hannah", "last_name": "Novak",
        "headline": "Director of Revenue Operations | HubSpot Partner",
        "location_name": "Prague, Czech Republic",
        "company": "RevScale", "title": "Director of Revenue Operations",
        "email": "h.novak@revscale.cz",
    },
    {
        "first_name": "Emeka", "last_name": "Oduya",
        "headline": "Enterprise Sales Executive | Healthcare SaaS",
        "location_name": "Lagos, Nigeria",
        "company": "MediTrack", "title": "Enterprise Sales Executive",
        "email": None,
    },
    {
        "first_name": "Sara", "last_name": "Lindqvist",
        "headline": "Sales Coach & Trainer | LinkedIn Top Voice",
        "location_name": "Stockholm, Sweden",
        "company": "SalesAcademy", "title": "Sales Coach",
        "email": "sara@salesacademy.se",
    },
    {
        "first_name": "Ryan", "last_name": "Kowalski",
        "headline": "Head of Sales | Series A Startup | Ex-Salesforce",
        "location_name": "Boston, Massachusetts",
        "company": "Prism AI", "title": "Head of Sales",
        "email": "ryan@prismai.com",
    },
    {
        "first_name": "Claudia", "last_name": "Moretti",
        "headline": "Account Director | Enterprise | EMEA",
        "location_name": "Milan, Italy",
        "company": "Nexgen Solutions", "title": "Account Director",
        "email": "claudia.moretti@nexgen.it",
    },
]

# Funnel distribution across 20 leads
# Keys match DealState string values
FUNNEL_STATES = [
    "Discovered",       # 0 - Marcus
    "Discovered",       # 1 - Priya
    "Qualified",        # 2 - James
    "Qualified",        # 3 - Sofia
    "Qualified",        # 4 - Liam
    "Ready to Connect", # 5 - Amara
    "Ready to Connect", # 6 - Tobias
    "Pending",          # 7 - Rachel
    "Pending",          # 8 - Nathan
    "Pending",          # 9 - Isabela
    "Connected",        # 10 - Derek
    "Connected",        # 11 - Yuki
    "Connected",        # 12 - Connor
    "Connected",        # 13 - Fatima
    "Connected",        # 14 - Andre
    "Completed",        # 15 - Hannah (converted)
    "Completed",        # 16 - Emeka (converted)
    "Failed",           # 17 - Sara (not interested)
    "Failed",           # 18 - Ryan (wrong fit)
    "Pending",          # 19 - Claudia
]

# ── Fake conversations (for Connected/Completed leads) ────────────────────────

CONVERSATIONS = {
    # Tuples: (is_outgoing, text, day_offset)
    # is_outgoing=True  → we sent it
    # is_outgoing=False → lead replied
    10: [  # Derek
        (True,  "Hey, are you the right person to talk to about outbound automation at Pulsar?", -5),
        (False, "Yes that'd be me. What's up?", -4),
        (True,  "We help sales teams automate LinkedIn outreach without the risk. Curious how you're doing outbound today?", -3),
        (False, "Mostly manual. We tried a tool last year but got burned by quality issues.", -2),
        (True,  "That's pretty common. What broke down - the messaging, targeting, or both?", -1),
    ],
    11: [  # Yuki
        (True,  "Saw you run APAC sales at TechBridge - how do you manage outreach across so many time zones?", -7),
        (False, "It's a challenge. We have local SDRs but coordination is messy.", -6),
        (True,  "Makes sense. Are you running LinkedIn outreach from a central playbook or each rep doing their own thing?", -5),
        (False, "Each rep mostly. It's hard to keep consistent.", -4),
        (True,  "We built something that solves exactly that - centralizes LinkedIn outreach with per-rep personalization. Worth a 20-min call?", -3),
        (False, "Send me more details first and I'll take a look.", -2),
    ],
    12: [  # Connor
        (True,  "Saw you're building Remofly - how are you finding leads for the remote-team space?", -8),
        (False, "LinkedIn mostly. Pretty manual right now.", -7),
        (True,  "Same story for most early-stage founders. Are you doing the outreach yourself or do you have someone?", -6),
        (False, "Mostly me. Takes a lot of time.", -5),
        (True,  "We automate the whole LinkedIn sequence - connection, follow-up, conversation handoff. Founders usually get 3-5 qualified convos/week.", -4),
        (False, "That sounds interesting actually. What does it look like in practice?", -3),
    ],
    13: [  # Fatima
        (True,  "Sales enablement at Saleshift - are you the one evaluating new automation tools?", -3),
        (False, "One of a few people, yes. What are you selling?", -2),
        (True,  "LinkedIn outreach automation. We focus on keeping conversations quality over volume. Happy to share a quick demo?", -1),
    ],
    14: [  # Andre
        (True,  "Managing 50 reps at Optivend - how are you currently handling outbound prospecting at that scale?", -6),
        (False, "We use a mix of tools. Nothing great for LinkedIn specifically.", -5),
        (True,  "LinkedIn is a gap for most teams at that size. We help centralize it - one platform, your whole team, tracked.", -4),
        (False, "Interesting. What's the typical setup time?", -3),
        (True,  "Most teams are live in a day. I can walk you through it this week if you have 20 minutes.", -2),
        (False, "Sure, Thursday works. Send a calendar link.", -1),
    ],
    15: [  # Hannah (converted)
        (True,  "RevOps at RevScale - curious how you're tracking LinkedIn outreach attribution today.", -12),
        (False, "Honestly we're not. It falls through the cracks.", -11),
        (True,  "That's the gap we close. Every LinkedIn touch goes into a unified pipeline with conversion tracking.", -10),
        (False, "That would actually be huge for us. What does pricing look like?", -9),
        (True,  "Depends on team size. Happy to walk through options - booked a slot for us: https://cal.com/demo/revscale", -8),
        (False, "Booked. See you then.", -7),
        (True,  "Perfect, looking forward to it.", -6),
    ],
    16: [  # Emeka (converted)
        (True,  "Healthcare enterprise sales is tough - how are you generating leads for MediTrack?", -10),
        (False, "Mostly referrals and cold email. LinkedIn is underused.", -9),
        (True,  "That's the common pattern in healthcare. We've helped teams in your space add 8-12 qualified meetings per month from LinkedIn alone.", -8),
        (False, "That's a big number. How?", -7),
        (True,  "Automated, personalized outreach that doesn't look automated. We handle the sequence, you handle the conversations.", -6),
        (False, "I'd like to see this in action. Do you have a demo?", -5),
        (True,  "Absolutely. Here's a link to book: https://cal.com/demo/meditrack", -4),
        (False, "Done. See you Friday.", -3),
    ],
    17: [  # Sara (not interested / failed)
        (True,  "Sales coaching + LinkedIn - do you use automation in your own outreach?", -14),
        (False, "I teach people to avoid automation actually. Prefer genuine connections.", -13),
        (True,  "That's fair - we're on the same page about quality. Our tool is built for that, not spray and pray.", -12),
        (False, "Appreciate it but I'm really not interested. Best of luck.", -11),
    ],
    18: [  # Ryan (wrong fit / failed)
        (True,  "Head of sales at an AI startup - how are you building your outbound motion from scratch?", -9),
        (False, "Figuring it out honestly. We're pre-product-market fit so still experimenting.", -8),
        (True,  "Makes sense. What channels are you testing?", -7),
        (False, "Email mostly. LinkedIn feels too slow for our stage.", -6),
        (True,  "Totally valid. We might be better suited once you have a repeatable motion. Happy to reconnect then.", -5),
        (False, "Yeah let's do that. Not the right time.", -4),
    ],
}

PROFILE_SUMMARIES = {
    10: ["VP Growth at Pulsar Analytics", "Previously tried a LinkedIn automation tool and had quality issues", "Manages outbound strategy", "Based in Chicago"],
    11: ["Regional Sales Manager at TechBridge covering APAC", "Coordinates across multiple time zones", "Each rep runs their own outreach with no central playbook", "Based in Tokyo"],
    12: ["Co-Founder of Remofly, a remote team platform", "Does outreach personally - time-constrained", "Early stage startup, no dedicated SDR", "Based in Dublin"],
    13: ["Sales Enablement Lead at Saleshift", "Part of a buying committee for tools", "Evaluates automation and CRM solutions", "Based in Paris"],
    14: ["Inside Sales Manager at Optivend managing 50 reps", "Uses multiple tools but nothing strong for LinkedIn specifically", "Interested in centralized LinkedIn outreach", "Based in Lisbon"],
    15: ["Director of Revenue Operations at RevScale", "LinkedIn attribution is a current gap in their stack", "Booked a demo call", "Based in Prague"],
    16: ["Enterprise Sales Executive at MediTrack in healthcare vertical", "Generates leads mainly via referrals and cold email", "LinkedIn is underused in their team", "Booked a demo call"],
    17: ["Sales Coach at SalesAcademy", "Actively teaches against automation in outreach", "LinkedIn Top Voice - has an audience and opinions", "Not a fit for automation tools"],
    18: ["Head of Sales at Prism AI (Series A startup)", "Pre-product-market fit, still experimenting with channels", "Prioritizing email over LinkedIn at this stage", "Ex-Salesforce background"],
}

CHAT_SUMMARIES = {
    10: ["Lead tried an automation tool before and had bad quality issues", "Currently doing outbound manually", "Open to hearing about automation if quality is addressed"],
    11: ["Lead manages APAC sales with decentralized SDR team", "Each rep does their own outreach - no standardization", "Interested in seeing details before committing to a call"],
    12: ["Lead is the founder and handles outreach personally", "Time is their biggest constraint", "Showed genuine interest after hearing the outcome metrics"],
    13: ["Lead is part of a buying committee, not sole decision maker", "Asked directly what we're selling - pragmatic personality"],
    14: ["Lead manages 50-rep inside sales team", "Multiple tools in stack, LinkedIn is a gap", "Asked about setup time - positive signal", "Agreed to a meeting on Thursday"],
    15: ["Lead is RevOps, not tracking LinkedIn attribution - confirmed pain point", "Asked about pricing - strong buying signal", "Booked a demo call - converted"],
    16: ["Lead confirmed LinkedIn is underused in healthcare sales context", "Asked how the outcome numbers are achieved - engaged", "Booked a demo call - converted"],
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def uid() -> str:
    return str(uuid.uuid4())


def ago(days: float = 0, hours: float = 0, minutes: float = 0) -> datetime:
    return NOW - timedelta(days=days, hours=hours, minutes=minutes)


def slug(first: str, last: str) -> str:
    return f"{first.lower()}-{last.lower()}-demo"


def make_cached_profile(p: dict) -> dict:
    s = slug(p["first_name"], p["last_name"])
    # URL uses the clean name (no -demo suffix) for visual realism
    clean_slug = f"{p['first_name'].lower()}-{p['last_name'].lower()}"
    return {
        "first_name": p["first_name"],
        "last_name": p["last_name"],
        "full_name": f"{p['first_name']} {p['last_name']}",
        "headline": p["headline"],
        "location_name": p["location_name"],
        "summary": None,
        "url": f"https://www.linkedin.com/in/{clean_slug}/",
        "urn": f"urn:li:member:{random.randint(100000000, 999999999)}",
        "public_identifier": s,
        "connection_degree": 2,
        "positions": [
            {
                "title": p["title"],
                "company_name": p["company"],
                "company_urn": None,
                "location": p["location_name"],
                "date_range": {
                    "start": {"year": random.randint(2020, 2023), "month": random.randint(1, 12)},
                    "end": None,
                },
                "description": None,
                "urn": None,
            }
        ],
        "educations": [],
        "country_code": None,
        "supported_locales": [],
        "connection_distance": "DISTANCE_2",
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    users_col = get_mongodb_collection("users")
    if users_col is None:
        print("ERROR: could not connect to MongoDB. Check your .env / MONGODB_URI.")
        sys.exit(1)

    # 1. Resolve user
    user_doc = users_col.find_one({"email": TARGET_EMAIL})
    if not user_doc:
        print(f"ERROR: no user found with email {TARGET_EMAIL!r}")
        sys.exit(1)
    user_id = str(user_doc["_id"])
    print(f"Found user: {TARGET_EMAIL} ({user_id})")

    # 2. Resolve or create a LinkedInProfile for this user
    profiles_col = get_mongodb_collection("linkedin_profiles")
    assert profiles_col is not None
    profile_doc = profiles_col.find_one({"user_id": user_id})
    if not profile_doc:
        # Create a placeholder profile — no cookies, not logged in
        linkedin_profile_id = uid()
        profiles_col.insert_one({
            "_id": linkedin_profile_id,
            "user_id": user_id,
            "linkedin_username": TARGET_EMAIL,
            "active": True,
            "is_active": True,
            "is_logged_in": False,
            "requires_verification": False,
            "connect_daily_limit": 20,
            "follow_up_daily_limit": 25,
            "daemon_status": "offline",
            "execution_mode": "desktop",
            "creation_date": NOW,
            "update_date": NOW,
        })
        print(f"Created placeholder LinkedInProfile ({linkedin_profile_id})")
    else:
        linkedin_profile_id = str(profile_doc["_id"])
        print(f"Reusing LinkedInProfile ({linkedin_profile_id})")

    # 3. Check for existing demo campaign
    campaigns_col = get_mongodb_collection("campaigns")
    assert campaigns_col is not None
    existing = campaigns_col.find_one({"name": DEMO_CAMPAIGN_NAME, "user_id": user_id})
    if existing:
        print(f"Demo campaign already exists ({existing['_id']}). Nothing to do. Run clean_demo.py first to reset.")
        sys.exit(0)

    # 4. Create campaign
    campaign_id = uid()
    campaigns_col.insert_one({
        "_id": campaign_id,
        "user_id": user_id,
        "linkedin_profile_id": linkedin_profile_id,
        "name": DEMO_CAMPAIGN_NAME,
        "status": "active",
        "is_paused": False,
        "product_pitch": (
            "Lengrowth is a LinkedIn outreach automation platform for B2B sales teams. "
            "We automate connection requests, follow-ups, and conversation tracking — "
            "while keeping each message personalized. Sales teams using Lengrowth book "
            "3-5x more qualified meetings without increasing headcount."
        ),
        "campaign_objective": (
            "Book discovery calls with B2B sales leaders (VP Sales, Head of Sales, "
            "Sales Directors) at SaaS companies with 20+ reps. Focus on outbound teams "
            "who are doing manual LinkedIn prospecting today."
        ),
        "booking_link": "https://cal.com/lengrowth/demo",
        "follow_up_strategy": (
            "Start with a discovery question anchored to their role. "
            "Once they respond, move toward uncovering their outbound pain. "
            "Pitch after 1-2 exchanges when there's a clear signal. "
            "Ask for a 20-min call once they're warm."
        ),
        "icp_titles": ["VP Sales", "Head of Sales", "Sales Director", "CRO", "Founder", "Sales Manager"],
        "target_degrees": [2, 3],
        "team_member_ids": [],
        "seed_public_ids": [],
        "velocity": 20,
        "action_fraction": 0.2,
        "connect_daily_limit": 20,
        "follow_up_daily_limit": 25,
        "model_blob": None,
        "created_at": ago(days=14),
        "update_date": ago(hours=2),
    })
    print(f"Created campaign: {DEMO_CAMPAIGN_NAME} ({campaign_id})")

    # 5. Create leads + deals
    leads_col = get_mongodb_collection("leads")
    deals_col = get_mongodb_collection("deals")
    chat_col = get_mongodb_collection("chat_messages")
    actions_col = get_mongodb_collection("action_logs")
    assert leads_col is not None
    assert deals_col is not None
    assert chat_col is not None
    assert actions_col is not None

    lead_ids = []
    for i, p in enumerate(LEADS_DATA):
        lead_id = uid()
        lead_ids.append(lead_id)
        public_id = slug(p["first_name"], p["last_name"])
        created = ago(days=14 - i * 0.5)

        lead_doc = {
            "_id": lead_id,
            "user_id": user_id,
            "public_identifier": public_id,
            "linkedin_url": f"https://www.linkedin.com/in/{public_id}/",
            "urn": f"urn:li:member:{random.randint(100000000, 999999999)}",
            "disqualified": False,
            "cached_profile": make_cached_profile(p),
            "connection_degree": 2,
            "creation_date": created,
            "update_date": created,
        }
        if p.get("email"):
            lead_doc["api_email"] = p["email"]

        leads_col.insert_one(lead_doc)

        # Deal
        state = FUNNEL_STATES[i]
        deal_id = uid()

        deal_doc = {
            "_id": deal_id,
            "user_id": user_id,
            "lead_id": lead_id,
            "campaign_id": campaign_id,
            "state": state,
            "outcome": "",
            "reason": "",
            "connect_attempts": 0,
            "backoff_hours": 0,
            "profile_summary": {},
            "chat_summary": {},
            "creation_date": created,
            "update_date": created,
        }

        if state == "Pending":
            deal_doc["connect_attempts"] = 1
            deal_doc["backoff_hours"] = 48
            deal_doc["next_check_pending_at"] = ago(days=-1)  # due in future

        if state in ("Connected", "Completed", "Failed"):
            ps_facts = PROFILE_SUMMARIES.get(i, [])
            cs_facts = CHAT_SUMMARIES.get(i, [])
            deal_doc["profile_summary"] = {"facts": ps_facts} if ps_facts else {}
            deal_doc["chat_summary"] = {"facts": cs_facts} if cs_facts else {}

        if state == "Completed":
            deal_doc["outcome"] = "converted"
        elif state == "Failed":
            deal_doc["outcome"] = "not_interested" if i == 17 else "wrong_fit"

        deals_col.insert_one(deal_doc)

        # Chat messages for leads with conversations
        if i in CONVERSATIONS:
            conv = CONVERSATIONS[i]
            for j, (is_outgoing, text, day_offset) in enumerate(conv):
                msg_time = ago(days=-day_offset, hours=random.randint(0, 3), minutes=random.randint(0, 59))
                chat_col.insert_one({
                    "_id": uid(),
                    "deal_id": deal_id,
                    "user_id": user_id,
                    "content": text,
                    "is_outgoing": is_outgoing,
                    "linkedin_urn": f"urn:li:msg:DEMO-{deal_id[:8]}-{j:03d}",
                    "creation_date": msg_time,
                })

    print(f"Created {len(LEADS_DATA)} leads and deals")

    # 6. Action logs — spread over 14 days to populate activity feed
    action_log_entries = []

    # Connects: one per non-Discovered lead, spread over days 1-10
    connect_targets = [i for i, s in enumerate(FUNNEL_STATES) if s not in ("Discovered", "Qualified")]
    for i, idx in enumerate(connect_targets):
        p = LEADS_DATA[idx]
        ts = ago(days=10 - i * 0.7, hours=random.randint(9, 17))
        action_log_entries.append({
            "_id": uid(),
            "user_id": user_id,
            "linkedin_profile_id": linkedin_profile_id,
            "campaign_id": campaign_id,
            "action_type": "connect",
            "status": "completed",
            "error_message": "",
            "details": {
                "lead_id": lead_ids[idx],
                "public_identifier": slug(p["first_name"], p["last_name"]),
                "lead_name": f"{p['first_name']} {p['last_name']}",
            },
            "created_at": ts,
        })

    # Check-pendings: for Pending and Connected leads
    check_targets = [i for i, s in enumerate(FUNNEL_STATES) if s in ("Pending", "Connected", "Completed", "Failed")]
    for i, idx in enumerate(check_targets):
        p = LEADS_DATA[idx]
        ts = ago(days=7 - i * 0.5, hours=random.randint(9, 17))
        action_log_entries.append({
            "_id": uid(),
            "user_id": user_id,
            "linkedin_profile_id": linkedin_profile_id,
            "campaign_id": campaign_id,
            "action_type": "check_pending",
            "status": "completed",
            "error_message": "",
            "details": {
                "lead_id": lead_ids[idx],
                "public_identifier": slug(p["first_name"], p["last_name"]),
                "lead_name": f"{p['first_name']} {p['last_name']}",
            },
            "created_at": ts,
        })

    # Follow-ups: for Connected, Completed, Failed leads
    followup_targets = [i for i, s in enumerate(FUNNEL_STATES) if s in ("Connected", "Completed", "Failed")]
    for i, idx in enumerate(followup_targets):
        p = LEADS_DATA[idx]
        # Each gets 1-3 follow-up actions
        count = random.randint(1, 3)
        for k in range(count):
            ts = ago(days=5 - i * 0.4 - k * 0.8, hours=random.randint(9, 17))
            action_log_entries.append({
                "_id": uid(),
                "user_id": user_id,
                "linkedin_profile_id": linkedin_profile_id,
                "campaign_id": campaign_id,
                "action_type": "follow_up",
                "status": "completed",
                "error_message": "",
                "details": {
                    "lead_id": lead_ids[idx],
                    "public_identifier": slug(p["first_name"], p["last_name"]),
                    "lead_name": f"{p['first_name']} {p['last_name']}",
                    "message_preview": CONVERSATIONS.get(idx, [("", "...", 0)])[min(k, len(CONVERSATIONS.get(idx, [])) - 1)][1][:80] if CONVERSATIONS.get(idx) else "Follow-up sent.",
                },
                "created_at": ts,
            })

    # A couple of failed connects for the errors widget
    for i in range(3):
        ts = ago(days=3 - i, hours=random.randint(9, 17))
        action_log_entries.append({
            "_id": uid(),
            "user_id": user_id,
            "linkedin_profile_id": linkedin_profile_id,
            "campaign_id": campaign_id,
            "action_type": "connect",
            "status": "failed",
            "error_message": "Connection limit reached for the day",
            "details": {},
            "created_at": ts,
        })

    # Campaign started event
    action_log_entries.append({
        "_id": uid(),
        "user_id": user_id,
        "linkedin_profile_id": linkedin_profile_id,
        "campaign_id": campaign_id,
        "action_type": "campaign_started",
        "status": "completed",
        "error_message": "",
        "details": {"campaign_name": DEMO_CAMPAIGN_NAME},
        "created_at": ago(days=14),
    })

    actions_col.insert_many(action_log_entries)
    print(f"Created {len(action_log_entries)} action log entries")

    # Summary
    from collections import Counter
    state_counts = Counter(FUNNEL_STATES)
    print("\nFunnel:")
    for state, count in sorted(state_counts.items(), key=lambda x: [
        "Discovered", "Qualified", "Ready to Connect", "Pending", "Connected", "Completed", "Failed"
    ].index(x[0]) if x[0] in ["Discovered", "Qualified", "Ready to Connect", "Pending", "Connected", "Completed", "Failed"] else 99):
        print(f"  {state}: {count}")

    print(f"\nDone. Visit /campaigns to see the demo campaign.")
    print(f"Campaign ID: {campaign_id}")


if __name__ == "__main__":
    main()
