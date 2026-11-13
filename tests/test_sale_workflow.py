"""Isolated TEST_ONLY identities and transactions; never seeded into runtime data."""
import secrets
from datetime import timedelta

import pytest
from app.db import Base, make_engine
from app.main import app
from app.models import Commodity, MandiObservation, Market
from app.prices import get_session
from app.sale_auth import password_hash
from app.sale_models import (
    MandiAssignment,
    Notification,
    NotificationDelivery,
    NotificationOutbox,
    NotificationPreference,
    SaleEvent,
    SaleOffer,
    SaleRequest,
    SaleUser,
    now,
)
from app.sale_notifications import deliver_pending
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

HEADERS = {'X-SAMAY-Action': '1'}
PASSWORD = 'TEST_ONLY-password-2026'


@pytest.fixture
def market_app(tmp_path):
    engine = make_engine(f'sqlite:///{tmp_path / "test.db"}')
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    def dependency():
        with factory() as db:
            yield db
    app.dependency_overrides[get_session] = dependency
    with factory() as db:
        market = Market(name='TEST_ONLY mandi', district='Kolar', state='Karnataka', data_source='TEST_ONLY')
        crop = Commodity(name='TEST_ONLY crop', data_source='TEST_ONLY')
        admin = SaleUser(name='TEST_ONLY admin', email='admin@example.test', password_hash=password_hash(PASSWORD), role='SYSTEM_ADMIN')
        db.add_all([market, crop, admin])
        db.flush()
        db.add(MandiObservation(market_id=market.id, commodity_id=crop.id, observed_on=now().date(), variety='local', grade='faq',
            data_kind='official', min_price_inr_per_quintal=900, modal_price_inr_per_quintal=1000,
            max_price_inr_per_quintal=1100, data_source='TEST_ONLY fixture'))
        db.commit()
        market_id, crop_id = market.id, crop.id
    clients = [TestClient(app) for _ in range(4)]
    for client in clients:
        client.headers.update(HEADERS)
    admin, farmer, owner, stranger = clients
    assert admin.post('/api/v1/auth/login', json={'email': 'admin@example.test', 'password': PASSWORD}).status_code == 200
    assert admin.post('/api/v1/admin/mandis', json={'market_id': market_id, 'active': True,
        'registration_details': 'TEST_ONLY authorization evidence', 'commodity_ids': [crop_id]}).status_code == 200
    token = admin.post('/api/v1/admin/mandi-invitations', json={'email': 'owner@example.test', 'role': 'MANDI_OWNER',
        'market_id': market_id, 'identity_evidence': 'TEST_ONLY independent identity checks'}).json()['invitation_token']
    for client, email, invitation in [(farmer, 'farmer@example.test', None), (owner, 'owner@example.test', token), (stranger, 'stranger@example.test', None)]:
        payload = {'email': email, 'password': PASSWORD, 'name': 'TEST_ONLY account'}
        if invitation:
            payload['invitation_token'] = invitation
        assert client.post('/api/v1/auth/register', json=payload).status_code == 201
    yield factory, admin, farmer, owner, stranger, market_id, crop_id
    for client in clients:
        client.close()
    app.dependency_overrides.clear()
    engine.dispose()


def create(market_app, **changes):
    _, _, farmer, _, _, market, crop = market_app
    payload = {'mandi_id': market, 'crop_id': crop, 'variety': 'local', 'grade': 'faq', 'total_harvest_quantity': '20',
        'requested_quantity': '12', 'expected_price_per_quintal': '1000', 'estimated_costs_inr': '300',
        'preferred_arrival_at': (now() + timedelta(days=2)).isoformat(), 'farmer_message': 'TEST_ONLY request', **changes}
    key = secrets.token_hex(16)
    return farmer.post('/api/v1/sale-requests', json=payload, headers={'Idempotency-Key': key}), payload, key


def make_offer(market_app, sale, **changes):
    owner = market_app[3]
    sale = owner.post(f'/api/v1/mandi/requests/{sale["public_request_id"]}/view', json={}).json()
    terms = {'version': sale['version'], 'quantity': '10', 'price': '1050',
        'arrival_at': (now() + timedelta(days=2)).isoformat(), 'expires_at': (now() + timedelta(hours=12)).isoformat(), **changes}
    return owner.post(f'/api/v1/mandi/requests/{sale["public_request_id"]}/counteroffer', json=terms), terms


def test_complete_lifecycle_partial_quantity_and_exact_money(market_app):
    factory, _, farmer, owner, stranger, _, _ = market_app
    response, _, _ = create(market_app)
    assert response.status_code == 201, response.text
    sale = response.json()
    public = sale['public_request_id']
    assert sale['reference_modal_price'] == '1000.00'
    assert sale['estimated_net_inr'] == '11700.00'
    assert owner.get('/api/v1/notifications/unread-count').json()['count'] == 1
    note = owner.get('/api/v1/mandi/notifications').json()[0]
    assert stranger.post(f'/api/v1/notifications/{note["id"]}/read', json={}).status_code == 404
    assert owner.post(f'/api/v1/notifications/{note["id"]}/read', json={}).status_code == 200
    offered, _ = make_offer(market_app, sale)
    assert offered.status_code == 200, offered.text
    sale = offered.json()
    offer = sale['offers'][-1]
    assert farmer.get('/api/v1/notifications/unread-count').json()['count'] >= 1
    sale = farmer.post(f'/api/v1/sale-requests/{public}/confirm', json={'version': sale['version'], 'offer_id': offer['id']}).json()
    assert sale['status'] == 'ARRIVAL_SCHEDULED'
    assert sale['booking']
    sale = owner.post(f'/api/v1/mandi/requests/{public}/mark-arrived', json={'version': sale['version'], 'received_quantity': '9.8'}).json()
    assert sale['status'] == 'ARRIVED'
    sale = owner.post(f'/api/v1/mandi/requests/{public}/record-weighment', json={'version': sale['version'], 'weighed_quantity': '9.725',
        'final_price': '1049.95', 'deductions_inr': '250.75', 'quality': 'TEST_ONLY inspected', 'payment_status': 'PENDING'}).json()
    assert sale['status'] == 'WEIGHED'
    assert sale['transaction']['gross_inr'] == '10210.76'
    assert sale['transaction']['net_inr'] == '9960.01'
    sale = owner.post(f'/api/v1/mandi/requests/{public}/complete', json={'version': sale['version']}).json()
    assert sale['status'] == 'COMPLETED'
    assert farmer.get(f'/api/v1/sale-requests/{public}').json()['transaction']['payment_status'] == 'PENDING'
    assert farmer.post(f'/api/v1/sale-requests/{public}/discrepancy', json={'version': sale['version'], 'reason': 'TEST_ONLY quantity discrepancy'}).status_code == 200
    timeline = farmer.get(f'/api/v1/sale-requests/{public}/timeline').json()
    assert [e['to_status'] for e in timeline[:9]] == ['SUBMITTED', 'NOTIFIED', 'VIEWED', 'COUNTER_OFFERED', 'FARMER_CONFIRMED', 'ARRIVAL_SCHEDULED', 'ARRIVED', 'WEIGHED', 'COMPLETED']
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(SaleRequest)) == 1
        assert db.scalar(select(func.count()).select_from(SaleEvent)) >= 10


def test_idempotency_and_private_access(market_app):
    _, _, farmer, owner, stranger, _, _ = market_app
    response, payload, key = create(market_app)
    public = response.json()['public_request_id']
    repeat = farmer.post('/api/v1/sale-requests', json=payload, headers={'Idempotency-Key': key})
    assert repeat.json()['public_request_id'] == public
    assert farmer.post('/api/v1/sale-requests', json={**payload, 'requested_quantity': '1'}, headers={'Idempotency-Key': key}).status_code == 409
    assert stranger.get(f'/api/v1/sale-requests/{public}').status_code == 404
    assert stranger.get(f'/api/v1/mandi/requests/{public}').status_code == 403
    assert owner.get(f'/api/v1/sale-requests/{public}').status_code == 404
    assert farmer.post(f'/api/v1/mandi/requests/{public}/complete', json={'version': 2}).status_code == 403
    assert owner.post(f'/api/v1/mandi/requests/{public}/complete', json={'version': 2}).status_code == 409


def test_no_owner_and_csrf_and_role_escalation(market_app):
    factory, _, farmer, _, _, market, _ = market_app
    with factory() as db:
        for assignment in db.scalars(select(MandiAssignment)):
            db.delete(assignment)
        db.commit()
    response, _, _ = create(market_app)
    assert response.status_code == 409
    assert not next(m for m in farmer.get('/api/v1/sale-mandis').json() if m['id'] == market)['online_requests_available']
    unauthenticated = TestClient(app)
    assert unauthenticated.post('/api/v1/auth/login', json={'email': 'x@y.test', 'password': PASSWORD}).status_code == 403
    assert farmer.post('/api/v1/auth/register', json={'email': 'hack@example.test', 'password': PASSWORD, 'name': 'bad', 'role': 'SYSTEM_ADMIN'}).status_code == 422


def test_expiry_and_concurrent_revision(market_app, monkeypatch):
    _, _, farmer, owner, _, _, _ = market_app
    response, _, _ = create(market_app)
    sale = response.json()
    public = sale['public_request_id']
    offered, terms = make_offer(market_app, sale)
    sale = offered.json()
    assert owner.post(f'/api/v1/mandi/requests/{public}/counteroffer', json=terms).status_code == 409
    monkeypatch.setattr('app.sale_service.now', lambda: now() + timedelta(days=1))
    response = farmer.post(f'/api/v1/sale-requests/{public}/confirm', json={'version': sale['version'], 'offer_id': sale['offers'][-1]['id']})
    assert response.status_code == 409
    assert farmer.get(f'/api/v1/sale-requests/{public}').json()['status'] == 'EXPIRED'


@pytest.mark.parametrize('action', ['cancel', 'reject-offer'])
def test_farmer_declines_or_cancels(market_app, action):
    farmer = market_app[2]
    response, _, _ = create(market_app)
    offered, _ = make_offer(market_app, response.json())
    sale = offered.json()
    response = farmer.post(f'/api/v1/sale-requests/{sale["public_request_id"]}/{action}', json={'version': sale['version'], 'reason': 'TEST_ONLY decline'})
    assert response.status_code == 200
    assert response.json()['status'] == 'CANCELLED'


@pytest.mark.parametrize('channel', ['email', 'sms', 'whatsapp'])
def test_external_failure_keeps_request_and_in_app_inbox(market_app, monkeypatch, channel):
    factory, _, _, owner, _, _, _ = market_app
    with factory() as db:
        user = db.scalar(select(SaleUser).where(SaleUser.role == 'MANDI_OWNER'))
        user.email_verified, user.phone_verified, user.phone = True, True, '+919000000000'
        pref = db.get(NotificationPreference, user.id)
        setattr(pref, channel, True)
        db.commit()
    response, _, _ = create(market_app)
    assert response.status_code == 201
    monkeypatch.setattr('app.sale_notifications.channel_availability', lambda: {channel: 'configured_untested'})
    def fail(*args, **kwargs):
        raise TimeoutError('TEST_ONLY provider unavailable')
    monkeypatch.setattr('app.sale_notifications.send_email', fail)
    monkeypatch.setattr('app.sale_notifications.twilio_send', fail)
    assert deliver_pending(factory) == 1
    with factory() as db:
        delivery = db.scalar(select(NotificationDelivery))
        assert delivery.status == 'UNKNOWN'
        assert db.scalar(select(func.count()).select_from(SaleRequest)) == 1
        assert db.scalar(select(func.count()).select_from(Notification)) == 1
        assert db.scalar(select(NotificationOutbox)).done
    assert owner.get('/api/v1/notifications/unread-count').json()['count'] == 1


def test_unconfigured_channels_remain_durable(market_app, monkeypatch):
    factory, _, _, _, _, _, _ = market_app
    with factory() as db:
        owner = db.scalar(select(SaleUser).where(SaleUser.role == 'MANDI_OWNER'))
        owner.email_verified = True
        db.get(NotificationPreference, owner.id).email = True
        db.commit()
    create(market_app)
    monkeypatch.setattr('app.sale_notifications.channel_availability', lambda: {'email': 'not_configured'})
    assert deliver_pending(factory) == 0
    with factory() as db:
        assert db.scalar(select(NotificationDelivery)).status == 'RETRY_SCHEDULED'
        assert not db.scalar(select(NotificationOutbox)).done


@pytest.mark.parametrize('changes', [{'requested_quantity': '-1'}, {'requested_quantity': '21'}, {'expected_price_per_quintal': '0'}, {'expected_price_per_quintal': 'NaN'}, {'estimated_costs_inr': '-1'}, {'preferred_arrival_at': '2026-01-01T10:00:00'}])
def test_strict_input_validation(market_app, changes):
    response, _, _ = create(market_app, **changes)
    assert response.status_code == 422


def test_cross_mandi_isolation_and_staff_permissions(market_app):
    factory, _, _, owner, _, _, _ = market_app
    response, _, _ = create(market_app)
    public = response.json()['public_request_id']
    with factory() as db:
        user = db.scalar(select(SaleUser).where(SaleUser.role == 'MANDI_OWNER'))
        mapping = db.scalar(select(MandiAssignment).where(MandiAssignment.user_id == user.id))
        other = Market(name='OTHER TEST_ONLY', district='Other', state='Karnataka', data_source='TEST_ONLY')
        db.add(other)
        db.flush()
        original_market = mapping.market_id
        db.delete(mapping)
        db.add(MandiAssignment(user_id=user.id, market_id=other.id))
        db.commit()
    assert owner.get(f'/api/v1/mandi/requests/{public}').status_code == 403
    assert owner.get('/api/v1/mandi/requests').json() == []
    with factory() as db:
        user = db.scalar(select(SaleUser).where(SaleUser.role == 'MANDI_OWNER'))
        user.role = 'MANDI_STAFF'
        db.add(MandiAssignment(user_id=user.id, market_id=original_market, can_transact=False))
        db.commit()
    assert owner.post(f'/api/v1/mandi/requests/{public}/view', json={}).status_code == 200
    assert owner.post(f'/api/v1/mandi/requests/{public}/reject', json={'version': 3, 'reason': 'TEST_ONLY'}).status_code == 403


def test_offers_append_only_and_mandi_rejection(market_app):
    factory, _, farmer, owner, _, _, _ = market_app
    response, _, _ = create(market_app)
    offered, _ = make_offer(market_app, response.json())
    sale = offered.json()
    second, _ = make_offer(market_app, sale, price='1100')
    assert second.status_code == 200
    assert len(second.json()['offers']) == 2
    assert farmer.post(f'/api/v1/sale-requests/{sale["public_request_id"]}/confirm', json={'version': second.json()['version'], 'offer_id': sale['offers'][0]['id']}).status_code == 409
    response, _, _ = create(market_app)
    sale = owner.post(f'/api/v1/mandi/requests/{response.json()["public_request_id"]}/view', json={}).json()
    assert owner.post(f'/api/v1/mandi/requests/{sale["public_request_id"]}/reject', json={'version': sale['version'], 'reason': 'No available slot'}).json()['status'] == 'REJECTED'
    with factory() as db:
        assert len(list(db.scalars(select(SaleOffer)))) == 2


def test_simultaneous_owner_responses_only_one_wins(market_app):
    from concurrent.futures import ThreadPoolExecutor
    owner = market_app[3]
    response, _, _ = create(market_app)
    public = response.json()['public_request_id']
    sale = owner.post(f'/api/v1/mandi/requests/{public}/view', json={}).json()
    def respond(reason):
        with TestClient(app) as client:
            client.cookies.update(owner.cookies)
            return client.post(f'/api/v1/mandi/requests/{public}/reject', headers=HEADERS,
                json={'version': sale['version'], 'reason': reason}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        codes = list(pool.map(respond, ['TEST_ONLY first', 'TEST_ONLY second']))
    assert sorted(codes) == [200, 409]


def test_notification_creation_failure_rolls_back_entire_submission(market_app, monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError('TEST_ONLY outbox unavailable')
    monkeypatch.setattr('app.sale_routes.notify', fail)
    response, _, _ = create(market_app)
    assert response.status_code == 500
    with market_app[0]() as db:
        assert db.scalar(select(func.count()).select_from(SaleRequest)) == 0
        assert db.scalar(select(func.count()).select_from(SaleEvent)) == 0


def test_email_consent_and_durable_storage_gate(market_app, monkeypatch):
    farmer = market_app[2]
    assert farmer.post('/api/v1/notification-preferences', json={'email': True}).status_code == 409
    assert farmer.post('/api/v1/auth/verify-email/confirm', json={'token': 'invalid-token-with-enough-length'}).status_code == 400
    monkeypatch.setenv('SAMAY_MARKETPLACE_ENABLED', 'false')
    from app.config import get_settings
    get_settings.cache_clear()
    try:
        assert farmer.get('/api/v1/sale-requests').status_code == 503
    finally:
        get_settings.cache_clear()


def test_public_bundle_refuses_marketplace_identity(market_app):
    import sqlite3

    from app.prepared_data import assert_public_market_snapshot
    factory = market_app[0]
    with factory() as db, sqlite3.connect(db.bind.url.database) as raw:
        with pytest.raises(ValueError, match='private marketplace data'):
            assert_public_market_snapshot(raw)


def test_email_verification_proves_mailbox_token_before_consent(market_app, monkeypatch):
    farmer = market_app[2]
    sent = []
    monkeypatch.setattr('app.sale_notifications.send_email', lambda recipient, subject, message: sent.append(message))
    result = farmer.post('/api/v1/auth/verify-email/start', json={})
    assert result.status_code == 200
    token = sent[0].rsplit(' ', 1)[1]
    assert token not in result.text
    assert not farmer.get('/api/v1/auth/me').json()['email_verified']
    assert farmer.post('/api/v1/auth/verify-email/confirm', json={'token': token}).json()['email_verified']
    assert farmer.post('/api/v1/auth/verify-email/confirm', json={'token': token}).status_code == 400
    assert farmer.post('/api/v1/notification-preferences', json={'email': True}).status_code == 200


def test_frozen_migration_and_immutable_audit(tmp_path, monkeypatch):
    from alembic import command
    from alembic.config import Config
    from app.config import ROOT, get_settings
    from sqlalchemy import inspect, text
    from sqlalchemy.exc import IntegrityError
    monkeypatch.setenv('SAMAY_DATABASE_URL', f'sqlite:///{tmp_path / "migrated.db"}')
    get_settings.cache_clear()
    config = Config(str(ROOT / 'backend/alembic.ini'))
    engine = make_engine(f'sqlite:///{tmp_path / "migrated.db"}')
    try:
        command.upgrade(config, 'head')
        command.upgrade(config, 'head')
        assert {'sale_requests', 'notification_outbox', 'mandi_users'} <= set(inspect(engine).get_table_names())
        with sessionmaker(bind=engine)() as db:
            farmer = SaleUser(email='audit@example.test', name='TEST_ONLY', password_hash='NOT_A_LOGIN', role='FARMER')
            market = Market(name='TEST_ONLY', district='Kolar', state='Karnataka', data_source='TEST_ONLY')
            crop = Commodity(name='TEST_ONLY', data_source='TEST_ONLY')
            db.add_all([farmer, market, crop])
            db.flush()
            sale = SaleRequest(public_request_id='TEST_ONLY-audit', farmer_id=farmer.id, mandi_id=market.id, crop_id=crop.id,
                variety='local', grade='faq', total_harvest_quantity=10, requested_quantity=5, expected_price_per_quintal=1000,
                preferred_arrival_at=now() + timedelta(days=2), estimated_costs_inr=0, status='SUBMITTED',
                idempotency_key='TEST_ONLY-audit-idempotency', payload_hash='0' * 64)
            db.add(sale)
            db.flush()
            db.add(SaleEvent(request_id=sale.id, actor_id=farmer.id, from_status=None, to_status='SUBMITTED', details={}))
            db.commit()
            with pytest.raises(IntegrityError, match='immutable audit history'):
                db.execute(text("UPDATE sale_request_events SET to_status='COMPLETED'"))
            db.rollback()
        command.downgrade(config, 'b2c3d4e5f6a7')
        assert 'sale_requests' not in inspect(engine).get_table_names()
        command.upgrade(config, 'head')
    finally:
        engine.dispose()
        get_settings.cache_clear()
