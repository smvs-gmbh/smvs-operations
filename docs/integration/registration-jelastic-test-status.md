# Registration intake — Jelastic test deployment status

Checked 2026-11-09. Public activation remains pending.

## Target and installed source

- Environment hostname: env-1381574.jcloud.ik-server.com
- Intended public hostname chosen by the user: operations.smvs-gmbh.ch
- Public node IP supplied by the user: 84.16.77.147
- Apache node ID: 221302
- SSH gateway: gate.jpc.infomaniak.com:3022, user 221302-9004
- Isolated installation: /var/lib/jelastic/vcs/registration-intake-test
- OS account: apache, UID 700
- Python: 3.15.2 (the provisioned template's interpreter)

The narrow Apache-Python source archive was uploaded and extracted into a private
mode-700 directory outside Apache's DocumentRoot (/var/www/webroot). A dedicated
virtual environment was created, dependencies installed from binary wheels, and
an in-process smoke test was run on the actual node using a disposable synthetic
SQLite database. No production configuration file, key, SendGrid credential or
Operations/NMVS database credential has been uploaded. No API/mail worker has
been left running. Apache configuration was not changed or restarted.

The remote smoke test passed: confirmation page and assets, missing core routes,
unauthenticated exchange rejection, unsigned webhook rejection, signed webhook
acceptance and replay producing exactly one record. It sent no email. This does
not establish production MySQL/TLS, public proxy routing or process supervision.

## Public connectivity observed

The user-created CNAME resolves operations.smvs-gmbh.ch to the environment hostname,
which resolves via the provider's shared entry points 185.74.71.125/126, rather
than directly to the supplied node IP. At the time of checking:

- HTTP on the domain returned 500 from openresty.
- HTTPS certificate verification failed due to a hostname mismatch.
- HTTP on the supplied node IP returned the Apache default page.
- Direct HTTPS on the supplied node IP refused connections.

Choose and finish one routing/TLS arrangement before public activation: shared
Jelastic ingress with supported custom-domain/TLS configuration, or direct node/
nginx ingress using the public IP and corresponding DNS/TLS setup. Do not infer
that a CNAME alone binds a virtual host or provisions a matching certificate.

## Remaining prerequisites

1. Confirm separate smvs_registration MySQL database, restricted account and CA-
   verified TLS access from this node. The public service must not use the core DB.
2. Complete the hostname binding, proxy route and valid matching HTTPS certificate.
3. Configure dedicated registration secrets, the approved SendGrid sender/template
   and key in a private environment file outside the document root.
4. Inspect actual startup facilities: Supervisor was not present in PATH. Use a
   supported durable supervisor and configure purge; do not rely on an SSH shell.
5. Configure and validate only the dedicated Apache proxy/vhost, body/rate limits,
   sensitive-log exclusions and default-denied exchange network route.
6. Perform external synthetic acceptance before enabling real Tally delivery or
   changing existing PHP/Make/Airtable flows.

The hostname does not authorise exposing the Operations core; only the isolated
registration intake is intended for this public environment.

## Confirmed topology and public name — 2026-11-09

The chosen public service name is **SMVS Connect**, with canonical hostname
`connect.smvs-gmbh.ch`. The authoritative Cyon A record was verified as
`195.15.232.138`. NGINX node 221301 has private IP `10.100.37.96` and public IP
`195.15.232.138`. Apache-Python node 221302 has private IP `10.100.37.97`; the user
removed its public IP. The previously supplied `128.65.197.250` belonged to Apache,
not NGINX. Earlier address observations above are historical, not the active target.

HTTP for Connect reaches NGINX and forwards to Apache (200). TCP 443 on the NGINX
public IP still refused connections at the latest check; a matching certificate
and active HTTPS listener have not yet been verified. Configure the NGINX
Let's Encrypt add-on for `connect.smvs-gmbh.ch`. Reserve Operations naming for the
internal core; no public portal exposure is authorised.

The deployment architecture was clarified by the user: the public service is to
forward tightly scoped authenticated requests to an internal API over private
connectivity. It should not have its own public-side registration database or
core DB credentials. The uploaded code still implements the original buffered
intake design; it must be adapted before activation. The separate-MySQL
prerequisite in earlier sections belongs to that superseded design.

## HTTPS acceptance — 2026-11-09

After the user corrected the Let's Encrypt External Domain to
`connect.smvs-gmbh.ch`, certificate verification succeeded both through normal DNS
and directly against `195.15.232.138` using the Connect hostname as SNI. TLS 1.3
was negotiated; the matching certificate was issued by Let's Encrypt YR2 and
expires 2027-02-07 14:41 UTC. HTTPS GET / returns 200. HTTP still returns 200 rather
than redirecting to HTTPS; an HTTP-to-HTTPS redirect remains to be configured while
preserving the ACME validation path. Registration service activation and private
internal API forwarding remain pending.

## HTTP redirect applied — 2026-11-09

Connected to NGINX node 221301 using the existing SSH key and gateway account
221301-9004. The nginx OS user belongs to ssh-access; its ACL permits in-place
writes to nginx-jelastic.conf but not general directory writes under /etc/nginx.
No permissions or ownership were changed. The original configuration was backed
up at /tmp/smvs-nginx-before-https-yx21ux5w/nginx-jelastic.conf (mode 600).

Added a return-308 rule at the beginning of the existing HTTP location /, excluding
URIs starting /.well-known/acme-challenge/. Existing proxy and ACME handling remain
in place. sudo nginx -t succeeded; an authorised nginx service reload succeeded.
External checks confirmed HTTP / and /confirm?test=redirect redirect to the exact
Connect HTTPS URL with path/query preserved; HTTPS / returns 200 with certificate
verification enabled. A nonexistent ACME challenge path returned 403 without a
redirect; this checks the redirect exception only, not actual certificate renewal.
Recheck the rule after Jelastic topology/add-on changes, which may rebuild managed
configuration. The registration application is still not publicly activated.

## Direct private API implementation — 2026-11-09

The stateless Connect implementation is now in app/connect. Its source bundle
excludes all database/core models, crypto/mail credentials and legacy exchange
routes. It was staged on public Apache node 221302 at
/var/lib/jelastic/vcs/smvs-connect-direct with its own minimal virtual environment.
Archive hashes and a synthetic ASGI/proxy test passed on the actual Python 3.15
node. No upstream request, new real mail or public application activation occurred.

The private target was identified through the SSH gateway as Apache node 207849,
10.100.32.195, environment env-9657618.jcloud.ik-server.com. Port 80 is reachable
from Connect; port 443 is not active. Existing remote smvs-operations is the older
foundation commit b3a7d64 with a local settings modification and no DB_* entries in
its .env. It was inspected only, not overwritten. The active development database
is local Docker on the Mac, forwarded on port 55000, not configured on this node.
The target Jelastic MySQL instance/data migration choice was requested from the
user and remains pending. Do not copy the remote legacy NMVS configuration to
Connect or silently replace that old project.

Private API/worker code is implemented locally: only two authenticated commands,
atomic receipt/CRM writes and confirmation, internal SendGrid outbox/cleanup,
local attributed resend and no-pull portal mode. Migration 0041 adds only the
internal registration_receipts table; it was applied locally, not remotely. The
full suite passed 448 tests. Private TLS CA/listener, firewall/process supervision,
current backend deployment and actual synthetic Tally cutover remain pending.

## MySQL target selected — 2026-11-09

The user selected env-5568720.jcloud.ik-server.com, primary MySQL node 220544 at
10.100.36.111 (secondary 220545 at 10.100.36.112, ProxySQL nodes 220547/220548).
The user authorises replacing the old Operations data. This is not permission to
drop other application databases on this shared cluster. Inspect actual schemas
with an authorised SQL admin before replacing only smvs_operations.

SSH access to the primary succeeds as OS user mysql. A passwordless SQL connection
is refused; no SQL administrative credentials are currently configured for the
deployment. A mode-600 local .env.mysql-bootstrap file was created with an empty
MYSQL_ADMIN_PASSWORD field; the user was asked to populate it locally, never in
chat. No database was deleted and no SQL user was created in this step.

Planned runtime principal: smvs_ops_app restricted to source 10.100.32.195 and
SELECT/INSERT/UPDATE/DELETE on smvs_operations only, with REQUIRE SSL. Keep schema
installation/migration privileges separate from the runtime account. Do not give
Connect a DB account. Inspect existing schema/users before provisioning.

Public CA/server certificates are readable on the DB node. The installed server
certificate is MySQL auto-generated, valid to 2036-10-24, with no SAN and a generic
MySQL Server CN. The intended verified DB TLS setup must account for that identity
(non-matching private-IP hostname); do not silently disable server verification or
replace global cluster certificates used by other applications without review.

## MySQL runtime account and data migration completed — 2026-11-09

SQL administration succeeded using the user's locally supplied bootstrap
credential over SSH and a temporary mode-600 client option file. No credential
was placed in command arguments or printed. The target smvs_operations schema
existed but had zero tables, so no DROP DATABASE/data deletion was needed. Other
schemas (including smvs, translation and verifyit) were not modified.

Created smvs_ops_app@10.100.32.195 with REQUIRE SSL and SELECT, INSERT, UPDATE,
DELETE on smvs_operations.* only. It has no global/DDL/user-management privileges.
Its generated secret is held only in private local .env.mysql-runtime and the
private runtime environment on internal node 207849. No DB secret went to Connect.

A single-transaction local Docker snapshot was transferred via SSH/SFTP and
imported into the verified empty target. All 58 tables and every table's exact
row count matched; schema revision is 0041_registration_receipts. SHA-256 checking
of all stored artifact contents reported zero failures. The temporary server
SQL export was removed after successful validation. The local Docker source was
not changed. This is a point-in-time copy, not ongoing synchronisation; do not
overwrite the cloud database with later development snapshots after registrations
start arriving. The import helper refuses a non-empty target.

Current code was staged separately at
/var/lib/jelastic/vcs/smvs-operations-current on internal node 207849 with its own
virtual environment and owner-only .env; the old webroot checkout is preserved.
Verified real runtime connection: database smvs_operations, current user
smvs_ops_app@10.100.32.195, TLS_AES_128_GCM_SHA256, all 58 tables visible. Other
application schemas are not visible. An explicit plaintext connection was
rejected by MySQL. No portal/API listener was started by the database migration.

DB TLS uses the trusted existing MySQL CA plus an exact SHA-256 server-certificate
pin, since the server's autogenerated certificate has no host SAN. Its legacy
format also lacks AKI; Python 3.13+ rejects this with default VERIFY_X509_STRICT.
The opt-in DB_SSL_LEGACY_CERTIFICATE=true is allowed only with both a trusted CA
and exact pin, retaining CERT_REQUIRED/signature/expiry checks while permitting
the older X.509 extension format. Ordinary CA/hostname TLS remains strict by
default. No global MySQL TLS/certificate configuration was changed. Certificate
replacement/primary-node change requires reviewing the configured CA/pin.

Settings: DB_SSL_CA points to the private runtime certs/mysql-ca.pem;
DB_SSL_SERVER_CERT_SHA256 identifies the trusted primary's exact leaf certificate.
CA/certificate material was retrieved over the authenticated SSH connection;
no server private key was copied. Full local validation: 454 tests passed, with
real restricted-account/TLS/plaintext-rejection checks on the internal node.

Still pending: private registration API TLS/listener and process supervision,
public Connect application activation, actual Tally signing-secret configuration
and controlled synthetic acceptance/cutover of the old registration flow.


## VPN portal DNS certificate — 2026-11-09

The user selected Let's Encrypt DNS-01 for operations.smvs-gmbh.ch.
Cyon TXT publication was verified and Certbot successfully issued the certificate
on internal node 207849, valid until 2027-02-07. The key remains on that node.
Certificate: /var/lib/jelastic/vcs/smvs-operations-current/acme/config/live/operations.smvs-gmbh.ch/fullchain.pem
Key: /var/lib/jelastic/vcs/smvs-operations-current/acme/config/live/operations.smvs-gmbh.ch/privkey.pem

Issuance used manual DNS validation: automatic renewal is NOT configured.
Configure a suitably restricted DNS authentication hook/delegation before relying
on automated renewal, or repeat the manual validation before expiry.
Cyon's editor accepted the full owner name with trailing dot and quoted TXT value.
The completed challenge TXT can now be removed.

At issuance, public DNS for operations.smvs-gmbh.ch still returned 128.65.197.250.
The intended VPN portal address is 10.100.32.195; Connect DNS is unchanged.
Certificate issuance does not activate HTTPS or expose the portal. Private Apache
TLS configuration, VPN access checks and hostname-specific passkey enrolment
remain pending. The temporary SSH tunnel at localhost:8020 remains the pilot path.


### Internal HTTPS prepared — 2026-11-09

Enabled Apache mod_ssl on node 207849 and bound TLS only to 10.100.32.195:443.
The virtual host uses the new Let's Encrypt certificate, TLS 1.2/1.3, fixed
loopback proxy target and exact portal Host validation. Access logging is disabled
for this virtual host to avoid recording invitation/token URLs.
Initial source allow-list permits only the server itself; the user's OpenVPN
client subnet / VPN server private address is requested before access is opened.
Do not replace this restriction with all private networks.
Original Apache configs are backed up under the private runtime backups/https-initial.

A separate supervised operations-portal-https process listens on 127.0.0.1:8015
with canonical PORTAL_AUTH_ORIGIN=https://operations.smvs-gmbh.ch. It trusts proxy
headers only from 127.0.0.1. The existing localhost:8020 SSH pilot remains unchanged.
Apache config check and reload succeeded. Server-side curl with standard CA
validation and explicit DNS resolution: login 200, certificate verification 0;
unauthenticated CRM 303 to the correct HTTPS login; original SSH pilot login 200.
No login/passkey bypass was introduced. Passkeys registered for localhost require
separate enrolment for the production hostname. Automated certificate renewal
remains pending.


### Narrow VPN source enabled — 2026-11-09

The user supplied routed networks (169.254/16, 192.168/16, 10.101/16,
172.16/12 and 10/8), not a confirmed client source pool. These broad ranges
were not added to the portal allow-list. The Mac's route to 10.100.32.195 uses
utun4 via OpenVPN; its tunnel address was 172.27.224.69/21. A controlled HTTPS
probe was initially denied and the Apache error recorded source 10.101.15.115,
indicating that the server sees a different source address across the VPN path.
No RemoteIP header-based rewriting is configured.

Added only observed source 10.101.15.115/32 alongside the server's own addresses.
Do not assume this is the permanent VPN server address without confirmation;
a VPN source change requires reviewing/updating the narrow allow-list.
Apache config check and reload passed. Direct curl from the VPN-connected Mac
with explicit DNS resolution and standard certificate validation: login 200,
certificate verification 0, unauthenticated CRM 303 to HTTPS login, wrong Host 403.
Local DNS still cached the old public A address at this check, so the explicit
resolution test does not establish that ordinary browser DNS has refreshed.
Production-hostname passkey enrolment and automatic renewal remain pending.


### Production hostname enrolment link issued — 2026-11-09

At the existing administrator's explicit request, a single-use, 30-minute invite
was issued from the authenticated server console for the existing active
reinhold.sojer@smvo.ch administrator account. Existing roles, passkeys and other
accounts were preserved. The link uses the canonical HTTPS hostname and a URL
fragment; its secret is intentionally not recorded in this document. The user
must complete the WebAuthn registration ceremony. Server I/O/SSH response was
slow during issuance; commit succeeded before the link was returned.


## Connect activation and synthetic cloud acceptance — 2026-11-10

Current operational status supersedes historical pending-deployment notes above.
The user confirmed successful administrator passkey enrolment for the production
portal hostname on 2026-11-09. The internal portal, scheduler, registration API
and cleanup processes remain supervised. Automatic registration mail remains
STOPPED: the user confirmed the old Make/Airtable mail flow is still active.

Activated the minimal stateless Connect package on node 221302, loopback port
8013, with an owner-only runtime environment and the registration API CA only.
No core DB credentials, encryption key or SendGrid key were placed on Connect.
Source manifest hashes were verified. Supervisor uses a private Unix socket and
rotated logs; user crontab includes startup and a two-minute process watchdog.
crond is active. Apache forwards only from NGINX node 10.100.37.96 / loopback,
with filesystem access denied, a fixed loopback proxy and no access log.

NGINX has fixed upstream 10.100.37.97:80, exact Connect hostname and route allow-
list, request body/time limits, webhook/confirmation rate zones, TLS 1.2/1.3 and
HSTS without includeSubDomains. It no longer selects upstreams using client
cookies or trusts forwarded source headers from arbitrary private nodes. HTTP
and HTTPS access logs are off. Existing certificate paths and HTTP ACME challenge
forwarding are preserved. Original Apache/NGINX configs are privately backed up.

Public checks: home/confirm/assets 200; CRM/Exceptions/docs/private-API routes
404; unsigned webhook 401; foreign confirmation origin 403; oversized webhook
413; wrong Host 421; HTTP redirect 308; Cache-Control no-store; no routing cookie.
Configuration syntax checks and service reloads passed.

Initially Connect-to-private-API TCP failed with No route to host. User added
TCP 8443 from 10.100.37.97/32 to internal node 207849's firewall. Subsequently
verified CA-based HTTPS to IP SAN 10.100.32.195: authenticated invalid confirmation
returns 400 and missing bearer returns 401. Application actual-source IP check
continues to permit only Connect, independently of the bearer/signature checks.

Synthetic event smvs-connect-acceptance-20261110 and submission
smvs-connect-submission-20261110 were POSTed to the public signed webhook. Both
initial submission and identical replay returned 200 / received:true. Internal
verification found exactly one receipt and one EndUserRegistration (ID 1), with
provisional CRM links and awaiting_email state. Name: SMVS Connect Acceptance
Test 2026-11-10. Only fake security data was used; no real NMVS organisation is
to be created. Neither request went through the actual Tally form/old Make flow.

Added --receipt-id for a one-off internal mail run. A regression test with two
queued registrations verifies only the selected receipt is sent, unknown IDs
send none and replay does not resend. Full suite 456 passed; Ruff and whitespace
checks passed. After explicit recipient/name checks, exactly one real SendGrid
confirmation was accepted for reinhold.sojer@smvo.ch. Workflow remains awaiting
email until the user completes the public confirmation page. No token, security
answer or API credential is recorded here. User confirmation requested.

Authoritative DNS now returns 10.100.32.195 for operations.smvs-gmbh.ch, but the
Mac temporary hosts entry remains and needs an administrator-assisted removal.
Automatic DNS-01 renewal remains pending; portal certificate expires 2027-02-07.


### Cloud confirmation accepted — 2026-11-10

User confirmed receipt and completed the public confirmation page. Internal
verification passed: EndUserRegistration ID 1 is needs_review with confirmed_at
set, linked CRM end-user/contact, and received/email_confirmed workflow events.
RegistrationReceipt payload_ciphertext, token_ciphertext and token_digest are
all erased. This does not imply that the separate encrypted temporary NMVS
question/answer has already been erased: that follows the documented review /
manual NMVS creation / rejection / seven-day expiry lifecycle.

Synthetic cloud transport, atomic persistence, replay safety, one-recipient
SendGrid delivery and public confirmation are now accepted. A real Tally
submission and the deliberate Make/Airtable/PHP cutover remain separate steps.
Automatic registration mail remains stopped; no NMVS organisation was created.


### Legacy sender clarification and cutover preparation — 2026-11-10

The user clarified that Tally is directly linked to Airtable and mail may come
from an Airtable script/automation, not Make. Historical Make references above
are assumptions, not verified implementation details. The user intends to use
Operations exclusively for new registrations and can remove the Airtable link.
Requested confirmation of that saved removal before enabling automatic mail.
Retain old PHP/token storage for outstanding previously sent links.

Queue check: one accepted/confirmed synthetic receipt, one needs_review workflow
record, zero non-synthetic source submissions and no queued mail. A real Tally
submission is still required for the form-source smoke test.


### New-registration producer cutover — 2026-11-10

User explicitly confirmed: Airtable integration disabled, Connect webhook active.
Before activating mail, verified zero queued confirmations. Backed up internal
Supervisor config to backups/registration-mail-cutover-20261110.conf. Set
registration-mail autostart=true and registration-cleanup autostart=false; reread
and update succeeded. Verified mail worker RUNNING and separate cleanup STOPPED,
with a clean initial run accepting zero emails. A single mail worker performs
queue delivery plus encrypted-data/token expiry cleanup every 30 seconds.

Requested a clearly labelled test through actual Tally form w7AWGA, test recipient
reinhold.sojer@smvo.ch and fake security data only. Real-form webhook acceptance
and automatic-mail smoke test remain pending. Legacy PHP endpoint/token records
are retained; no existing Airtable data or outstanding links were deleted.


### Real Tally webhook mapping correction — 2026-11-10

The user's real-form submission returned 422. A signed-rejection diagnostic
records only fixed logical field names, types, counts and GLN-format validity;
no submitted names, emails, security question/answer, signature or payload.
Privacy regression test verifies answer/email markers never appear in logs.

Observed resend had 22 fields and none matched the configured IDs. Read-only
inspection of the user's authenticated Tally event-log DOM confirmed that the
old map incorrectly used public-form group/layout UUIDs. Actual webhook keys use
short IDs (for example question_GRdqzQ for organisation name). Corrected all 20
logical field IDs in both public Connect and private API; no label-based fallback
or authentication weakening. Added an independent, fully synthetic fixture using
the actual observed key/selection structure, including dropdown options and the
extra checkbox-option field. Tests verify replay safety, option mapping, exact
security-answer preservation and rejection of an invalid GLN. Full suite: 458
passed; Ruff passed. Both API processes restarted after source update.

The source test also contains a 10-digit GLN; retained the 13-digit validation.
Requested a fresh test with a clearly marked synthetic 0000000000000 GLN and
the same test recipient; the old event cannot pass simply by resending unchanged
invalid input. No request content or security answer is retained here. Actual
form success remains pending. Consider adding matching GLN validation in Tally
so future users see this before submission.


### Actual-form end-to-end acceptance complete — 2026-11-10

After correcting actual webhook question IDs, the user submitted a new Tally
form with a clearly marked test name and a 13-digit synthetic GLN. Verified one
non-synthetic-source receipt (meaning actually delivered by Tally, with test
answers), EndUserRegistration ID 2 and linked provisional CRM end-user/contact.
The running worker automatically delivered its confirmation: SendGrid accepted,
mail_attempts=1. The user then explicitly confirmed the new email link.

Final internal assertions all passed: status needs_review, confirmed_at set,
email_confirmed workflow audit action, CRM links present, exactly one mail
attempt, receipt payload_ciphertext NULL and token_ciphertext/token_digest NULL.
The first ten-digit source test remains invalid and created no CRM records.
Do not create either marked test in NMVS. The separate encrypted temporary
question/answer follows the reviewed-data / NMVS-entry / rejection / seven-day
expiry lifecycle; confirmation alone does not remove that internal working data.

New registrations now use Tally -> stateless Connect -> private Operations API
-> CRM review and automatic SendGrid confirmation. Legacy Airtable producer was
disabled by the user; retain existing PHP/token store for old outstanding links.
Full local suite 458 passed, Ruff passed. No git commit was requested or made.
Remaining deployment work: automated portal certificate renewal, temporary Mac
hosts entry removal, and front-end GLN validation in Tally.

## Administrator erasure deployment — 2026-11-10

- Implemented explicit administrator deletion in registration Actions, with optional
  atomic removal of the linked unshared CRM End User/contact, and guarded CRM
  deletion for End Users, contacts and MAHs.
- Regression suite: 461 passed; focused deletion tests additionally verify that the
  rendered workflow exposes the confirmation and optional CRM deletion controls.
- Installed `0042_crm_deletion_events` on cloud MySQL and uploaded the explicit
  changed-file set to the private Operations node, keeping timestamped source backups.
- Supervisor reported all four restarted services started: both portal listeners,
  registration API and registration mail worker. No actual test records were deleted.
- Subsequent reachability verification could not complete: the private node did
  not answer SSH and HTTP, including an HTTP probe from the database node. Asked
  the operator to check the Jelastic environment/node state. Production acceptance
  remains pending until connectivity is restored; do not treat service-start output
  as proof of a healthy reachable portal.

### Reachability recovered; duplicate portal disabled — 2026-11-10

The operator reported 97% RAM utilisation. The node subsequently answered again;
inspection showed 512 MiB RAM and all 256 MiB swap occupied. HTTPS login returned
200. Disabled autostart for the obsolete localhost-origin `operations-portal`
listener and stopped it, retaining `operations-portal-https`, registration API,
registration mail and scheduler. Supervisor reread/update succeeded without
restarting the active HTTPS listener. Subsequent readings showed 290 MiB used RAM,
221 MiB available and 191 MiB used swap (existing swap is not forcibly cleared).
HTTPS login remained 200; an unauthenticated deletion POST returned 401. No test
records were erased. Recommend increasing the node's memory allowance and measuring
import peaks before treating 512 MiB as a production capacity target. Actual
administrator deletion remains an operator acceptance action using the UI.

### CRM checkbox search fix — 2026-11-10

Corrected the shared view toolbar to send `false` for unchecked boolean filters,
including End Users `unlinked` and self-declaration `duplicates`. Explicit false
also clears an active saved-view checkbox. Legacy GET links containing an empty
checkbox value are redirected to a valid false value before endpoint validation.
Search text and view context are preserved; other invalid booleans still fail.
Updated module asset versions so existing browsers load the corrected script.

### CRM-linked registration deletion review — 2026-11-10

Replaced the CRM deletion shortcut with an administrator-only review page. It
shows linked registration scope, End User and contact, with explicit confirmation
for the existing atomic workflow-plus-CRM deletion operation. Legacy CRM deletion
POSTs blocked by relationships now render the same review rather than a JSON error.
Registration deletion guard failures render an HTML explanation with scope and
navigation as well. No links are silently detached and no real records are erased
during deployment. No schema or public Connect changes are required.

### MAH imported contact relationship correction — 2026-11-10

Diagnosed missing MAH role backfill: imported references were displayed but not
persisted as CRM contact IDs. Added idempotent role reconciliation invoked after
both MAH and Contacts seeding, so either import order works. Only unset roles are
filled; explicit manual empty/legacy choices remain intact. Match by Airtable ID
or unique exact label, never collapse contacts by email. Skip archived/pending
registration contacts; retain entire unresolved roles for manual review and show
pending references on the Contacts card. Before applying the cloud repair, retain
a private original-profile/version backup on the Operations node.

Cloud repair completed: 88 MAH profiles updated, 87 SPOC groups and 83 Alert
contact groups assigned. Original profiles/version/timestamps and intended
additions were backed up on the private node in a mode-0600 JSON file before the
transaction. A second reconciliation produced no changes. AbbVie AG now has one
SPOC and two separate Alert contacts. Moderna Switzerland GmbH (MAH ID 64) retains
an ambiguous Alert contact reference for explicit manual selection. Existing
manual assignments were preserved. Full suite: 465 passed.

### Local checkpoint; direct deployment paused — 2026-11-10

At the operator's request, subsequent changes are developed/tested locally and
committed before Git push and explicit deployment. The imported-contact erasure
correction (migration 0043, source-fingerprint suppression and assignment detachment)
is tested locally but NOT installed in Jelastic. Local MySQL was additively upgraded
from 0041 to 0043; cloud schema remains 0042. A read-only comparison found 272
matching app/migration/requirements files in the private tree; the meaningful
candidate differences and separate Connect/test assets are listed in the
[deployment checkpoint](../deployment/STATUS-2026-11-10.md). All 15 public Connect
manifest source files match local source and their deployed manifest. Full local
suite: 466 passed. No production data was modified during this checkpoint review.
