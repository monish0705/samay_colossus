"""Transactional marketplace rules shared by HTTP handlers and tests."""
from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import select, update

from app.models import Commodity, MandiObservation, Market
from app.sale_auth import require_role
from app.sale_models import (
    ArrivalBooking,
    MandiAssignment,
    Notification,
    NotificationDelivery,
    NotificationOutbox,
    NotificationPreference,
    SaleEvent,
    SaleOffer,
    SaleRequest,
    SaleTransaction,
    SaleUser,
    now,
)

TRANSITIONS = {
    'SUBMITTED': {'NOTIFICATION_PENDING', 'NOTIFIED', 'CANCELLED'},
    'NOTIFICATION_PENDING': {'NOTIFIED', 'VIEWED', 'CANCELLED'},
    'NOTIFIED': {'VIEWED', 'CANCELLED'},
    'VIEWED': {'MANDI_ACCEPTED', 'COUNTER_OFFERED', 'REJECTED', 'CANCELLED'},
    'MANDI_ACCEPTED': {'FARMER_CONFIRMED', 'CANCELLED', 'EXPIRED', 'COUNTER_OFFERED'},
    'COUNTER_OFFERED': {'FARMER_CONFIRMED', 'CANCELLED', 'EXPIRED', 'COUNTER_OFFERED'},
    'FARMER_CONFIRMED': {'ARRIVAL_SCHEDULED'},
    'ARRIVAL_SCHEDULED': {'ARRIVED', 'CANCELLED'},
    'ARRIVED': {'WEIGHED'}, 'WEIGHED': {'COMPLETED'},
}


def money(value):
    return Decimal(value).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)


def assignment(db, user, market_id, transact=False):
    require_role(user, 'MANDI_OWNER', 'MANDI_STAFF')
    row = db.get(MandiAssignment, (user.id, market_id))
    if not row or (transact and user.role == 'MANDI_STAFF' and not row.can_transact):
        raise HTTPException(403, 'mandi_not_assigned_or_permission_denied')
    return row


def load_request(db, public_id, user, owner=False, transact=False):
    row = db.scalar(select(SaleRequest).where(SaleRequest.public_request_id == public_id))
    if not row:
        raise HTTPException(404, 'sale_request_not_found')
    if owner:
        assignment(db, user, row.mandi_id, transact)
    elif user.role != 'FARMER' or row.farmer_id != user.id:
        raise HTTPException(404, 'sale_request_not_found')
    return row


def notify(db, row, event, recipients):
    market = db.get(Market, row.mandi_id)
    crop = db.get(Commodity, row.crop_id)
    crop_kn = {'Tomato': 'ಟೊಮೇಟೊ', 'Onion': 'ಈರುಳ್ಳಿ', 'Potato': 'ಆಲೂಗಡ್ಡೆ', 'Copra': 'ಕೊಬ್ಬರಿ', 'Arecanut': 'ಅಡಿಕೆ'}.get(crop.name, crop.name)
    states_kn = {'NOTIFIED': 'ಹೊಸ ಮಾರಾಟ ವಿನಂತಿ ಬಂದಿದೆ', 'VIEWED': 'ವಿನಂತಿ ವೀಕ್ಷಿಸಲಾಗಿದೆ',
        'MANDI_ACCEPTED': 'ಮಂಡಿ ಒಪ್ಪಿದೆ; ಷರತ್ತುಗಳನ್ನು ಪರಿಶೀಲಿಸಿ ದೃಢೀಕರಿಸಿ', 'COUNTER_OFFERED': 'ಮಂಡಿ ಮರು ಪ್ರಸ್ತಾವನೆ ನೀಡಿದೆ; ಪರಿಶೀಲಿಸಿ ಸ್ವೀಕರಿಸಿ ಅಥವಾ ತಿರಸ್ಕರಿಸಿ',
        'FARMER_CONFIRMED': 'ರೈತರು ಷರತ್ತುಗಳನ್ನು ದೃಢೀಕರಿಸಿದ್ದಾರೆ', 'ARRIVAL_SCHEDULED': 'ಆಗಮನ ನಿಗದಿಯಾಗಿದೆ',
        'ARRIVED': 'ಉತ್ಪನ್ನ ಬಂದಿದೆ', 'WEIGHED': 'ತೂಕ ಮಾಡಲಾಗಿದೆ', 'COMPLETED': 'ಮಾರಾಟ ದಾಖಲೆ ಪೂರ್ಣಗೊಂಡಿದೆ',
        'REJECTED': 'ಮಂಡಿ ವಿನಂತಿಯನ್ನು ತಿರಸ್ಕರಿಸಿದೆ', 'CANCELLED': 'ವಿನಂತಿ ರದ್ದಾಗಿದೆ', 'EXPIRED': 'ಪ್ರಸ್ತಾವನೆಯ ಅವಧಿ ಮುಗಿದಿದೆ'}
    arrival = row.preferred_arrival_at.astimezone(ZoneInfo('Asia/Kolkata')).strftime('%d-%m-%Y %H:%M IST')
    for user in recipients:
        english = (f'SAMAY {row.public_request_id}: {event.to_status}. {crop.name}, '
                   f'{row.requested_quantity} quintals; farmer expected INR {row.expected_price_per_quintal}/quintal. '
                   f'{market.name}. Preferred arrival: {arrival}. Review terms in your authenticated portal.')
        kannada = (f'ಸಮಯ್ {row.public_request_id}: {states_kn.get(event.to_status, event.to_status)}. ಬೆಳೆ: {crop_kn}; '
                   f'ಪ್ರಮಾಣ: {row.requested_quantity} ಕ್ವಿಂಟಾಲ್; ರೈತರು ನಿರೀಕ್ಷಿಸಿದ ಬೆಲೆ: ರೂ {row.expected_price_per_quintal}/ಕ್ವಿಂಟಾಲ್. '
                   f'{market.name}. ಆಗಮನ: {arrival}. ನಿಮ್ಮ ಖಾತೆಯಲ್ಲಿ ವಿವರಗಳನ್ನು ಪರಿಶೀಲಿಸಿ.')
        if event.details.get('reason'):
            english += ' Reason: ' + event.details['reason']
            kannada += ' ಕಾರಣ: ' + event.details['reason']
        note = Notification(recipient_id=user.id, mandi_id=row.mandi_id, request_id=row.id,
                            event_id=event.id, message={'en': english, 'kn': kannada})
        db.add(note)
        db.flush()
        pref = db.get(NotificationPreference, user.id)
        for channel in ['email', 'sms', 'whatsapp']:
            if not pref or not getattr(pref, channel):
                continue
            verified = user.email_verified if channel == 'email' else user.phone_verified
            recipient = user.email if channel == 'email' else user.phone
            if not verified or not recipient:
                continue
            delivery = NotificationDelivery(notification_id=note.id, channel=channel,
                recipient=recipient, provider='smtp' if channel == 'email' else 'twilio', status='PENDING')
            db.add(delivery)
            db.flush()
            db.add(NotificationOutbox(delivery_id=delivery.id))


def owners(db, market_id):
    return list(db.scalars(select(SaleUser).join(MandiAssignment, MandiAssignment.user_id == SaleUser.id)
        .where(MandiAssignment.market_id == market_id, SaleUser.active.is_(True),
               SaleUser.role.in_(['MANDI_OWNER', 'MANDI_STAFF']))))


def transition(db, row, user, target, version, details=None, recipients=None):
    if row.version != version:
        raise HTTPException(409, 'request_changed_refresh_before_retry')
    if target not in TRANSITIONS.get(row.status, set()):
        raise HTTPException(409, 'invalid_state_transition')
    old = row.status
    changed = db.execute(update(SaleRequest).where(SaleRequest.id == row.id, SaleRequest.version == version)
        .values(status=target, version=version + 1, updated_at=now()), execution_options={'synchronize_session': False})
    if changed.rowcount != 1:
        raise HTTPException(409, 'concurrent_response_refresh_before_retry')
    db.refresh(row)
    event = SaleEvent(request_id=row.id, actor_id=user.id, from_status=old, to_status=target, details=details or {})
    db.add(event)
    db.flush()
    if recipients is not None:
        notify(db, row, event, recipients)
    return event


def latest_offer(db, row):
    return db.scalar(select(SaleOffer).where(SaleOffer.request_id == row.id).order_by(SaleOffer.id.desc()))


def expire(db, row, actor):
    offer = latest_offer(db, row)
    if row.status in {'MANDI_ACCEPTED', 'COUNTER_OFFERED'} and offer and offer.expires_at <= now():
        recipients = owners(db, row.mandi_id) + [db.get(SaleUser, row.farmer_id)]
        transition(db, row, actor, 'EXPIRED', row.version, recipients=recipients)
        db.commit()


def view(db, row, owner):
    if row.status in {'NOTIFICATION_PENDING', 'NOTIFIED'}:
        transition(db, row, owner, 'VIEWED', row.version, recipients=[db.get(SaleUser, row.farmer_id)])


def request_dict(db, row, user):
    offers = list(db.scalars(select(SaleOffer).where(SaleOffer.request_id == row.id).order_by(SaleOffer.id)))
    booking = db.scalar(select(ArrivalBooking).where(ArrivalBooking.request_id == row.id))
    transaction = db.scalar(select(SaleTransaction).where(SaleTransaction.request_id == row.id))
    observation = db.get(MandiObservation, row.reference_price_observation_id) if row.reference_price_observation_id else None
    farmer = db.get(SaleUser, row.farmer_id)
    result = {column.name: getattr(row, column.name) for column in row.__table__.columns
              if column.name not in {'payload_hash', 'idempotency_key', 'farmer_id'}}
    result.update(mandi_name=db.get(Market, row.mandi_id).name, crop_name=db.get(Commodity, row.crop_id).name,
        reference_price_date=observation.observed_on if observation else None,
        estimated_net_inr=money(row.requested_quantity * row.expected_price_per_quintal - row.estimated_costs_inr),
        offers=[{c.name: getattr(o, c.name) for c in o.__table__.columns} for o in offers],
        booking={c.name: getattr(booking, c.name) for c in booking.__table__.columns} if booking else None,
        transaction={c.name: getattr(transaction, c.name) for c in transaction.__table__.columns} if transaction else None,
        unit='INR/quintal', quantity_unit='quintals',
        payment_notice='Payment status is manually recorded; SAMAY does not transfer money.')
    if row.contact_sharing_consent and farmer.phone_verified:
        result['farmer_phone'] = farmer.phone
    def exact(value):
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, dict):
            return {key: exact(item) for key, item in value.items()}
        if isinstance(value, list):
            return [exact(item) for item in value]
        return value
    return exact(result)
