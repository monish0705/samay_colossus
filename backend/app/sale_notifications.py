"""Durable outbox delivery. SMTP acceptance is not proof of mailbox delivery."""
import base64
import json
import smtplib
import ssl
from datetime import timedelta
from email.message import EmailMessage
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import uuid4

from sqlalchemy import or_, select, update

from app.config import get_settings
from app.sale_models import Notification, NotificationDelivery, NotificationOutbox, SaleUser, now


def setting(name, default=None):
    value = getattr(get_settings(), name.removeprefix('SAMAY_').lower(), None)
    if hasattr(value, 'get_secret_value'):
        value = value.get_secret_value()
    return default if value is None else value


def channel_availability():
    twilio = all(setting(k) for k in ['SAMAY_TWILIO_ACCOUNT_SID', 'SAMAY_TWILIO_AUTH_TOKEN'])
    return {'in_app': 'available',
            'email': 'configured_untested' if setting('SAMAY_SMTP_HOST') and setting('SAMAY_SMTP_FROM') else 'not_configured',
            'sms': 'configured_untested' if twilio and setting('SAMAY_TWILIO_SMS_FROM') else 'not_configured',
            'whatsapp': 'configured_untested' if twilio and setting('SAMAY_TWILIO_WHATSAPP_FROM') and
                setting('SAMAY_TWILIO_WHATSAPP_CONTENT_SID_EN') and setting('SAMAY_TWILIO_WHATSAPP_CONTENT_SID_KN') else 'not_configured'}


def send_email(recipient, subject, text, message_id=None):
    if channel_availability()['email'] == 'not_configured':
        raise RuntimeError('email_not_configured')
    message = EmailMessage()
    message['From'], message['To'], message['Subject'] = setting('SAMAY_SMTP_FROM'), recipient, subject
    message['Message-ID'] = message_id or f'<{uuid4().hex}@samay.local>'
    message.set_content(text)
    # TLS is mandatory; no plaintext credential fallback.
    with smtplib.SMTP(setting('SAMAY_SMTP_HOST'), int(setting('SAMAY_SMTP_PORT', '587')), timeout=15) as smtp:
        smtp.starttls(context=ssl.create_default_context())
        if setting('SAMAY_SMTP_USERNAME'):
            smtp.login(setting('SAMAY_SMTP_USERNAME'), setting('SAMAY_SMTP_PASSWORD'))
        refused = smtp.send_message(message)
        if refused:
            raise RuntimeError('smtp_recipient_refused')
    return 'SENT', None


def twilio_request(path, data=None):
    sid, token = setting('SAMAY_TWILIO_ACCOUNT_SID'), setting('SAMAY_TWILIO_AUTH_TOKEN')
    # Official Message resource endpoint; no arbitrary recipient-controlled URL.
    url = f'https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages{path}.json'
    auth = base64.b64encode(f'{sid}:{token}'.encode()).decode()
    request = Request(url, data=urlencode(data).encode() if data is not None else None,
                      headers={'Authorization': f'Basic {auth}'})
    with urlopen(request, timeout=15) as response:
        return json.load(response)


def twilio_send(channel, recipient, text, language):
    if channel_availability()[channel] == 'not_configured':
        raise RuntimeError(f'{channel}_not_configured')
    fields = {'To': recipient, 'From': setting('SAMAY_TWILIO_SMS_FROM')} if channel == 'sms' else {
        'To': 'whatsapp:' + recipient, 'From': setting('SAMAY_TWILIO_WHATSAPP_FROM'),
        'ContentSid': setting(f'SAMAY_TWILIO_WHATSAPP_CONTENT_SID_{language.upper()}'),
        'ContentVariables': json.dumps({'1': text})}
    if channel == 'sms':
        fields['Body'] = text
    result = twilio_request('', fields)
    return 'SENT', result['sid']  # Provider acceptance only; delivery is polled separately.


def deliver_pending(factory, limit=50):
    """Single worker recommended. Claims are atomic; unknown sends require reconciliation."""
    attempted = 0
    with factory() as db:
        ids = list(db.scalars(select(NotificationOutbox.delivery_id).where(NotificationOutbox.done.is_(False),
            NotificationOutbox.due_at <= now(), or_(NotificationOutbox.claimed_until.is_(None), NotificationOutbox.claimed_until < now()))
            .limit(limit)))
    for delivery_id in ids:
        with factory() as db:
            claim = db.execute(update(NotificationOutbox).where(NotificationOutbox.delivery_id == delivery_id,
                NotificationOutbox.done.is_(False), or_(NotificationOutbox.claimed_until.is_(None), NotificationOutbox.claimed_until < now()))
                .values(claimed_until=now() + timedelta(minutes=2)))
            db.commit()
            if claim.rowcount != 1:
                continue
            outbox = db.get(NotificationOutbox, delivery_id)
            delivery = db.get(NotificationDelivery, delivery_id)
            if delivery.status == 'SENDING':
                # A worker died after starting an external send. Blind retry can duplicate SMS.
                delivery.status, delivery.error_reason, outbox.done = 'UNKNOWN', 'reconcile_provider_before_retry', True
                db.commit()
                continue
            note = db.get(Notification, delivery.notification_id)
            user = db.get(SaleUser, note.recipient_id)
            from app.sale_models import MandiAssignment, NotificationPreference
            pref = db.get(NotificationPreference, user.id)
            authorized = user.active and (user.role == 'FARMER' or db.get(MandiAssignment, (user.id, note.mandi_id)) is not None)
            verified = user.email_verified if delivery.channel == 'email' else user.phone_verified
            current_recipient = user.email if delivery.channel == 'email' else user.phone
            if not authorized or not verified or delivery.recipient != current_recipient or not pref or not getattr(pref, delivery.channel):
                delivery.status, delivery.error_reason, outbox.done = 'FAILED', 'consent_or_authorization_revoked', True
                db.commit()
                continue
            if channel_availability()[delivery.channel] == 'not_configured':
                delivery.status, delivery.error_reason = 'RETRY_SCHEDULED', 'channel_not_configured'
                outbox.due_at, outbox.claimed_until = now() + timedelta(minutes=15), None
                db.commit()
                continue
            delivery.attempts += 1
            delivery.attempted_at, delivery.status = now(), 'SENDING'
            db.commit()
            attempted += 1
            text = note.message.get(user.language, note.message['en'])
            portal = setting('SAMAY_PUBLIC_APP_URL', '').rstrip('/')
            if portal:
                text += f' {portal}/' + ('sale-requests' if user.role == 'FARMER' else 'mandi')
            try:
                if delivery.channel == 'email':
                    state, provider_id = send_email(delivery.recipient, 'SAMAY sale request update', text, f'<sale-{delivery.id}@samay.local>')
                else:
                    state, provider_id = twilio_send(delivery.channel, delivery.recipient, text, user.language)
                delivery.status, delivery.provider_id, delivery.error_reason = state, provider_id, None
                outbox.done = True
            except HTTPError as exc:
                # Only explicit rejection is safe to retry; unknown timeouts are not.
                retry = exc.code == 429 and delivery.attempts < 5
                delivery.status, delivery.error_reason = ('RETRY_SCHEDULED' if retry else 'FAILED'), f'provider_http_{exc.code}'
                outbox.done = not retry
                outbox.due_at = now() + timedelta(seconds=min(3600, 30 * 2 ** delivery.attempts))
            except smtplib.SMTPResponseException as exc:
                retry = 400 <= exc.smtp_code < 500 and delivery.attempts < 5
                delivery.status, delivery.error_reason = ('RETRY_SCHEDULED' if retry else 'FAILED'), f'smtp_{exc.smtp_code}'
                outbox.done = not retry
                outbox.due_at = now() + timedelta(seconds=30 * 2 ** delivery.attempts)
            except Exception:
                delivery.status, delivery.error_reason, outbox.done = 'UNKNOWN', 'send_outcome_unknown_manual_reconciliation_required', True
            outbox.claimed_until = None
            db.commit()
    return attempted


def refresh_provider_status(factory):
    with factory() as db:
        rows = db.scalars(select(NotificationDelivery).where(NotificationDelivery.provider == 'twilio',
            NotificationDelivery.provider_id.is_not(None), NotificationDelivery.status == 'SENT').limit(50))
        for row in rows:
            try:
                result = twilio_request('/' + row.provider_id)
                if result['status'] in {'delivered', 'read'}:
                    row.status = result['status'].upper()
                elif result['status'] in {'failed', 'undelivered', 'canceled'}:
                    row.status, row.error_reason = 'FAILED', 'provider_reported_failure'
            except Exception:
                continue  # Never convert a failed status lookup into delivered.
        db.commit()
