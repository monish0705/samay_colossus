"""Private marketplace foundation only; no purchase offers or trades are fabricated."""
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app.business_models import (
    AccountRole,
    BusinessAccount,
    BusinessCropPreference,
    BusinessMarketAssignment,
    BusinessRole,
    BusinessUser,
    BusinessVerification,
    PrivateBuyer,
    PrivateMandi,
    WorkspacePreference,
)
from app.business_schemas import (
    BusinessAccessResponse,
    BusinessMemberInput,
    BusinessProfileResponse,
    BusinessRegistration,
    BusinessReview,
    MarketAssignmentInput,
    WorkspaceSelection,
)
from app.business_service import active_workspace, authorized_business, roles_for, workspaces_for
from app.models import Commodity
from app.sale_auth import DB, User, digest, require_role, throttle, write_guard
from app.sale_models import SaleUser, now

router = APIRouter(prefix='/api/v1', tags=['private marketplace'], dependencies=[Depends(write_guard)])
ALLOWED_REVIEWS = {
    'PENDING_VERIFICATION': {'VERIFIED', 'REJECTED'},
    'VERIFIED': {'SUSPENDED'}, 'REJECTED': {'PENDING_VERIFICATION'},
    'SUSPENDED': {'PENDING_VERIFICATION', 'VERIFIED'},
}


def profile(db, business, user):
    membership = db.get(BusinessUser, (business.id, user.id))
    scoped_roles = list(db.scalars(select(BusinessRole.role).where(BusinessRole.business_id == business.id, BusinessRole.user_id == user.id)))
    assignment = db.get(BusinessMarketAssignment, business.id)
    output = {c.name: getattr(business, c.name) for c in business.__table__.columns if c.name not in {'submission_key', 'payload_hash'}}
    output.update(commodity_ids=list(db.scalars(select(BusinessCropPreference.commodity_id).where(BusinessCropPreference.business_id == business.id))),
        authorized_roles=scoped_roles, can_publish=bool(membership and membership.active and membership.can_manage and scoped_roles
            and business.verification_state == 'VERIFIED' and (business.business_type == 'PRIVATE_BUYER' or assignment)),
        is_apmc=False, public_offers_implemented=True)
    subtype = db.scalar(select(PrivateMandi).where(PrivateMandi.business_id == business.id)) if business.business_type == 'PRIVATE_MANDI' else db.scalar(select(PrivateBuyer).where(PrivateBuyer.business_id == business.id))
    output['private_mandi_id'] = subtype.id if isinstance(subtype, PrivateMandi) else None
    output['operating_hours'] = subtype.operating_hours if isinstance(subtype, PrivateMandi) else None
    output['buyer_type'] = subtype.buyer_type if isinstance(subtype, PrivateBuyer) else None
    output['assigned_private_mandi_id'] = assignment.private_mandi_id if assignment else None
    return output


@router.post('/business/register', status_code=201, response_model=BusinessProfileResponse)
def register_business(body: BusinessRegistration, db: DB, user: User, idempotency_key: str = Header(min_length=16, max_length=100)):
    fingerprint = digest(body.model_dump_json())
    previous = db.scalar(select(BusinessAccount).where(BusinessAccount.created_by == user.id, BusinessAccount.submission_key == idempotency_key))
    if previous:
        if previous.payload_hash != fingerprint:
            raise HTTPException(409, 'business_submission_key_reused')
        return profile(db, previous, user)
    throttle(db, f'business-register:{user.id}', 10)
    if any(not db.get(Commodity, i) for i in body.commodity_ids):
        raise HTTPException(422, 'unknown_business_crop')
    account = BusinessAccount(**body.model_dump(exclude={'commodity_ids', 'operating_hours', 'buyer_type'}),
        created_by=user.id, submission_key=idempotency_key, payload_hash=fingerprint)
    db.add(account)
    try:
        db.flush()
        db.add(BusinessUser(business_id=account.id, user_id=user.id, can_manage=False, active=True))
        if account.business_type == 'PRIVATE_MANDI':
            db.add(PrivateMandi(business_id=account.id, operating_hours=body.operating_hours))
        else:
            db.add(PrivateBuyer(business_id=account.id, buyer_type=body.buyer_type))
        for crop_id in body.commodity_ids:
            db.add(BusinessCropPreference(business_id=account.id, commodity_id=crop_id))
        db.commit()
    except IntegrityError:
        db.rollback()
        previous = db.scalar(select(BusinessAccount).where(BusinessAccount.created_by == user.id, BusinessAccount.submission_key == idempotency_key))
        if previous and previous.payload_hash == fingerprint:
            return profile(db, previous, user)
        raise HTTPException(409, 'business_registration_conflict') from None
    return profile(db, account, user)


@router.get('/business/profile', response_model=BusinessProfileResponse | list[BusinessProfileResponse])
def business_profile(db: DB, user: User, business_id: int | None = Query(default=None, gt=0)):
    if business_id is not None:
        return profile(db, authorized_business(db, user, business_id), user)
    rows = db.scalars(select(BusinessAccount).join(BusinessUser, BusinessUser.business_id == BusinessAccount.id)
        .where(BusinessUser.user_id == user.id, BusinessUser.active.is_(True)).order_by(BusinessAccount.id))
    return [profile(db, b, user) for b in rows]


@router.get('/business/roles', response_model=BusinessAccessResponse)
def business_roles(db: DB, user: User):
    choices = workspaces_for(db, user)
    return {'user_id': user.id, 'roles': roles_for(db, user), 'workspaces': choices,
            'active_workspace': active_workspace(db, user, choices)}


@router.post('/business/active-role', response_model=BusinessAccessResponse)
def select_workspace(body: WorkspaceSelection, db: DB, user: User):
    choices = workspaces_for(db, user)
    if body.mode == 'FARMER':
        if body.business_id is not None or body.role is not None or 'FARMER' not in roles_for(db, user):
            raise HTTPException(403, 'farmer_workspace_not_authorized')
    elif not any(w['business_id'] == body.business_id and w['role'] == body.role for w in choices):
        raise HTTPException(403, 'business_workspace_not_authorized')
    preference = db.get(WorkspacePreference, user.id)
    if not preference:
        preference = WorkspacePreference(user_id=user.id)
        db.add(preference)
    preference.mode, preference.business_id, preference.role, preference.updated_at = body.mode, body.business_id, body.role, now()
    db.commit()
    return business_roles(db, user)


@router.get('/business/verification-status')
def verification_status(business_id: int, db: DB, user: User):
    business = authorized_business(db, user, business_id)
    history = db.scalars(select(BusinessVerification).where(BusinessVerification.business_id == business_id).order_by(BusinessVerification.id))
    return {'business_id': business_id, 'state': business.verification_state, 'version': business.version,
            'history': [{c.name: getattr(row, c.name) for c in row.__table__.columns} for row in history]}


@router.get('/business/workspace/{business_id}', response_model=BusinessProfileResponse)
def workspace(business_id: int, db: DB, user: User):
    return profile(db, authorized_business(db, user, business_id, verified=True), user)


@router.get('/admin/businesses/pending', response_model=list[BusinessProfileResponse])
def pending_businesses(db: DB, user: User, limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    require_role(user, 'SYSTEM_ADMIN')
    return [profile(db, b, user) for b in db.scalars(select(BusinessAccount).where(BusinessAccount.verification_state == 'PENDING_VERIFICATION')
        .order_by(BusinessAccount.id).offset(offset).limit(limit))]


@router.get('/admin/businesses/{business_id}', response_model=BusinessProfileResponse)
def admin_business(business_id: int, db: DB, user: User):
    require_role(user, 'SYSTEM_ADMIN')
    business = db.get(BusinessAccount, business_id)
    if not business:
        raise HTTPException(404, 'business_not_found')
    return profile(db, business, user)


@router.post('/admin/businesses/{business_id}/verify', response_model=BusinessProfileResponse)
def review_business(business_id: int, body: BusinessReview, db: DB, user: User):
    require_role(user, 'SYSTEM_ADMIN')
    business = db.get(BusinessAccount, business_id)
    if not business:
        raise HTTPException(404, 'business_not_found')
    before = business.verification_state
    if body.state not in ALLOWED_REVIEWS[before]:
        raise HTTPException(409, 'invalid_business_verification_transition')
    if body.state == 'VERIFIED' and (not body.contact_verified or
            business.business_type == 'PRIVATE_MANDI' and not body.registration_checked or
            body.documents_required and not business.document_references):
        raise HTTPException(422, 'business_verification_evidence_required')
    changed = db.execute(update(BusinessAccount).where(BusinessAccount.id == business_id, BusinessAccount.version == body.version)
        .values(verification_state=body.state, version=body.version + 1), execution_options={'synchronize_session': False})
    if changed.rowcount != 1:
        raise HTTPException(409, 'business_changed_refresh_before_review')
    db.refresh(business)
    db.add(BusinessVerification(business_id=business_id, reviewer_id=user.id, from_state=before, to_state=body.state,
        evidence=body.evidence, contact_verified=body.contact_verified, registration_checked=body.registration_checked))
    if body.state == 'VERIFIED':
        member = db.get(BusinessUser, (business_id, business.created_by))
        member.can_manage, member.active, member.assigned_by = True, True, user.id
        role = 'PRIVATE_MANDI_OWNER' if business.business_type == 'PRIVATE_MANDI' else 'PRIVATE_BUYER'
        if not db.get(BusinessRole, (business_id, member.user_id, role)):
            db.add(BusinessRole(business_id=business_id, user_id=member.user_id, role=role, approved_by=user.id))
        if not db.get(AccountRole, (member.user_id, role)):
            db.add(AccountRole(user_id=member.user_id, role=role, approved_by=user.id))
        if business.business_type == 'PRIVATE_MANDI' and not db.get(BusinessMarketAssignment, business_id):
            market = db.scalar(select(PrivateMandi).where(PrivateMandi.business_id == business_id))
            db.add(BusinessMarketAssignment(business_id=business_id, private_mandi_id=market.id, approved_by=user.id))
    db.commit()
    return profile(db, business, user)


@router.post('/admin/businesses/{business_id}/members')
def assign_member(business_id: int, body: BusinessMemberInput, db: DB, user: User):
    require_role(user, 'SYSTEM_ADMIN')
    business = db.get(BusinessAccount, business_id)
    target = db.get(SaleUser, body.user_id)
    if not business or not target or not target.active:
        raise HTTPException(404, 'business_or_user_not_found')
    expected = 'PRIVATE_MANDI_OWNER' if business.business_type == 'PRIVATE_MANDI' else 'PRIVATE_BUYER'
    if body.role not in {expected, 'MANDI_STAFF'} or body.user_id == business.created_by:
        raise HTTPException(422, 'incompatible_business_member_role')
    membership = db.get(BusinessUser, (business_id, body.user_id))
    if not membership:
        membership = BusinessUser(business_id=business_id, user_id=body.user_id)
        db.add(membership)
    membership.active, membership.can_manage, membership.assigned_by = body.active, body.can_manage, user.id
    role = db.get(BusinessRole, (business_id, body.user_id, body.role))
    if not role:
        db.add(BusinessRole(business_id=business_id, user_id=body.user_id, role=body.role, approved_by=user.id))
    db.commit()
    return {'business_id': business_id, 'user_id': body.user_id, 'active': body.active}


@router.post('/admin/businesses/{business_id}/market-assignment')
def assign_private_market(business_id: int, body: MarketAssignmentInput, db: DB, user: User):
    require_role(user, 'SYSTEM_ADMIN')
    market = db.get(PrivateMandi, body.private_mandi_id)
    if not market or market.business_id != business_id:
        raise HTTPException(422, 'private_market_must_belong_to_business')
    assignment = db.get(BusinessMarketAssignment, business_id)
    if not assignment:
        assignment = BusinessMarketAssignment(business_id=business_id)
        db.add(assignment)
    assignment.private_mandi_id, assignment.approved_by = market.id, user.id
    db.commit()
    return {'business_id': business_id, 'private_mandi_id': market.id, 'is_apmc': False}
