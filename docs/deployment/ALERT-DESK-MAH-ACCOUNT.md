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
