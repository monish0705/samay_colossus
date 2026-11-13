"""Prompt 2 business purchasing API; discovery/comparison UI is a separate stage."""

from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import func, select

from app import purchase_service as svc
from app.business_models import BusinessAccount, BusinessUser
from app.purchase_models import (
    BusinessResponse,
    FarmerPurchaseRequest,
    PurchaseHistory,
    PurchaseNotification,
    PurchaseOffer,
    PurchasePrice,
)
from app.purchase_schemas import (
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


@router.get("/business/analytics")
def analytics(db: DB, user: User, business_id: int = Query(gt=0)):
    svc.business_access(db, user, business_id)
    offers = list(db.scalars(select(PurchaseOffer).where(PurchaseOffer.business_id == business_id)))
    requests = list(db.scalars(select(FarmerPurchaseRequest).join(PurchaseOffer).where(PurchaseOffer.business_id == business_id)))
    held = sum(svc.counts(db, o)[0] for o in offers)
    upcoming = []
    for request in requests:
        if request.status == "CONFIRMED":
            response = db.scalar(
                select(BusinessResponse).where(BusinessResponse.request_id == request.id).order_by(BusinessResponse.id.desc())
            )
            if response and response.arrival_at > now():
                upcoming.append(
                    {
                        "request_id": request.id,
                        "arrival_at": response.arrival_at,
                        "quantity": svc.quantity(response.quantity_milli),
                        "price": format(response.price, ".2f"),
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
                and datetime.fromisoformat(svc.terms_for(db, o)["price_valid_until"]) > now()
            )
        ),
        "average_offered_price": format((sum(prices) / len(prices)).quantize(Decimal(".01"), rounding=ROUND_HALF_UP), ".2f")
        if prices
        else None,
        "incoming_requests": len(requests),
        "accepted_requests": sum(svc.serialize_request(db, r, user)["status"] in {"ACCEPTED", "CONFIRMED"} for r in requests),
        "upcoming_arrivals": upcoming,
        "completed_purchases": sum(r.status == "COMPLETED" for r in requests),
        "completion_recording_available": False,
        "appointment_booking_available": False,
        "note": "Confirmed arrival terms are not completed purchases. Booking and actual sale recording belong to the next stage.",
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
