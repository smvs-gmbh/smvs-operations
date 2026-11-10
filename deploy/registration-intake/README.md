> Historical buffered design. Do not activate on the public node; use deploy/connect/README.md and scripts/package_connect.py for the selected stateless deployment.

# Isolated registration intake — Jelastic test deployment

This package contains only the public registration service. It contains no core
portal, NMVS credentials, test workspace or environment secrets. Do not upload the
complete Operations repository or its `.env` to this container.

## Infrastructure

Use a separate Jelastic environment/node with nginx as the HTTPS entry point and
a Docker application node reachable only on its private port 8080. Assign the
public IP to nginx, not to the application port. Add a Cyon DNS A record for the
chosen hostname, then configure a valid matching TLS certificate. The generated
`nginx.conf.example` must be adapted to the actual topology and validated with
`nginx -t`. Do not replace an existing production nginx configuration wholesale.
Forward Host exactly as configured in REGISTRATION_PUBLIC_ORIGIN. Uvicorn does
not trust forwarded client headers; nginx enforces client-IP rate limits itself.

Use a separate `smvs_registration` MySQL database and restricted user. Configure
CA-verified TLS to MySQL, with the CA file mounted read-only. For a public test use
synthetic registrations only; keep REGISTRATION_ENVIRONMENT=production. Do not
use the local development SQLite setup on the public server.

## Build and deploy

Build this package directory as the Docker build context:

```sh
docker build -t smvs-registration-intake:TEST_VERSION .
```

Build for the actual Jelastic node architecture (typically linux/amd64); a local
Apple Silicon image is only a local test and must not be assumed deployable on
an x86 node. Build on the destination or use an explicit matching build platform.
Record the resolved image digest and dependency versions for the deployed build.

Push to your chosen private image registry or transfer an image archive to the
chosen Jelastic node. Registry/node details must be established before publishing.
The service runs as non-root UID 10001. Give it no Operations host mounts or core
DB network access. Keep the application port private. Supply environment variables
through Jelastic's protected environment configuration, not through image layers.

Copy the names from `registration-intake.env.example`; supply new dedicated keys
on the server, not the local test keys. Set:

- REGISTRATION_ENVIRONMENT=production
- REGISTRATION_PUBLIC_ORIGIN=https://YOUR_REGISTRATION_HOST (no trailing slash)
- REGISTRATION_DATABASE_URL=mysql+pymysql://.../smvs_registration?ssl_ca=/run/certs/ca.pem
- dedicated Fernet, exchange and Tally-signing secrets
- SENDGRID_API_KEY with Mail Send permission only
- REGISTRATION_MAIL_FROM=office@smvs-gmbh.ch
- REGISTRATION_MAIL_LINK_FIELD=confirmation_link

Initialise only the isolated database, once, with installation credentials:
`python -m app.registration init`. Then switch to the runtime DB account without
DDL privileges. Run the default container command for the API. Run a separate,
supervised worker using the same image, database and secrets with command:
`python -m app.registration mail-watch`. Do not start the worker until the
synthetic recipient, webhook and public origin have been checked.

Also supervise periodic `python -m app.registration purge`, independently of mail.
Configure bounded container logs, backup retention and monitoring. Persist MySQL
outside replaceable application containers. Never expose MySQL publicly.

## Controlled acceptance test

1. Verify HTTPS certificate and hostname from outside the VPN. GET /confirm must
   return 200. /crm, /exceptions, /auth/login and /docs must return 404.
2. An unsigned POST /webhooks/tally/registrations must return 401. Public requests
   to /exchange/registrations must be blocked by nginx (403).
3. Send one synthetic signed submission for form w7AWGA to the new endpoint.
   First validate its actual Tally field keys; do not use a real security answer.
   Replaying the same event must not queue another email.
4. Start one mail-once job, then check SendGrid acceptance and actual receipt.
   The email must link to the new HTTPS hostname, never localhost.
5. GET /confirm must not confirm. The recipient explicitly presses Confirm email;
   a repeat confirmation must fail without revealing registration data.
6. From Operations/VPN, allow only the pull worker's verified source IP to the
   exchange paths and configure its separate exchange secret and encryption key.
   The pull goes outward to intake, not from intake into the core.
7. Use an isolated test core for the first end-to-end import/review. Confirm
   Needs review, repeat-safe import, audit events and security-answer erasure.

Do not change the existing PHP confirmation endpoint or switch off Airtable/Make
until this test is accepted and a cutover is agreed. Adding a webhook to the live
Tally form may run both flows; restrict the supervised test to synthetic data and
check the existing automations before submitting.

## Rollback

Disable the new Tally webhook and stop its mail worker. Preserve the isolated DB
and encryption key for already-issued links, or deliberately revoke/reissue them.
Do not delete pending registrations or stop the old PHP flow as an incidental
part of testing. Replace the application image with the previous tested version;
there is no automatic destructive database reset on startup.

## Local verification — 2026-11-09

The allowlisted archive was built into a Python 3.13 container and smoke-tested
with read-only root filesystem, dropped capabilities and UID 10001. The confirmation
page/assets worked; core routes returned 404; unsigned webhooks and unauthenticated
exchange were rejected. A signed synthetic webhook replay produced exactly one
registration. Wrong Host and confirmation Origin were rejected. No email was sent
by this container test. The 11 registration integration tests also passed.

Public HTTPS/nginx, Jelastic networking, production MySQL TLS and real Tally webhook
delivery remain deployment acceptance checks; they are not established by the
local container test.
