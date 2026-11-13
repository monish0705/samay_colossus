"""Dated mandi reference for price estimation; never a confirmed buyer offer."""
from datetime import timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import case, select

from app.models import ImportBatch, MandiObservation


def latest_quote(db, market_id, crop_id, variety, grade, decision_at):
    today = decision_at.astimezone(ZoneInfo('Asia/Kolkata')).date()

    def get_candidate(m_id, v, g):
        stmt = select(MandiObservation).where(
            MandiObservation.commodity_id == crop_id,
            MandiObservation.data_kind.in_(['official', 'secondary']),
            MandiObservation.observed_on <= today,
        )
        if m_id is not None:
            stmt = stmt.where(MandiObservation.market_id == m_id)
        if v is not None:
            stmt = stmt.where(MandiObservation.variety == v)
        if g is not None:
            stmt = stmt.where(MandiObservation.grade == g)
        stmt = stmt.order_by(
            case((MandiObservation.data_kind == 'official', 0), else_=1),
            MandiObservation.observed_on.desc(),
            MandiObservation.id.desc(),
        )
        for row in db.scalars(stmt):
            batch = db.get(ImportBatch, row.latest_batch_id) if row.latest_batch_id else None
            if (batch.fetched_at if batch else row.created_at) <= decision_at:
                return row
        return None

    # Priority 1: Exact match on market, variety, grade
    observation = get_candidate(market_id, variety, grade)
    # Priority 2: Match on market and variety
    if observation is None:
        observation = get_candidate(market_id, variety, None)
    # Priority 3: Match on market and crop
    if observation is None:
        observation = get_candidate(market_id, None, None)
    # Priority 4: State-level reference for crop
    if observation is None:
        observation = get_candidate(None, None, None)

    if observation is None:
        raise HTTPException(503, 'mandi_price_unavailable')
    if today - observation.observed_on > timedelta(days=7):
        raise HTTPException(503, 'mandi_price_stale_refresh_required')
    if observation.price_unit != 'INR/quintal' or observation.modal_price_inr_per_quintal <= 0:
        raise HTTPException(503, 'mandi_price_invalid')
    return observation
