# Historical buffered-intake implementation

Not the selected production architecture. Use [the direct Connect workflow](end-user-registration.md). The separate public store and pull worker below remain only for old local tests; do not activate them on Connect.

# End-user registration workflow

Implemented locally on 2026-11-09. The existing Tally/PHP/Airtable production flow
has not been changed. Public deployment is pending. A controlled real SendGrid test and explicit
email confirmation succeeded locally on 2026-11-09; CRM review, NMVS-recording
simulation and reopening were verified in an isolated temporary database.

## Process and authority

1. An End User submits the existing Tally form `w7AWGA`:
   <https://forms.smvs-gmbh.ch/r/w7AWGA>.
2. A **separate public registration intake** verifies the signed Tally webhook,
   validates the expected form and stable field IDs, stores an encrypted,
   purpose-limited registration and queues its confirmation email. Repeated
   event/submission IDs do not create a second registration or email.
3. An **internal pull worker** retrieves the registration. Operations creates a
   provisional CRM End User and contact, links the contact as SPOC and records
   **Awaiting email confirmation**. No name/email-based merge is performed.
   This happens at the next successful pull, including while confirmation is pending.
4. A separate mail worker calls SendGrid with the existing dynamic template
   `d-3cae560da6c644aa92b54d4e170b059b`. `Accepted` means the SendGrid API accepted
   the request, not that the email was delivered. Sending is disabled until the
   verified sender, template link variable and API key are configured.
5. The email link opens a minimal confirmation page. A GET never confirms the
   registration. The recipient explicitly selects **Confirm email**. A random,
   single-use 24-hour token is submitted in a same-origin POST and consumed.
   The token is in the URL fragment, removed from the address bar by the page,
   and is not placed in a query string or normal access log.
6. The internal pull imports confirmation as **Needs review**. Confirmation proves
   access to the submitted mailbox, not the organisation's legitimacy or licence.
7. The NMVO reviews the organisation, GLN/UID, address, software and contact in
   **Workflows → End-user registrations**. Linked CRM pages support corrections.
   Possible duplicate names/GLNs are flagged and require explicit review. The
   submitted confirmation email remains recorded separately; changing the contact
   email cannot silently transfer the earlier verification to another address.
8. **Approve review · ready for NMVS** records the authenticated reviewer and
   enables temporary access to the security question/answer. The review captures
   a hash of current CRM details; changes after approval require renewed review.
9. The operator creates the organisation manually in the NMVS, using the temporary
   values, then selects **Record manual NMVS creation** and enters its organisation
   ID. Operations records this manual step and erases the security question/answer.
   There is **no NMVS organisation-creation API call**.
10. When the organisation appears in a Snapshot, use **CRM → End Users → Link
    organisation** to associate the maintained CRM record with its NMVS record.
    The recorded external ID does not create a fictional Snapshot record.

The workflow does not create a PortalUser, passkey or internal NMVO/Admin role.
Provisional contacts are marked pending and cannot be newly assigned to other
MAHs/End Users or selected for self-declaration invitations before review approval.

## Internal operation

The list has status counts, direct search, personal views and configurable columns.
Record navigation, an initially closed Actions toolbox and an attributed Action log
follow the portal UI conventions. Actions use version checks to reject stale forms.

- **Resend confirmation email** explicitly rotates the old link and requeues one
  email while the intake data is still available. Synchronise first. Resends have
  a five-minute interval and invalidate earlier links.
- **Reject registration** requires a reason and reversibly archives the provisional
  CRM End User/contact. Temporary security data is removed internally.
- **Reopen review** requires a reason. It does not undo a real NMVS creation or
  restore deleted security answers. Historical NMVS IDs and audit entries remain.
- **View temporary security data** is an authenticated NMVO POST, recorded in the
  Action log. Values are not included in the normal detail page, CRM profile,
  email, staging archive or Action-log note. Do not copy them into free-text notes.
- Expired intake data that could not be imported yields an explicit expired entry,
  without inventing a CRM identity. A corrected registration/new secure collection
  may be required if data or the original email was wrong or has expired.

## Separation and data lifecycle

`app.registration.gateway:from_environment` is its own ASGI entry point. It does
not import `app.main`, Operations routers, the core DB session or NMVS credentials.
Its routes are limited to the Tally webhook, confirmation page/assets and a
restricted internal exchange API. `/crm`, `/exceptions`, `/workflows`, `/admin` and
API documentation do not exist in that application.

The intake has its own SQLAlchemy metadata and a separate `smvs_registration`
MySQL database/user. A core database URL is refused. Production connections require
an explicit CA and TLS hostname validation, and a non-TLS socket is refused.
Explicit local SQLite files are supported only in development; do not use them as
the production database. The intake reads `.env.registration-intake`, not the core
`.env`. Deploy it with a separate OS account, directory and environment that cannot
read core secrets. Ignoring unrelated environment fields is not OS isolation.

The core initiates exchange over authenticated HTTPS; the public service never
connects to the core DB. Use a separate random exchange secret and restrict the
exchange paths at nginx to the internal worker's egress/network where possible.
The pull validates the bounded response and commits CRM changes **before**
acknowledging them. Failed acknowledgements are safe to replay. Received updates
cannot approve reviews or grant portal permissions.

Registration payloads, original confirmation tokens and temporary security data
are encrypted with a dedicated Fernet key held outside SQL. Token matching uses a
SHA-256 digest. The registration key is purpose-specific and must not be a core
NMVS encryption key. Key rotation/backup policy must preserve the ability to read
unexpired registrations without retaining deleted answers indefinitely.

The public payload expires after seven days by default (configurable 1–30); the
internal security-data deadline is additionally capped at seven days from the
submission/receipt. After confirmed data is durably imported and acknowledged, the
public encrypted payload is cleared. Internal question/answer values are cleared
on rejection, recorded NMVS creation or expiry cleanup. An initial unconfirmed
acknowledgement does not erase the pending confirmation payload.

Run the pull/mail workers continuously and schedule the intake `purge` command
independently, including when mail is not configured. Access checks deny expired
security values immediately; physical cleanup requires the workers/maintenance to
run. CRM identity data and minimal receipt/audit metadata have a separate retention
purpose. Tally itself and encrypted backups may still hold copies: configure and
validate their deletion/retention separately. Deleting a field in the active DB
cannot retroactively remove it from an old backup.

## Configuration and supervised processes

The templates are `config/registration-intake.env.example` (public service only)
and `config/registration-core.env.example` (internal Operations only).
Use distinct randomly generated encryption, exchange and Tally-signing secrets.
Never print or commit real keys. The verified sender is `office@smvs-gmbh.ch`;
the existing template uses `first_name`, `last_name` and `confirmation_link`.

Initialise the **separate intake store** with its restricted installation account:

```sh
.venv/bin/python -m app.registration init
```

The intake runtime account need not retain DDL privileges. Then run a supervised
ASGI process behind the dedicated public nginx host, with loopback binding when
nginx is on the same node:

```sh
.venv/bin/uvicorn app.registration.gateway:from_environment --factory --host 127.0.0.1 --port 8013 --no-access-log
```

Run the mail worker in that isolated service environment:

```sh
.venv/bin/python -m app.registration mail-watch
```

Run the pull worker **inside Operations/VPN**, using its normal guarded DB account:

```sh
.venv/bin/python -m app.domain.crm.registration_sync --watch
```

One-off commands: `python -m app.registration mail-once`,
`python -m app.registration purge`, and `python -m app.domain.crm.registration_sync`.
All loops need process supervision, monitoring, bounded logs and the deployment
hardening from the security review. Do not publish the local test fixture.

The mail worker durably claims an email before the network request. A timeout or
server-side failure has an **uncertain** outcome and is not silently retried. This
avoids unbounded duplicate confirmations when the provider may already have
accepted a message. A crash during `sending` likewise requires review/resend.
There is no claim of exactly-once email delivery or delivered-email tracking.
The operator can rotate/requeue through **Resend confirmation email**.

Required SendGrid dynamic data:

- The configured `REGISTRATION_MAIL_LINK_FIELD` receives the full confirmation URL.
- `organisation_name`, `first_name`, `last_name` are also supplied. Use escaped
  placeholders in the template. If the existing template needs different names,
  verify/adapt that contract before enabling real mail.
- Click/open tracking is disabled for these credential-bearing messages.
- Set `REGISTRATION_MAIL_FROM` to the verified sender; do not assume an address.

## Public activation and PHP/Airtable cutover

1. Complete the core/intake deployment security controls: private core, isolated
   DB/users/secrets, HTTPS, trusted proxy headers, nginx request/rate limits and
   sensitive-log exclusions. The new intake provides bounded bodies, signatures,
   CSRF protection on confirmation and a restrictive CSP; it is not a substitute
   for the deployment/security-review acceptance checks.
2. Choose the public registration hostname. Configure the exact canonical origin
   and SendGrid sender/link placeholder/API key in the isolated service.
3. Configure a Tally webhook to
   `https://PUBLIC_REGISTRATION_HOST/webhooks/tally/registrations` with the matching
   signing secret. Do not configure the private Operations host as a public webhook.
4. Run one controlled synthetic end-to-end test: real signed webhook, one accepted
   email, explicit confirmation, CRM import, review, manual NMVS-recording simulation,
   expiry/resend/replay checks. Inspect the actual payload to verify the current
   field-key contract; translated labels are not used as database keys.
5. Stop the old Make/Airtable **new-registration confirmation sender** at cutover so
   one registration does not trigger two confirmation workflows. Do not disable
   unrelated self-declaration automations.
6. Existing PHP links are not automatically recognised by the new token store.
   Keep the legacy route for its known outstanding confirmations during a bounded
   transition, or deliberately reissue confirmations after a reviewed migration.
   Do not silently rewrite the old token URLs or import plaintext legacy tokens.
7. Reconcile every pending registration before retiring PHP/Airtable processing.
   The supplied PHP code is a legacy reference; it is not copied into Operations.

## Repeatable local test workspace

```sh
.venv/bin/python -m app.registration.test_workspace
```

Open `http://localhost:8014/workflows/registrations`. The disposable SQLite workspace
contains three fixed synthetic organisations: awaiting confirmation, needs review
and ready for manual NMVS creation. It makes no Tally/SendGrid requests. Restarting
resets all test records. Automated integration tests exercise signed webhooks,
confirmation, replay, delayed acknowledgement, review, rejection/reopening,
encryption, expiry and SendGrid outcomes without transmitting real messages.

## Primary references checked 2026-11-09

- [Tally webhook signatures, field keys and retries](https://tally.so/help/webhooks)
- [SendGrid Mail Send / dynamic template API](https://www.twilio.com/docs/sendgrid/api-reference/mail-send/mail-send)

## Jelastic deployment package

`deploy/registration-intake/README.md` describes the isolated Docker/nginx test
deployment. `scripts/package_registration_intake.py OUTPUT.zip` creates a source
archive using an explicit file allowlist; it excludes the core app, all actual
environment files, credentials, test workspaces and databases. Adapt the nginx
template to the actual Jelastic topology before deployment. Public activation
requires a verified HTTPS hostname, separate TLS-protected MySQL database and
restricted exchange access. No public container has been provisioned by this step.

## Preferred hosting: preinstalled Apache-Python

The user selected Apache-Python on Jelastic instead of a custom Docker image.
Use `deploy/registration-intake/README-apache.md`: Uvicorn on loopback behind the
dedicated Apache vhost and public nginx. Package using
`scripts/package_registration_intake.py --platform apache OUTPUT.zip`. This avoids
a container registry. The actual node paths, Python version, supervisor and proxy
configuration must be inspected before remote installation; Apache mod_wsgi is
not the FastAPI runtime. Public deployment remains pending.
