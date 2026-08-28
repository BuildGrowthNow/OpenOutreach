"""
MongoDB Indexes for Production Performance

Ensures all 37 indexes across 18 collections are created for optimal query performance.
"""

import logging
from .connection import mongodb_connection, get_mongodb

logger = logging.getLogger(__name__)


def ensure_all_indexes():
    """
    Create all indexes needed for production performance.
    Idempotent - safe to run multiple times.
    """
    if not mongodb_connection.client:
        logger.warning("MongoDB not connected, skipping index creation")
        return

    db = get_mongodb()
    if db is None:
        logger.warning("MongoDB database not available, skipping index creation")
        return

    # Define all indexes
    # Format: (collection_name, [(keys, options), ...])
    indexes = [
        # Users
        ('users', [
            ({'email': 1}, {'name': 'user_email_idx', 'unique': True}),
            ({'is_active': 1}, {'name': 'user_active_idx'}),
        ]),

        # Tasks (critical for daemon)
        ('tasks', [
            ({'status': 1, 'scheduled_at': 1}, {'name': 'task_queue_idx'}),
            ({'linkedin_profile_id': 1, 'status': 1, 'scheduled_at': 1}, {'name': 'task_profile_queue_idx'}),
            ({'linkedin_profile_id': 1, 'channel': 1, 'status': 1, 'scheduled_at': 1}, {'name': 'task_profile_channel_queue_idx'}),
            ({'user_id': 1, 'status': 1}, {'name': 'task_user_status_idx'}),
            ({'payload.campaign_id': 1}, {'name': 'task_campaign_idx'}),
            ({'payload.deal_id': 1, 'task_type': 1, 'status': 1}, {'name': 'task_deal_type_idx'}),
            ({'payload.deal_id': 1, 'payload.step_id': 1, 'status': 1}, {'name': 'task_sequence_step_idx'}),
        ]),

        # Campaigns
        ('campaigns', [
            ({'user_id': 1}, {'name': 'campaign_user_idx'}),
            ({'linkedin_profile_id': 1}, {'name': 'campaign_profile_idx'}),
            ({'status': 1}, {'name': 'campaign_status_idx'}),
            ({'is_paused': 1}, {'name': 'campaign_paused_idx'}),
        ]),

        # Deals
        ('deals', [
            ({'campaign_id': 1, 'state': 1}, {'name': 'deal_campaign_state_idx'}),
            ({'campaign_id': 1, 'state': 1, 'active_channel': 1}, {'name': 'deal_campaign_state_channel_idx'}),
            ({'lead_id': 1}, {'name': 'deal_lead_idx'}),
            ({'user_id': 1}, {'name': 'deal_user_idx'}),
            ({'lead_id': 1, 'campaign_id': 1}, {'name': 'deal_lead_campaign_unique', 'unique': True}),
            ({'mailbox_id': 1, 'email_sent_at': 1}, {'name': 'deal_mailbox_sent_idx', 'sparse': True}),
            ({'state': 1, 'next_check_pending_at': 1}, {'name': 'deal_pending_check_idx', 'sparse': True}),
        ]),

        # Leads
        ('leads', [
            ({'public_identifier': 1}, {'name': 'lead_public_id_idx', 'unique': True, 'sparse': True}),
            ({'linkedin_url': 1}, {'name': 'lead_url_idx'}),
            ({'user_id': 1}, {'name': 'lead_user_idx'}),
            ({'disqualified': 1}, {'name': 'lead_disqualified_idx'}),
            ({'phone': 1}, {'name': 'lead_phone_unique_idx', 'unique': True, 'sparse': True}),
        ]),

        # WhatsApp Profiles
        ('whatsapp_profiles', [
            ({'user_id': 1}, {'name': 'wa_profile_user_idx'}),
            ({'status': 1}, {'name': 'wa_profile_status_idx'}),
            ({'phone_number': 1}, {'name': 'wa_profile_phone_unique_idx', 'unique': True, 'sparse': True}),
        ]),

        # LinkedIn Profiles
        ('linkedin_profiles', [
            ({'user_id': 1}, {'name': 'profile_user_idx'}),
            ({'linkedin_username': 1}, {'name': 'profile_username_unique_idx', 'unique': True, 'sparse': True}),
            ({'active': 1}, {'name': 'profile_active_idx'}),
            ({'user_id': 1, 'is_active': 1}, {'name': 'profile_user_active_idx'}),
        ]),

        # Action Logs
        ('action_logs', [
            ({'linkedin_profile_id': 1, 'action_type': 1, 'created_at': -1}, {'name': 'action_profile_type_time_idx'}),
            ({'campaign_id': 1, 'created_at': -1}, {'name': 'action_campaign_time_idx'}),
            ({'status': 1, 'created_at': -1}, {'name': 'action_status_time_idx'}),
            ({'user_id': 1, 'created_at': -1}, {'name': 'action_user_time_idx'}),
        ]),

        # Chat Messages
        ('chat_messages', [
            ({'deal_id': 1, 'creation_date': -1}, {'name': 'message_deal_time_idx'}),
            ({'deal_id': 1, 'linkedin_urn': 1}, {'name': 'message_deal_urn_unique', 'unique': True}),
            ({'is_outgoing': 1, 'creation_date': -1}, {'name': 'message_direction_time_idx'}),
            ({'wa_msg_hash': 1}, {'name': 'message_wa_hash_idx', 'unique': True, 'sparse': True}),
        ]),

        # Notifications
        ('notifications', [
            ({'recipient_id': 1, 'is_read': 1}, {'name': 'notification_recipient_read_idx'}),
            ({'created_at': -1}, {'name': 'notification_time_idx'}),
            ({'recipient_id': 1, 'created_at': -1}, {'name': 'notification_recipient_time_idx'}),
            ({'notification_type': 1, 'created_at': -1}, {'name': 'notification_type_time_idx'}),
        ]),

        # Tracked Links
        ('tracked_links', [
            ({'short_code': 1}, {'name': 'link_shortcode_unique', 'unique': True}),
            ({'campaign_id': 1}, {'name': 'link_campaign_idx'}),
            ({'user_id': 1}, {'name': 'link_user_idx'}),
            ({'is_active': 1}, {'name': 'link_active_idx'}),
        ]),

        # Link Clicks
        ('link_clicks', [
            ({'link_id': 1, 'clicked_at': -1}, {'name': 'click_link_time_idx'}),
            ({'ip_address': 1, 'clicked_at': -1}, {'name': 'click_ip_time_idx'}),
        ]),

        # Link Deal Conversions
        ('link_deal_conversions', [
            ({'link_id': 1}, {'name': 'conversion_link_idx'}),
            ({'deal_id': 1}, {'name': 'conversion_deal_idx'}),
            ({'converted_at': -1}, {'name': 'conversion_time_idx'}),
        ]),

        # Search Keywords
        ('search_keywords', [
            ({'campaign_id': 1, 'keyword': 1}, {'name': 'keyword_campaign_unique', 'unique': True}),
            ({'campaign_id': 1, 'used': 1}, {'name': 'keyword_unused_idx'}),
        ]),

        # State Machine
        ('campaign_state_graphs', [
            ({'campaign_id': 1}, {'name': 'graph_campaign_unique', 'unique': True}),
            ({'is_active': 1}, {'name': 'graph_active_idx'}),
        ]),

        ('state_nodes', [
            ({'state_graph_id': 1}, {'name': 'node_graph_idx'}),
            ({'node_type': 1}, {'name': 'node_type_idx'}),
        ]),

        ('state_transitions', [
            ({'state_graph_id': 1}, {'name': 'transition_graph_idx'}),
            ({'source_node_id': 1}, {'name': 'transition_source_idx'}),
            ({'target_node_id': 1}, {'name': 'transition_target_idx'}),
        ]),

        ('campaign_states', [
            ({'deal_id': 1, 'status': 1}, {'name': 'state_deal_status_idx'}),
            ({'state_graph_id': 1, 'status': 1}, {'name': 'state_graph_status_idx'}),
            ({'wait_until': 1}, {'name': 'state_wait_idx', 'sparse': True}),
        ]),

        ('campaign_execution_logs', [
            ({'state_machine_id': 1, 'timestamp': -1}, {'name': 'exec_log_machine_time_idx'}),
        ]),

        # Health
        ('campaign_health_metrics', [
            ({'campaign_id': 1, 'timestamp': -1}, {'name': 'health_campaign_time_idx'}),
        ]),

        ('health_alerts', [
            ({'campaign_id': 1, 'is_resolved': 1}, {'name': 'alert_campaign_resolved_idx'}),
            ({'severity': 1, 'created_at': -1}, {'name': 'alert_severity_time_idx'}),
        ]),

        ('recovery_actions', [
            ({'campaign_id': 1, 'executed_at': -1}, {'name': 'recovery_campaign_time_idx'}),
        ]),

        # Rate Limits
        ('smart_rate_limit_contexts', [
            ({'linkedin_profile_id': 1}, {'name': 'rate_limit_profile_unique', 'unique': True}),
            ({'last_action_at': -1}, {'name': 'rate_limit_action_time_idx'}),
        ]),

        ('rate_limit_warnings', [
            ({'linkedin_profile_id': 1, 'at_time': -1}, {'name': 'warning_profile_time_idx'}),
            ({'resolved': 1, 'at_time': -1}, {'name': 'warning_resolved_time_idx'}),
        ]),

        # Site Config
        ('site_config', [
            ({'user_id': 1}, {'name': 'config_user_unique', 'unique': True, 'sparse': True}),
        ]),

        # Billing
        ('stripe_plans', [
            ({'plan_name': 1}, {'name': 'stripe_plan_name_idx', 'unique': True}),
        ]),


        ('webhook_events', [
            ({'stripe_event_id': 1}, {'name': 'webhook_event_id_idx', 'unique': True}),
            ({'processed_at': -1}, {'name': 'webhook_processed_time_idx'}),
        ]),

        # Lead Personas
        ('lead_personas', [
            ({'lead_id': 1, 'campaign_id': 1}, {'name': 'persona_lead_campaign_unique', 'unique': True}),
            ({'campaign_id': 1}, {'name': 'persona_campaign_idx'}),
        ]),

        # Notes
        ('notes', [
            ({'deal_id': 1, 'created_at': -1}, {'name': 'note_deal_time_idx'}),
            ({'user_id': 1, 'created_at': -1}, {'name': 'note_user_time_idx'}),
        ]),

        # User Profiles
        ('user_profiles', [
            ({'user_id': 1}, {'name': 'user_profile_user_unique', 'unique': True}),
            ({'email': 1}, {'name': 'user_profile_email_idx'}),
        ]),

        # LinkedIn Credentials
        ('linkedin_credentials', [
            ({'linkedin_profile_id': 1}, {'name': 'creds_profile_idx'}),
            ({'user_id': 1}, {'name': 'creds_user_idx'}),
            ({'status': 1}, {'name': 'creds_status_idx'}),
            ({'is_primary': 1}, {'name': 'creds_primary_idx'}),
        ]),

        # LinkedIn Credential Logs
        ('linkedin_credential_logs', [
            ({'credential_id': 1, 'created_at': -1}, {'name': 'creds_log_cred_time_idx'}),
            ({'action': 1, 'created_at': -1}, {'name': 'creds_log_action_time_idx'}),
        ]),

        # Mailboxes
        ('mailboxes', [
            ({'user_id': 1}, {'name': 'mailbox_user_idx'}),
            ({'from_address': 1}, {'name': 'mailbox_from_idx'}),
        ]),

        # Email domain pattern cache (free enrichment waterfall)
        ('email_domain_patterns', [
            ({'company_name': 1}, {'name': 'email_domain_company_idx'}),
            ({'updated_at': 1}, {'name': 'email_domain_updated_idx'}),
        ]),

        # Campaign Templates
        ('campaign_templates', [
            ({'created_by_id': 1}, {'name': 'template_creator_idx'}),
            ({'is_public': 1}, {'name': 'template_public_idx'}),
        ]),

        ('sequence_events', [
            ({'campaign_id': 1, 'created_at': -1}, {'name': 'sequence_event_campaign_time_idx'}),
            ({'deal_id': 1, 'step_id': 1, 'created_at': -1}, {'name': 'sequence_event_deal_step_idx'}),
        ]),

        # Ghost Mode
        ('ghost_campaigns', [
            ({'campaign_id': 1}, {'name': 'ghost_campaign_idx'}),
            ({'is_active': 1}, {'name': 'ghost_active_idx'}),
        ]),

        ('ghost_simulation_logs', [
            ({'ghost_campaign_id': 1, 'started_at': -1}, {'name': 'ghost_sim_campaign_time_idx'}),
        ]),

        ('ghost_test_scenarios', [
            ({'is_public': 1}, {'name': 'ghost_scenario_public_idx'}),
            ({'created_by_id': 1}, {'name': 'ghost_scenario_creator_idx'}),
        ]),

        # Smart Rate Limiting (additional indexes)
        ('smart_rate_limit_contexts', [
            ({'detectability_score': 1}, {'name': 'rate_context_detect_idx'}),
        ]),

        ('rate_limit_warnings', [
            ({'resolved': 1, 'warning_level': 1}, {'name': 'rate_warn_status_idx'}),
        ]),

        # State Machine (additional indexes)
        ('campaign_state_graphs', [
            ({'is_active': 1, 'is_valid': 1}, {'name': 'state_graph_active_valid_idx'}),
        ]),

        ('state_nodes', [
            ({'state_graph_id': 1, 'x': 1}, {'name': 'state_node_graph_x_idx'}),
            ({'node_type': 1, 'is_active': 1}, {'name': 'state_node_type_active_idx'}),
        ]),

        ('state_transitions', [
            ({'state_graph_id': 1, 'order': 1}, {'name': 'state_trans_graph_order_idx'}),
        ]),

        ('campaign_states', [
            ({'deal_id': 1, 'is_active': 1}, {'name': 'campaign_state_deal_idx'}),
            ({'state_graph_id': 1, 'completed': 1}, {'name': 'campaign_state_graph_complete_idx'}),
        ]),

        ('campaign_execution_logs', [
            ({'campaign_state_id': 1, 'executed_at': -1}, {'name': 'exec_log_state_time_idx'}),
            ({'node_id': 1, 'result': 1}, {'name': 'exec_log_node_result_idx'}),
        ]),

        # Campaign Health Monitoring (additional indexes)
        ('campaign_health_metrics', [
            ({'errors_total': 1, 'timestamp': -1}, {'name': 'health_metric_errors_idx'}),
        ]),

        ('health_alerts', [
            ({'campaign_id': 1, 'is_resolved': 1, 'created_at': -1}, {'name': 'health_alert_campaign_idx'}),
            ({'severity': 1, 'is_resolved': 1}, {'name': 'health_alert_severity_idx'}),
        ]),

        ('recovery_actions', [
            ({'campaign_id': 1, 'executed_at': -1}, {'name': 'recovery_campaign_time_idx'}),
            ({'alert_id': 1}, {'name': 'recovery_alert_idx'}),
        ]),

        ('ip_signup_attempts', [
            ({'ip_address': 1, 'created_at': -1}, {'name': 'ip_signup_time_idx'}),
            ({'created_at': 1}, {'name': 'signup_time_idx'}),
        ]),


        ('admin_audit_logs', [
            ({'admin_user_id': 1, 'created_at': -1}, {'name': 'audit_admin_time_idx'}),
            ({'target_user_id': 1, 'created_at': -1}, {'name': 'audit_target_time_idx'}),
            ({'action': 1, 'created_at': -1}, {'name': 'audit_action_time_idx'}),
        ]),

        # Referrals and Coupons
        ('referral_codes', [
            ({'user_id': 1}, {'name': 'referral_user_idx'}),
            ({'code': 1}, {'name': 'referral_code_unique_idx', 'unique': True}),
        ]),

        ('coupons', [
            ({'code': 1}, {'name': 'coupon_code_unique_idx', 'unique': True}),
            ({'valid_from': 1, 'valid_until': 1}, {'name': 'coupon_valid_idx'}),
            ({'stripe_coupon_id': 1}, {'name': 'coupon_stripe_id_idx'}),
        ]),

        # Daemon v2 identity, one-time enrollment, and refresh rotation.
        ('daemon_enrollment_codes', [
            ({'code_hash': 1}, {'name': 'daemon_enrollment_code_hash_unique', 'unique': True}),
            ({'expires_at': 1}, {'name': 'daemon_enrollment_expiry_ttl', 'expireAfterSeconds': 0}),
            ({'user_id': 1, 'used': 1}, {'name': 'daemon_enrollment_user_used_idx'}),
        ]),
        ('daemon_devices', [
            ({'user_id': 1, 'revoked': 1}, {'name': 'daemon_device_user_status_idx'}),
            ({'user_id': 1, 'last_seen_at': -1}, {'name': 'daemon_device_user_seen_idx'}),
        ]),
        ('daemon_refresh_families', [
            ({'device_id': 1, 'token_hash': 1}, {'name': 'daemon_refresh_device_hash_unique', 'unique': True}),
            ({'family_id': 1, 'used': 1, 'revoked': 1}, {'name': 'daemon_refresh_family_state_idx'}),
            ({'expires_at': 1}, {'name': 'daemon_refresh_expiry_ttl', 'expireAfterSeconds': 0}),
        ]),
        ('daemon_nonces', [
            ({'device_id': 1, 'nonce': 1}, {'name': 'daemon_nonce_unique', 'unique': True}),
            ({'expires_at': 1}, {'name': 'daemon_nonce_expiry_ttl', 'expireAfterSeconds': 0}),
        ]),
        ('daemon_events', [
            ({'user_id': 1, 'device_id': 1, 'event_id': 1}, {'name': 'daemon_event_dedupe_unique', 'unique': True}),
            ({'user_id': 1, 'created_at': -1}, {'name': 'daemon_event_tenant_time_idx'}),
        ]),
        ('security_audit_events', [
            ({'created_at': -1}, {'name': 'security_event_time_idx'}),
            ({'event': 1, 'created_at': -1}, {'name': 'security_event_type_time_idx'}),
            ({'tenant_id': 1, 'created_at': -1}, {'name': 'security_event_tenant_time_idx'}),
        ]),
        ('tasks', [
            ({'user_id': 1, 'linkedin_profile_id': 1, 'channel': 1, 'status': 1, 'scheduled_at': 1}, {'name': 'daemon_v2_task_claim_idx'}),
            ({'user_id': 1, 'leased_by_device_id': 1, 'lease_id': 1, 'status': 1}, {'name': 'daemon_v2_task_lease_idx'}),
        ]),
    ]

    created_count = 0
    skipped_count = 0
    error_count = 0

    for collection_name, collection_indexes in indexes:
        try:
            collection = db[collection_name]

            # Get existing indexes for this collection
            existing_indexes = set()
            try:
                existing_indexes = {idx["name"] for idx in collection.list_indexes()}
            except Exception as e:
                logger.debug(f"Could not list indexes for '{collection_name}': {e}")

            for keys, options in collection_indexes:
                index_name = options.get("name", "")

                # Skip if already exists
                if index_name in existing_indexes:
                    logger.debug(f"Index '{index_name}' already exists on '{collection_name}', skipping")
                    skipped_count += 1
                    continue

                try:
                    # Create the index
                    index_keys = []
                    if isinstance(keys, dict):
                        index_keys = list(keys.items())
                    else:
                        index_keys = keys

                    # Extract options, removing 'name' as it's passed separately
                    create_options = {k: v for k, v in options.items() if k != 'name'}

                    collection.create_index(index_keys, name=index_name, **create_options)
                    logger.info(f"Created index '{index_name}' on '{collection_name}'")
                    created_count += 1

                except Exception as e:
                    logger.error(f"Failed to create index '{index_name}' on '{collection_name}': {e}")
                    error_count += 1

        except Exception as e:
            logger.error(f"Failed to process indexes for collection '{collection_name}': {e}")
            error_count += 1

    # Summary
    total = created_count + skipped_count + error_count
    logger.info(
        f"Index creation complete: {created_count} created, "
        f"{skipped_count} skipped (already exist), {error_count} errors, "
        f"{total} total"
    )

    return {
        "created": created_count,
        "skipped": skipped_count,
        "errors": error_count,
        "total": total
    }


def drop_all_indexes():
    """
    Drop all indexes (except _id) from all collections.
    DANGEROUS - Use only for testing/development.
    """
    if not mongodb_connection.client:
        logger.warning("MongoDB not connected")
        return

    db = get_mongodb()
    if db is None:
        return

    collection_names = db.list_collection_names()

    for collection_name in collection_names:
        try:
            collection = db[collection_name]

            # Get all indexes except _id_
            indexes_to_drop = []
            for idx in collection.list_indexes():
                if idx["name"] != "_id_":
                    indexes_to_drop.append(idx["name"])

            # Drop each index
            for idx_name in indexes_to_drop:
                try:
                    collection.drop_index(idx_name)
                    logger.info(f"Dropped index '{idx_name}' from '{collection_name}'")
                except Exception as e:
                    logger.error(f"Failed to drop index '{idx_name}' from '{collection_name}': {e}")

        except Exception as e:
            logger.error(f"Failed to process collection '{collection_name}': {e}")


__all__ = ['ensure_all_indexes', 'drop_all_indexes']
