# MAH task visibility and My account — CHG-030

2026-11-27. Local development and synthetic TEST only. Pilot evidence, not an
approved QMS baseline. URS-128 / FRS-EXC-017. Schema remains 0057_participant_login.

## Scope

Routine MAH codes: A2/A3/A52. A7/A24/A68 require an explicit same-MAH,
current-source request or an attributed current-source own-side finding. Same
policy in all views/search, direct URLs, template endpoints, writes and bulk.
Preserve namespace, unique product/GLN ownership and End User Location rules.
A staff request can establish involvement after product/scope checks. Unknown
codes remain unavailable. An EU source label is not a trusted Hub identity.
No new own-Hub mapping or unsolicited notifications are introduced.
Policy reference: [EMVO-00306 v2, Best Practice on Alert Handling, pp. 15–16](https://emvo-medicines.eu/wp-content/uploads/Best-Practice-on-Alert-Handling.docx.pdf).
The local task-allocation policy is owner-approved; it is not an assertion that
all these alert types necessarily imply MAH fault.

This deliberately supersedes CHG-028's default informational A24 visibility.
Existing source and findings remain retained. A hidden case cannot self-authorise
through a crafted own_cause submission; a request may first establish access.
Current-source own-side evidence continues even after a later progress entry.

My account provides read-only current email/organisation/role, compact passkey
list, Add passkey, confirmed secondary Revoke and separate Sign out. Cases are
the default after invitation/Magic Link/passkey sign-in. Optional setup offers
Later; successful enrolment returns with confirmation. Fresh proof is enforced
on the server, with a contextual prompt and fixed account return, not a permanent
technical warning. CRM still owns contact changes.

## Verification and rollout boundary

Local suite: 624 passed (one existing Starlette TestClient deprecation warning).
Changed Python modules pass Ruff. Browser and hosted results are recorded below
once executed. No schema or data migration. TEST configuration and both approved
recipient addresses remain unchanged, including existing real passkeys/sessions.
Deployment must use committed source, protected native TEST backup and complete
archive hash verification. Restart all four TEST processes and reconcile source
SHA with local/remote Git. Tests capture mail only; no actual email is requested.

## Rollback

Switch TEST current symlink back to its recorded previous committed release and
restart its four supervisor roles. Schema 0057 and runtime configuration stay as
is. Preserve new activity, credentials, findings and delivery receipts; do not
restore an older database over subsequent user work. Protected preflight SQL/gzip
and per-table fingerprints are retained privately for recovery/reconciliation.
Production/VerifyIt are outside this change.


Local browser verification (Chrome, virtual CTAP2 authenticator): actual Magic
Link confirmation, passkey enrolment and sign-in, new-tab session persistence,
conditional MAH case exclusion, optional Later, return with success notice,
contextual fresh-proof prompt and account return all passed. Desktop/mobile
screens inspected; 390px viewport has no horizontal document overflow. Mail was
captured in a private local fixture, never delivered externally.


## Executed TEST checks (2026-11-27)

Tested application source: `0c9910fe1b873265c4ac3476706a009f8091354e`;
previous TEST release `6587f3358ed33da9747794ac876184df4752eca8`.
All 666 candidate file hashes verified. Protected SQL/gzip snapshot of all
79 tables read back successfully before switching the committed release.
All four supervisor services restarted. All 79 table fingerprints, existing
passkeys/sessions/findings and both real contact addresses unchanged after restart;
runtime configuration byte-identical, existing SendGrid template retained.

- Native MySQL: actual TEST-origin Magic Link single-use, WebAuthn registration,
  signed assertion, logout/sign-in/revocation, read-only My account identity and
  current-source MAH request guards passed. Test transactions rolled back; all
  79 table fingerprints restored. Native list compilation emitted SQLAlchemy
  correlated-query cartesian-product warnings; scope assertions still passed.
- Hosted targeted regression: 46 passed, one existing Starlette TestClient
  deprecation warning. Initial test-runner shell lacked fixture DB settings
  (7 configuration failures, 39 passes); rerun with isolated synthetic fixture
  settings, without loading the runtime database credentials, passed all 46.
- Local: 624 full-suite tests; final focused 19 pass after account button styling;
  Ruff and diff checks passed. Chrome desktop/mobile flow and actual virtual
  authenticator checks passed, including contextual reauthentication and return.
- Public HTTPS: sign-in, unauthenticated account redirect, current CSS/JS,
  no-store/no-referrer, private staff route refusal and existing VerifyIt root
  availability passed. No external messages sent by these checks or rollout.

Supporting machine-readable results are in
[the non-secret evidence summary](../validation/evidence/2026-11-27-mah-account.json).
Protected backup/fingerprint/native/final process records remain in TEST's
owner-only `evidence/mah-account-*` and `backups/before-mah-account-*` paths.
The final documentation-only commit is synchronised to origin and installed as
the TEST source archive with all four process working directories checked against
that SHA. No schema change, fixture reset, contact rewrite or PROD operation.

Owner acceptance: use the added CHG-030 section of the
[TEST instructions](../validation/ALERT-DESK-TEST-ANLEITUNG.md). Test with an
existing passkey; no re-enrolment is required by this deployment. The two approved
real addresses remain available for future invitations/sign-in requests.
