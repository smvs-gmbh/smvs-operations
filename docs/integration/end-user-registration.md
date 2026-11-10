# End-user registration: SMVS Connect and the private Operations API

Current architecture agreed 2026-11-09. Both services live in the smvs-operations
repository, but the public deployment contains only the explicit Connect file
allowlist. **Connect has no database, encryption key, SendGrid key or CRM read API.**
The earlier buffered intake is [historical](registration-buffered-legacy.md).

## Deployment boundaries

- Public: https://connect.smvs-gmbh.ch; NGINX node 221301, public IP
  195.15.232.138, private IP 10.100.37.96. Apache-Python node 221302 is private at
  10.100.37.97. The certificate and HTTP-to-HTTPS redirect have been verified.
- Internal: env-9657618.jcloud.ik-server.com, Apache-Python node 207849,
  private IP 10.100.32.195. The public node can reach port 80; the private TLS
  listener is not yet installed. The old webroot checkout is preserved; the current private runtime is staged
  separately with the restricted MySQL account.
- The public gateway forwards only two fixed commands through authenticated,
  CA-verified HTTPS. A candidate private listener is 10.100.32.195:8443; restrict
  access to the actual Connect source address at the firewall. The core portal
  remains VPN-protected and is not mounted in either registration API.

## Transactional workflow

1. Tally form w7AWGA posts its signed raw JSON to
   `/webhooks/tally/registrations` on Connect. Connect verifies signature, bounded
   JSON and stable field keys; translated form labels are not used as keys.
2. Connect forwards only to private POST `/v1/registrations/submissions`, with a
   separate bearer credential and the original Tally signature. The private API
   verifies both. It cannot list records, edit CRM, approve, resend or assign roles.
3. In ONE internal database transaction it stores an encrypted receipt/outbox,
   creates the provisional CRM End User/contact and a review/audit record with
   status **Awaiting email confirmation**. Event/submission IDs are unique.
4. Only AFTER commit does Connect return a successful webhook acknowledgement.
   Failure, timeout, unexpected reply or uncertain commit outcome returns 503.
   Re-delivery is safe even if the commit succeeded but the response was lost.
5. A supervised INTERNAL worker sends the approved SendGrid template
   d-3cae560da6c644aa92b54d4e170b059b from office@smvs-gmbh.ch, with first_name,
   last_name and confirmation_link. Accepted is not proof of delivery. The mail
   link is `https://connect.smvs-gmbh.ch/confirm#RANDOM_TOKEN`; tracking is disabled.
6. GET /confirm never confirms anything. Browser code removes the fragment from
   the address bar and submits its 24-hour, one-time token only after an explicit
   same-origin button press. Temporary upstream failures permit retry.
7. Connect forwards only to private POST `/v1/registrations/confirm`. Token
   consumption, **Needs review**, audit event and receipt-payload deletion occur
   atomically inside Operations. No background pull is required.
8. The NMVO reviews details, duplicates, address/software and verified contact.
   Changes to contact email cannot silently transfer verification. Approval records
   the operator and a hash of current CRM details, yielding **Ready for NMVS**.
9. The NMVO manually creates the organisation in the NMVS. Only then record its
   external ID. Operations erases the temporary security question/answer. This
   service does not call an NMVS organisation-creation API.
10. When the organisation appears in a Snapshot, link it through CRM End Users.
    No fictional Snapshot record or PortalUser/passkey is generated.

## Internal controls and lifecycle

- Pending contacts are not available for new unrelated assignments or invitation
  recipient selection before review approval.
- Local resend rotates the token, invalidates the old link, requires current form
  version and a five-minute interval, and records the attributed request. The
  internal outbox worker processes it; there is no public resend endpoint.
- Review/reject/reopen/security access keep the existing authenticated NMVO and
  CSRF controls. A reopen does not undo NMVS creation or restore erased secrets.
- Receipt payloads and the core security question/answer are encrypted with a
  dedicated internal key. Connect never receives that key. Unconfirmed receipt
  data expires within seven days; confirmed receipt data is removed after its
  committed transfer to the review record. Core security data is removed upon
  rejection, manual NMVS recording or expiry. The worker purges expired values.
- Run cleanup independently of mail using `internal_worker --purge-only`. Purging
  active fields does not erase historical backups or copies held by Tally; their
  retention needs separate handling.
- The mail worker claims durably before network I/O. Uncertain delivery/sending
  states require explicit review/resend rather than automatic duplicate emails.

## Entry points and configuration

Public package: `scripts/package_connect.py OUTPUT.zip`,
`deploy/connect/README.md`, `config/connect.env.example`.
The entry point is `app.connect.gateway:from_environment` using `.env.connect`.

Private API: `app.registration.internal_gateway:from_environment`, using guarded
core database sessions and internal `.env` settings from
`config/registration-internal.env.example`. Apply migration
`0041_registration_receipts` to the existing `smvs_operations` schema.
No separate public database is required. `REGISTRATION_DELIVERY_MODE=direct`
selects the direct portal UI and local resend; the legacy pull worker must not
run for direct receipts. Keep the public Connect config separate from core config.

Private worker: `python -m app.registration.internal_worker --watch`.
For cleanup without mail add `--purge-only`. Supervise API/mail/cleanup processes,
bound logs, restrict ingress and validate private certificate identity/CA. Do not
accept plaintext internal HTTP or disable TLS verification for sensitive answers.

## Validation and activation status

The full test suite passed **458 tests** on 2026-11-10. Direct-pipeline tests cover
atomic commit/rollback, replay after response loss, signature/bearer and actual
source-IP checks, fixed routes, expiry/resend, state/audit updates, no-pull UI,
a public distribution without core/SQLAlchemy modules, and targeted mail isolation.

The restricted TLS-only MySQL runtime account and all 58 tables are deployed on
primary 10.100.36.111. Operations and Connect processes, private CA-verified TLS,
source restrictions and public NGINX/Apache boundaries are active. The synthetic
public webhook/replay produced one CRM workflow record; one real SendGrid mail
was accepted and confirmed by the user. Internally verified Needs review,
email_confirmed audit event, receipt-payload erasure and one-time-token erasure.

### Cutover from direct Tally/Airtable integration

The user clarified that Tally is directly connected to Airtable; mail may be
sent by an Airtable automation/script. Make involvement is unconfirmed. Do not
assume that disabling a Make scenario stops the actual legacy producer.

1. Disable the Tally-to-Airtable integration and confirm this has been saved.
   Keep the signed Connect webhook active with the configured signing secret.
2. Preserve the old PHP confirmation endpoint and Airtable token records for
   outstanding previously sent links. Do not redirect those token links to Connect.
3. Inspect the internal pending mail queue before enabling the Operations worker.
   On 2026-11-10 it contained no queued mail, only the confirmed synthetic test.
4. Enable exactly one internal mail/cleanup worker and stop the separate purge-only
   worker; automatic startup must match the chosen active worker.
5. Submit a clearly labelled test through the actual Tally form using the test
   recipient. Verify one webhook receipt, one mail, explicit email confirmation,
   Needs review and provisional CRM links. Do not create that test in NMVS.
6. Document completed cutover. Use Operations for new registrations; retain the
   old confirmation service until legacy pending links are reconciled/expired.

On 2026-11-10 the user confirmed that the Airtable integration is disabled and
the Connect webhook remains active. The mail queue was empty at cutover.
registration-mail is now supervised/autostarted; registration-cleanup is stopped
and no longer autostarts because the mail worker also performs cleanup.
The real-form smoke test passed on 2026-11-10 after correcting layout IDs to
actual webhook question IDs. Tally registration ID 2 was received with linked
CRM end-user/contact, one automatically accepted SendGrid mail, explicit user
confirmation, Needs review and an email_confirmed audit event. The receipt
payload and single-use token were erased. The first invalid test had ten GLN
digits; production validation remains thirteen digits. Tally should gain matching
front-end validation so invalid GLNs are rejected before submission.

## Primary references

- https://tally.so/help/webhooks
- https://www.twilio.com/docs/sendgrid/api-reference/mail-send/mail-send
- https://uvicorn.dev/deployment/

### Administrator erasure — 2026-11-10

Direct-mode registration details expose an administrator-only permanent deletion
form with explicit confirmation and optimistic version checking. Optional atomic
CRM deletion removes the linked provisional End User/contact only if unshared.
Pending mail is cancelled; an in-flight `sending` claim blocks deletion. Receipt
payload and token fields are cleared; `mail_status=deleted` is an acknowledged
technical tombstone. `sync_receipt` skips tombstones, including on webhook replay.
Workflow events and the registration row are physically deleted. A separate
`crm_deletion_events` table records only operator ID, UTC time and record type/ID,
without copying erased names, addresses, notes or security answers. Legacy buffered
mode refuses this action because deleting only the core copy would be incomplete.
Regression checks cover role enforcement, confirmation, stale forms, shared-contact
protection, in-flight mail, workflow-only erasure and signed replay after erasure.
