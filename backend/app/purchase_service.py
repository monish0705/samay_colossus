"""Transactional private purchases. No price or completed-sale statistics are invented."""

from decimal import Decimal
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import func, select, text

from app.business_models import BusinessAccount, BusinessMarketAssignment, BusinessRole, BusinessUser, WorkspacePreference
from app.business_service import authorized_business
from app.models import Commodity
from app.purchase_models import (
    BusinessResponse,
    FarmerPurchaseRequest,
    PurchaseHistory,
    PurchaseNotification,
    PurchaseOffer,
    PurchasePrice,
    PurchaseRequestHistory,
    PurchaseRequirements,
    PurchaseReservation,
)
from app.sale_models import SaleUser, now

IST = ZoneInfo("Asia/Kolkata")
ACTIVE = {"PUBLISHED", "PARTIALLY_FILLED", "FULLY_FILLED"}


def milli(value):
    return int(Decimal(value) * 1000)


def quantity(value):
    return format(Decimal(value) / 1000, ".3f")


def lock(db):
    # Auth throttles finish before this point. Serialize read/validate/write together;
    # SQLite has no row-level FOR UPDATE. Production multi-host deployments need a
    # shared transactional database; PostgreSQL locks the business/offer rows below.
    db.commit()
    if db.bind.dialect.name == "sqlite":
        db.execute(text("BEGIN IMMEDIATE"))
    db.expire_all()


def business_access(db, user, business_id, manage=False):
    business = db.scalar(select(BusinessAccount).where(BusinessAccount.id == business_id).with_for_update())
    authorized_business(db, user, business_id, manage=manage, verified=True)
    pref = db.get(WorkspacePreference, user.id)
    scoped = db.get(BusinessRole, (business_id, user.id, pref.role)) if pref and pref.role else None
    if not pref or pref.mode != "BUSINESS" or pref.business_id != business_id or not scoped:
        raise HTTPException(403, "active_business_workspace_required")
    return business


def offer_for(db, user, offer_id, manage=False):
    offer = db.scalar(select(PurchaseOffer).where(PurchaseOffer.id == offer_id).with_for_update())
    if not offer:
        raise HTTPException(404, "purchase_offer_not_found")
    business_access(db, user, offer.business_id, manage)
    return offer


def terms_for(db, offer):
    return db.get(PurchaseRequirements, offer.id).terms


def counts(db, offer):
    held = db.scalar(
        select(func.coalesce(func.sum(PurchaseReservation.quantity_milli), 0)).where(
            PurchaseReservation.offer_id == offer.id, PurchaseReservation.state == "HELD", PurchaseReservation.expires_at > now()
        )
    )
    return int(held), offer.committed_milli


def effective_status(offer):
    if offer.status not in {"CANCELLED", "DRAFT"} and (offer.expires_at <= now()):
        return "EXPIRED"
    return offer.status


def serialize_offer(db, offer):
    held, committed = counts(db, offer)
    status = effective_status(offer)
    if status in ACTIVE:
        status = "FULLY_FILLED" if committed == offer.total_milli else "PARTIALLY_FILLED" if committed else "PUBLISHED"
    return {
        "id": offer.id,
        "commodity_name": db.get(Commodity, offer.commodity_id).name,
        "business_id": offer.business_id,
        "version": offer.version,
        "status": status,
        "terms": terms_for(db, offer),
        "quantity_required": quantity(offer.total_milli),
        "quantity_reserved": quantity(held),
        "quantity_committed": quantity(committed),
        "quantity_remaining": quantity(offer.total_milli - held - committed),
        "unit": "quintal",
        "currency": "INR",
        "price_updated_at": offer.price_updated_at,
        "created_at": offer.created_at,
        "request_count": db.scalar(
            select(func.count()).select_from(FarmerPurchaseRequest).where(FarmerPurchaseRequest.offer_id == offer.id)
        ),
    }


def history(db, offer, actor_id, action):
    db.add(
        PurchaseHistory(
            offer_id=offer.id,
            actor_id=actor_id,
            action=action,
            revision=offer.version,
            snapshot={
                "terms": terms_for(db, offer),
                "status": offer.status,
                "total_milli": offer.total_milli,
                "reserved_milli": offer.reserved_milli,
                "committed_milli": offer.committed_milli,
            },
        )
    )


def event(db, request, actor_id, action, details=None):
    db.add(PurchaseRequestHistory(request_id=request.id, actor_id=actor_id, action=action, details=details or {}))


def notify(db, offer, request, recipients, en, kn):
    for uid in set(recipients):
        db.add(
            PurchaseNotification(
                recipient_id=uid,
                business_id=offer.business_id,
                offer_id=offer.id,
                request_id=request.id if request else None,
                message={"en": en, "kn": kn},
            )
        )


def owners(db, offer):
    return list(
        db.scalars(
            select(BusinessUser.user_id).where(
                BusinessUser.business_id == offer.business_id, BusinessUser.active.is_(True), BusinessUser.can_manage.is_(True)
            )
        )
    )


def pending_notices(db, offer, en, kn):
    for request in db.scalars(
        select(FarmerPurchaseRequest).where(
            FarmerPurchaseRequest.offer_id == offer.id, FarmerPurchaseRequest.status.in_(["SUBMITTED", "ACCEPTED", "COUNTEROFFERED"])
        )
    ):
        notify(db, offer, request, [request.farmer_id], en, kn)


def cleanup(db, offer):
    for reservation in db.scalars(
        select(PurchaseReservation).where(
            PurchaseReservation.offer_id == offer.id, PurchaseReservation.state == "HELD", PurchaseReservation.expires_at <= now()
        )
    ):
        reservation.state = "RELEASED"
        offer.reserved_milli -= reservation.quantity_milli
        request = db.get(FarmerPurchaseRequest, reservation.request_id)
        request.status, request.version = "EXPIRED", request.version + 1
        event(db, request, offer.created_by, "RESPONSE_EXPIRED", {"response_id": reservation.response_id, "automated_expiry": True})
        notify(
            db,
            offer,
            request,
            [request.farmer_id],
            "Business response expired; reserved quantity was released.",
            "ವ್ಯಾಪಾರದ ಪ್ರತಿಕ್ರಿಯೆ ಅವಧಿ ಮುಗಿದಿದೆ; ಕಾಯ್ದಿರಿಸಿದ ಪ್ರಮಾಣ ಬಿಡುಗಡೆ ಮಾಡಲಾಗಿದೆ.",
        )
    db.flush()


def revision(offer, expected):
    if offer.version != expected:
        raise HTTPException(409, "purchase_offer_changed_refresh")


def validate_dates(terms):
    if terms.expires_at <= now() or terms.price_valid_until <= now():
        raise HTTPException(422, "offer_validity_must_be_in_future")
    if any(d < now().astimezone(IST).date() for d in terms.arrival_dates):
        raise HTTPException(422, "arrival_dates_must_not_be_in_past")


def price_record(db, offer, actor_id):
    terms = terms_for(db, offer)
    db.add(
        PurchasePrice(
            offer_id=offer.id,
            revision=offer.version,
            price=Decimal(terms["offered_price"]),
            price_kind=terms["price_kind"],
            actor_id=actor_id,
        )
    )
    offer.price_updated_at = now()


def create_offer(db, user, body, key, fingerprint):
    business_access(db, user, body.business_id, True)
    previous = db.scalar(select(PurchaseOffer).where(PurchaseOffer.business_id == body.business_id, PurchaseOffer.submission_key == key))
    if previous:
        if previous.payload_hash != fingerprint:
            raise HTTPException(409, "purchase_submission_key_reused")
        return previous
    if not db.get(Commodity, body.commodity_id):
        raise HTTPException(422, "unknown_business_crop")
    validate_dates(body)
    offer = PurchaseOffer(
        business_id=body.business_id,
        commodity_id=body.commodity_id,
        created_by=user.id,
        total_milli=milli(body.total_quantity),
        starts_at=body.starts_at,
        expires_at=body.expires_at,
        submission_key=key,
        payload_hash=fingerprint,
    )
    db.add(offer)
    db.flush()
    db.add(PurchaseRequirements(offer_id=offer.id, terms=body.model_dump(mode="json", exclude={"business_id"})))
    db.flush()
    price_record(db, offer, user.id)
    history(db, offer, user.id, "CREATED")
    return offer


def update_offer(db, user, offer, body):
    cleanup(db, offer)
    revision(offer, body.version)
    if effective_status(offer) in {"CANCELLED", "EXPIRED"}:
        # Expired offers can explicitly extend validity through a fully validated edit.
        if offer.status == "CANCELLED":
            raise HTTPException(409, "cancelled_offer_is_terminal")
    validate_dates(body)
    if body.commodity_id != offer.commodity_id:
        raise HTTPException(422, "crop_cannot_change_create_new_offer")
    total = milli(body.total_quantity)
    if total < offer.reserved_milli + offer.committed_milli:
        raise HTTPException(409, "quantity_below_existing_reservations")
    was_expired = effective_status(offer) == "EXPIRED"
    old = terms_for(db, offer)
    new = body.model_dump(mode="json", exclude={"version"})
    offer.total_milli, offer.starts_at, offer.expires_at = total, body.starts_at, body.expires_at
    offer.version += 1
    if offer.status in ACTIVE:
        offer.status = (
            "FULLY_FILLED" if offer.committed_milli == offer.total_milli else "PARTIALLY_FILLED" if offer.committed_milli else "PUBLISHED"
        )
    if was_expired:
        offer.status = "PAUSED"
    db.get(PurchaseRequirements, offer.id).terms = new
    if any(
        old.get(k) != new.get(k)
        for k in ["offered_price", "price_kind", "minimum_price", "maximum_price", "price_basis", "price_valid_until"]
    ):
        price_record(db, offer, user.id)
    history(db, offer, user.id, "REVISED")
    pending_notices(
        db,
        offer,
        "Buying offer terms changed. Review the new revision; existing confirmed/response terms remain unchanged.",
        "ಖರೀದಿ ಆಫರ್ ಷರತ್ತುಗಳು ಬದಲಾಗಿವೆ. ಹೊಸ ವಿವರಗಳನ್ನು ಪರಿಶೀಲಿಸಿ; ಈಗಾಗಲೇ ಒಪ್ಪಿದ ಷರತ್ತುಗಳು ಬದಲಾಗುವುದಿಲ್ಲ.",
    )


def transition(db, user, offer, action, version):
    cleanup(db, offer)
    revision(offer, version)
    state = effective_status(offer)
    if action == "publish":
        if state not in {"DRAFT", "PAUSED"}:
            raise HTTPException(409, "offer_cannot_publish_from_current_state")
        from app.purchase_schemas import OfferTerms

        validate_dates(OfferTerms.model_validate(terms_for(db, offer)))
        offer.status = "PUBLISHED"
    elif action == "pause":
        if state not in ACTIVE:
            raise HTTPException(409, "offer_not_active")
        offer.status = "PAUSED"
    elif action == "cancel":
        if state == "CANCELLED":
            raise HTTPException(409, "offer_already_cancelled")
        offer.status = "CANCELLED"
        for request in db.scalars(
            select(FarmerPurchaseRequest).where(FarmerPurchaseRequest.offer_id == offer.id, FarmerPurchaseRequest.status == "SUBMITTED")
        ):
            request.status, request.version = "CANCELLED", request.version + 1
            event(db, request, user.id, "OFFER_CANCELLED")
            notify(
                db,
                offer,
                request,
                [request.farmer_id],
                "Buying offer was cancelled before a response was agreed.",
                "ಪ್ರತಿಕ್ರಿಯೆ ಒಪ್ಪುವ ಮೊದಲು ಖರೀದಿ ಆಫರ್ ರದ್ದಾಗಿದೆ.",
            )
        # Accepted/counteroffered responses and committed agreements retain frozen
        # terms and reservations. Cancelling publication never silently cancels them.
    offer.version += 1
    history(db, offer, user.id, action.upper())
    pending_notices(
        db,
        offer,
        f"Buying offer publication is now {offer.status.lower()}; existing responses retain their agreed terms.",
        "ಖರೀದಿ ಪ್ರಕಟಣೆಯ ಸ್ಥಿತಿ ಬದಲಾಗಿದೆ; ಈಗಾಗಲೇ ನೀಡಿದ ಪ್ರತಿಕ್ರಿಯೆಗಳ ಷರತ್ತುಗಳು ಹಾಗೆಯೇ ಉಳಿಯುತ್ತವೆ.",
    )


def available(db, offer):
    terms = terms_for(db, offer)
    from datetime import datetime

    if effective_status(offer) not in ACTIVE or offer.starts_at > now() or datetime.fromisoformat(terms["price_valid_until"]) <= now():
        raise HTTPException(409, "purchase_offer_not_currently_available")
    business = db.get(BusinessAccount, offer.business_id)
    if (
        not business
        or business.verification_state != "VERIFIED"
        or (business.business_type == "PRIVATE_MANDI" and not db.get(BusinessMarketAssignment, business.id))
    ):
        raise HTTPException(409, "business_not_verified")
    return terms


def arrival_check(terms, arrival):
    if arrival <= now() or arrival.astimezone(IST).date().isoformat() not in terms["arrival_dates"]:
        raise HTTPException(422, "arrival_not_available")


def submit_request(db, user, offer, body, key, fingerprint):
    previous = db.scalar(
        select(FarmerPurchaseRequest).where(FarmerPurchaseRequest.farmer_id == user.id, FarmerPurchaseRequest.submission_key == key)
    )
    if previous:
        if previous.payload_hash != fingerprint:
            raise HTTPException(409, "purchase_request_key_reused")
        return previous
    terms = available(db, offer)
    revision(offer, body.offer_version)
    if db.get(BusinessUser, (offer.business_id, user.id)):
        raise HTTPException(403, "cannot_request_own_business_offer")
    if body.variety.casefold() != terms["variety"].casefold() or body.grade.casefold() != terms["grade"].casefold():
        raise HTTPException(422, "crop_requirements_do_not_match")
    amount = milli(body.quantity)
    if not milli(terms["minimum_quantity"]) <= amount <= milli(terms["maximum_quantity"]):
        raise HTTPException(422, "quantity_outside_offer_lot_limits")
    if amount > offer.total_milli - offer.reserved_milli - offer.committed_milli:
        raise HTTPException(409, "insufficient_remaining_purchase_quantity")
    arrival_check(terms, body.arrival_at)
    duplicate = db.scalar(
        select(FarmerPurchaseRequest.id).where(
            FarmerPurchaseRequest.offer_id == offer.id,
            FarmerPurchaseRequest.farmer_id == user.id,
            FarmerPurchaseRequest.status.in_(["SUBMITTED", "ACCEPTED", "COUNTEROFFERED"]),
        )
    )
    if duplicate:
        raise HTTPException(409, "active_request_already_exists_for_offer")
    request = FarmerPurchaseRequest(
        public_id="SAMAY-P-" + uuid4().hex[:20].upper(),
        offer_id=offer.id,
        farmer_id=user.id,
        quantity_milli=amount,
        expected_price=body.expected_price,
        arrival_at=body.arrival_at,
        details={**body.model_dump(mode="json"), "offer_terms_at_submission": terms},
        submission_key=key,
        payload_hash=fingerprint,
    )
    db.add(request)
    db.flush()
    event(db, request, user.id, "SUBMITTED")
    notify(
        db,
        offer,
        request,
        owners(db, offer),
        "A farmer sent a selling request for your buying offer.",
        "ನಿಮ್ಮ ಖರೀದಿ ಆಫರ್‌ಗೆ ರೈತರು ಮಾರಾಟ ವಿನಂತಿ ಕಳುಹಿಸಿದ್ದಾರೆ.",
    )
    return request


def request_for(db, user, request_id, manage=True):
    request = db.get(FarmerPurchaseRequest, request_id)
    if not request:
        raise HTTPException(404, "private_request_not_found")
    offer = offer_for(db, user, request.offer_id, manage)
    return request, offer


def release_previous(db, offer, request):
    for reservation in db.scalars(
        select(PurchaseReservation).where(PurchaseReservation.request_id == request.id, PurchaseReservation.state == "HELD")
    ):
        reservation.state = "RELEASED"
        offer.reserved_milli -= reservation.quantity_milli
    db.flush()


def respond(db, user, request, offer, body, action):
    cleanup(db, offer)
    if request.version != body.version or request.status not in {"SUBMITTED", "ACCEPTED", "COUNTEROFFERED"}:
        raise HTTPException(409, "private_request_changed_or_terminal")
    release_previous(db, offer, request)
    terms = terms_for(db, offer)
    if action != "reject":
        available(db, offer)
        if any(request.details[field].casefold() != terms[field].casefold() for field in ["variety", "grade"]):
            raise HTTPException(422, "crop_requirements_do_not_match")
        arrival_check(terms, body.arrival_at)
        if not now() < body.expires_at <= min(offer.expires_at, body.arrival_at):
            raise HTTPException(422, "response_expiry_must_precede_arrival_and_offer_expiry")
        amount = milli(body.quantity)
        if not milli(terms["minimum_quantity"]) <= amount <= min(request.quantity_milli, milli(terms["maximum_quantity"])):
            raise HTTPException(422, "response_quantity_outside_request_or_lot_limits")
        if amount > offer.total_milli - offer.reserved_milli - offer.committed_milli:
            raise HTTPException(409, "insufficient_remaining_purchase_quantity")
        if terms["daily_intake"]:
            reservations = db.scalars(
                select(PurchaseReservation).where(
                    PurchaseReservation.offer_id == offer.id, PurchaseReservation.state.in_(["HELD", "COMMITTED"])
                )
            )
            used = sum(
                r.quantity_milli for r in reservations if r.arrival_at.astimezone(IST).date() == body.arrival_at.astimezone(IST).date()
            )
            if used + amount > milli(terms["daily_intake"]):
                raise HTTPException(409, "daily_purchasing_capacity_exceeded")
        response = BusinessResponse(
            request_id=request.id,
            actor_id=user.id,
            kind=action.upper(),
            quantity_milli=amount,
            price=body.price,
            arrival_at=body.arrival_at,
            expires_at=body.expires_at,
            terms={
                **terms,
                "confirmed_price": str(body.price),
                "confirmed_quantity": quantity(amount),
                "payment_terms": body.payment_terms,
                "message": body.message,
                "offer_revision": offer.version,
            },
        )
        db.add(response)
        db.flush()
        db.add(
            PurchaseReservation(
                offer_id=offer.id,
                request_id=request.id,
                response_id=response.id,
                quantity_milli=amount,
                arrival_at=body.arrival_at,
                expires_at=body.expires_at,
            )
        )
        offer.reserved_milli += amount
        request.status = "ACCEPTED" if action == "accept" else "COUNTEROFFERED"
        details = {"response_id": response.id}
    else:
        request.status = "REJECTED"
        details = {"reason": body.reason}
        db.add(
            BusinessResponse(
                request_id=request.id,
                actor_id=user.id,
                kind="REJECT",
                quantity_milli=0,
                price=0,
                arrival_at=request.arrival_at,
                expires_at=now(),
                terms=details,
            )
        )
    request.version += 1
    offer.version += 1
    event(db, request, user.id, request.status, details)
    history(db, offer, user.id, "REQUEST_" + request.status)
    notify(
        db,
        offer,
        request,
        [request.farmer_id],
        "Your selling request has a business response. Review the exact terms before confirming.",
        "ನಿಮ್ಮ ಮಾರಾಟ ವಿನಂತಿಗೆ ವ್ಯಾಪಾರದಿಂದ ಪ್ರತಿಕ್ರಿಯೆ ಬಂದಿದೆ. ದೃಢೀಕರಿಸುವ ಮೊದಲು ಷರತ್ತುಗಳನ್ನು ಪರಿಶೀಲಿಸಿ.",
    )


def confirm(db, user, request, offer, version):
    cleanup(db, offer)
    if request.version != version or request.status not in {"ACCEPTED", "COUNTEROFFERED"}:
        raise HTTPException(409, "private_response_expired_or_request_changed")
    business = db.get(BusinessAccount, offer.business_id)
    if business.verification_state != "VERIFIED" or (
        business.business_type == "PRIVATE_MANDI" and not db.get(BusinessMarketAssignment, business.id)
    ):
        raise HTTPException(409, "business_not_verified")
    reservation = db.scalar(
        select(PurchaseReservation).where(PurchaseReservation.request_id == request.id, PurchaseReservation.state == "HELD")
    )
    if not reservation:
        raise HTTPException(409, "private_response_expired")
    reservation.state = "COMMITTED"
    offer.reserved_milli -= reservation.quantity_milli
    offer.committed_milli += reservation.quantity_milli
    offer.version += 1
    if offer.status in ACTIVE:
        offer.status = "FULLY_FILLED" if offer.committed_milli == offer.total_milli else "PARTIALLY_FILLED"
    request.status, request.version = "CONFIRMED", request.version + 1
    event(db, request, user.id, "CONFIRMED", {"response_id": reservation.response_id})
    history(db, offer, user.id, "QUANTITY_COMMITTED")
    notify(
        db, offer, request, owners(db, offer), "The farmer confirmed the exact response terms.", "ರೈತರು ಪ್ರತಿಕ್ರಿಯೆಯ ನಿಖರ ಷರತ್ತುಗಳನ್ನು ದೃಢೀಕರಿಸಿದ್ದಾರೆ."
    )


def serialize_request(db, request, user):
    farmer = db.get(SaleUser, request.farmer_id)
    responses = list(db.scalars(select(BusinessResponse).where(BusinessResponse.request_id == request.id).order_by(BusinessResponse.id)))
    latest = responses[-1] if responses else None
    status = request.status
    if latest and status in {"ACCEPTED", "COUNTEROFFERED"} and latest.expires_at <= now():
        status = "EXPIRED"

    def safe_terms(terms):
        # Protected references belong to the business-only offer endpoint, never
        # a request response that can also be retrieved through the farmer API.
        return {k: v for k, v in terms.items() if k != "image_references"}

    details = dict(request.details)
    details["offer_terms_at_submission"] = safe_terms(details["offer_terms_at_submission"])
    response_rows = [
        {
            "id": r.id,
            "kind": r.kind,
            "quantity": quantity(r.quantity_milli),
            "price": format(r.price, ".2f"),
            "arrival_at": r.arrival_at,
            "expires_at": r.expires_at,
            "terms": safe_terms(r.terms),
            "created_at": r.created_at,
        }
        for r in responses
    ]
    return {
        "id": request.id,
        "public_id": request.public_id,
        "offer_id": request.offer_id,
        "farmer_name": farmer.name,
        "farmer_phone": farmer.phone if request.details["contact_consent"] and farmer.phone_verified else None,
        "quantity": quantity(request.quantity_milli),
        "expected_price": format(request.expected_price, ".2f"),
        "arrival_at": request.arrival_at,
        "created_at": request.created_at,
        "status": status,
        "version": request.version,
        "details": details,
        "responses": response_rows,
        "unit": "quintal",
        "currency": "INR",
        "history": [
            {"action": h.action, "created_at": h.created_at, "details": h.details}
            for h in db.scalars(
                select(PurchaseRequestHistory).where(PurchaseRequestHistory.request_id == request.id).order_by(PurchaseRequestHistory.id)
            )
        ],
    }
