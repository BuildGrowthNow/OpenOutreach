"""Role-based permissions for organization workspaces (Phase 3A).

The role matrix mirrors the rollout plan:

| Capability              | owner | admin | member |
|-------------------------|-------|-------|--------|
| view billing            | yes   | yes   | no     |
| change plan/seats       | yes   | no    | no     |
| invite/remove members   | yes   | yes   | no     |
| change roles            | yes   | no*   | no     |
| assign seats            | yes   | yes   | no     |
| manage proxies          | yes   | yes   | no     |
| view all org data       | yes   | yes   | no     |
| create/edit profiles    | yes   | yes   | own    |
| create/edit campaigns   | yes   | yes   | own    |
| delete org              | yes   | no    | no     |

*Admins may remove members but cannot promote/demote admins or the owner.
"""
from __future__ import annotations

from openoutreach.organizations.models import ROLE_ADMIN, ROLE_MEMBER, ROLE_OWNER

_ROLE_RANK = {ROLE_MEMBER: 1, ROLE_ADMIN: 2, ROLE_OWNER: 3}


def role_rank(role: str) -> int:
    return _ROLE_RANK.get(role, 0)


def is_owner(role: str) -> bool:
    return role == ROLE_OWNER


def is_admin_or_owner(role: str) -> bool:
    return role in (ROLE_OWNER, ROLE_ADMIN)


def can_view_billing(role: str) -> bool:
    return is_admin_or_owner(role)


def can_manage_billing(role: str) -> bool:
    return is_owner(role)


def can_manage_team(role: str) -> bool:
    return is_admin_or_owner(role)


def can_change_roles(role: str) -> bool:
    return is_owner(role)


def can_assign_seats(role: str) -> bool:
    return is_admin_or_owner(role)


def can_manage_proxies(role: str) -> bool:
    return is_admin_or_owner(role)


def can_view_all_profiles(role: str) -> bool:
    return is_admin_or_owner(role)


def can_create_profiles(role: str) -> bool:
    return role in (ROLE_OWNER, ROLE_ADMIN, ROLE_MEMBER)


def can_delete_profiles(role: str) -> bool:
    # Deleting a profile retires its proxy and releases a seat. Keep that
    # destructive, billing-affecting action with the workspace managers.
    return is_admin_or_owner(role)


def can_manage_campaigns(role: str) -> bool:
    return role in (ROLE_OWNER, ROLE_ADMIN, ROLE_MEMBER)


def can_manage_member(actor_role: str, target_role: str) -> bool:
    """Return whether ``actor_role`` may remove/change ``target_role``."""
    if target_role == ROLE_OWNER:
        return False
    if actor_role == ROLE_OWNER:
        return True
    if actor_role == ROLE_ADMIN:
        return target_role == ROLE_MEMBER
    return False


def can_assign_role(actor_role: str, new_role: str) -> bool:
    """Only the owner can promote/demote admins; admins cannot change roles."""
    if actor_role != ROLE_OWNER:
        return False
    return new_role in (ROLE_ADMIN, ROLE_MEMBER)
