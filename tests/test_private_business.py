"""Private business foundation. All identities and documents are TEST_ONLY fixtures."""
import secrets

import pytest
from app.business_models import AccountRole, BusinessAccount, BusinessMarketAssignment, BusinessRole
from app.business_service import may_publish
from app.models import Market
from app.sale_models import SaleUser
from sqlalchemy import func, select

pytest_plugins = ['test_sale_workflow']


def application(market_app, kind='PRIVATE_MANDI', client=None):
    crop_id = market_app[6]
    body = {'business_type': kind, 'name': f'TEST_ONLY {kind}', 'contact_name': 'TEST_ONLY contact',
        'phone': '+919000000000', 'email': 'business@example.test', 'address': 'TEST_ONLY protected address',
        'district': 'Kolar', 'state': 'Karnataka', 'registration_details': 'TEST_ONLY registration reference',
        'verification_information': 'TEST_ONLY verification documents supplied independently',
        'document_references': ['TEST_ONLY protected document reference'], 'commodity_ids': [crop_id],
        **({'operating_hours': 'TEST_ONLY 09:00–17:00'} if kind == 'PRIVATE_MANDI' else {'buyer_type': 'INDIVIDUAL_TRADER'})}
    key = secrets.token_hex(16)
    response = (client or market_app[2]).post('/api/v1/business/register', json=body, headers={'Idempotency-Key': key})
    assert response.status_code == 201, response.text
    return response.json(), body, key


def review(client, business, state='VERIFIED', **extra):
    return client.post(f'/api/v1/admin/businesses/{business["id"]}/verify', json={
        'version': business['version'], 'state': state, 'evidence': 'TEST_ONLY independently checked identity and contact',
        'contact_verified': True, 'registration_checked': True, 'documents_required': True, **extra})


@pytest.mark.parametrize('kind,role', [('PRIVATE_MANDI', 'PRIVATE_MANDI_OWNER'), ('PRIVATE_BUYER', 'PRIVATE_BUYER')])
def test_registration_is_pending_and_admin_approval_grants_scoped_role(market_app, kind, role):
    factory, admin, farmer, _, _, _, _ = market_app
    with factory() as db:
        original_markets = db.scalar(select(func.count()).select_from(Market))
    business, _, _ = application(market_app, kind)
    assert business['verification_state'] == 'PENDING_VERIFICATION'
    assert business['can_publish'] is False and business['is_apmc'] is False
    assert role not in farmer.get('/api/v1/business/roles').json()['roles']
    denied = farmer.post('/api/v1/business/active-role', json={'mode': 'BUSINESS', 'business_id': business['id'], 'role': role})
    assert denied.status_code == 403
    approved = review(admin, business)
    assert approved.status_code == 200, approved.text
    assert approved.json()['can_publish'] is False  # Admin is the reviewer, not the owner's member.
    profile = farmer.get(f'/api/v1/business/profile?business_id={business["id"]}').json()
    assert profile['can_publish'] is True
    assert {'FARMER', role} <= set(farmer.get('/api/v1/business/roles').json()['roles'])
    assert farmer.get(f'/api/v1/business/workspace/{business["id"]}').status_code == 200
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(Market)) == original_markets
        owner = db.get(SaleUser, profile['created_by'])
        assert may_publish(db, owner, business['id']).id == business['id']
        assert owner.role == 'FARMER'  # Legacy role and APMC code are preserved.


def test_multi_business_workspace_persists_and_revocation_fails_closed(market_app):
    _, admin, farmer, _, _, _, _ = market_app
    mandi, _, _ = application(market_app)
    buyer, _, _ = application(market_app, 'PRIVATE_BUYER')
    assert review(admin, mandi).status_code == 200
    approved_buyer = review(admin, buyer).json()
    roles = farmer.get('/api/v1/business/roles').json()
    assert len(roles['workspaces']) == 2
    selection = {'mode': 'BUSINESS', 'business_id': buyer['id'], 'role': 'PRIVATE_BUYER'}
    assert farmer.post('/api/v1/business/active-role', json=selection).status_code == 200
    # New request and a new authenticated session both restore server-side preference.
    assert farmer.get('/api/v1/business/roles').json()['active_workspace']['business_id'] == buyer['id']
    assert farmer.post('/api/v1/auth/login', json={'email': 'farmer@example.test', 'password': 'TEST_ONLY-password-2026'}).status_code == 200
    assert farmer.get('/api/v1/business/roles').json()['active_workspace']['mode'] == 'BUSINESS'
    suspended = review(admin, approved_buyer, 'SUSPENDED').json()
    assert suspended['verification_state'] == 'SUSPENDED'
    after = farmer.get('/api/v1/business/roles').json()
    assert 'PRIVATE_BUYER' not in after['roles']
    assert 'PRIVATE_MANDI_OWNER' in after['roles']
    assert after['active_workspace']['mode'] == 'FARMER'
    assert farmer.post('/api/v1/business/active-role', json=selection).status_code == 403
    assert farmer.get(f'/api/v1/business/workspace/{buyer["id"]}').status_code == 403
    history = farmer.get(f'/api/v1/business/verification-status?business_id={buyer["id"]}').json()['history']
    assert [item['to_state'] for item in history] == ['VERIFIED', 'SUSPENDED']


def test_business_and_admin_isolation_and_no_frontend_role_escalation(market_app):
    factory, admin, farmer, _, stranger, _, _ = market_app
    business, body, key = application(market_app)
    assert farmer.post(f'/api/v1/admin/businesses/{business["id"]}/verify', json={'version': 1, 'state': 'VERIFIED', 'evidence': 'TEST_ONLY forged review'}).status_code == 403
    assert stranger.get(f'/api/v1/business/profile?business_id={business["id"]}').status_code == 404
    assert stranger.get(f'/api/v1/business/verification-status?business_id={business["id"]}').status_code == 404
    assert stranger.get('/api/v1/admin/businesses/pending').status_code == 403
    assert stranger.post('/api/v1/business/active-role', json={'mode': 'BUSINESS', 'business_id': business['id'], 'role': 'PRIVATE_MANDI_OWNER'}).status_code == 403
    for forbidden in [{'role': 'SYSTEM_ADMIN'}, {'verification_state': 'VERIFIED'}, {'created_by': 999}]:
        assert farmer.post('/api/v1/business/register', json={**body, **forbidden}, headers={'Idempotency-Key': secrets.token_hex(16)}).status_code == 422
    assert len(admin.get('/api/v1/admin/businesses/pending').json()) == 1
    assert farmer.post('/api/v1/business/register', json=body, headers={'Idempotency-Key': key}).json()['id'] == business['id']
    assert farmer.post('/api/v1/business/register', json={**body, 'name': 'CHANGED'}, headers={'Idempotency-Key': key}).status_code == 409
    with factory() as db:
        assert not list(db.scalars(select(BusinessRole)))


def test_verification_evidence_versions_rejection_and_reapplication(market_app):
    _, admin, farmer, _, _, _, _ = market_app
    business, _, _ = application(market_app)
    assert review(admin, business, contact_verified=False).status_code == 422
    assert review(admin, business, registration_checked=False).status_code == 422
    assert review(admin, business, version=99).status_code == 409
    rejected = review(admin, business, 'REJECTED').json()
    assert rejected['verification_state'] == 'REJECTED'
    assert review(admin, rejected).status_code == 409
    pending = review(admin, rejected, 'PENDING_VERIFICATION').json()
    assert review(admin, pending).status_code == 200
    assert farmer.get('/api/v1/business/roles').json()['workspaces']


def test_staff_permissions_and_cross_private_market_assignment(market_app):
    factory, admin, farmer, _, stranger, _, _ = market_app
    first, _, _ = application(market_app)
    second, _, _ = application(market_app, client=stranger)
    verified_first = review(admin, first).json()
    verified_second = review(admin, second).json()
    target_id = stranger.get('/api/v1/auth/me').json()['id']
    assert admin.post(f'/api/v1/admin/businesses/{first["id"]}/market-assignment', json={'private_mandi_id': verified_second['private_mandi_id']}).status_code == 422
    assert admin.post(f'/api/v1/admin/businesses/{first["id"]}/members', json={'user_id': target_id, 'role': 'PRIVATE_BUYER'}).status_code == 422
    assert admin.post(f'/api/v1/admin/businesses/{first["id"]}/members', json={'user_id': target_id, 'role': 'MANDI_STAFF', 'can_manage': False}).status_code == 200
    assert stranger.get(f'/api/v1/business/workspace/{first["id"]}').status_code == 200
    with factory() as db:
        with pytest.raises(Exception) as denied:
            may_publish(db, db.get(SaleUser, target_id), first['id'])
        assert denied.value.status_code == 403
        assert db.get(BusinessMarketAssignment, first['id']).private_mandi_id == verified_first['private_mandi_id']
    assert admin.post(f'/api/v1/admin/businesses/{first["id"]}/members', json={'user_id': target_id, 'role': 'MANDI_STAFF', 'active': False}).status_code == 200
    assert stranger.get(f'/api/v1/business/workspace/{first["id"]}').status_code == 404


def test_pending_businesses_cannot_publish_and_private_data_is_not_public(market_app):
    import sqlite3

    from app.prepared_data import assert_public_market_snapshot
    factory, _, farmer, _, _, _, _ = market_app
    business, _, _ = application(market_app)
    with factory() as db:
        applicant = db.get(SaleUser, business['created_by'])
        with pytest.raises(Exception) as denied:
            may_publish(db, applicant, business['id'])
        assert denied.value.status_code == 403
        with sqlite3.connect(db.bind.url.database) as connection:
            with pytest.raises(ValueError, match='private marketplace data'):
                assert_public_market_snapshot(connection)
    assert farmer.get('/api/v1/business/profile').headers['cache-control'] == 'private, no-store'


def test_migration_backfills_legacy_roles_and_preserves_accounts(tmp_path, monkeypatch):
    from alembic import command
    from alembic.config import Config
    from app.config import ROOT, get_settings
    from app.db import make_engine
    from sqlalchemy import inspect, text
    from sqlalchemy.orm import Session
    monkeypatch.setenv('SAMAY_DATABASE_URL', f'sqlite:///{tmp_path / "private.db"}')
    get_settings.cache_clear()
    config = Config(str(ROOT / 'backend/alembic.ini'))
    engine = make_engine(f'sqlite:///{tmp_path / "private.db"}')
    try:
        command.upgrade(config, 'c3d4e5f6a7b8')
        with Session(engine) as db:
            db.add(SaleUser(email='legacy@example.test', name='TEST_ONLY legacy APMC owner', password_hash='UNCHANGED_TEST_ONLY_HASH', role='MANDI_OWNER'))
            db.commit()
        command.upgrade(config, 'head')
        command.upgrade(config, 'head')
        with Session(engine) as db:
            user = db.scalar(select(SaleUser))
            assert user.role == 'MANDI_OWNER' and user.password_hash == 'UNCHANGED_TEST_ONLY_HASH'
            assert db.get(AccountRole, (user.id, 'MANDI_OWNER'))
            assert db.scalar(select(func.count()).select_from(BusinessAccount)) == 0
        assert {'private_mandis', 'private_buyers', 'business_roles'} <= set(inspect(engine).get_table_names())
        command.downgrade(config, 'c3d4e5f6a7b8')
        with engine.connect() as connection:
            assert connection.execute(text('SELECT role FROM mandi_users')).scalar_one() == 'MANDI_OWNER'
        command.upgrade(config, 'head')
    finally:
        engine.dispose()
        get_settings.cache_clear()
