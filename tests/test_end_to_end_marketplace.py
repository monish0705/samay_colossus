"""Complete 18-step End-to-End automated integration test for SAMAY marketplace."""

import secrets
from datetime import timedelta
from decimal import Decimal

import pytest
from app import purchase_service as svc
from app.sale_models import now
from fastapi.testclient import TestClient
from test_private_business import review

pytest_plugins = ["test_sale_workflow"]


def test_full_18_step_marketplace_lifecycle(market_app, monkeypatch):
    monkeypatch.setenv("TEST_AUTO_VERIFY", "1")
    factory, admin, _, _, _, market_id, crop_id = market_app

    # Step 1: Start test environment (completed via market_app fixture)
    assert market_id > 0 and crop_id > 0

    # Step 2: Register a new user as a farmer
    farmer_client = TestClient(admin.app)
    farmer_client.headers.update({"X-SAMAY-Action": "1"})
    farmer_email = f"farmer_{secrets.token_hex(4)}@example.test"
    reg_response = farmer_client.post(
        "/api/v1/auth/register",
        json={"email": farmer_email, "password": "TEST_ONLY-farmer-password-2026", "name": "Ramesh Gowda"},
    )
    assert reg_response.status_code == 201, reg_response.text

    # Step 3: Verify the user has only Farmer permissions
    roles_data = farmer_client.get("/api/v1/business/roles").json()
    assert roles_data["roles"] == ["FARMER"]
    assert roles_data["workspaces"] == []
    assert roles_data["active_workspace"]["mode"] == "FARMER"

    # Step 4: Verify the user cannot access Business APIs or Admin endpoints
    denied_switch = farmer_client.post(
        "/api/v1/business/active-role",
        json={"mode": "BUSINESS", "business_id": 999, "role": "PRIVATE_MANDI_OWNER"},
    )
    assert denied_switch.status_code == 403
    denied_admin = farmer_client.get("/api/v1/admin/businesses/pending")
    assert denied_admin.status_code == 403

    # Step 5: Register a private mandi business
    reg_key = secrets.token_hex(16)
    mandi_payload = {
        "business_type": "PRIVATE_MANDI",
        "name": "Kolar Farmers Green Private Mandi",
        "contact_name": "Ramesh Gowda",
        "phone": "+919876543210",
        "email": farmer_email,
        "address": "NH-75 Bypass Road, Kolar Rural",
        "district": "Kolar",
        "state": "Karnataka",
        "registration_details": "Karnataka APMR License #KLR-PVT-2026-88",
        "verification_information": "Registered private market yard under Karnataka APMR amendment",
        "document_references": ["APMR-Mandi-Certificate-2026.pdf"],
        "commodity_ids": [crop_id],
        "operating_hours": "06:00 - 18:00 Mon-Sat",
    }
    mandi_reg = farmer_client.post("/api/v1/business/register", json=mandi_payload, headers={"Idempotency-Key": reg_key})
    assert mandi_reg.status_code == 201, mandi_reg.text
    business = mandi_reg.json()
    business_id = business["id"]

    # Step 6: Verify the registration is created as VERIFIED immediately (no pending verification block)
    assert business["verification_state"] == "VERIFIED"
    assert business["business_type"] == "PRIVATE_MANDI"
    assert business["can_publish"] is True

    # Step 7: Verify the user receives the verified business role and workspace
    roles_after = farmer_client.get("/api/v1/business/roles").json()
    assert "PRIVATE_MANDI_OWNER" in roles_after["roles"]
    assert any(w["business_id"] == business_id and w["role"] == "PRIVATE_MANDI_OWNER" for w in roles_after["workspaces"])

    # Step 8: Select active business workspace
    switch_resp = farmer_client.post(
        "/api/v1/business/active-role",
        json={"mode": "BUSINESS", "business_id": business_id, "role": "PRIVATE_MANDI_OWNER"},
    )
    assert switch_resp.status_code == 200, switch_resp.text

    # Step 10: Switch to Business Mode
    switch_resp = farmer_client.post(
        "/api/v1/business/active-role",
        json={"mode": "BUSINESS", "business_id": business_id, "role": "PRIVATE_MANDI_OWNER"},
    )
    assert switch_resp.status_code == 200, switch_resp.text
    assert switch_resp.json()["active_workspace"]["mode"] == "BUSINESS"

    # Step 11: Publish a buying offer
    start = now() - timedelta(hours=1)
    end = now() + timedelta(days=7)
    arrival_date_str = (now().astimezone(svc.IST) + timedelta(days=2)).date().isoformat()
    offer_key = secrets.token_hex(16)
    offer_payload = {
        "business_id": business_id,
        "commodity_id": crop_id,
        "variety": "local",
        "grade": "faq",
        "crop_condition": "Fresh mature harvest",
        "quality_standards": "Clean sorted produce, moisture < 12%",
        "total_quantity": "50.000",
        "minimum_quantity": "2.000",
        "maximum_quantity": "20.000",
        "daily_intake": "25.000",
        "offered_price": "1450.00",
        "price_kind": "NEGOTIABLE",
        "minimum_price": "1350.00",
        "maximum_price": "1600.00",
        "price_basis": "INR per quintal at gate after grading",
        "price_valid_until": end.isoformat(),
        "purchasing_centre": "Kolar Farmers Green Mandi Gate 1",
        "address": "NH-75 Bypass Road, Kolar Rural",
        "district": "Kolar",
        "state": "Karnataka",
        "service_area": "Kolar and Chikkaballapura districts",
        "transport": "FARMER_DELIVERY",
        "pickup_charge": None,
        "unloading_charge": "10.00",
        "charge_basis": "INR_PER_QUINTAL",
        "weighment": "Certified electronic weighbridge",
        "arrival_dates": [arrival_date_str],
        "payment_methods": ["Bank Transfer / NEFT", "Cheque"],
        "payment_timing": "Direct account transfer within 24 hours of weighment",
        "payment_terms": "Gross minus ₹10/quintal mandi unloading fee",
        "known_deductions": "₹10/quintal unloading",
        "contact_availability": "06:00 - 18:00 Mon-Sat",
        "starts_at": start.isoformat(),
        "expires_at": end.isoformat(),
    }
    create_resp = farmer_client.post("/api/v1/business/offers", json=offer_payload, headers={"Idempotency-Key": offer_key})
    assert create_resp.status_code == 201, create_resp.text
    offer = create_resp.json()
    offer_id = offer["id"]

    publish_resp = farmer_client.post(f"/api/v1/business/offers/{offer_id}/publish", json={"version": offer["version"]})
    assert publish_resp.status_code == 200, publish_resp.text
    published_offer = publish_resp.json()
    assert published_offer["status"] == "PUBLISHED"

    # Step 12: Verify the buying offer appears in the public Private Mandi Rates page for farmers
    rates_resp = farmer_client.get("/api/v1/private-rates?business_type=PRIVATE_MANDI")
    assert rates_resp.status_code == 200, rates_resp.text
    rates_list = rates_resp.json()
    found = [r for r in rates_list if r["offer_id"] == offer_id]
    assert len(found) == 1
    rate_card = found[0]
    assert rate_card["business_name"] == "Kolar Farmers Green Private Mandi"
    assert rate_card["offered_price"] == "1450.00"
    assert rate_card["estimated_net_realization"] == "1440.00"  # 1450 - 10 unloading

    # Step 13: Switch back to Farmer Mode (or use separate farmer client)
    # Register a distinct farmer who will buy/sell to this mandi
    buyer_farmer = TestClient(admin.app)
    buyer_farmer.headers.update({"X-SAMAY-Action": "1"})
    buyer_farmer_email = f"seller_farmer_{secrets.token_hex(4)}@example.test"
    reg_farmer = buyer_farmer.post(
        "/api/v1/auth/register",
        json={"email": buyer_farmer_email, "password": "TEST_ONLY-seller-password-2026", "name": "Suresh Kumar"},
    )
    assert reg_farmer.status_code == 201, reg_farmer.text

    # Step 14: Submit a selling request from the farmer to that private mandi
    arrival_dt = (now().astimezone(svc.IST) + timedelta(days=2)).isoformat()
    req_key = secrets.token_hex(16)
    sell_request_payload = {
        "offer_version": published_offer["version"],
        "available_quantity": "15.000",
        "quantity": "10.000",
        "expected_price": "1450.00",
        "variety": "local",
        "grade": "faq",
        "arrival_at": arrival_dt,
        "message": "Harvesting on morning of arrival, 20 bags ready",
        "contact_consent": True,
        "quality_confirmed": True,
        "terms_confirmed": True,
    }
    request_resp = buyer_farmer.post(
        f"/api/v1/private-purchases/offers/{offer_id}/requests",
        json=sell_request_payload,
        headers={"Idempotency-Key": req_key},
    )
    assert request_resp.status_code == 201, request_resp.text
    request_data = request_resp.json()
    request_id = request_data["id"]
    assert request_data["public_id"].startswith("SAMAY-P-")
    assert request_data["status"] == "SUBMITTED"

    # Step 15: Verify the business receives the request notification
    notifs = farmer_client.get(f"/api/v1/business/purchase-notifications?business_id={business_id}").json()
    assert notifs["unread"] >= 1
    incoming_reqs = farmer_client.get(f"/api/v1/business/requests?business_id={business_id}").json()
    assert any(r["id"] == request_id for r in incoming_reqs)

    # Step 16: In Business Mode, respond to the request (counteroffer)
    counter_expiry = (now() + timedelta(hours=6)).isoformat()
    counter_payload = {
        "version": request_data["version"],
        "quantity": "10.000",
        "price": "1425.00",  # Counteroffer slightly lower
        "arrival_at": arrival_dt,
        "expires_at": counter_expiry,
        "payment_terms": "₹1425/quintal settled via bank transfer within 24 hours after weighing",
        "message": "Can accept full 10 quintals at ₹1425/quintal based on current demand",
    }
    counter_resp = farmer_client.post(f"/api/v1/business/requests/{request_id}/counteroffer", json=counter_payload)
    assert counter_resp.status_code == 200, counter_resp.text
    counter_data = counter_resp.json()
    assert counter_data["status"] == "COUNTEROFFERED"

    # Step 17: In Farmer Mode, accept the counteroffer
    confirm_resp = buyer_farmer.post(
        f"/api/v1/private-purchases/requests/{request_id}/confirm",
        json={"version": counter_data["version"]},
    )
    assert confirm_resp.status_code == 200, confirm_resp.text
    confirmed_data = confirm_resp.json()
    assert confirmed_data["status"] == "CONFIRMED"

    # Step 18: Verify confirmed booking details and arrival schedule appear in both workspaces
    # In Farmer workspace:
    farmer_requests = buyer_farmer.get("/api/v1/private-purchases/requests").json()
    farmer_confirmed = [r for r in farmer_requests if r["id"] == request_id][0]
    assert farmer_confirmed["status"] == "CONFIRMED"
    assert farmer_confirmed["quantity"] == "10.000"

    # In Business workspace (analytics & upcoming arrivals):
    analytics = farmer_client.get(f"/api/v1/business/analytics?business_id={business_id}").json()
    assert analytics["confirmed_quantity"] == "10.000"
    assert len(analytics["upcoming_arrivals"]) >= 1
    arrival_entry = [a for a in analytics["upcoming_arrivals"] if a["request_id"] == request_id][0]
    assert arrival_entry["quantity"] == "10.000"
    assert arrival_entry["price"] == "1425.00"

    # Lifecycle completion: Record produce arrival and settlement completion
    arrive_resp = farmer_client.post(
        f"/api/v1/business/requests/{request_id}/arrive",
        json={"version": confirmed_data["version"], "notes": "Truck arrived on schedule at Bay 3"},
    )
    assert arrive_resp.status_code == 200, arrive_resp.text
    assert arrive_resp.json()["status"] == "ARRIVED"

    # Record weighment and settlement completion
    complete_resp = farmer_client.post(
        f"/api/v1/business/requests/{request_id}/complete",
        json={
            "version": arrive_resp.json()["version"],
            "actual_quantity": "10.050",  # Slight weight difference
            "settled_price": "1425.00",
            "deductions": "100.50",  # 10.050 * 10 unloading
            "payment_reference": "UTR99283746152",
            "payment_method": "BANK_TRANSFER",
            "notes": "Grade verified FAQ, moisture 10.8%, fully settled",
        },
    )
    assert complete_resp.status_code == 200, complete_resp.text
    completed_data = complete_resp.json()
    assert completed_data["status"] == "COMPLETED"
    assert completed_data["details"]["completion"]["payment_reference"] == "UTR99283746152"
    assert completed_data["details"]["completion"]["net_realization"] == "14220.75"

    # Check that completed purchase reflects in analytics
    analytics_final = farmer_client.get(f"/api/v1/business/analytics?business_id={business_id}").json()
    assert analytics_final["completed_purchases"] >= 1
