"""TEST_ONLY local transactions, no real business approvals or selling claims."""

import secrets
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal

import pytest
from app import purchase_service as svc
from app.purchase_models import FarmerPurchaseRequest, PurchaseNotification, PurchaseOffer, PurchaseReservation
from app.purchase_schemas import ResponseInput
from app.sale_models import SaleUser, now
from fastapi import HTTPException
from sqlalchemy import func, select
from test_private_business import application, review

pytest_plugins = ["test_sale_workflow"]


def setup_business(market_app, kind="PRIVATE_BUYER"):
    _, admin, _, owner, _, _, _ = market_app
    b, _, _ = application(market_app, kind, owner)
    assert review(admin, b).status_code == 200
    role = "PRIVATE_BUYER" if kind == "PRIVATE_BUYER" else "PRIVATE_MANDI_OWNER"
    assert owner.post("/api/v1/business/active-role", json={"mode": "BUSINESS", "business_id": b["id"], "role": role}).status_code == 200
    return b, owner


def offer_body(market_app, business_id, **extra):
    start, end = now() - timedelta(hours=1), now() + timedelta(days=7)
    return {
        "business_id": business_id,
        "commodity_id": market_app[6],
        "variety": "local",
        "grade": "faq",
        "crop_condition": "TEST_ONLY fresh",
        "quality_standards": "TEST_ONLY clean",
        "total_quantity": "100",
        "minimum_quantity": "1",
        "maximum_quantity": "100",
        "daily_intake": None,
        "offered_price": "1000.25",
        "price_kind": "NEGOTIABLE",
        "minimum_price": "900",
        "maximum_price": "1200",
        "price_basis": "TEST_ONLY INR/quintal after inspection",
        "price_valid_until": end.isoformat(),
        "purchasing_centre": "TEST_ONLY centre",
        "address": "TEST_ONLY address",
        "district": "Kolar",
        "state": "Karnataka",
        "service_area": "TEST_ONLY local area",
        "transport": "FARMER_DELIVERY",
        "pickup_charge": None,
        "unloading_charge": "5",
        "charge_basis": "INR_PER_QUINTAL",
        "weighment": "TEST_ONLY scale",
        "arrival_dates": [(now() + timedelta(days=2)).date().isoformat()],
        "payment_methods": ["TEST_ONLY bank transfer"],
        "payment_timing": "TEST_ONLY after verification",
        "payment_terms": "TEST_ONLY explicitly confirmed terms",
        "known_deductions": "TEST_ONLY unloading charge",
        "contact_availability": "TEST_ONLY business hours",
        "starts_at": start.isoformat(),
        "expires_at": end.isoformat(),
        **extra,
    }


def create_offer(market_app, client, b, **extra):
    body = offer_body(market_app, b["id"], **extra)
    key = secrets.token_hex(16)
    response = client.post("/api/v1/business/offers", json=body, headers={"Idempotency-Key": key})
    assert response.status_code == 201, response.text
    row = response.json()
    published = client.post(f"/api/v1/business/offers/{row['id']}/publish", json={"version": row["version"]})
    assert published.status_code == 200, published.text
    return published.json(), body, key


def request(market_app, offer, client=None, amount="20", **extra):
    client = client or market_app[2]
    body = {
        "offer_version": offer["version"],
        "available_quantity": "100",
        "quantity": amount,
        "expected_price": "1000",
        "variety": "local",
        "grade": "faq",
        "arrival_at": (now() + timedelta(days=2)).isoformat(),
        "quality_confirmed": True,
        "terms_confirmed": True,
        **extra,
    }
    return client.post(
        f"/api/v1/private-purchases/offers/{offer['id']}/requests", json=body, headers={"Idempotency-Key": secrets.token_hex(16)}
    )


def response_body(req, quantity="20", **extra):
    return {
        "version": req["version"],
        "quantity": quantity,
        "price": "1001.25",
        "arrival_at": req["arrival_at"],
        "expires_at": (now() + timedelta(hours=5)).isoformat(),
        "payment_terms": "TEST_ONLY agreed payment after weighing",
        **extra,
    }


@pytest.mark.parametrize("kind", ["PRIVATE_BUYER", "PRIVATE_MANDI"])
def test_publish_edit_freeze_reserve_confirm_and_analytics(market_app, kind):
    _, _, farmer, _, _, _, _ = market_app
    b, owner = setup_business(market_app, kind)
    o, body, key = create_offer(market_app, owner, b)
    assert o["status"] == "PUBLISHED" and o["quantity_remaining"] == "100.000"
    assert owner.post("/api/v1/business/offers", json=body, headers={"Idempotency-Key": key}).json()["id"] == o["id"]
    req = request(market_app, o).json()
    assert owner.get(f"/api/v1/business/purchase-notifications?business_id={b['id']}").json()["unread"] == 1
    assert owner.get(f"/api/v1/business/offers/{o['id']}").json()["quantity_remaining"] == "100.000"
    accepted = owner.post(f"/api/v1/business/requests/{req['id']}/accept", json=response_body(req)).json()
    assert accepted["status"] == "ACCEPTED"
    o = owner.get(f"/api/v1/business/offers/{o['id']}").json()
    assert o["quantity_reserved"] == "20.000" and o["quantity_committed"] == "0.000"
    edited = {k: v for k, v in body.items() if k != "business_id"}
    edited.update(version=o["version"], offered_price="1100")
    update = owner.put(f"/api/v1/business/offers/{o['id']}", json=edited)
    assert update.status_code == 200, update.text
    assert farmer.get("/api/v1/private-purchases/notifications").json()
    confirmed = farmer.post(f"/api/v1/private-purchases/requests/{req['id']}/confirm", json={"version": accepted["version"]})
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["responses"][0]["price"] == "1001.25"
    assert confirmed.json()["responses"][0]["terms"]["offered_price"] == "1000.25"
    current = owner.get(f"/api/v1/business/offers/{o['id']}").json()
    assert current["quantity_remaining"] == "80.000" and current["quantity_committed"] == "20.000"
    assert [p["price"] for p in current["price_history"]] == ["1000.25", "1100.00"]
    analytics = owner.get(f"/api/v1/business/analytics?business_id={b['id']}").json()
    assert analytics["confirmed_quantity"] == "20.000" and analytics["requested_quantity"] == "20.000"
    assert analytics["completed_purchases"] == 0 and len(analytics["upcoming_arrivals"]) == 1
    assert current["history"][-1]["action"] == "QUANTITY_COMMITTED"
    assert owner.put(f"/api/v1/business/offers/{o['id']}", json=edited).status_code == 409


def test_scoped_active_role_pending_and_farmer_cannot_manage(market_app):
    _, admin, farmer, owner, stranger, _, _ = market_app
    b, _, _ = application(market_app, "PRIVATE_BUYER", owner)
    assert (
        owner.post(
            "/api/v1/business/offers", json=offer_body(market_app, b["id"]), headers={"Idempotency-Key": secrets.token_hex(16)}
        ).status_code
        == 403
    )
    review(admin, b)
    assert (
        owner.post(
            "/api/v1/business/offers", json=offer_body(market_app, b["id"]), headers={"Idempotency-Key": secrets.token_hex(16)}
        ).status_code
        == 403
    )
    owner.post("/api/v1/business/active-role", json={"mode": "BUSINESS", "business_id": b["id"], "role": "PRIVATE_BUYER"})
    o, _, _ = create_offer(market_app, owner, b)
    assert farmer.get(f"/api/v1/business/offers/{o['id']}").status_code == 404
    assert stranger.get(f"/api/v1/business/requests?business_id={b['id']}").status_code == 404
    b2, _, _ = application(market_app, "PRIVATE_BUYER", stranger)
    review(admin, b2)
    stranger.post("/api/v1/business/active-role", json={"mode": "BUSINESS", "business_id": b2["id"], "role": "PRIVATE_BUYER"})
    assert stranger.post(f"/api/v1/business/offers/{o['id']}/cancel", json={"version": o["version"]}).status_code == 404
    profile = owner.get(f"/api/v1/business/profile?business_id={b['id']}").json()
    review(admin, profile, "SUSPENDED")
    assert owner.get(f"/api/v1/business/offers/{o['id']}").status_code == 403
    assert farmer.get(f"/api/v1/private-purchases/offers/{o['id']}").status_code == 409


def test_counteroffer_reject_pause_and_resume(market_app):
    _, _, farmer, _, stranger, _, _ = market_app
    b, owner = setup_business(market_app)
    o, _, _ = create_offer(market_app, owner, b)
    req = request(market_app, o).json()
    r = owner.post(f"/api/v1/business/requests/{req['id']}/counteroffer", json=response_body(req, "10"))
    assert r.status_code == 200, r.text
    current = owner.get(f"/api/v1/business/offers/{o['id']}").json()
    assert current["quantity_remaining"] == "90.000"
    r = owner.post(
        f"/api/v1/business/requests/{req['id']}/reject", json={"version": r.json()["version"], "reason": "TEST_ONLY incompatible quality"}
    )
    assert r.status_code == 200 and r.json()["status"] == "REJECTED"
    current = owner.get(f"/api/v1/business/offers/{o['id']}").json()
    assert current["quantity_remaining"] == "100.000"
    paused = owner.post(f"/api/v1/business/offers/{o['id']}/pause", json={"version": current["version"]}).json()
    assert request(market_app, paused, stranger).status_code == 409
    resumed = owner.post(f"/api/v1/business/offers/{o['id']}/publish", json={"version": paused["version"]}).json()
    assert resumed["status"] == "PUBLISHED"
    assert farmer.post(f"/api/v1/private-purchases/requests/{req['id']}/confirm", json={"version": r.json()["version"]}).status_code == 409


def test_expiry_daily_capacity_and_invalid_units(market_app):
    factory, _, farmer, _, stranger, _, _ = market_app
    b, owner = setup_business(market_app)
    body = offer_body(market_app, b["id"], unit="kg")
    assert owner.post("/api/v1/business/offers", json=body, headers={"Idempotency-Key": secrets.token_hex(16)}).status_code == 422
    o, _, _ = create_offer(market_app, owner, b, daily_intake="25")
    one, two = request(market_app, o).json(), request(market_app, o, stranger).json()
    r = owner.post(f"/api/v1/business/requests/{one['id']}/accept", json=response_body(one))
    assert r.status_code == 200
    assert owner.post(f"/api/v1/business/requests/{two['id']}/accept", json=response_body(two)).status_code == 409
    with factory() as db:
        reservation = db.scalar(select(PurchaseReservation).where(PurchaseReservation.request_id == one["id"]))
        reservation.expires_at = now() - timedelta(seconds=1)
        db.commit()
    r2 = owner.post(f"/api/v1/business/requests/{two['id']}/accept", json=response_body(two))
    assert r2.status_code == 200, r2.text
    assert farmer.post(f"/api/v1/private-purchases/requests/{one['id']}/confirm", json={"version": r.json()["version"]}).status_code == 409
    with factory() as db:
        row = db.get(PurchaseOffer, o["id"])
        row.expires_at = now() - timedelta(seconds=1)
        db.commit()
    assert owner.get(f"/api/v1/business/offers/{o['id']}").json()["status"] == "EXPIRED"
    assert request(market_app, o).status_code == 409


def test_concurrent_acceptances_cannot_overbook(market_app):
    factory, _, _, _, stranger, _, _ = market_app
    b, owner = setup_business(market_app)
    o, _, _ = create_offer(market_app, owner, b)
    one, two = request(market_app, o, amount="60").json(), request(market_app, o, stranger, amount="60").json()
    with factory() as db:
        owner_id = db.scalar(select(SaleUser.id).where(SaleUser.email == "owner@example.test"))

    def accept(req):
        with factory() as db:
            user = db.get(SaleUser, owner_id)
            svc.lock(db)
            try:
                request_row, offer_row = svc.request_for(db, user, req["id"])
                svc.respond(db, user, request_row, offer_row, ResponseInput.model_validate(response_body(req, "60")), "accept")
                db.commit()
                return 200
            except HTTPException as e:
                db.rollback()
                return e.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(accept, [one, two]))
    assert sorted(statuses) == [200, 409]
    with factory() as db:
        row = db.get(PurchaseOffer, o["id"])
        assert row.reserved_milli == 60000 and row.committed_milli == 0
        assert db.scalar(select(func.count()).select_from(PurchaseReservation).where(PurchaseReservation.state == "HELD")) == 1


def test_exact_boundary_and_quantity_reduction(market_app):
    b, owner = setup_business(market_app)
    o, body, _ = create_offer(market_app, owner, b, total_quantity="1.001", maximum_quantity="1.001", minimum_quantity="0.001")
    req = request(market_app, o, amount="1.001").json()
    r = owner.post(f"/api/v1/business/requests/{req['id']}/accept", json=response_body(req, "1.001"))
    assert r.status_code == 200, r.text
    current = owner.get(f"/api/v1/business/offers/{o['id']}").json()
    assert current["quantity_remaining"] == "0.000"
    edit = {k: v for k, v in body.items() if k != "business_id"}
    edit.update(version=current["version"], total_quantity="1", maximum_quantity="1")
    assert owner.put(f"/api/v1/business/offers/{o['id']}", json=edit).status_code == 409
    assert (
        market_app[2].post(f"/api/v1/private-purchases/requests/{req['id']}/confirm", json={"version": r.json()["version"]}).status_code
        == 200
    )
    assert owner.get(f"/api/v1/business/offers/{o['id']}").json()["status"] == "FULLY_FILLED"
    with market_app[0]() as db:
        assert db.scalar(select(func.sum(PurchaseReservation.quantity_milli)).where(PurchaseReservation.state == "COMMITTED")) == 1001
        assert db.scalar(select(func.count()).select_from(FarmerPurchaseRequest)) == 1
        assert db.scalar(select(func.count()).select_from(PurchaseNotification)) >= 3
        assert Decimal(db.get(PurchaseOffer, o["id"]).committed_milli) / 1000 == Decimal("1.001")


def test_idempotency_terms_privacy_and_cancel_notification(market_app):
    _, _, farmer, _, _, _, _ = market_app
    b, owner = setup_business(market_app)
    o, _, _ = create_offer(market_app, owner, b, image_references=["TEST_ONLY private image reference"])
    payload = {
        "offer_version": o["version"],
        "available_quantity": "20",
        "quantity": "20",
        "expected_price": "1000",
        "variety": "local",
        "grade": "faq",
        "arrival_at": (now() + timedelta(days=2)).isoformat(),
        "quality_confirmed": True,
        "terms_confirmed": True,
        "contact_consent": False,
    }
    key = secrets.token_hex(16)
    url = f"/api/v1/private-purchases/offers/{o['id']}/requests"
    r = farmer.post(url, json=payload, headers={"Idempotency-Key": key})
    assert r.status_code == 201
    assert "image_references" not in r.json()["details"]["offer_terms_at_submission"]
    assert r.json()["farmer_phone"] is None
    assert farmer.post(url, json=payload, headers={"Idempotency-Key": key}).json()["id"] == r.json()["id"]
    assert farmer.post(url, json={**payload, "quantity": "10"}, headers={"Idempotency-Key": key}).status_code == 409
    assert farmer.post(url, json=payload, headers={"Idempotency-Key": secrets.token_hex(16)}).status_code == 409
    cancelled = owner.post(f"/api/v1/business/offers/{o['id']}/cancel", json={"version": o["version"]})
    assert cancelled.status_code == 200
    assert farmer.get("/api/v1/private-purchases/requests").json()[0]["status"] == "CANCELLED"
    assert "cancelled" in farmer.get("/api/v1/private-purchases/notifications").json()[0]["message"]["en"]


def test_purchase_migration_and_immutable_audits(tmp_path, monkeypatch):
    import sqlite3

    from alembic import command
    from alembic.config import Config
    from app.config import ROOT, get_settings

    path = tmp_path / "purchase-migration.db"
    monkeypatch.setenv("SAMAY_DATABASE_URL", f"sqlite:///{path}")
    get_settings.cache_clear()
    config = Config(str(ROOT / "backend/alembic.ini"))
    try:
        command.upgrade(config, "d4e5f6a7b8c9")
        with sqlite3.connect(path) as c:
            c.execute(
                "INSERT INTO mandi_users (email,name,password_hash,role,active,email_verified,phone_verified,language,created_at) VALUES ('TEST_ONLY@example.test','TEST_ONLY','UNCHANGED','FARMER',1,0,0,'en','2026-01-01 00:00:00')"
            )
        command.upgrade(config, "head")
        command.upgrade(config, "head")
        with sqlite3.connect(path) as c:
            assert c.execute("select password_hash from mandi_users").fetchone()[0] == "UNCHANGED"
            tables = {row[0] for row in c.execute("select name from sqlite_master where type='table'")}
            assert {"purchase_offers", "farmer_sale_requests", "purchase_offer_quantity_reservations"} <= tables
            triggers = {row[0] for row in c.execute("select name from sqlite_master where type='trigger'")}
            assert "business_responses_no_update" in triggers
            # The trigger rejects mutations even when a SQL client bypasses the API.
            c.execute(
                "INSERT INTO business_responses (request_id,actor_id,kind,quantity_milli,price,arrival_at,expires_at,terms,created_at) VALUES (1,1,'TEST_ONLY',1,1,'2026-01-01','2026-01-02','{}','2026-01-01')"
            )
            with pytest.raises(sqlite3.IntegrityError, match="immutable_purchase_audit"):
                c.execute("UPDATE business_responses SET price=2")
            c.rollback()
        command.downgrade(config, "d4e5f6a7b8c9")
        with sqlite3.connect(path) as c:
            assert c.execute("select password_hash from mandi_users").fetchone()[0] == "UNCHANGED"
        command.upgrade(config, "head")
    finally:
        get_settings.cache_clear()


def test_revised_grade_requires_compatible_request(market_app):
    b, owner = setup_business(market_app)
    offer, body, _ = create_offer(market_app, owner, b)
    req = request(market_app, offer).json()
    edited = {k: v for k, v in body.items() if k != "business_id"}
    edited.update(version=offer["version"], grade="TEST_ONLY changed grade")
    assert owner.put(f"/api/v1/business/offers/{offer['id']}", json=edited).status_code == 200
    response = owner.post(f"/api/v1/business/requests/{req['id']}/accept", json=response_body(req))
    assert response.status_code == 422
    assert owner.get(f"/api/v1/business/offers/{offer['id']}").json()["quantity_reserved"] == "0.000"
