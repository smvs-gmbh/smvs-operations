# Alert Desk participant sign-in — CHG-029

2026-11-27. Pilot implementation, not an approved QMS baseline. Production stays
outside this deployment. Use the fixed configured public HTTPS origin on TEST;
localhost is permitted only for development. Staff portal passkeys are separate.

## Access flow

The permanent `/alerts` entry shows My cases for an active session and otherwise
an email-first sign-in page. `/alerts/login` always offers passkey or email link.
Only an existing NMVO-invited, sent, non-revoked access grant with current CRM
contact/version/role/organisation/scope is eligible. There is no self-registration
or automatic assignment. A previously expired invitation/session is not itself a
reason to withhold a returning participant's mailbox sign-in. Staff directory and
response-request routing distinguish permanent invitation eligibility from a
browser session: a session expiring no longer requires staff to send another
invitation, nor prevents a targeted findings request. Revocation, changed
contact version, archived organisation/contact, scope change or re-invitation
invalidates the captured authorisation binding. Re-invitation therefore requires
fresh mailbox verification and passkey enrolment for the changed grant.

Email-link requests return the same neutral response for unknown, ineligible,
rate-limited and eligible addresses. Three links per email per fifteen minutes
and an aggregate limit protect mail volume. The API schedules delivery after the
response; no raw link/token is retained in the database, and there is no automatic
retry after uncertain delivery. A process interruption before mail delivery may
require the user to request a new link. Existing durable mail-attempt/outcome
recording still applies when a provider call is made. Do not describe provider
acceptance or a queued callback as proof of inbox delivery.

The link expires after fifteen minutes, is stored only as a hash, is consumed by
a POST after an explicit confirmation, and carries its secret in the fragment.
Opening/scanning the GET does not consume it; the page removes the fragment.
After mailbox proof, multiple approved organisations/roles are shown for explicit
selection; the system never silently chooses one. Scope selection is short-lived
and single-use. Each current assignment is rechecked at consumption.

The same configured SendGrid template ID supplies heading/message/message_text
and links. No new template or key is required. The mail parser recognises
`/alerts/login#…`, as well as invitation/case URLs. Keep the existing TEST two-email
allowlist and sender. No automatic invitations or real messages are part of rollout.

## Passkeys and sessions

Register a discoverable, user-verifying WebAuthn passkey in Account access after
an invitation/code or email-link sign-in. Registration and revocation require a
sign-in within ten minutes. Support up to ten live passkeys for the current
organisation/role; the account page lists registration times and offers revoke.
Passkeys are bound to the configured origin/RP ID and current grant binding, not
the staff portal. Development keys do not carry over to the hosted TEST origin.

Authentication verifies the entered email, credential ownership, current grant,
challenge, origin, RP ID, user verification, user handle and signature counter.
Challenges are hashed, single-use, three-minute browser-bound tokens. Revocation
signs out all sessions for that organisation/role, including the legacy session;
it does not revoke another organisation's passkeys. Lost-key recovery is mailbox
proof for an otherwise current invited grant; it does not grant new permissions.

New sessions are independently revocable, last eight hours, and do not overwrite
other devices' sessions. Store only their hashes. Existing invitation/code sessions
remain accepted until expiry/revocation. Access cookies are HttpOnly, Secure on
HTTPS and SameSite=Lax for direct email/bookmark navigation. Challenge/context
cookies stay Strict. All state-changing public commands require the exact Origin
and bounded JSON; the API remains loopback and bearer-protected. Private/no-store
headers, no-referrer and same-origin scripts/images remain. Passkey sign-in options
do not disclose an email-specific credential list.

Authentication events retain request/delivery, sign-in, registration, failure,
revocation and logout evidence without raw capabilities, codes or private keys.
Case findings/templates/source ownership and NMVO decision authority are unchanged.
System-wide consolidated audit/retention work remains separately open (CHG-003/024).

## Schema and deployment

Revision 0057 adds login tokens, participant sessions, participant passkeys, login
throttles and authentication events. Existing source/CRM/invitation/findings tables
are not rewritten by upgrade. Downgrade refuses to discard populated auth tables.
Take a protected consistent TEST backup; verify source manifest, actual target,
schema, existing row fingerprints and runtime configuration. Commit tested code
before deployment. Preserve TEST sender, template ID/key and the two real contacts.
For code rollback retain additive tables/auth events and subsequent participant data.

## Technical checks and owner acceptance

Supporting local suite: 621 passed, existing Starlette/httpx deprecation warning.
Cryptographic unit tests use actual signed registration/assertion responses,
including negative email/origin/UV/handle/counter/grant-binding cases. Test magic
expiry/replay, neutral errors/rate limits, changed membership, multiple scopes,
fresh-proof management and revocation. Verify schema/model parity and retained
evidence through migration tests.

Chrome with an isolated virtual authenticator completed the real JS mailbox-link
confirmation, passkey registration, sign-out, passkey sign-in and new-tab session
reuse against synthetic isolated data. No external emails were sent. This proves
the browser protocol path, not the owner's device/inbox acceptance.

On hosted TEST, each owner/tester should:

1. Open `/alerts/login`, enter the approved CRM email and request a sign-in link.
2. Verify the single button opens the configured TEST `/alerts/login#…`; confirm
   access. Inspect delivery outcomes privately without publishing token content.
3. In Account access register a real-device passkey, then sign out and sign in
   with the same email/passkey. Open a new tab and check My cases.
4. Use another browser/profile for mailbox recovery; verify organisation/role
   isolation and expired/reused link refusal. Register TEST keys separately from
   local/staff keys. Test revocation with a recoverable test passkey.
5. Confirm unknown/uninvited addresses receive a neutral screen and no email,
   role/Location changes revoke access, and existing findings remain.

Record acceptance separately; do not include invitation/link/credential secrets in
screenshots, Git or public tickets. Email languages remain deferred.


## Installed technical evidence — 2026-11-27

TEST upgraded to 0057 with existing data/configuration preserved. Hosted targeted
checks: 44 passed. Actual TEST-origin WebAuthn and Magic Link checks on native
MySQL succeeded in an isolated transaction; all writes were rolled back and all
79 tables matched their originals. Local full suite: 621 passed. Existing
Starlette/httpx deprecation remains. No external emails were sent by these checks.
Final source archive is reconciled to local/remote Git HEAD, with protected remote
manifest/sync evidence; owner real-device/inbox acceptance remains separate.
