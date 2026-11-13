"""Authenticated farmer/mandi workflows. Every mutation is scoped and versioned."""
import secrets
from datetime import timedelta
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from sqlalchemy import exists, func, or_, select, update
from sqlalchemy.exc import IntegrityError

from app.api_schemas import ErrorEnvelope
from app.config import get_settings
from app.models import Commodity, MandiObservation, Market
from app.sale_auth import COOKIE, DB, User, digest, password_hash, password_valid, require_role, throttle, write_guard
from app.sale_models import (
    ArrivalBooking,
    ContactChallenge,
    MandiAssignment,
    MandiRegistration,
    Notification,
    NotificationDelivery,
    NotificationPreference,
    SaleEvent,
    SaleInvitation,
    SaleOffer,
    SaleRequest,
    SaleSession,
    SaleTransaction,
    SaleUser,
    now,
)
from app.sale_schemas import (
    ArrivedInput,
    ConfirmInput,
    InviteInput,
    Login,
    MandiInput,
    OfferInput,
    PaymentInput,
    PreferenceInput,
    ReasonInput,
    Register,
    SaleCreate,
    SaleResponse,
    StaffInput,
    TokenInput,
    Versioned,
    WeighmentInput,
)
from app.sale_service import (
    assignment,
    dispatch_waiting,
    expire,
    latest_offer,
    load_request,
    money,
    notify,
    owners,
    request_dict,
    transition,
    view,
)

router = APIRouter(prefix='/api/v1', tags=['sale marketplace'], dependencies=[Depends(write_guard)], responses={
    status: {'model': ErrorEnvelope, 'description': meaning} for status, meaning in [
        (401, 'Authentication required'), (403, 'Role, assignment or CSRF header denied'),
        (404, 'Request or notification not accessible'), (409, 'State/version conflict, inactive mandi or expired offer'),
        (422, 'Invalid request fields'), (429, 'Rate limit exceeded'), (503, 'Durable storage or channel unavailable')]})


def identity(user):
    return {'id': user.id, 'name': user.name, 'email': user.email, 'role': user.role,
            'roles': getattr(user, 'authorized_roles', [user.role]),
            'language': user.language, 'email_verified': user.email_verified, 'phone_verified': user.phone_verified}


def session_login(db, user, response):
    token = secrets.token_urlsafe(32)
    db.add(SaleSession(token_hash=digest(token), user_id=user.id, expires_at=now() + timedelta(hours=12)))
    db.commit()
    response.set_cookie(COOKIE, token, max_age=43200, httponly=True, samesite='lax',
                        secure=get_settings().environment == 'production', path='/')
    response.headers['Cache-Control'] = 'no-store'
    return identity(user)


@router.post('/auth/register', status_code=201)
def register(body: Register, request: Request, response: Response, db: DB):
    throttle(db, 'register:' + (request.client.host if request.client else 'unknown'), 20)
    if db.scalar(select(SaleUser).where(SaleUser.email == body.email)):
        raise HTTPException(409, 'account_exists_use_login')
    invitation = None
    role = 'FARMER'
    if body.invitation_token:
        invitation = db.scalar(select(SaleInvitation).where(SaleInvitation.token_hash == digest(body.invitation_token)))
        if not invitation or invitation.used or invitation.expires_at <= now() or invitation.email.lower() != body.email:
            raise HTTPException(400, 'invalid_or_expired_invitation')
        # Atomic consume prevents concurrent redemption.
        claimed = db.execute(update(SaleInvitation).where(SaleInvitation.id == invitation.id, SaleInvitation.used.is_(False)).values(used=True))
        if claimed.rowcount != 1:
            raise HTTPException(409, 'invitation_already_used')
        role = invitation.role
    user = SaleUser(email=body.email, name=body.name, password_hash=password_hash(body.password), role=role, language=body.language)
    db.add(user)
    db.flush()
    from app.business_models import AccountRole
    db.add(AccountRole(user_id=user.id, role=role))
    if invitation:
        db.add(MandiAssignment(user_id=user.id, market_id=invitation.market_id, can_transact=role == 'MANDI_OWNER'))
        db.flush()
        dispatch_waiting(db, invitation.market_id, user)
    db.add(NotificationPreference(user_id=user.id))
    return session_login(db, user, response)


@router.post('/auth/login')
def login(body: Login, request: Request, response: Response, db: DB):
    throttle(db, 'login:' + (request.client.host if request.client else 'unknown') + ':' + body.email)
    user = db.scalar(select(SaleUser).where(SaleUser.email == body.email))
    # Constant-cost failure even for nonexistent users.
    encoded = user.password_hash if user else 'pbkdf2_sha256$600000$invalid$invalid'
    if not password_valid(body.password, encoded) or not user or not user.active:
        raise HTTPException(401, 'invalid_credentials')
    return session_login(db, user, response)


@router.get('/auth/me')
def me(user: User):
    return identity(user)


@router.post('/auth/logout')
def logout(request: Request, response: Response, db: DB, user: User):
    session = db.get(SaleSession, digest(request.cookies.get(COOKIE, '')))
    if session:
        db.delete(session)
    db.commit()
    response.delete_cookie(COOKIE, path='/')
    return {'logged_out': True}


@router.post('/auth/verify-email/start')
def start_email_verification(db: DB, user: User):
    from app.sale_notifications import send_email
    throttle(db, f'verify-email:{user.id}', 3)
    token = secrets.token_urlsafe(32)
    challenge = ContactChallenge(user_id=user.id, token_hash=digest(token), expires_at=now() + timedelta(minutes=30))
    db.add(challenge)
    # No token returned to the browser; possession requires mailbox access.
    try:
        send_email(user.email, 'SAMAY email verification', f'Enter this verification code in SAMAY: {token}')
    except Exception:
        db.rollback()
        raise HTTPException(503, 'verification_email_unavailable') from None
    db.commit()
    return {'status': 'accepted_by_smtp_not_delivery_confirmed'}


@router.post('/auth/verify-email/confirm')
def confirm_email(body: TokenInput, db: DB, user: User):
    throttle(db, f'verify-confirm:{user.id}', 10)
    row = db.scalar(select(ContactChallenge).where(ContactChallenge.token_hash == digest(body.token), ContactChallenge.user_id == user.id))
    if not row or row.used or row.expires_at <= now():
        raise HTTPException(400, 'invalid_or_expired_code')
    row.used = True
    user.email_verified = True
    db.commit()
    return identity(user)


@router.post('/admin/mandis')
def register_mandi(body: MandiInput, db: DB, user: User):
    require_role(user, 'SYSTEM_ADMIN')
    market = db.get(Market, body.market_id)
    if not market or market.name.upper().startswith('DEMO_DATA') or any(not db.get(Commodity, i) for i in body.commodity_ids):
        raise HTTPException(404, 'unknown_market_or_crop')
    row = db.get(MandiRegistration, body.market_id)
    if not row:
        row = MandiRegistration(market_id=body.market_id)
        db.add(row)
    row.active, row.registration_details = body.active, body.registration_details
    row.commodity_ids, row.approved_by, row.approved_at = body.commodity_ids, user.id, now()
    db.flush()
    dispatch_waiting(db, body.market_id, user)
    db.commit()
    return {'market_id': body.market_id, 'active': row.active}


@router.post('/admin/mandi-invitations', status_code=201)
def invite(body: InviteInput, db: DB, user: User):
    require_role(user, 'SYSTEM_ADMIN')
    if not db.get(MandiRegistration, body.market_id):
        raise HTTPException(409, 'register_mandi_first')
    token = secrets.token_urlsafe(32)
    db.add(SaleInvitation(token_hash=digest(token), email=body.email.lower(), role=body.role, market_id=body.market_id,
        approved_by=user.id, identity_evidence=body.identity_evidence, expires_at=now() + timedelta(days=2)))
    db.commit()
    return {'invitation_token': token, 'expires_in_hours': 48,
            'instruction': 'Deliver once through an authorized private channel after identity checks. Email is not yet verified.'}


@router.get('/sale-mandis')
def sale_mandis(db: DB):
    result = []
    authentic = exists(select(MandiObservation.id).where(MandiObservation.market_id == Market.id, MandiObservation.data_kind.in_(['official', 'secondary'])))
    registered = exists(select(MandiRegistration.market_id).where(MandiRegistration.market_id == Market.id))
    for market in db.scalars(select(Market).where(or_(authentic, registered)).order_by(Market.name)):
        reg = db.get(MandiRegistration, market.id)
        available = bool(reg and reg.active and any(u.role == 'MANDI_OWNER' for u in owners(db, market.id)))
        result.append({'id': market.id, 'name': market.name, 'online_requests_available': available,
                       'commodity_ids': reg.commodity_ids if reg else list(db.scalars(select(MandiObservation.commodity_id).where(MandiObservation.market_id == market.id, MandiObservation.data_kind.in_(['official', 'secondary'])).distinct())),
                       'can_save_request': not reg or reg.active,
                       'reason': None if available else 'mandi_has_not_activated_online_requests'})
    return result


@router.post('/sale-requests', status_code=201, response_model=SaleResponse)
def create_sale(body: SaleCreate, db: DB, user: User, idempotency_key: str = Header(min_length=16, max_length=100)):
    require_role(user, 'FARMER')
    fingerprint = digest(body.model_dump_json())
    old = db.scalar(select(SaleRequest).where(SaleRequest.farmer_id == user.id, SaleRequest.idempotency_key == idempotency_key))
    if old:
        if old.payload_hash != fingerprint:
            raise HTTPException(409, 'idempotency_key_reused_with_different_payload')
        return request_dict(db, old, user)
    throttle(db, f'create-sale:{user.id}', 30)
    reg = db.get(MandiRegistration, body.mandi_id)
    recipients = owners(db, body.mandi_id)
    validate_sale_market(db, body, reg)
    online = bool(reg and reg.active and len(recipients) > 0)
    if body.preferred_arrival_at <= now():
        raise HTTPException(422, 'arrival_must_be_in_future')
    obs = db.scalar(select(MandiObservation).where(MandiObservation.market_id == body.mandi_id,
        MandiObservation.commodity_id == body.crop_id, MandiObservation.variety == body.variety,
        MandiObservation.grade == body.grade, MandiObservation.data_kind == 'official', MandiObservation.observed_on <= now().date())
        .order_by(MandiObservation.observed_on.desc(), MandiObservation.id.desc()))
    price = body.expected_price_per_quintal
    if body.use_mandi_price:
        from app.mandi_quote import latest_quote
        obs = latest_quote(db, body.mandi_id, body.crop_id, body.variety, body.grade, now())
        price = obs.modal_price_inr_per_quintal
        if body.expected_price_per_quintal is not None and price != body.expected_price_per_quintal:
            raise HTTPException(409, 'mandi_price_changed_review_again')
    row = SaleRequest(**body.model_dump(exclude={'use_mandi_price', 'expected_price_per_quintal'}), expected_price_per_quintal=price, farmer_id=user.id,
        public_request_id=f'SAMAY-SALE-{now().year}-{uuid4().hex[:16].upper()}',
        status='SUBMITTED', idempotency_key=idempotency_key, payload_hash=fingerprint,
        reference_modal_price=obs.modal_price_inr_per_quintal if obs else None,
        reference_price_observation_id=obs.id if obs else None)
    db.add(row)
    try:
        db.flush()
        created = SaleEvent(request_id=row.id, actor_id=user.id, from_status=None, to_status='SUBMITTED',
            details={'price_basis': 'mandi_reference' if body.use_mandi_price else 'farmer_expectation',
                     'waiting_for_mandi_activation': not online})
        db.add(created)
        db.flush()
        if online:
            event = transition(db, row, user, 'NOTIFIED', row.version,
                {'channel': 'in_app', 'meaning': 'Persisted in assigned inboxes; not proof of external delivery or reading.'})
            notify(db, row, event, recipients)
        db.commit()
    except IntegrityError:
        db.rollback()
        old = db.scalar(select(SaleRequest).where(SaleRequest.farmer_id == user.id, SaleRequest.idempotency_key == idempotency_key))
        if old and old.payload_hash == fingerprint:
            return request_dict(db, old, user)
        raise HTTPException(409, 'duplicate_submission_conflict') from None
    return request_dict(db, row, user)


@router.post('/sale-requests/preview')
def preview_sale(body: SaleCreate, db: DB, user: User):
    require_role(user, 'FARMER')
    reg = db.get(MandiRegistration, body.mandi_id)
    validate_sale_market(db, body, reg)
    if body.preferred_arrival_at <= now():
        raise HTTPException(422, 'arrival_must_be_in_future')
    obs = db.scalar(select(MandiObservation).where(MandiObservation.market_id == body.mandi_id,
        MandiObservation.commodity_id == body.crop_id, MandiObservation.variety == body.variety,
        MandiObservation.grade == body.grade, MandiObservation.data_kind == 'official',
        MandiObservation.observed_on <= now().date()).order_by(MandiObservation.observed_on.desc()))
    price = body.expected_price_per_quintal
    if body.use_mandi_price:
        from app.mandi_quote import latest_quote
        obs = latest_quote(db, body.mandi_id, body.crop_id, body.variety, body.grade, now())
        price = obs.modal_price_inr_per_quintal
    return {'expected_price_per_quintal': str(price), 'waiting_for_mandi_activation': not bool(reg and reg.active and any(u.role == 'MANDI_OWNER' for u in owners(db, body.mandi_id))),
            'reference_modal_price': str(obs.modal_price_inr_per_quintal) if obs else None,
            'reference_price_date': obs.observed_on if obs else None,
            'estimated_net_inr': str(money(body.requested_quantity * price - body.estimated_costs_inr)),
            'unit': 'INR/quintal', 'notice': 'Reference only; no confirmed owner offer yet.'}


@router.get('/sale-requests', response_model=list[SaleResponse])
@router.get('/mandi/requests', response_model=list[SaleResponse])
def list_sales(request: Request, db: DB, user: User, status: str | None = None, limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    query = select(SaleRequest)
    if '/mandi/' in request.url.path:
        require_role(user, 'MANDI_OWNER', 'MANDI_STAFF')
        query = query.join(MandiAssignment, MandiAssignment.market_id == SaleRequest.mandi_id).where(MandiAssignment.user_id == user.id)
    else:
        require_role(user, 'FARMER')
        query = query.where(SaleRequest.farmer_id == user.id)
    if status:
        query = query.where(SaleRequest.status == status)
    rows = list(db.scalars(query.order_by(SaleRequest.updated_at.desc()).offset(offset).limit(limit)))
    for row in rows:
        expire(db, row, user)
    return [request_dict(db, row, user) for row in rows]


@router.get('/mandi/dashboard')
def dashboard(db: DB, user: User):
    require_role(user, 'MANDI_OWNER', 'MANDI_STAFF')
    counts = db.execute(select(SaleRequest.status, func.count()).join(MandiAssignment, MandiAssignment.market_id == SaleRequest.mandi_id)
        .where(MandiAssignment.user_id == user.id).group_by(SaleRequest.status)).all()
    return {'counts': dict(counts), 'total': sum(c for _, c in counts)}


@router.get('/sale-requests/{request_id}', response_model=SaleResponse)
@router.get('/mandi/requests/{request_id}', response_model=SaleResponse)
def detail(request_id: str, request: Request, db: DB, user: User):
    row = load_request(db, request_id, user, owner='/mandi/' in request.url.path)
    expire(db, row, user)
    return request_dict(db, row, user)


@router.get('/sale-requests/{request_id}/timeline')
@router.get('/mandi/requests/{request_id}/timeline')
def timeline(request_id: str, request: Request, db: DB, user: User):
    row = load_request(db, request_id, user, owner='/mandi/' in request.url.path)
    return [{c.name: getattr(e, c.name) for c in e.__table__.columns} for e in db.scalars(select(SaleEvent).where(SaleEvent.request_id == row.id).order_by(SaleEvent.id))]


@router.post('/mandi/requests/{request_id}/view')
def mark_viewed(request_id: str, db: DB, user: User):
    row = load_request(db, request_id, user, owner=True)
    expire(db, row, user)
    view(db, row, user)
    db.commit()
    return request_dict(db, row, user)


@router.post('/mandi/requests/{request_id}/accept')
@router.post('/mandi/requests/{request_id}/counteroffer')
def offer(request_id: str, body: OfferInput, request: Request, db: DB, user: User):
    row = load_request(db, request_id, user, owner=True, transact=True)
    expire(db, row, user)
    reg = db.get(MandiRegistration, row.mandi_id)
    if not reg or not reg.active:
        raise HTTPException(409, 'mandi_online_requests_inactive')
    if body.quantity > row.requested_quantity or not now() < body.expires_at < body.arrival_at:
        raise HTTPException(422, 'invalid_offer_quantity_or_dates')
    kind = 'MANDI_ACCEPTED' if request.url.path.endswith('/accept') else 'COUNTER_OFFERED'
    # No hidden acceptance of a changed expected price or reduced quantity.
    if kind == 'MANDI_ACCEPTED' and (body.quantity != row.requested_quantity or body.price != row.expected_price_per_quintal):
        raise HTTPException(422, 'changed_price_or_quantity_requires_counteroffer')
    transition(db, row, user, kind, body.version, recipients=[db.get(SaleUser, row.farmer_id)])
    db.add(SaleOffer(request_id=row.id, author_id=user.id, kind=kind, **body.model_dump(exclude={'version'})))
    db.commit()
    return request_dict(db, row, user)


@router.post('/mandi/requests/{request_id}/reject')
def reject(request_id: str, body: ReasonInput, db: DB, user: User):
    row = load_request(db, request_id, user, owner=True, transact=True)
    transition(db, row, user, 'REJECTED', body.version, {'reason': body.reason}, [db.get(SaleUser, row.farmer_id)])
    db.commit()
    return request_dict(db, row, user)


@router.post('/sale-requests/{request_id}/confirm')
def confirm(request_id: str, body: ConfirmInput, db: DB, user: User):
    row = load_request(db, request_id, user)
    expire(db, row, user)
    chosen = latest_offer(db, row)
    if not chosen or chosen.id != body.offer_id or chosen.expires_at <= now():
        raise HTTPException(409, 'offer_expired_or_superseded')
    transition(db, row, user, 'FARMER_CONFIRMED', body.version, {'offer_id': chosen.id}, owners(db, row.mandi_id))
    db.add(ArrivalBooking(request_id=row.id, offer_id=chosen.id, arrival_at=chosen.arrival_at, confirmed_by=user.id))
    transition(db, row, user, 'ARRIVAL_SCHEDULED', row.version, {'offer_id': chosen.id})
    db.commit()
    return request_dict(db, row, user)


@router.post('/sale-requests/{request_id}/cancel')
@router.post('/sale-requests/{request_id}/reject-offer')
def cancel(request_id: str, body: ReasonInput, request: Request, db: DB, user: User):
    row = load_request(db, request_id, user)
    if request.url.path.endswith('/reject-offer') and row.status not in {'COUNTER_OFFERED', 'MANDI_ACCEPTED'}:
        raise HTTPException(409, 'no_actionable_offer')
    booking = db.scalar(select(ArrivalBooking).where(ArrivalBooking.request_id == row.id))
    if booking and now() >= booking.arrival_at - timedelta(hours=2):
        raise HTTPException(409, 'cancellation_cutoff_two_hours_before_arrival')
    transition(db, row, user, 'CANCELLED', body.version, {'reason': body.reason}, owners(db, row.mandi_id))
    db.commit()
    return request_dict(db, row, user)


@router.post('/mandi/requests/{request_id}/schedule-arrival')
def scheduled(request_id: str, body: Versioned, db: DB, user: User):
    row = load_request(db, request_id, user, owner=True, transact=True)
    if row.status != 'ARRIVAL_SCHEDULED' or row.version != body.version:
        raise HTTPException(409, 'farmer_must_confirm_offer_and_slot_first')
    return request_dict(db, row, user)  # The mutually agreed offer slot is the booking; no unilateral changes.


@router.post('/mandi/requests/{request_id}/mark-arrived')
def arrived(request_id: str, body: ArrivedInput, db: DB, user: User):
    row = load_request(db, request_id, user, owner=True, transact=True)
    booking = db.scalar(select(ArrivalBooking).where(ArrivalBooking.request_id == row.id))
    chosen = db.get(SaleOffer, booking.offer_id) if booking else None
    if not chosen or body.received_quantity > chosen.quantity:
        raise HTTPException(422, 'received_quantity_exceeds_booking')
    transition(db, row, user, 'ARRIVED', body.version, recipients=[db.get(SaleUser, row.farmer_id)])
    booking.arrived_at, booking.received_quantity = now(), body.received_quantity
    db.commit()
    return request_dict(db, row, user)


@router.post('/mandi/requests/{request_id}/record-weighment')
def weigh(request_id: str, body: WeighmentInput, db: DB, user: User):
    row = load_request(db, request_id, user, owner=True, transact=True)
    booking = db.scalar(select(ArrivalBooking).where(ArrivalBooking.request_id == row.id))
    if not booking or booking.received_quantity is None or body.weighed_quantity > booking.received_quantity:
        raise HTTPException(422, 'weighed_quantity_exceeds_received')
    gross = money(body.weighed_quantity * body.final_price)
    if body.deductions_inr > gross:
        raise HTTPException(422, 'deductions_exceed_gross')
    transition(db, row, user, 'WEIGHED', body.version, recipients=[db.get(SaleUser, row.farmer_id)])
    db.add(SaleTransaction(request_id=row.id, recorded_by=user.id, **body.model_dump(exclude={'version'}),
                           gross_inr=gross, net_inr=money(gross - body.deductions_inr)))
    db.commit()
    return request_dict(db, row, user)


@router.post('/mandi/requests/{request_id}/complete')
def complete(request_id: str, body: Versioned, db: DB, user: User):
    row = load_request(db, request_id, user, owner=True, transact=True)
    if not db.scalar(select(SaleTransaction).where(SaleTransaction.request_id == row.id)):
        raise HTTPException(409, 'weighment_required')
    transition(db, row, user, 'COMPLETED', body.version, recipients=[db.get(SaleUser, row.farmer_id)])
    db.commit()
    return request_dict(db, row, user)


@router.post('/mandi/requests/{request_id}/payment')
def payment(request_id: str, body: PaymentInput, db: DB, user: User):
    row = load_request(db, request_id, user, owner=True, transact=True)
    if row.status not in {'WEIGHED', 'COMPLETED'} or row.version != body.version:
        raise HTTPException(409, 'weighment_required_or_request_changed')
    # Compare-and-swap even for same-state audit events.
    changed = db.execute(update(SaleRequest).where(SaleRequest.id == row.id, SaleRequest.version == body.version)
        .values(version=body.version + 1, updated_at=now()))
    if changed.rowcount != 1:
        raise HTTPException(409, 'concurrent_response')
    record = db.scalar(select(SaleTransaction).where(SaleTransaction.request_id == row.id))
    before = {'payment_status': record.payment_status, 'payment_reference': record.payment_reference}
    record.payment_status, record.payment_reference = body.payment_status, body.payment_reference
    event = SaleEvent(request_id=row.id, actor_id=user.id, from_status=row.status, to_status=row.status,
        details={'type': 'manual_payment_update', 'before': before, 'after': body.model_dump(exclude={'version'})})
    db.add(event)
    db.flush()
    notify(db, row, event, [db.get(SaleUser, row.farmer_id)])
    db.commit()
    return request_dict(db, row, user)


@router.post('/sale-requests/{request_id}/discrepancy')
def discrepancy(request_id: str, body: ReasonInput, db: DB, user: User):
    row = load_request(db, request_id, user)
    if row.version != body.version or row.status not in {'WEIGHED', 'COMPLETED'}:
        raise HTTPException(409, 'transaction_required_or_request_changed')
    event = SaleEvent(request_id=row.id, actor_id=user.id, from_status=row.status, to_status=row.status,
                      details={'type': 'farmer_discrepancy', 'reason': body.reason})
    db.add(event)
    db.flush()
    notify(db, row, event, owners(db, row.mandi_id))
    db.commit()
    return {'recorded': True}


@router.get('/notifications')
@router.get('/mandi/notifications')
def notifications(db: DB, user: User, limit: int = Query(50, ge=1, le=100)):
    rows = db.scalars(notification_query(user).order_by(Notification.id.desc()).limit(limit))
    result = []
    for n in rows:
        row = db.get(SaleRequest, n.request_id)
        result.append({'id': n.id, 'request_id': row.public_request_id, 'message': n.message,
            'created_at': n.created_at, 'read_at': n.read_at,
            'deliveries': [{'channel': d.channel, 'status': d.status, 'attempts': d.attempts, 'error_reason': d.error_reason}
                for d in db.scalars(select(NotificationDelivery).where(NotificationDelivery.notification_id == n.id))]})
    return result


@router.get('/notifications/unread-count')
def unread(db: DB, user: User):
    query = notification_query(user).where(Notification.read_at.is_(None)).subquery()
    return {'count': db.scalar(select(func.count()).select_from(query))}


def notification_query(user):
    query = select(Notification).where(Notification.recipient_id == user.id)
    if user.role in {'MANDI_OWNER', 'MANDI_STAFF'}:
        query = query.join(MandiAssignment, MandiAssignment.market_id == Notification.mandi_id).where(MandiAssignment.user_id == user.id)
    return query


@router.post('/notifications/{notification_id}/read')
def read_notification(notification_id: int, db: DB, user: User):
    note = db.scalar(notification_query(user).where(Notification.id == notification_id))
    if not note or note.recipient_id != user.id:
        raise HTTPException(404, 'notification_not_found')
    note.read_at = note.read_at or now()
    db.commit()
    return {'read': True}


@router.get('/notification-preferences')
def preferences(db: DB, user: User):
    from app.sale_notifications import channel_availability
    pref = db.get(NotificationPreference, user.id)
    return {'email': bool(pref and pref.email), 'sms': bool(pref and pref.sms), 'whatsapp': bool(pref and pref.whatsapp),
            'channels': channel_availability(), 'email_verified': user.email_verified, 'phone_verified': user.phone_verified}


@router.post('/notification-preferences')
def update_preferences(body: PreferenceInput, db: DB, user: User):
    if body.email and not user.email_verified or (body.sms or body.whatsapp) and not user.phone_verified:
        raise HTTPException(409, 'verified_contact_required')
    pref = db.get(NotificationPreference, user.id)
    if not pref:
        pref = NotificationPreference(user_id=user.id)
        db.add(pref)
    for key, value in body.model_dump().items():
        setattr(pref, key, value)
    db.commit()
    return preferences(db, user)


@router.get('/mandi/staff')
def staff(db: DB, user: User):
    require_role(user, 'MANDI_OWNER', 'SYSTEM_ADMIN')
    assigned = list(db.scalars(select(MandiAssignment.market_id).where(MandiAssignment.user_id == user.id)))
    query = select(MandiAssignment)
    if user.role != 'SYSTEM_ADMIN':
        query = query.where(MandiAssignment.market_id.in_(assigned))
    return [{'user_id': a.user_id, 'market_id': a.market_id, 'can_transact': a.can_transact,
             'name': db.get(SaleUser, a.user_id).name, 'role': db.get(SaleUser, a.user_id).role} for a in db.scalars(query)]


@router.post('/mandi/staff')
def update_staff(body: StaffInput, db: DB, user: User):
    require_role(user, 'MANDI_OWNER', 'SYSTEM_ADMIN')
    if user.role != 'SYSTEM_ADMIN':
        assignment(db, user, body.market_id)
    target = db.get(SaleUser, body.user_id)
    row = db.get(MandiAssignment, (body.user_id, body.market_id))
    if not target or target.role != 'MANDI_STAFF' or not row:
        raise HTTPException(404, 'assigned_staff_not_found')
    if body.active:
        row.can_transact = body.can_transact
    else:
        db.delete(row)
    db.commit()
    return {'updated': True}


def validate_sale_market(db, body, registration):
    if registration:
        if not registration.active:
            raise HTTPException(409, 'mandi_online_requests_paused')
        if body.crop_id not in registration.commodity_ids:
            raise HTTPException(422, 'crop_not_accepted_by_mandi')
    else:
        authentic = db.scalar(select(MandiObservation.id).where(MandiObservation.market_id == body.mandi_id,
            MandiObservation.commodity_id == body.crop_id, MandiObservation.variety == body.variety,
            MandiObservation.grade == body.grade, MandiObservation.data_kind.in_(['official', 'secondary'])).limit(1))
        if not authentic:
            raise HTTPException(422, 'unknown_market_crop_series')
