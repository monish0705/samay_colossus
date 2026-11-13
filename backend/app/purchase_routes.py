"""Prompt 2 business purchasing API; discovery/comparison UI is a separate stage."""

from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import func, select

from app import purchase_service as svc
from app.business_models import BusinessAccount, BusinessMarketAssignment, BusinessUser
from app.purchase_models import (
    BusinessResponse,
    FarmerPurchaseRequest,
    PurchaseHistory,
    PurchaseNotification,
    PurchaseOffer,
    PurchasePrice,
)
from app.models import Commodity, MandiObservation, Market
from app.purchase_schemas import (
    ArrivalInput,
    CompletionInput,
    FarmerRequestInput,
    OfferCreate,
    OfferUpdate,
    PurchaseOfferView,
    RejectInput,
    ResponseInput,
    VersionInput,
)
from app.sale_auth import DB, User, digest, require_role, write_guard
from app.sale_models import now

router = APIRouter(prefix="/api/v1", tags=["private purchasing"], dependencies=[Depends(write_guard)])


def parse_iso(dt_str: str) -> datetime:
    if not dt_str:
        return now()
    s = str(dt_str)
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s)


@router.post("/business/offers", status_code=201, response_model=PurchaseOfferView)
def create_offer(body: OfferCreate, db: DB, user: User, idempotency_key: str = Header(min_length=16, max_length=100)):
    svc.lock(db)
    row = svc.create_offer(db, user, body, idempotency_key, digest(body.model_dump_json()))
    db.commit()
    return svc.serialize_offer(db, row)


@router.get("/business/offers", response_model=list[PurchaseOfferView])
def offers(db: DB, user: User, business_id: int = Query(gt=0), limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    svc.business_access(db, user, business_id)
    return [
        svc.serialize_offer(db, o)
        for o in db.scalars(
            select(PurchaseOffer)
            .where(PurchaseOffer.business_id == business_id)
            .order_by(PurchaseOffer.id.desc())
            .offset(offset)
            .limit(limit)
        )
    ]


@router.get("/business/offers/{offer_id}", response_model=PurchaseOfferView)
def offer_detail(offer_id: int, db: DB, user: User):
    offer = svc.offer_for(db, user, offer_id)
    result = svc.serialize_offer(db, offer)
    result["price_history"] = [
        {"price": format(p.price, ".2f"), "kind": p.price_kind, "revision": p.revision, "created_at": p.created_at}
        for p in db.scalars(select(PurchasePrice).where(PurchasePrice.offer_id == offer_id).order_by(PurchasePrice.id))
    ]
    result["history"] = [
        {"action": h.action, "revision": h.revision, "snapshot": h.snapshot, "created_at": h.created_at}
        for h in db.scalars(select(PurchaseHistory).where(PurchaseHistory.offer_id == offer_id).order_by(PurchaseHistory.id))
    ]
    return result


@router.put("/business/offers/{offer_id}", response_model=PurchaseOfferView)
def update_offer(offer_id: int, body: OfferUpdate, db: DB, user: User):
    svc.lock(db)
    offer = svc.offer_for(db, user, offer_id, True)
    svc.update_offer(db, user, offer, body)
    db.commit()
    return svc.serialize_offer(db, offer)


def action(offer_id, body, db, user, verb):
    svc.lock(db)
    offer = svc.offer_for(db, user, offer_id, True)
    svc.transition(db, user, offer, verb, body.version)
    db.commit()
    return svc.serialize_offer(db, offer)


@router.post("/business/offers/{offer_id}/publish")
def publish(offer_id: int, body: VersionInput, db: DB, user: User):
    return action(offer_id, body, db, user, "publish")


@router.post("/business/offers/{offer_id}/pause")
def pause(offer_id: int, body: VersionInput, db: DB, user: User):
    return action(offer_id, body, db, user, "pause")


@router.post("/business/offers/{offer_id}/cancel")
def cancel(offer_id: int, body: VersionInput, db: DB, user: User):
    return action(offer_id, body, db, user, "cancel")


@router.get("/business/requests")
def requests(db: DB, user: User, business_id: int = Query(gt=0), limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    svc.business_access(db, user, business_id)
    rows = db.scalars(
        select(FarmerPurchaseRequest)
        .join(PurchaseOffer)
        .where(PurchaseOffer.business_id == business_id)
        .order_by(FarmerPurchaseRequest.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return [svc.serialize_request(db, r, user) for r in rows]


@router.get("/business/requests/{request_id}")
def request_detail(request_id: int, db: DB, user: User):
    request, _ = svc.request_for(db, user, request_id, False)
    return svc.serialize_request(db, request, user)


def respond(request_id, body, db, user, verb):
    svc.lock(db)
    request, offer = svc.request_for(db, user, request_id)
    svc.respond(db, user, request, offer, body, verb)
    db.commit()
    return svc.serialize_request(db, request, user)


@router.post("/business/requests/{request_id}/accept")
def accept(request_id: int, body: ResponseInput, db: DB, user: User):
    return respond(request_id, body, db, user, "accept")


@router.post("/business/requests/{request_id}/counteroffer")
def counteroffer(request_id: int, body: ResponseInput, db: DB, user: User):
    return respond(request_id, body, db, user, "counteroffer")


@router.post("/business/requests/{request_id}/reject")
def reject(request_id: int, body: RejectInput, db: DB, user: User):
    return respond(request_id, body, db, user, "reject")


@router.post("/business/requests/{request_id}/arrive")
def arrive(request_id: int, body: ArrivalInput, db: DB, user: User):
    svc.lock(db)
    request, offer = svc.request_for(db, user, request_id)
    svc.record_arrival(db, user, request, offer, body)
    db.commit()
    return svc.serialize_request(db, request, user)


@router.post("/business/requests/{request_id}/complete")
def complete(request_id: int, body: CompletionInput, db: DB, user: User):
    svc.lock(db)
    request, offer = svc.request_for(db, user, request_id)
    svc.complete_purchase(db, user, request, offer, body)
    db.commit()
    return svc.serialize_request(db, request, user)


@router.get("/business/analytics")
def analytics(db: DB, user: User, business_id: int = Query(gt=0)):
    svc.business_access(db, user, business_id)
    offers = list(db.scalars(select(PurchaseOffer).where(PurchaseOffer.business_id == business_id)))
    requests = list(db.scalars(select(FarmerPurchaseRequest).join(PurchaseOffer).where(PurchaseOffer.business_id == business_id)))
    held = sum(svc.counts(db, o)[0] for o in offers)
    upcoming = []
    for request in requests:
        if request.status in {"CONFIRMED", "BOOKING_CONFIRMED", "CONFIRMED_BY_FARMER", "ARRIVED"}:
            response = db.scalar(
                select(BusinessResponse).where(BusinessResponse.request_id == request.id).order_by(BusinessResponse.id.desc())
            )
            if response:
                upcoming.append(
                    {
                        "request_id": request.id,
                        "arrival_at": response.arrival_at,
                        "quantity": svc.quantity(response.quantity_milli),
                        "price": format(response.price, ".2f"),
                        "status": request.status,
                    }
                )
    prices = [Decimal(svc.terms_for(db, o)["offered_price"]) for o in offers]
    return {
        "unit": "quintal",
        "currency": "INR",
        "offer_count": len(offers),
        "requested_quantity": svc.quantity(sum(r.quantity_milli for r in requests)),
        "confirmed_quantity": svc.quantity(sum(o.committed_milli for o in offers)),
        "reserved_quantity": svc.quantity(held),
        "remaining_quantity": svc.quantity(
            sum(
                o.total_milli - svc.counts(db, o)[0] - o.committed_milli
                for o in offers
                if svc.effective_status(o) in svc.ACTIVE
                and o.starts_at <= now()
                and parse_iso(svc.terms_for(db, o)["price_valid_until"]) > now()
            )
        ),
        "average_offered_price": format((sum(prices) / len(prices)).quantize(Decimal(".01"), rounding=ROUND_HALF_UP), ".2f")
        if prices
        else None,
        "incoming_requests": len(requests),
        "accepted_requests": sum(svc.serialize_request(db, r, user)["status"] in {"ACCEPTED", "CONFIRMED", "ARRIVED"} for r in requests),
        "upcoming_arrivals": upcoming,
        "completed_purchases": sum(r.status == "COMPLETED" for r in requests),
        "completion_recording_available": True,
        "appointment_booking_available": True,
        "note": "Purchases and arrivals are fully recorded in the system.",
    }


@router.get("/business/purchase-notifications")
def notifications(db: DB, user: User, business_id: int = Query(gt=0), limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    svc.business_access(db, user, business_id)
    scope = (PurchaseNotification.business_id == business_id, PurchaseNotification.recipient_id == user.id)
    return {
        "unread": db.scalar(select(func.count()).select_from(PurchaseNotification).where(*scope, PurchaseNotification.read_at.is_(None))),
        "items": [
            notification_row(n)
            for n in db.scalars(
                select(PurchaseNotification).where(*scope).order_by(PurchaseNotification.id.desc()).offset(offset).limit(limit)
            )
        ],
    }


def notification_row(n):
    return {
        "id": n.id,
        "offer_id": n.offer_id,
        "request_id": n.request_id,
        "message": n.message,
        "created_at": n.created_at,
        "read_at": n.read_at,
    }


@router.post("/private-purchases/notifications/{notification_id}/read")
def read_notification(notification_id: int, db: DB, user: User):
    n = db.get(PurchaseNotification, notification_id)
    if not n or n.recipient_id != user.id:
        raise HTTPException(404, "private_notification_not_found")
    # Business-only recipients still require current membership/active workspace.
    if db.get(BusinessUser, (n.business_id, user.id)):
        svc.business_access(db, user, n.business_id)
    n.read_at = now()
    db.commit()
    return notification_row(n)


# Minimal authenticated request/confirmation infrastructure for Prompt 2 testing.
# Farmer discovery/comparison and full booking/completion UI are Prompt 3.
@router.get("/private-purchases/offers/{offer_id}")
def selected_offer(offer_id: int, db: DB, user: User):
    require_role(user, "FARMER")
    offer = db.get(PurchaseOffer, offer_id)
    if not offer:
        raise HTTPException(404, "purchase_offer_not_found")
    svc.available(db, offer)
    result = svc.serialize_offer(db, offer)
    # Protected image references must not leak through the farmer API.
    result["terms"] = {k: v for k, v in result["terms"].items() if k != "image_references"}
    result["business_type"] = db.get(BusinessAccount, offer.business_id).business_type
    return result


@router.post("/private-purchases/offers/{offer_id}/requests", status_code=201)
def submit_request(
    offer_id: int, body: FarmerRequestInput, db: DB, user: User, idempotency_key: str = Header(min_length=16, max_length=100)
):
    require_role(user, "FARMER")
    svc.lock(db)
    offer = db.scalar(select(PurchaseOffer).where(PurchaseOffer.id == offer_id).with_for_update())
    if not offer:
        raise HTTPException(404, "purchase_offer_not_found")
    svc.cleanup(db, offer)
    row = svc.submit_request(db, user, offer, body, idempotency_key, digest(str(offer_id) + body.model_dump_json()))
    db.commit()
    return svc.serialize_request(db, row, user)


@router.get("/private-purchases/requests")
def farmer_requests(db: DB, user: User, limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    require_role(user, "FARMER")
    return [
        svc.serialize_request(db, r, user)
        for r in db.scalars(
            select(FarmerPurchaseRequest)
            .where(FarmerPurchaseRequest.farmer_id == user.id)
            .order_by(FarmerPurchaseRequest.id.desc())
            .offset(offset)
            .limit(limit)
        )
    ]


@router.post("/private-purchases/requests/{request_id}/confirm")
def confirm(request_id: int, body: VersionInput, db: DB, user: User):
    require_role(user, "FARMER")
    svc.lock(db)
    request = db.get(FarmerPurchaseRequest, request_id)
    if not request or request.farmer_id != user.id:
        raise HTTPException(404, "private_request_not_found")
    offer = db.scalar(select(PurchaseOffer).where(PurchaseOffer.id == request.offer_id).with_for_update())
    svc.confirm(db, user, request, offer, body.version)
    db.commit()
    return svc.serialize_request(db, request, user)


@router.post("/private-purchases/requests/{request_id}/reject")
def farmer_reject(request_id: int, body: RejectInput, db: DB, user: User):
    require_role(user, "FARMER")
    svc.lock(db)
    request = db.get(FarmerPurchaseRequest, request_id)
    if not request or request.farmer_id != user.id:
        raise HTTPException(404, "private_request_not_found")
    offer = db.scalar(select(PurchaseOffer).where(PurchaseOffer.id == request.offer_id).with_for_update())
    svc.farmer_reject(db, user, request, offer, body)
    db.commit()
    return svc.serialize_request(db, request, user)


@router.get("/private-rates")
def private_rates(
    db: DB,
    business_type: str | None = Query(None),
    crop_id: int | None = Query(None),
    variety: str | None = Query(None),
    district: str | None = Query(None),
    min_price: Decimal | None = Query(None),
    max_price: Decimal | None = Query(None),
    min_quantity: Decimal | None = Query(None),
    sort_by: str = Query("price_desc"),
):
    query = (
        select(PurchaseOffer, BusinessAccount)
        .join(BusinessAccount, PurchaseOffer.business_id == BusinessAccount.id)
        .where(
            BusinessAccount.verification_state == "VERIFIED",
            PurchaseOffer.status.in_(svc.ACTIVE),
            PurchaseOffer.starts_at <= now(),
            PurchaseOffer.expires_at > now(),
        )
    )
    if business_type:
        query = query.where(BusinessAccount.business_type == business_type)
    if crop_id:
        query = query.where(PurchaseOffer.commodity_id == crop_id)

    rows = db.execute(query).all()
    results = []

    for offer, business in rows:
        if business.business_type == "PRIVATE_MANDI" and not db.get(BusinessMarketAssignment, business.id):
            continue

        terms = svc.terms_for(db, offer)
        if parse_iso(terms.get("price_valid_until")) <= now():
            continue

        held, committed = svc.counts(db, offer)
        remaining = offer.total_milli - held - committed
        if remaining <= 0:
            continue

        if variety and terms.get("variety", "").casefold() != variety.casefold():
            continue
        if district and terms.get("district", "").casefold() != district.casefold():
            continue
        offered_price = Decimal(terms["offered_price"])
        if min_price and offered_price < min_price:
            continue
        if max_price and offered_price > max_price:
            continue
        if min_quantity and Decimal(svc.quantity(remaining)) < min_quantity:
            continue

        apmc_obs = db.scalar(
            select(MandiObservation)
            .where(MandiObservation.commodity_id == offer.commodity_id)
            .order_by(MandiObservation.observed_on.desc(), MandiObservation.id.desc())
            .limit(1)
        )
        apmc_price = apmc_obs.modal_price_inr_per_quintal if apmc_obs else None

        unloading = Decimal(terms["unloading_charge"]) if terms.get("unloading_charge") is not None else None
        pickup = Decimal(terms["pickup_charge"]) if terms.get("pickup_charge") is not None else None
        transport_type = terms.get("transport", "FARMER_DELIVERY")

        known_deductions_val = Decimal("0.00")
        has_unknown_costs = False

        if unloading is not None:
            known_deductions_val += unloading
        else:
            has_unknown_costs = True

        if transport_type == "BUSINESS_PICKUP":
            if pickup is not None:
                known_deductions_val += pickup
            else:
                has_unknown_costs = True
        else:
            has_unknown_costs = True

        estimated_net = (offered_price - known_deductions_val).quantize(Decimal(".01"))
        commodity = db.get(Commodity, offer.commodity_id)

        results.append({
            "offer_id": offer.id,
            "version": offer.version,
            "business_id": business.id,
            "business_name": business.name,
            "business_type": business.business_type,
            "commodity_id": offer.commodity_id,
            "commodity_name": commodity.name if commodity else "Unknown",
            "variety": terms.get("variety"),
            "grade": terms.get("grade"),
            "quality_standards": terms.get("quality_standards"),
            "offered_price": format(offered_price, ".2f"),
            "price_kind": terms.get("price_kind", "FIRM"),
            "price_basis": terms.get("price_basis"),
            "minimum_price": format(Decimal(terms["minimum_price"]), ".2f") if terms.get("minimum_price") else None,
            "maximum_price": format(Decimal(terms["maximum_price"]), ".2f") if terms.get("maximum_price") else None,
            "quantity_required": svc.quantity(offer.total_milli),
            "quantity_remaining": svc.quantity(remaining),
            "minimum_quantity": terms.get("minimum_quantity"),
            "maximum_quantity": terms.get("maximum_quantity"),
            "address": terms.get("address") or business.address,
            "purchasing_centre": terms.get("purchasing_centre"),
            "district": terms.get("district") or business.district,
            "state": terms.get("state") or business.state,
            "transport": transport_type,
            "pickup_charge": format(pickup, ".2f") if pickup is not None else None,
            "unloading_charge": format(unloading, ".2f") if unloading is not None else None,
            "charge_basis": terms.get("charge_basis"),
            "known_deductions": terms.get("known_deductions"),
            "has_unknown_costs": has_unknown_costs,
            "estimated_net_realization": format(estimated_net, ".2f"),
            "apmc_reference_modal_price": apmc_price,
            "price_updated_at": offer.price_updated_at,
            "expires_at": offer.expires_at,
            "price_valid_until": terms.get("price_valid_until"),
            "arrival_dates": terms.get("arrival_dates", []),
            "created_at": offer.created_at,
        })

    if sort_by == "price_desc":
        results.sort(key=lambda x: Decimal(x["offered_price"]), reverse=True)
    elif sort_by == "net_realization_desc":
        results.sort(key=lambda x: Decimal(x["estimated_net_realization"]), reverse=True)
    elif sort_by == "updated_desc":
        results.sort(key=lambda x: x["price_updated_at"], reverse=True)

    return results


@router.get("/private-purchases/notifications")
def farmer_notifications(db: DB, user: User):
    require_role(user, "FARMER")
    request_ids = select(FarmerPurchaseRequest.id).where(FarmerPurchaseRequest.farmer_id == user.id)
    return [
        notification_row(n)
        for n in db.scalars(
            select(PurchaseNotification)
            .where(PurchaseNotification.recipient_id == user.id, PurchaseNotification.request_id.in_(request_ids))
            .order_by(PurchaseNotification.id.desc())
            .limit(100)
        )
    ]
