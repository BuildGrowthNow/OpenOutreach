#!/usr/bin/env python
"""
Bulk import 1st-degree LinkedIn connections for LenGrowth outreach.

Usage:
1. Export your LinkedIn 1st-degree connections to a CSV file:
   - Go to https://www.linkedin.com/myservices/connections-export/
   - Download your connections CSV

2. Prepare your connections list (either CSV or JSON format)
   - CSV format: One LinkedIn profile URL or public identifier per line
   - JSON format: Array of objects with "linkedin_url" and optional "name" fields

3. Run this script:
   python bulk_add_connections.py --source /path/to/connections.csv

The script will:
- Parse your connections file
- Create Lead records for each connection
- Create QUALIFIED Deals (skipping qualification)
- Add them to your active campaign for messaging

Note: Make sure you have set up your environment variables (.env file) 
and the Django project is working before running this script.
"""

import os
import sys
import csv
import json
import argparse
from pathlib import Path

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'openoutreach.settings')

def setup_django():
    """Initialize Django settings."""
    import django
    django.setup()

def get_or_create_campaign(campaign_name="LenGrowth Outreach"):
    """Get existing campaign or create a new one."""
    from openoutreach.core.models import Campaign
    
    campaign, created = Campaign.objects.get_or_create(
        name=campaign_name,
        defaults={
            "description": f"Automated LinkedIn outreach for {campaign_name}",
            "archived": False,
        }
    )
    
    if created:
        print(f"Created new campaign: {campaign_name}")
    else:
        print(f"Using existing campaign: {campaign_name}")
    
    return campaign

def add_connections_as_seeds(campaign, public_ids, session):
    """Add 1st-degree connections directly to the campaign as seed leads.
    
    Since you're already connected to these people, we add them directly
    to the follow-up pool without requiring a connection request first.
    
    Note: Leads will still go through qualification to filter your ICP.
    """
    from openoutreach.crm.models import Deal, DealState, Lead
    from openoutreach.linkedin.db.leads import create_enriched_lead, promote_lead_to_deal
    from linkedin_cli.url_utils import public_id_to_url, url_to_public_id
    
    created = 0
    already_exists = 0
    
    for public_id in public_ids:
        if not public_id:
            continue
            
        # Skip self
        if public_id == session.self_profile.get("public_identifier"):
            continue
        
        try:
            url = public_id_to_url(public_id)
            
            # Check if lead already exists in this campaign
            if Deal.objects.filter(campaign=campaign, lead__public_identifier=public_id).exists():
                already_exists += 1
                continue
            
            # Create or get lead
            lead, lead_created = Lead.objects.get_or_create(
                public_identifier=public_id,
                defaults={"linkedin_url": url}
            )
            
            # Enrich the lead with profile data
            profile = None
            try:
                profile = lead.get_profile(session)
            except Exception as e:
                print(f"Warning: Could not enrich {public_id}: {e}")
            
            # Create QUALIFIED deal directly
            # Since these are 1st-degree connections, they skip connection_request step
            # and go directly to follow_up
            deal = Deal.objects.create(
                lead=lead,
                campaign=campaign,
                state=DealState.QUALIFIED,
                reason="1st-degree connection added directly to follow-up queue",
            )
            
            # Mark as a seed profile for freemium pipeline
            if not campaign.seed_public_ids:
                campaign.seed_public_ids = []
            if public_id not in campaign.seed_public_ids:
                campaign.seed_public_ids.append(public_id)
            
            created += 1
            print(f"  {public_id} -> QUALIFIED (seed)")
            
        except Exception as e:
            print(f"Error processing {public_id}: {e}")
            continue
    
    # Save campaign seed list
    if created > 0:
        campaign.save(update_fields=["seed_public_ids"])
    
    print(f"\nAdded {created} connections to campaign as seeds")
    print(f"Skipped {already_exists} already in campaign")
    return created

def parse_csv_file(filepath):
    """Parse CSV file with LinkedIn connections."""
    connections = []
    print(f"Parsing CSV file: {filepath}")
    
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        
        # Skip header if present
        first_row = next(reader, None)
        if not first_row:
            return connections
            
        # Check if first row looks like a header
        if 'firstName' in str(first_row) or 'LastName' in str(first_row):
            print("Detected header row, skipping...")
        else:
            # Re-insert the first row for processing
            connections.append(first_row[0] if first_row else "")
    
    # Read remaining rows
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header_skipped = False
        
        for row in reader:
            if not header_skipped:
                # Check if this is a header
                if len(row) >= 2 and any(x.lower().startswith('first') for x in row[:2]):
                    header_skipped = True
                    continue
                header_skipped = True
            
            # Handle different CSV formats
            if len(row) >= 1:
                url = row[0].strip()
                if url and not url.startswith('#'):
                    connections.append(url)
    
    return connections

def parse_json_file(filepath):
    """Parse JSON file with LinkedIn connections."""
    connections = []
    print(f"Parsing JSON file: {filepath}")
    
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
        if isinstance(data, list):
            for item in data:
                if isinstance(item, str):
                    connections.append({"linkedin_url": item})
                elif isinstance(item, dict) and 'linkedin_url' in item:
                    connections.append(item)
    
    return connections

def process_connections(campaign, connections, batch_size=100):
    """Process connections and create Leads for qualification.
    
    These leads will go through the qualification pipeline:
    1. Create Lead records
    2. Each lead is embedded
    3. Lead goes through qualification (AI checks if it matches ICP)
    4. If qualified (P > threshold), it goes to follow-up queue
    5. If not qualified, it's marked as FAILED with 'wrong_fit' reason
    
    For 1st-degree connections, since you're already connected to them,
    they can skip the connection_request step and go directly to follow_up.
    """
    from openoutreach.crm.models import Deal, DealState, Lead
    from openoutreach.linkedin.db.leads import create_enriched_lead
    
    from linkedin_cli.url_utils import url_to_public_id
    
    created = 0
    skipped = 0
    errors = []
    
    # Process in batches
    batch = []
    
    for conn in connections:
        try:
            # Extract URL or public_id
            if isinstance(conn, str):
                url = conn.strip()
                name = None
            else:
                url = conn.get('linkedin_url', '').strip()
                name = conn.get('name')
            
            if not url:
                skipped += 1
                continue
            
            # Convert URL to public_id
            public_id = url_to_public_id(url)
            if not public_id:
                errors.append(f"Invalid URL: {url}")
                skipped += 1
                continue
            
            # Create or get Lead
            lead, lead_created = Lead.objects.get_or_create(
                public_identifier=public_id,
                defaults={"linkedin_url": url}
            )
            
            # Check if this lead already has a deal in this campaign
            existing_deal = Deal.objects.filter(lead=lead, campaign=campaign).first()
            if existing_deal:
                skipped += 1
                continue
            
            # Create Deal in QUALIFIED state
            # This puts the lead into the system so it can be enriched and embedded
            deal = Deal.objects.create(
                lead=lead,
                campaign=campaign,
                state=DealState.QUALIFIED,
                reason="1st-degree connection added - needs qualification",
            )
            
            created += 1
            batch.append(lead.pk)
            
        except Exception as e:
            errors.append(f"Error processing {conn}: {str(e)}")
            skipped += 1
        
        # Process batch periodically
        if len(batch) >= batch_size:
            print(f"Processed batch: {created} created, {skipped} skipped")
            batch = []
    
    print(f"\n{'='*50}")
    print(f"Bulk import complete!")
    print(f"{'='*50}")
    print(f"Total processed: {len(connections)}")
    print(f"Leads created: {created}")
    print(f"Already existed/skipped: {skipped}")
    
    if errors:
        print(f"\nErrors ({len(errors)}):")
        for err in errors[:10]:  # Show first 10 errors
            print(f"  - {err}")
        if len(errors) > 10:
            print(f"  ... and {len(errors) - 10} more errors")
    
    print(f"\nNext steps:")
    print(f"1. Start the OpenOutreach daemon to run qualification:")
    print(f"   make run")
    print(f"2. The AI will automatically qualify each lead and decide if they fit your ICP")
    print(f"3. Qualified leads will go to the follow-up queue automatically")
    
    return created

def main():
    parser = argparse.ArgumentParser(
        description="Bulk import LinkedIn 1st-degree connections for LenGrowth outreach"
    )
    parser.add_argument(
        '--source', '-s',
        required=True,
        help="Path to CSV or JSON file with LinkedIn connections"
    )
    parser.add_argument(
        '--campaign', '-c',
        default="LenGrowth Outreach",
        help="Campaign name (default: LenGrowth Outreach)"
    )
    parser.add_argument(
        '--batch-size', '-b',
        type=int,
        default=100,
        help="Batch size for database operations (default: 100)"
    )
    
    args = parser.parse_args()
    
    # Validate input file
    source_path = Path(args.source)
    if not source_path.exists():
        print(f"Error: Source file not found: {args.source}")
        sys.exit(1)
    
    print(f"\n{'='*50}")
    print("LinkedIn 1st-Degree Connections Bulk Import")
    print(f"{'='*50}\n")
    
    # Setup Django
    setup_django()
    
    # Get or create campaign
    campaign = get_or_create_campaign(args.campaign)
    
    # Parse connections file
    ext = source_path.suffix.lower()
    if ext == '.csv':
        connections = parse_csv_file(args.source)
    elif ext == '.json':
        connections = parse_json_file(args.source)
    else:
        # Try to detect format
        with open(args.source, 'r') as f:
            first_char = f.read(1)
            if first_char == '[':
                connections = parse_json_file(args.source)
            else:
                connections = parse_csv_file(args.source)
    
    print(f"Found {len(connections)} connections to process\n")
    
    # Process connections
    process_connections(campaign, connections, args.batch_size)
    
    print(f"\nNext steps:")
    print(f"1. Make sure your .env file has your LinkedIn credentials")
    print(f"2. Start the OpenOutreach daemon: make run")
    print(f"3. The AI will start messaging your 1st-degree connections automatically")

if __name__ == "__main__":
    main()