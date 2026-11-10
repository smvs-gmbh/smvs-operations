# Internal portal access

The internal pilot supports **Administrator** and **NMVO User**. An account can
hold both roles. Administrators manage users, Imports and Intelligence. NMVO
Users access the operational and CRM views, including internal MAH report drafts.
The server checks roles for direct links, downloads and form submissions. External
MAH access requires separate report release and SAI holder scoping.

## Local pilot

1. Install the project requirements and migrate the configured local database
   with `.venv/bin/alembic upgrade head`.
2. Choose one address for the pilot. For example, use `http://localhost:8011`.
   WebAuthn credentials are bound to the relying party. Open the configured
   address in a passkey-capable browser.
3. Create the first internal administrator from the trusted server console.

   ```sh
   PORTAL_AUTH_ORIGIN=http://localhost:8011 .venv/bin/python -m app.domain.auth admin@example.test
   ```

   Use the actual internal email when setting up a real account. The command
   prints a single-use enrolment URL. Treat it as a credential and share it
   only through a trusted channel. Before the first passkey is registered, the
   same command can replace the initial invitation for that email.
4. Start the protected pilot instance.

   ```sh
   PORTAL_AUTH_ENABLED=true PORTAL_AUTH_ORIGIN=http://localhost:8011 \
     .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8011
   ```

5. Open the invitation and register a passkey. Under **Users**, create
   invitations for additional users and assign roles. Prefer two independent
   passkeys for administrator accounts. **Add passkey** is available for five
   minutes after sign-in.

The default development preview is available on loopback only. Before using
the protected mode with real users, shut down any preview that shares the same
database. Deploy protected instances on the intended HTTPS hostname and
configure edge rate limits for the passkey endpoints.

## Sessions and recovery

Invitations expire after 24 hours and are consumed after successful registration.
Challenges are short-lived and tied to the initiating browser. Sessions expire
after eight hours. Disabling an account or changing its roles revokes its
outstanding tokens and sessions.

Recovery codes, supervised account recovery and the authentication audit log
remain planned. Maintain a second internal administrator and enrol spare
passkeys during the pilot. Twilio SMS and MAH accounts remain separate follow-up work. Personal CRM
column preferences and views have since been implemented.

## Public production deployment

The target is `https://operations.smvs-gmbh.ch` on Infomaniak Jelastic with DNS
at Cyon and public passkey access. The current pilot is not a production security
approval. See [Security Review 2026-11-09](SECURITY-REVIEW-2026-11-09.md) for
confirmed gaps, separate local/hosting evidence and the required release checks.
In particular, authenticated identity is not yet propagated into local Resolve
Audit events, and production DB TLS identity verification needs implementation.
