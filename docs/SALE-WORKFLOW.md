# Farmer-to-mandi sale requests

**13 November update:** the farmer price/form and unonboarded-mandi behavior described below
have been simplified. See [automatic prices and pending activation](MANDI-PRICE-AND-REQUESTS.md).
New farmer screens use automatic dated mandi references, two required request fields and
durable waiting requests. Existing farmer-entered-price API clients remain compatible.

SAMAY facilitates requests, negotiated terms, arrival bookings and recorded sale details.
It does not execute physical sales or transfer money. Market observations, farmer expectations,
owner offers and actual weighment prices are stored and displayed separately.

## Architecture

The existing FastAPI service owns identity, authorization and the sale state machine.
`sale_auth.py` uses salted PBKDF2-SHA256 passwords, opaque hashed server-side sessions,
12-hour HttpOnly cookies, SameSite=Lax, Secure cookies in production, restricted CORS,
a required non-simple `X-SAMAY-Action: 1` header for mutations and database-backed throttles.
No client-supplied farmer or owner IDs determine authorization. Public farmer registration
cannot select a role. Mandi accounts require an expiring, single-use administrator invitation.

`sale_service.py` implements scoped access, Decimal calculations, compare-and-swap versions,
append-only events and notification creation. Each successful request transition and its
in-app notifications/outbox rows commit together. A unique farmer/idempotency-key constraint
protects creation, including retries. Reusing a key for different inputs returns 409.
The UI keeps the same key while retrying the same confirmed request.

`sale_routes.py` reuses existing Market, Commodity and MandiObservation entities. Variety
and grade remain the existing normalized strings instead of adding incompatible identifiers.
The configured registry is queried dynamically; no crop count or mandi count is assumed.
Official exact-series reference observations are attached server-side. Missing reference
data is displayed as unavailable, with no invented quote.

The standalone owner portal uses the same backend, database and React application.
The new screens have no demonstration transactions, seeded owners or fabricated counts.
Existing unrelated application modes have been left intact.

## Database migration

Revision `c3d4e5f6a7b8` follows `b2c3d4e5f6a7`. Definitions are frozen within the migration.
It adds these tables without changing historical observations or models:

- mandi_users, sale_sessions, sale_invitations, sale_contact_challenges, sale_auth_throttles
- mandi_registrations, mandi_user_market_assignments
- sale_requests, sale_request_events, sale_request_offers
- sale_arrival_bookings, sale_transaction_records
- notifications, notification_preferences, notification_deliveries, notification_outbox

Foreign keys, unique idempotency/public IDs, indexes and financial checks are enforced.
SQLite triggers reject updates/deletes of request events and offer revisions. Other database
engines require equivalent database permissions/triggers as a deployment hardening step;
there are no HTTP history-edit/delete endpoints.

Run from the repository root, using the SAME database configuration as the running API:

```powershell
.\.venv\Scripts\python.exe -m alembic -c backend/alembic.ini upgrade head
```

Back up durable runtime data before a deployment migration. Do not replace an active sale
database with the prepared market-data bundle. Bundles must never contain farmer accounts,
sessions or sale histories. Database files and local verification audit files remain ignored.

## Local startup and real onboarding

```powershell
.\.venv\Scripts\python.exe scripts/start_local.py --bundled-research --backend-port 8012 --frontend-port 5175
```

This migrates the isolated bundled profile, preserves its existing user/history data and
launches a notification worker when it launches the backend. Do not run two launchers on the
same ports. If reusing an already running API, restart it after this code/migration update.

For continuing real use, choose a stable SAMAY_DATABASE_URL and use `--enable-research`
instead of the hash-named bundled profile. Changing the prepared bundle creates a different
isolated profile; previous profiles are preserved but are not automatically merged. Import
new observations into the stable database rather than replacing accounts/bookings with a bundle.

Before creating accounts in an isolated bundled profile, set the database URL in the
administration terminal to its runtime copy, NOT `data/prepared/samay.db`:

```powershell
# Inspect .local-data and use the exact bundled-<hash>.db path printed/used by startup.
$env:SAMAY_DATABASE_URL = 'sqlite:///C:/absolute/path/to/.local-data/bundled-<hash>.db'
.\.venv\Scripts\python.exe scripts/sale_admin.py bootstrap-admin --email 'YOUR_REAL_EMAIL' --name 'YOUR_REAL_NAME'
```

The password is requested privately; there is no default password. Bootstrapping refuses
to create another administrator if one already exists. Use a real operator's details.

1. Sign in at `/mandi` as the administrator; open Mandi Settings.
2. Register an existing mandi, record verified registration details, choose accepted crops
   and activate request handling.
3. Verify the operator identity/authority independently. Create a MANDI_OWNER invitation
   for that exact market and email. Deliver its one-time code through an authorized private
   channel. Codes expire in 48 hours; they do not themselves verify an email address.
4. The operator opens `/mandi`, selects Redeem authorized invitation, and registers using
   the matching email and invitation code. There are no automatic owner accounts.
5. Staff use separate administrator-approved MANDI_STAFF invitations. Owners can grant
   transaction permission or remove a staff assignment through Staff Management. New staff
   default to viewing only. Owners cannot invite themselves into another market.
6. Farmers create their own accounts at `/sale-requests`. No email/phone is shared publicly.

Email ownership is verified separately: settings sends a secret token via configured SMTP;
the token must be entered from the recipient mailbox within 30 minutes. It is never returned
to the browser by the start endpoint. Each external channel requires explicit consent.

Phone verification is a trusted host-operator process until a dedicated phone verification
provider is integrated. Only after independent ownership verification:

```powershell
.\.venv\Scripts\python.exe scripts/sale_admin.py verify-phone --email 'REAL_ACCOUNT_EMAIL' --phone '+91REALNUMBER' --evidence 'Protected verification record reference'
```

This stores a protected local evidence reference and enables the account to opt in to SMS
or WhatsApp. Running the command is an operator attestation, not a claim SAMAY verified an OTP.
Phone sharing with a mandi additionally requires the farmer's per-request consent.

## Farmer journey

1. Generate the existing selling recommendation; choose Sell to This Mandi.
2. Authenticate. The request form uses the current plan/scope, allows partial quantity,
   and lets the farmer select an available registered mandi and crop.
3. Enter buyer expectation, estimated total selling costs, preferred arrival time and message.
4. Review the server-calculated estimate and official reference date, then explicitly confirm.
5. Track `/sale-requests`, notifications, offers and the event timeline.
6. Confirm the latest nonexpired offer, including price, quantity and arrival slot. This
   creates the booking. Reduced quantity does not silently book the rest of the harvest.
7. View arrival, weighed quantity, final price, deductions and payment recording. Report
   discrepancies through the request detail page.

An unregistered/inactive mandi or a mandi without an active assigned owner cannot receive
online requests. Both UI and API enforce this. Notifications say persisted in the assigned
inbox; they do not claim the owner read the request or that an external message was delivered.

## Owner routes

- `/mandi`: actual database summary and requests
- `/mandi/incoming`: incoming requests/status filters
- `/mandi/requests/{public_request_id}`: details, responses and complete lifecycle
- `/mandi/counteroffers`, `/mandi/arrivals`, `/mandi/arrived`, `/mandi/completed`
- `/mandi/notifications`: inbox/read status/channel attempts
- `/mandi/settings`: channel consent/verification; administrator onboarding when authorized
- `/mandi/staff`: assigned staff and permission management

The owner must open a request before responding. An acceptance preserves the requested
quantity/expected price; changing either requires a counteroffer. Every revision is a new
offer row. Farmers must confirm the exact latest offer ID. Slots cannot be unilaterally
changed after confirmation. Staff record received/weighed quantity and actual quality;
deductions cannot exceed gross proceeds. Money rounds to paise using ROUND_HALF_UP.
Manual payment updates retain an audit trail and notify the farmer.

## Lifecycle

```text
SUBMITTED -> NOTIFIED -> VIEWED -> MANDI_ACCEPTED or COUNTER_OFFERED
-> FARMER_CONFIRMED -> ARRIVAL_SCHEDULED -> ARRIVED -> WEIGHED -> COMPLETED
```

NOTIFICATION_PENDING is also supported for a future deferred-inbox process; the current
transactional inbox can immediately persist NOTIFIED. External failures never block or
change the business status to a fictitious delivery result. VIEWED can reject, offered
states can expire/cancel, and COUNTER_OFFERED can append another revision. Confirmation
and scheduling are two audit events in one transaction.

Farmer offer rejection closes the request as CANCELLED. No revised farmer-proposal feature
is enabled. Cancellation is allowed before arrival, until two hours before the agreed
booking slot. Completed/arrived/weighed requests cannot be cancelled through this flow.
Offers expire on access and cannot be confirmed after expiry even if an old page is open.
Version mismatches return 409 and require reloading instead of overwriting another response.

## API contract

OpenAPI/Swagger exposes request validation and sale response schemas at `/docs`.
Money/quantity values serialize as decimal strings; timestamps include UTC offsets.

- Auth: POST `/api/v1/auth/register`, `/auth/login`, `/auth/logout`; GET `/auth/me`
- Verification: POST `/api/v1/auth/verify-email/start`, `/auth/verify-email/confirm`
- Registry: GET `/api/v1/sale-mandis`; admin POST `/admin/mandis`, `/admin/mandi-invitations`
- Farmer: POST `/api/v1/sale-requests/preview`, `/sale-requests`; GET `/sale-requests`
- Farmer detail: GET `/sale-requests/{id}`, `/{id}/timeline`
- Farmer actions: POST `/{id}/confirm`, `/reject-offer`, `/cancel`, `/discrepancy`
- Owner: GET `/api/v1/mandi/dashboard`, `/mandi/requests`, `/mandi/requests/{id}`, `/{id}/timeline`
- Owner actions: POST `/{id}/view`, `/accept`, `/counteroffer`, `/reject`, `/schedule-arrival`,
  `/mark-arrived`, `/record-weighment`, `/complete`, `/payment`
- Staff: GET/POST `/api/v1/mandi/staff`
- Notifications: GET `/api/v1/notifications`, `/notifications/unread-count`, `/mandi/notifications`;
  POST `/notifications/{id}/read`; GET/POST `/notification-preferences`

The owner action prefixes above are `/api/v1/mandi/requests/{id}`; farmer prefixes are
`/api/v1/sale-requests/{id}`. Creation requires `Idempotency-Key` (16–100 characters).
State-changing actions require the current request `version`; confirmation also requires
`offer_id`. Request IDs are generated, not sequentially guessed.

Errors: 401 unauthenticated; 403 unauthorized role/assignment/CSRF; 404 private request
not found; 409 inactive mandi, state/version conflict, expired/superseded offer or consent
issue; 422 invalid fields/quantity/dates; 429 throttled; 503 unavailable durable storage,
verification channel or database. The existing error envelope includes a request ID.

## Notifications and actual provider status

In-app notifications are primary. The portal polls every 5 seconds, backs off to 30 seconds
on errors, reconnects automatically and shows a warning/retry control. Overlapping polls
are avoided. New notifications update the badge and incoming list without a manual refresh.
Assignment revocation removes access to the old owner inbox as well as request details.

`sale_notification_worker.py` atomically claims outbox rows with leases, rechecks recipient
authorization/verification/consent and sends only configured channels. It logs safe status
codes, not provider response bodies or contact secrets. Run against the SAME database:

```powershell
.\.venv\Scripts\python.exe scripts/sale_notification_worker.py
# Scheduled single batch alternative:
.\.venv\Scripts\python.exe scripts/sale_notification_worker.py --once
```

SMTP uses STARTTLS. SENT means accepted by the SMTP server, not delivered to the mailbox.
Twilio SMS and WhatsApp use the documented Message resource:
https://www.twilio.com/docs/messaging/api/message-resource
Twilio acceptance records a provider SID; subsequent authenticated resource polling can
record DELIVERED, READ or FAILED. No unauthenticated provider callback is accepted.
WhatsApp requires approved sender/templates and recipient permission; templates must have
one variable containing the localized concise request update. Configure both languages.

Unconfigured channels remain RETRY_SCHEDULED in the durable outbox. Explicit SMTP 4xx or
provider HTTP 429 rejections use bounded exponential retries. Timeouts, ambiguous outcomes
or a worker crash during SENDING become UNKNOWN and require provider reconciliation;
blind resending could duplicate a message. Exactly-once delivery across an external provider
cannot be promised. In-app notification uniqueness is enforced by recipient/event.

Environment variables (see `.env.example`, never commit actual values):

- SAMAY_MARKETPLACE_ENABLED
- SAMAY_DATABASE_URL; SAMAY_PUBLIC_APP_URL
- SAMAY_SMTP_HOST, SAMAY_SMTP_PORT, SAMAY_SMTP_FROM
- SAMAY_SMTP_USERNAME, SAMAY_SMTP_PASSWORD
- SAMAY_TWILIO_ACCOUNT_SID, SAMAY_TWILIO_AUTH_TOKEN, SAMAY_TWILIO_SMS_FROM
- SAMAY_TWILIO_WHATSAPP_FROM
- SAMAY_TWILIO_WHATSAPP_CONTENT_SID_EN, SAMAY_TWILIO_WHATSAPP_CONTENT_SID_KN

Actual external channel delivery has NOT been tested: no authorized SMTP/Twilio credentials
or real verified recipients were supplied. Tests simulate unavailable/failing providers;
these are not claims of delivered emails, SMS or WhatsApp messages.

## Verification and deployment requirements

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_sale_workflow.py -q
Set-Location frontend
npm.cmd test
npm.cmd run lint
npm.cmd run build
Set-Location ..
.\.venv\Scripts\python.exe -m pip install -e 'backend[browser]'
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\python.exe scripts/run_sale_e2e.py
```

The browser test runs Chromium against the production React bundle and actual HTTP API,
with a disposable TEST_ONLY dataset, administrator/owner/farmer identities and transactions.
It follows recommendation -> request -> automatic owner inbox -> counteroffer -> farmer
confirmation -> arrival -> weighment -> completion and checks identical English/Kannada
amounts and mobile overflow. Screenshots and machine-readable results are under reports/.
No fixture identities or bookings enter the running local database.

Production needs HTTPS, a shared durable SQL database, protected backups, least-privilege
database access, worker scheduling, approved operators and verified/consented contacts.
The current Vercel bootstrap normally copies market history into a temporary per-instance
database; sale routes fail closed in that mode. Provision a shared database and driver,
set SAMAY_PERSISTENT_DATABASE_URL in hosting secrets and run/test migrations before enabling
this workflow there. Prepared history/model restoration is a separate concern from sale
data durability. This change has not deployed the marketplace or onboarded a real operator.

Remaining operational work: real mandi approval, external-provider end-to-end delivery,
native-speaker Kannada review, organization-specific cancellation/slot capacity policies,
account recovery/administrator rotation tooling and production concurrency/load testing.
No inventory reservation across separate farmer requests or payment gateway is implemented.
