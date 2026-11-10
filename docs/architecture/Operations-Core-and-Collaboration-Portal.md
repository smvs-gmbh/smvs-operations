# Private Operations core and public collaboration portal

Date: 2026-11-09. Status: recommended architecture proposal following the product
owner's suggestion; not deployed. The security hardening measures from the
[security review](../technical/SECURITY-REVIEW-2026-11-09.md) remain required.
This proposal supersedes the public-core assumption only after acceptance and
implementation; the existing OpenVPN configuration has not been inspected.

## Deployment boundary

- **Operations core:** NMVO/Administrator workspace, CRM, Exceptions, imports,
  Intelligence and workflows. Accessible only through the existing OpenVPN plus
  application passkeys over HTTPS. Enforce the network boundary for all routes,
  static/evidence downloads, alternate provider hostnames, IPv4 and IPv6.
- **Collaboration portal:** separate public application with an explicit small
  route set for assigned Shared Investigations. Prefer a separate deployment and
  service account; sharing reusable source modules does not require exposing the
  core application. A different menu or proxy path in front of the full core is
  not this isolation boundary.
- **Core MySQL:** private; no public-portal credential or route grants access.
- **Collaboration store:** separate database and database user, preferably on a
  separate node/network segment. It contains only deliberately released case
  snapshots, invitations, participant contributions and permitted attachments.
  No copies of the CRM, exception catalogue or original NMVS report collection.
- **Origins:** retain `operations.smvs-gmbh.ch` for the private core; choose a
  separate public hostname for collaboration. Host-only session cookies,
  separate secrets and narrowly scoped credentials. Never share parent-domain
  cookies, NMVS credentials or core encryption keys with the public application.

## Exchange pattern

An internal integration worker initiates outbound authenticated HTTPS exchanges
with the public application's bounded exchange API. The public application does
not need inbound access to the private core.

1. The NMVO deliberately releases an investigation snapshot to identified
   participants. Publication is an audited domain operation with an explicit
   field/attachment allowlist and revision, not a serialised ORM object.
2. An internal outbox publishes snapshots idempotently. Pending delivery,
   acknowledged delivery and failure remain distinguishable.
3. Participants add findings, answers and a case-specific readiness-for-closure
   response to the public store. End-user statements remain distinguishable from
   NMVO assessments and observed source evidence.
4. The internal worker retrieves contributions. It treats even authenticated
   public-service output as untrusted input: validate schemas, sizes, object
   mapping and revisions, deduplicate IDs and reject unsupported operations.
   A contribution can never issue arbitrary core commands, change permissions or
   resolve an Alert by itself.
5. The NMVO reviews contributions and retains final decision ownership. The core
   publishes the permitted outcome back to the collaboration portal.

The worker uses restricted public-service credentials; the public service never
receives credentials for the core. Retry/reconciliation is explicit. Compromise
of the public portal must not provide a generic SQL/API tunnel into Operations.
It could still expose released cases, forge contributions or interrupt service;
data minimisation, provenance, monitoring and operator review remain necessary.

## Participant access and released data

Use the existing Shared Investigation proposal: a short-lived, single-use Magic
Link can establish an expiring, revocable case-/organisation-/contact-scoped
session. Recheck permissions on every request and attachment download. Links do
not establish a person's identity merely because they were emailed; forwarded
links and shared mailboxes require an explicit verification/attribution policy.
Participants do not receive internal portal accounts or NMVO permissions.

Release only what the participant needs: relevant pack/product context, selected
questions, shared evidence, contributions and status. Keep complete serial numbers
masked/omitted by default; release them only where required and explicitly
permitted. Raw audit reports, unrelated packs, internal notes, risk indicators,
CRM contact lists and contracts remain private. Revoke access and expire copies
under the case retention policy. Public compromise remains a risk to whatever is
intentionally released.

## Tally registration is a separate use case

The proposed public collaboration application is initially for RCA only. A Tally
registration webhook is not automatically part of its route set. It needs a
separate narrow public intake endpoint/service and staging store, or a later
explicitly designed intake module. An internal worker can retrieve validated
registrations into the CRM. Security questions/answers remain temporary and
separately encrypted; they are never investigation content. No general CRM route
is exposed to receive a webhook.

## Delivery order and verification

1. Implement the already accepted security hardening for the core; configure and
   verify VPN-only access, HTTPS, passkeys and a private database.
2. Define a versioned Shared Investigation publication/contribution contract and
   participation/revocation rules; minimise data before building the public UI.
3. Implement a separate public portal/store and internal outbox/inbox worker;
   test cross-case and cross-organisation denial, replay, forged contributions,
   expiry, revocation and attachment access.
4. Verify that a public-service identity cannot reach/read the core DB, its
   routes or keys. Test alternate Jelastic hostnames and both IP families.
5. Add the signed, idempotent Tally registration intake as its own bounded flow;
   the NMVO-only registration workflow remains in Operations.

## References

- [Shared Investigation and CRM](Shared-Investigation-and-CRM-Proposal.md)
- [OWASP: least privilege and per-request authorisation](https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html)
- [OWASP: service boundaries and service authentication](https://cheatsheetseries.owasp.org/cheatsheets/Microservices_Security_Cheat_Sheet.html)

## Registration deployment decision — 2026-11-09

SMVS Connect (connect.smvs-gmbh.ch) is the chosen public service name. For
registration, the user selected a stateless public gateway and direct private
API, not a separate public database or public exchange store. The public gateway
forwards only signed submissions and confirmation tokens, over authenticated
verified TLS, to two bounded commands inside Operations. Receipt/outbox and CRM
updates commit atomically in the existing core database before acknowledgement.
SendGrid and temporary security data remain internal. See the current
[registration architecture](../integration/end-user-registration.md).

This decision applies to registration. It does not authorise public CRM access
or automatically select an architecture for future shared-investigation data.
