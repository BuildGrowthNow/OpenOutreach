"""Explicit, idempotent legacy state-machine migration.

Default mode is a report-only dry run. ``--apply`` updates only campaigns whose
legacy graph can be translated and whose canonical sequence is empty. It never
drops legacy collections; take a database backup and record the report before
using it in production.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

from openoutreach.core.sequence_schema import validate_sequence_graph
from openoutreach.mongodb.connection import get_mongodb_collection, initialize_mongodb_connection


def _translate_node(node: dict) -> dict:
    kind = node.get("node_type")
    config = node.get("config") or {}
    if kind == "start":
        return {"id": str(node.get("_id")), "type": "action", "data": {"label": node.get("name") or "Start", "action": "connect", "channel": "linkedin", "requires": []}, "position": {"x": node.get("x", 0), "y": node.get("y", 0)}}
    if kind in {"wait"}:
        return {"id": str(node.get("_id")), "type": "wait", "data": {"label": node.get("name") or "Wait", "wait_days": config.get("wait_days", config.get("days", 1)), "wait_hours": config.get("wait_hours", config.get("hours", 0))}, "position": {"x": node.get("x", 0), "y": node.get("y", 0)}}
    if kind in {"end"}:
        return {"id": str(node.get("_id")), "type": "end", "data": {"label": node.get("name") or "End"}, "position": {"x": node.get("x", 0), "y": node.get("y", 0)}}
    action = config.get("action")
    channel = config.get("channel")
    if action in {"connect", "follow_up", "send_email", "send_whatsapp"}:
        return {"id": str(node.get("_id")), "type": "action", "data": {"label": node.get("name") or action, "action": action, "channel": channel, "requires": config.get("requires", [])}}
    raise ValueError(f"unsupported legacy node type {kind!r}")


def migrate(apply: bool = False) -> dict:
    graphs = get_mongodb_collection("campaign_state_graphs")
    nodes = get_mongodb_collection("state_nodes")
    transitions = get_mongodb_collection("state_transitions")
    campaigns = get_mongodb_collection("campaigns")
    report = {"dry_run": not apply, "migrated": 0, "skipped": 0, "failures": []}
    if any(collection is None for collection in (graphs, nodes, transitions, campaigns)):
        report["failures"].append("one or more required collections are unavailable")
        return report
    for graph in graphs.find({}, {"_id": 1, "campaign_id": 1}):
        campaign_id = str(graph.get("campaign_id") or "")
        legacy_nodes = list(nodes.find({"state_graph_id": graph.get("_id"), "is_active": {"$ne": False}}).sort("x", 1))
        legacy_transitions = list(transitions.find({"state_graph_id": graph.get("_id"), "is_active": {"$ne": False}}).sort("order", 1))
        try:
            translated = [_translate_node(node) for node in legacy_nodes]
            translated_ids = {node["id"] for node in translated}
            edges = [{"id": str(item.get("_id")), "source": str(item.get("source_node_id")), "target": str(item.get("target_node_id")), "data": ({"condition": item.get("condition_type")} if item.get("condition_type") in {"yes", "no"} else {})} for item in legacy_transitions]
            if not campaign_id or not translated or any(edge["source"] not in translated_ids or edge["target"] not in translated_ids for edge in edges):
                raise ValueError("missing campaign or dangling legacy edge")
            errors = validate_sequence_graph(translated, edges)
            if errors:
                raise ValueError(f"canonical validation failed ({len(errors)} errors)")
            target = campaigns.find_one({"_id": campaign_id}, {"sequence_steps": 1})
            if not target or target.get("sequence_steps"):
                report["skipped"] += 1
                continue
            if apply:
                campaigns.update_one({"_id": campaign_id, "sequence_steps": {"$in": [[], None]}}, {"$set": {"sequence_steps": translated, "sequence_edges": edges, "sequence_schema_version": 1, "sequence_active": False, "legacy_migration_at": datetime.now(timezone.utc)}})
            report["migrated"] += 1
        except Exception as exc:
            report["failures"].append({"campaign_id_present": bool(campaign_id), "reason": str(exc)[:200]})
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="write canonical graphs; default is read-only")
    args = parser.parse_args()
    if not initialize_mongodb_connection():
        raise SystemExit("MongoDB connection unavailable")
    print(json.dumps(migrate(apply=args.apply), sort_keys=True))
