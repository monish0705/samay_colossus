"""Authorization boundaries for private workspaces and future offer/request services."""
from fastapi import HTTPException
from sqlalchemy import or_, select

from app.business_models import (
    AccountRole,
    BusinessAccount,
    BusinessMarketAssignment,
    BusinessRole,
    BusinessUser,
    WorkspacePreference,
)
from app.sale_models import now

PRIVATE_ROLES = {'PRIVATE_MANDI_OWNER', 'PRIVATE_BUYER'}


def roles_for(db, user):
    # Legacy primary roles stay valid for existing APMC accounts. Private powers
    # always require an active scoped membership and a verified business.
    roles = {user.role} - PRIVATE_ROLES
    roles.update(db.scalars(select(AccountRole.role).where(AccountRole.user_id == user.id,
        AccountRole.role.not_in(PRIVATE_ROLES),
        or_(AccountRole.role == user.role, AccountRole.approved_by.is_not(None)))))
    roles.update(w['role'] for w in workspaces_for(db, user))
    return sorted(roles)


def workspaces_for(db, user):
    rows = db.execute(select(BusinessRole, BusinessAccount).join(BusinessAccount, BusinessRole.business_id == BusinessAccount.id)
        .join(BusinessUser, (BusinessUser.business_id == BusinessRole.business_id) & (BusinessUser.user_id == BusinessRole.user_id))
        .where(BusinessRole.user_id == user.id, BusinessUser.active.is_(True), BusinessAccount.verification_state == 'VERIFIED')).all()
    result = []
    for role, business in rows:
        if business.business_type == 'PRIVATE_MANDI' and not db.get(BusinessMarketAssignment, business.id):
            continue
        result.append({'business_id': business.id, 'name': business.name, 'business_type': business.business_type, 'role': role.role})
    return result


def authorized_business(db, user, business_id, manage=False, verified=False):
    business = db.get(BusinessAccount, business_id)
    membership = db.get(BusinessUser, (business_id, user.id))
    if not business or not membership or not membership.active:
        raise HTTPException(404, 'business_not_found')
    if manage or verified:
        if business.verification_state != 'VERIFIED':
            raise HTTPException(403, 'business_not_verified')
        roles = list(db.scalars(select(BusinessRole.role).where(BusinessRole.business_id == business_id, BusinessRole.user_id == user.id)))
        expected = 'PRIVATE_MANDI_OWNER' if business.business_type == 'PRIVATE_MANDI' else 'PRIVATE_BUYER'
        if expected not in roles and 'MANDI_STAFF' not in roles:
            raise HTTPException(403, 'business_role_not_assigned')
        if business.business_type == 'PRIVATE_MANDI' and not db.get(BusinessMarketAssignment, business_id):
            raise HTTPException(403, 'private_market_not_assigned')
    if manage and not membership.can_manage:
        raise HTTPException(403, 'business_manage_permission_required')
    return business


def may_publish(db, user, business_id):
    """Future public offers MUST call this guard; no offer publishing in Prompt 1."""
    return authorized_business(db, user, business_id, manage=True, verified=True)


def active_workspace(db, user, workspaces=None):
    choices = workspaces if workspaces is not None else workspaces_for(db, user)
    preference = db.get(WorkspacePreference, user.id)
    if preference and preference.mode == 'BUSINESS':
        match = next((w for w in choices if w['business_id'] == preference.business_id and w['role'] == preference.role), None)
        if match:
            return {'mode': 'BUSINESS', **match}
        # Revoked/suspended selections fail closed and are corrected persistently.
        preference.mode, preference.business_id, preference.role, preference.updated_at = 'FARMER', None, None, now()
        db.commit()
    return {'mode': 'FARMER', 'business_id': None, 'role': None}
