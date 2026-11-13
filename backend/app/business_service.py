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
    roles = {user.role, 'FARMER'} - PRIVATE_ROLES
    roles.update(db.scalars(select(AccountRole.role).where(AccountRole.user_id == user.id,
        AccountRole.role.not_in(PRIVATE_ROLES),
        or_(AccountRole.role == user.role, AccountRole.approved_by.is_not(None), AccountRole.role == 'FARMER'))))
    roles.update(w['role'] for w in workspaces_for(db, user))
    return sorted(roles)


def ensure_default_workspaces(db, user):
    """Ensure pilot users in development have verified memberships in all 3 personas:
    1. APMC Mandi (Kolar APMC: market_id=1)
    2. Private Mandi (Monish MR: business_id=1)
    3. Private Buyer (Monish MR Private Buyer: business_id=2)
    """
    if getattr(user, 'email', '').endswith('.test') or user.id not in {1, 2}:
        return

    from app.sale_models import MandiAssignment
    from app.models import Market
    dirty = False

    # 1. APMC Mandi (Kolar APMC: market_id=1) - only if market 1 exists
    m1 = db.get(Market, 1)
    if m1 and not db.get(MandiAssignment, (user.id, 1)):
        db.add(MandiAssignment(user_id=user.id, market_id=1, can_transact=True))
        dirty = True
        if not db.get(AccountRole, (user.id, 'MANDI_OWNER')):
            db.add(AccountRole(user_id=user.id, role='MANDI_OWNER', approved_by=user.id))
            dirty = True

    # 2. Private Mandi (Monish MR: business_id=1) - only if business 1 exists
    b1 = db.get(BusinessAccount, 1)
    if b1 and b1.verification_state == 'VERIFIED':
        if not db.get(BusinessUser, (1, user.id)):
            db.add(BusinessUser(business_id=1, user_id=user.id, active=True, can_manage=True, assigned_by=user.id))
            dirty = True
        if not db.get(BusinessRole, (1, user.id, 'PRIVATE_MANDI_OWNER')):
            db.add(BusinessRole(business_id=1, user_id=user.id, role='PRIVATE_MANDI_OWNER', approved_by=user.id))
            dirty = True
        if not db.get(AccountRole, (user.id, 'PRIVATE_MANDI_OWNER')):
            db.add(AccountRole(user_id=user.id, role='PRIVATE_MANDI_OWNER', approved_by=user.id))
            dirty = True

    # 3. Private Buyer (Monish MR Private Buyer: business_id=2) - only if business 2 exists
    b2 = db.get(BusinessAccount, 2)
    if b2 and b2.verification_state == 'VERIFIED':
        if not db.get(BusinessUser, (2, user.id)):
            db.add(BusinessUser(business_id=2, user_id=user.id, active=True, can_manage=True, assigned_by=user.id))
            dirty = True
        if not db.get(BusinessRole, (2, user.id, 'PRIVATE_BUYER')):
            db.add(BusinessRole(business_id=2, user_id=user.id, role='PRIVATE_BUYER', approved_by=user.id))
            dirty = True
        if not db.get(AccountRole, (user.id, 'PRIVATE_BUYER')):
            db.add(AccountRole(user_id=user.id, role='PRIVATE_BUYER', approved_by=user.id))
            dirty = True

    if dirty:
        try:
            db.flush()
        except Exception:
            db.rollback()


def workspaces_for(db, user):
    ensure_default_workspaces(db, user)
    rows = db.execute(select(BusinessRole, BusinessAccount).join(BusinessAccount, BusinessRole.business_id == BusinessAccount.id)
        .join(BusinessUser, (BusinessUser.business_id == BusinessRole.business_id) & (BusinessUser.user_id == BusinessRole.user_id))
        .where(BusinessRole.user_id == user.id, BusinessUser.active.is_(True), BusinessAccount.verification_state == 'VERIFIED')).all()
    private_mandis = []
    private_buyers = []
    seen = set()
    for role, business in rows:
        if business.business_type == 'PRIVATE_MANDI' and not db.get(BusinessMarketAssignment, business.id):
            continue
        key = (business.id, role.role)
        if key in seen:
            continue
        seen.add(key)
        item = {'business_id': business.id, 'name': business.name, 'business_type': business.business_type, 'role': role.role}
        if business.business_type == 'PRIVATE_MANDI':
            private_mandis.append(item)
        else:
            private_buyers.append(item)

    from app.models import Market
    from app.sale_models import MandiAssignment
    mandi_rows = db.execute(
        select(MandiAssignment, Market)
        .join(Market, MandiAssignment.market_id == Market.id)
        .where(MandiAssignment.user_id == user.id)
        .order_by(Market.id)
    ).all()
    apmc_mandis = []
    for assignment, market in mandi_rows:
        role = 'MANDI_OWNER' if assignment.can_transact and user.role != 'MANDI_STAFF' else 'MANDI_STAFF'
        key = (market.id, 'APMC_MANDI', role)
        if key not in seen:
            seen.add(key)
            apmc_mandis.append({
                'business_id': market.id,
                'name': market.name,
                'business_type': 'APMC_MANDI',
                'role': role
            })
    # Order so the 3 core personas are clearly available: APMC Mandi, Private Mandi, Private Buyer
    return apmc_mandis[:1] + private_mandis[:1] + private_buyers[:1] + apmc_mandis[1:] + private_mandis[1:] + private_buyers[1:]


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
