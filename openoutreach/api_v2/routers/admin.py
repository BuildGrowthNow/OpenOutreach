"""
Admin Panel API endpoints - user management, finance, and platform administration.
"""
import logging
from datetime import datetime, timedelta, timezone as tz
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from openoutreach.api_v2.dependencies import get_admin_user
from openoutreach.mongodb.models_user import User
from openoutreach.mongodb.connection import get_mongodb_collection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])


class UserDetailResponse(BaseModel):
    """Response model for user details."""
    id: str
    email: str
    full_name: str
    created_at: str
    updated_at: str
    last_login: Optional[str]
    last_login_ip: Optional[str]
    signup_ip: Optional[str]
    status: str
    plan: str
    subscription_status: str
    billing_period: Optional[str]
    trial_ends_at: Optional[str]
    current_period_end: Optional[str]
    linkedin_account_limit: int
    campaign_limit: Optional[int]
    cloud_profiles: int
    is_admin: bool
    admin_role: Optional[str]
    admin_notes: Optional[str]
    stripe_customer_id: Optional[str]
    stripe_subscription_id: Optional[str]
    referral_code: Optional[str]
    referrer_id: Optional[str]
    referral_credits_earned: int
    email_verified: bool
    is_deleted: bool
    deleted_at: Optional[str]


class UserListItem(BaseModel):
    """Response model for user list items."""
    id: str
    email: str
    full_name: str
    created_at: str
    signup_date: str
    last_login: Optional[str]
    status: str
    plan: str
    subscription_status: str
    linkedin_profiles_count: int
    campaigns_count: int


class UserUpdateRequest(BaseModel):
    """Request model to update user."""
    status: Optional[str] = None
    plan: Optional[str] = None
    admin_role: Optional[str] = None
    notes: Optional[str] = None


class AdminNotesResponse(BaseModel):
    """Response model for admin notes."""
    notes: Optional[str]


class FinanceMetricsResponse(BaseModel):
    """Response model for finance metrics."""
    total_users: int
    active_subscriptions: int
    trialing_users: int
    mrr: float
    arr: float
    trial_conversion_rate: float
    churn_rate: float


class InvoiceDetailResponse(BaseModel):
    """Response model for invoice details."""
    id: str
    user_id: str
    user_email: str
    amount: int
    status: str
    created: int
    period_start: int
    period_end: int
    pdf_url: Optional[str]


class LinkedInProfileInfoResponse(BaseModel):
    """Response model for LinkedIn profile info."""
    id: str
    username: Optional[str]
    display_name: Optional[str]
    is_active: bool
    created_at: str
    execution_mode: str
    daemon_status: str
    daemon_last_seen: Optional[str]
    daemon_version: Optional[str]
    daemon_platform: Optional[str]
    daemon_browser: Optional[str]
    daemon_ip: Optional[str]
    last_heartbeat: Optional[str]
    is_logged_in: bool
    requires_verification: bool
    verification_type: Optional[str]
    connect_daily_limit: int
    follow_up_daily_limit: int
    proxy_server: Optional[str]


class CampaignInfoResponse(BaseModel):
    """Response model for campaign info."""
    id: str
    name: str
    is_paused: bool
    created_at: str
    leads_count: int


def _dt(value: Optional[datetime]) -> Optional[str]:
    """Safely convert a datetime to ISO string."""
    return value.isoformat() if value else None


def _build_user_detail_response(user: User) -> UserDetailResponse:
    """Build a UserDetailResponse from a User model instance."""
    return UserDetailResponse(
        id=user._id,
        email=user.email,
        full_name=user.full_name,
        created_at=_dt(user.created_at) or "",
        updated_at=_dt(user.updated_at) or "",
        last_login=_dt(user.last_login),
        last_login_ip=getattr(user, "last_login_ip", None),
        signup_ip=getattr(user, "signup_ip", None),
        status=user.status,
        plan=user.plan,
        subscription_status=user.subscription_status,
        billing_period=user.billing_period,
        trial_ends_at=_dt(user.trial_ends_at),
        current_period_end=_dt(user.current_period_end),
        linkedin_account_limit=user.linkedin_account_limit,
        campaign_limit=user.campaign_limit,
        cloud_profiles=user.cloud_profiles,
        is_admin=user.is_admin,
        admin_role=user.admin_role,
        admin_notes=user.admin_notes,
        stripe_customer_id=user.stripe_customer_id,
        stripe_subscription_id=user.stripe_subscription_id,
        referral_code=user.referral_code,
        referrer_id=user.referrer_id,
        referral_credits_earned=user.referral_credits_earned,
        email_verified=user.email_verified,
        is_deleted=user.is_deleted,
        deleted_at=_dt(user.deleted_at),
    )


def _get_plan_limits(plan_name: str):
    """Get plan limits from billing plans."""
    try:
        from openoutreach.billing.plans import get_plan
        return get_plan(plan_name)
    except ImportError:
        logger.warning("Failed to import billing plans")
        return None



@router.get("/users", dependencies=[Depends(get_admin_user)])
async def list_users(
    status_filter: Optional[str] = Query(None, alias="status"),
    plan: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
) -> dict:
    """Paginated user list with optional filters."""
    users_collection = get_mongodb_collection("users")
    if users_collection is None:
        raise HTTPException(
            status_code=500,
            detail="Database unavailable",
        )

    query: dict = {}

    if status_filter:
        query["status"] = status_filter
    if plan:
        query["plan"] = plan
    if search:
        query["$or"] = [
            {"email": {"$regex": search, "$options": "i"}},
            {"full_name": {"$regex": search, "$options": "i"}},
        ]

    total = users_collection.count_documents(query)
    users_data = list(users_collection.find(query).skip(skip).limit(limit))

    users_list = []
    for user_doc in users_data:
        user = User.from_dict(user_doc)

        linkedin_profiles_collection = get_mongodb_collection("linkedin_profiles")
        linkedin_count = 0
        if linkedin_profiles_collection is not None:
            linkedin_count = linkedin_profiles_collection.count_documents(
                {"user_id": user._id, "is_active": True}
            )

        campaigns_collection = get_mongodb_collection("campaigns")
        campaigns_count = 0
        if campaigns_collection is not None:
            campaigns_count = campaigns_collection.count_documents(
                {"user_id": user._id, "is_paused": False}
            )

        users_list.append(
            UserListItem(
                id=user._id,
                email=user.email,
                full_name=user.full_name,
                created_at=user.created_at.isoformat() if user.created_at else "",
                signup_date=user.created_at.isoformat() if user.created_at else "",
                last_login=user.last_login.isoformat() if user.last_login else None,
                status=user.status,
                plan=user.plan,
                subscription_status=user.subscription_status,
                linkedin_profiles_count=linkedin_count,
                campaigns_count=campaigns_count,
            )
        )

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "users": users_list,
    }


@router.get("/users/{user_id}", dependencies=[Depends(get_admin_user)])
async def get_user_detail(user_id: str) -> UserDetailResponse:
    """Get full user details."""
    user = User.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return _build_user_detail_response(user)


@router.patch("/users/{user_id}", dependencies=[Depends(get_admin_user)])
async def update_user(user_id: str, request: UserUpdateRequest) -> UserDetailResponse:
    """Update user status, plan, or admin role."""
    user = User.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if request.status is not None:
        if request.status not in ["active", "blocked", "inactive"]:
            raise HTTPException(
                status_code=400,
                detail="Invalid status",
            )
        user.status = request.status
        logger.info(f"Admin updated user {user_id} status to {request.status}")

    if request.plan is not None:
        plan = _get_plan_limits(request.plan)
        if not plan:
            raise HTTPException(
                status_code=400,
                detail="Invalid plan",
            )
        user.plan = request.plan
        user.linkedin_account_limit = plan["max_linkedin_accounts"]
        user.campaign_limit = plan["max_campaigns"]
        logger.info(f"Admin changed user {user_id} plan to {request.plan}")

    if request.admin_role is not None:
        user.admin_role = request.admin_role
        logger.info(f"Admin updated user {user_id} role to {request.admin_role}")

    if request.notes is not None:
        user.admin_notes = request.notes
        logger.info(f"Admin updated notes for user {user_id}")

    user.save()

    return _build_user_detail_response(user)


@router.get("/users/{user_id}/linkedin-profiles", dependencies=[Depends(get_admin_user)])
async def get_user_linkedin_profiles(user_id: str) -> dict:
    """Get user's LinkedIn profiles."""
    user = User.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    profiles_collection = get_mongodb_collection("linkedin_profiles")
    if profiles_collection is None:
        return {"profiles": []}

    profiles_data = list(profiles_collection.find({"user_id": user_id}))

    now = datetime.now(tz.utc)
    five_min_ago = now - timedelta(minutes=5)

    def _build_profile(p: dict) -> LinkedInProfileInfoResponse:
        heartbeat = p.get("last_heartbeat")
        is_online = heartbeat is not None and heartbeat >= five_min_ago
        daemon_status = "online" if is_online else "offline"
        proxy_raw: Optional[str] = p.get("proxy_server")
        proxy_host: Optional[str] = None
        if proxy_raw:
            try:
                from urllib.parse import urlparse
                parsed = urlparse(proxy_raw)
                proxy_host = parsed.hostname or proxy_raw
            except Exception:
                proxy_host = proxy_raw
        return LinkedInProfileInfoResponse(
            id=str(p.get("_id")),
            username=p.get("username") or p.get("linkedin_username"),
            display_name=p.get("display_name"),
            is_active=p.get("is_active", True),
            created_at=p["created_at"].isoformat() if isinstance(p.get("created_at"), datetime) else str(p.get("created_at", "")),
            execution_mode=p.get("execution_mode", "desktop"),
            daemon_status=daemon_status,
            daemon_last_seen=heartbeat.isoformat() if isinstance(heartbeat, datetime) else None,
            daemon_version=p.get("daemon_version"),
            daemon_platform=p.get("daemon_platform"),
            daemon_browser=p.get("daemon_browser"),
            daemon_ip=p.get("daemon_ip"),
            last_heartbeat=heartbeat.isoformat() if isinstance(heartbeat, datetime) else None,
            is_logged_in=bool(p.get("is_logged_in", False)),
            requires_verification=bool(p.get("requires_verification", False)),
            verification_type=p.get("verification_type"),
            connect_daily_limit=p.get("connect_daily_limit", 20),
            follow_up_daily_limit=p.get("follow_up_daily_limit", 20),
            proxy_server=proxy_host,
        )

    profiles = [_build_profile(p) for p in profiles_data]
    return {"profiles": profiles}


@router.get("/users/{user_id}/campaigns", dependencies=[Depends(get_admin_user)])
async def get_user_campaigns(user_id: str) -> dict:
    """Get user's campaigns."""
    user = User.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    campaigns_collection = get_mongodb_collection("campaigns")
    if campaigns_collection is None:
        return {"campaigns": []}

    campaigns_data = list(campaigns_collection.find({"user_id": user_id}))

    campaigns = []
    for campaign in campaigns_data:
        deals_collection = get_mongodb_collection("deals")
        leads_count = 0
        if deals_collection is not None:
            leads_count = deals_collection.count_documents({"campaign_id": str(campaign.get("_id"))})

        campaigns.append(
            CampaignInfoResponse(
                id=str(campaign.get("_id")),
                name=campaign.get("name", ""),
                is_paused=campaign.get("is_paused", False),
                created_at=campaign.get("created_at", "").isoformat() if isinstance(campaign.get("created_at"), datetime) else str(campaign.get("created_at", "")),
                leads_count=leads_count,
            )
        )
    return {"campaigns": campaigns}


@router.get("/finance", dependencies=[Depends(get_admin_user)])
async def get_finance_metrics() -> FinanceMetricsResponse:
    """Get platform finance metrics."""
    users_collection = get_mongodb_collection("users")
    if users_collection is None:
        raise HTTPException(
            status_code=500,
            detail="Database unavailable",
        )

    total_users = users_collection.count_documents({})
    active_subscriptions = users_collection.count_documents(
        {"subscription_status": "active"}
    )
    trialing_users = users_collection.count_documents(
        {"subscription_status": "trialing"}
    )

    trial_conversions = users_collection.count_documents({
        "subscription_status": "active",
        "$expr": {"$ne": ["$trial_ends_at", None]},
    })

    trial_total = users_collection.count_documents({
        "$expr": {"$ne": ["$trial_ends_at", None]},
    })

    trial_conversion_rate = (
        (trial_conversions / trial_total * 100) if trial_total > 0 else 0
    )

    canceled_subs = users_collection.count_documents({
        "subscription_status": "canceled"
    })
    churn_rate = (
        (canceled_subs / (active_subscriptions + canceled_subs) * 100)
        if (active_subscriptions + canceled_subs) > 0
        else 0
    )

    mrr = 0.0
    users_data = list(users_collection.find({"subscription_status": "active"}))
    for user_doc in users_data:
        user = User.from_dict(user_doc)
        plan = _get_plan_limits(user.plan)
        if plan:
            if user.billing_period == "monthly":
                mrr += plan["monthly_price"] / 100.0
            elif user.billing_period == "annual":
                mrr += (plan["annual_price"] / 12) / 100.0

    arr = mrr * 12

    return FinanceMetricsResponse(
        total_users=total_users,
        active_subscriptions=active_subscriptions,
        trialing_users=trialing_users,
        mrr=mrr,
        arr=arr,
        trial_conversion_rate=trial_conversion_rate,
        churn_rate=churn_rate,
    )


@router.get("/finance/invoices", dependencies=[Depends(get_admin_user)])
async def get_all_invoices(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
) -> dict:
    """Get all platform invoices using Stripe's bulk list API."""
    import stripe as _stripe

    users_collection = get_mongodb_collection("users")
    if users_collection is None:
        raise HTTPException(
            status_code=500,
            detail="Database unavailable",
        )

    customer_email_map: dict[str, tuple[str, str]] = {}
    for doc in users_collection.find(
        {"stripe_customer_id": {"$ne": None}},
        projection={"_id": 1, "email": 1, "stripe_customer_id": 1},
    ):
        customer_email_map[doc["stripe_customer_id"]] = (doc["_id"], doc["email"])

    try:
        params: dict = {"limit": limit}
        if skip > 0:
            earlier = _stripe.Invoice.list(limit=skip)
            if earlier.data:
                params["starting_after"] = earlier.data[-1].id

        invoices_response = _stripe.Invoice.list(**params)
        invoices_list = invoices_response.data if invoices_response else []
    except Exception as e:
        logger.error(f"Failed to list invoices from Stripe: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch invoices")

    results = []
    for inv in invoices_list:
        customer_id = inv.customer.id if hasattr(inv.customer, "id") else inv.customer  # type: ignore
        user_id, user_email = customer_email_map.get(customer_id, ("unknown", "unknown"))  # type: ignore[arg-type]
        results.append(
            InvoiceDetailResponse(
                id=inv.id,
                user_id=user_id,
                user_email=user_email,
                amount=inv.amount_paid,
                status=inv.status or "unknown",
                created=inv.created,
                period_start=inv.period_start,
                period_end=inv.period_end,
                pdf_url=inv.invoice_pdf,
            )
        )

    return {
        "total": invoices_response.total_count if hasattr(invoices_response, "total_count") else len(results),  # type: ignore
        "skip": skip,
        "limit": limit,
        "invoices": results,
    }


@router.get("/dashboard", dependencies=[Depends(get_admin_user)])
async def get_dashboard_summary() -> dict:
    """Get admin dashboard summary."""
    users_collection = get_mongodb_collection("users")
    if users_collection is None:
        raise HTTPException(
            status_code=500,
            detail="Database unavailable",
        )

    total_users = users_collection.count_documents({})
    active_users = users_collection.count_documents({"status": "active"})
    blocked_users = users_collection.count_documents({"status": "blocked"})

    today = datetime.now(tz.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    new_signups = users_collection.count_documents({"created_at": {"$gte": today}})

    now = datetime.now(tz.utc)
    expired_trials = list(
        users_collection.find({
            "subscription_status": "trialing",
            "trial_ends_at": {"$lt": now},
        })
    )

    active_subscriptions = users_collection.count_documents(
        {"subscription_status": "active"}
    )

    metrics = await get_finance_metrics()

    return {
        "summary": {
            "total_users": total_users,
            "active_users": active_users,
            "blocked_users": blocked_users,
            "new_signups_today": new_signups,
            "active_subscriptions": active_subscriptions,
            "expired_trials_count": len(expired_trials),
        },
        "finance": {
            "mrr": metrics.mrr,
            "arr": metrics.arr,
            "trial_conversion_rate": metrics.trial_conversion_rate,
            "churn_rate": metrics.churn_rate,
        },
    }


@router.get("/users/{user_id}/notes", dependencies=[Depends(get_admin_user)])
async def get_user_notes(user_id: str) -> AdminNotesResponse:
    """Get admin notes for a user."""
    users_collection = get_mongodb_collection("users")
    if users_collection is None:
        raise HTTPException(
            status_code=500,
            detail="Database unavailable",
        )

    user_doc = users_collection.find_one({"_id": user_id})
    if not user_doc:
        raise HTTPException(status_code=404, detail="User not found")

    return AdminNotesResponse(notes=user_doc.get("admin_notes"))


@router.post("/users/{user_id}/notes", dependencies=[Depends(get_admin_user)])
async def update_user_notes(user_id: str, request: AdminNotesResponse) -> AdminNotesResponse:
    """Update admin notes for a user."""
    users_collection = get_mongodb_collection("users")
    if users_collection is None:
        raise HTTPException(
            status_code=500,
            detail="Database unavailable",
        )

    result = users_collection.update_one(
        {"_id": user_id},
        {"$set": {"admin_notes": request.notes}},
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")

    logger.info(f"Admin updated notes for user {user_id}")
    return AdminNotesResponse(notes=request.notes)


@router.get("/audit-logs", dependencies=[Depends(get_admin_user)])
async def list_audit_logs(
    admin_user_id: Optional[str] = Query(None),
    target_user_id: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> dict:
    """Paginated admin audit log."""
    collection = get_mongodb_collection("admin_audit_logs")
    if collection is None:
        raise HTTPException(status_code=500, detail="Database unavailable")

    query: dict = {}
    if admin_user_id:
        query["admin_user_id"] = admin_user_id
    if target_user_id:
        query["target_user_id"] = target_user_id
    if action:
        query["action"] = action

    total = collection.count_documents(query)
    logs = list(collection.find(query).sort("created_at", -1).skip(skip).limit(limit))

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "logs": [
            {
                "id": str(log.get("_id")),
                "admin_user_id": log.get("admin_user_id"),
                "action": log.get("action"),
                "target_user_id": log.get("target_user_id"),
                "details": log.get("details", {}),
                "created_at": log["created_at"].isoformat()
                    if isinstance(log.get("created_at"), datetime) else str(log.get("created_at", "")),
            }
            for log in logs
        ],
    }


@router.get("/users/{user_id}/tasks", dependencies=[Depends(get_admin_user)])
async def get_user_tasks(
    user_id: str,
    status: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
) -> dict:
    """Get recent tasks for a user."""
    tasks_collection = get_mongodb_collection("tasks")
    if tasks_collection is None:
        return {"tasks": []}

    query: dict = {"user_id": user_id}
    if status:
        query["status"] = status

    tasks_data = list(
        tasks_collection.find(query).sort("scheduled_at", -1).limit(limit)
    )

    return {
        "tasks": [
            {
                "id": str(t.get("_id")),
                "task_type": t.get("task_type"),
                "status": t.get("status"),
                "scheduled_at": t["scheduled_at"].isoformat()
                    if isinstance(t.get("scheduled_at"), datetime) else str(t.get("scheduled_at", "")),
                "started_at": t["started_at"].isoformat()
                    if isinstance(t.get("started_at"), datetime) else None,
                "completed_at": t["completed_at"].isoformat()
                    if isinstance(t.get("completed_at"), datetime) else None,
                "campaign_id": t.get("payload", {}).get("campaign_id"),
                "linkedin_profile_id": t.get("payload", {}).get("linkedin_profile_id")
                    or t.get("linkedin_profile_id"),
                "last_error": t.get("payload", {}).get("last_error"),
            }
            for t in tasks_data
        ]
    }


@router.get("/users/{user_id}/action-logs", dependencies=[Depends(get_admin_user)])
async def get_user_action_logs(
    user_id: str,
    limit: int = Query(50, ge=1, le=200),
) -> dict:
    """Get recent action logs for a user."""
    collection = get_mongodb_collection("action_logs")
    if collection is None:
        return {"logs": []}

    logs = list(
        collection.find({"user_id": user_id}).sort("created_at", -1).limit(limit)
    )

    return {
        "logs": [
            {
                "id": str(log.get("_id")),
                "action_type": log.get("action_type"),
                "campaign_id": log.get("campaign_id"),
                "linkedin_profile_id": log.get("linkedin_profile_id"),
                "status": log.get("status"),
                "error_message": log.get("error_message"),
                "duration_ms": log.get("duration_ms"),
                "created_at": log["created_at"].isoformat()
                    if isinstance(log.get("created_at"), datetime) else str(log.get("created_at", "")),
            }
            for log in logs
        ]
    }


@router.get("/platform", dependencies=[Depends(get_admin_user)])
async def get_platform_metrics() -> dict:
    """Platform-wide metrics: tasks, active daemons, connection rates."""
    tasks_col = get_mongodb_collection("tasks")
    profiles_col = get_mongodb_collection("linkedin_profiles")
    action_logs_col = get_mongodb_collection("action_logs")

    now = datetime.now(tz.utc)
    last_24h = now - timedelta(hours=24)
    five_min_ago = now - timedelta(minutes=5)

    running_tasks = tasks_col.count_documents({"status": "RUNNING"}) if tasks_col is not None else 0
    pending_tasks = tasks_col.count_documents({"status": "PENDING"}) if tasks_col is not None else 0
    failed_tasks_24h = tasks_col.count_documents({
        "status": "FAILED", "completed_at": {"$gte": last_24h}
    }) if tasks_col is not None else 0
    completed_tasks_24h = tasks_col.count_documents({
        "status": "COMPLETED", "completed_at": {"$gte": last_24h}
    }) if tasks_col is not None else 0

    online_daemons = profiles_col.count_documents({
        "last_heartbeat": {"$gte": five_min_ago}
    }) if profiles_col is not None else 0
    desktop_daemons = profiles_col.count_documents({
        "execution_mode": "desktop", "last_heartbeat": {"$gte": five_min_ago}
    }) if profiles_col is not None else 0
    cloud_daemons = profiles_col.count_documents({
        "execution_mode": "cloud", "last_heartbeat": {"$gte": five_min_ago}
    }) if profiles_col is not None else 0

    connects_24h = action_logs_col.count_documents({
        "action_type": "connect", "status": "completed", "created_at": {"$gte": last_24h}
    }) if action_logs_col is not None else 0
    follow_ups_24h = action_logs_col.count_documents({
        "action_type": "follow_up", "status": "completed", "created_at": {"$gte": last_24h}
    }) if action_logs_col is not None else 0

    return {
        "tasks": {
            "running": running_tasks,
            "pending": pending_tasks,
            "failed_24h": failed_tasks_24h,
            "completed_24h": completed_tasks_24h,
        },
        "daemons": {
            "online": online_daemons,
            "desktop": desktop_daemons,
            "cloud": cloud_daemons,
        },
        "activity_24h": {
            "connects": connects_24h,
            "follow_ups": follow_ups_24h,
        },
    }
