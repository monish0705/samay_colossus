"""Dated mandi reference for price estimation; never a confirmed buyer offer."""
from datetime import timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import case, select

from app.models import ImportBatch, MandiObservation


def latest_quote(db, market_id, crop_id, variety, grade, decision_at):
    today = decision_at.astimezone(ZoneInfo('Asia/Kolkata')).date()
    rows = db.scalars(select(MandiObservation).where(
        MandiObservation.market_id == market_id, MandiObservation.commodity_id == crop_id,
        MandiObservation.variety == variety, MandiObservation.grade == grade,
        MandiObservation.data_kind.in_(['official', 'secondary']),
        MandiObservation.observed_on <= today).order_by(
            case((MandiObservation.data_kind == 'official', 0), else_=1),
            MandiObservation.observed_on.desc(), MandiObservation.id.desc()))
    observation = None
    for row in rows:
        batch = db.get(ImportBatch, row.latest_batch_id) if row.latest_batch_id else None
        if (batch.fetched_at if batch else row.created_at) <= decision_at:
            observation = row
            break
    if observation is None:
        raise HTTPException(503, 'mandi_price_unavailable')
    if today - observation.observed_on > timedelta(days=7):
        raise HTTPException(503, 'mandi_price_stale_refresh_required')
    if observation.price_unit != 'INR/quintal' or observation.modal_price_inr_per_quintal <= 0:
        raise HTTPException(503, 'mandi_price_invalid')
    return observation
