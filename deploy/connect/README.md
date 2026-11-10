# SMVS Connect — stateless public registration service

Selected public hostname: https://connect.smvs-gmbh.ch
NGINX 221301: 10.100.37.96 / 195.15.232.138
Apache-Python 221302: 10.100.37.97 / no public IP
Private Operations environment: env-9657618.jcloud.ik-server.com
Private Operations Apache node 207849: 10.100.32.195

This is the current architecture. The earlier registration-intake archive is the
superseded buffered design and must NOT be activated on the public node.

Connect contains no database driver/model, encryption key or SendGrid key. It
exposes only the signed Tally webhook, confirmation page/assets and same-origin
confirmation POST. It forwards to two fixed private registration API commands.
There is no public exchange/list/resend/CRM/Exceptions API. A successful webhook
reply is sent only after the internal API's atomic receipt/CRM commit succeeds.
Failure or uncertainty returns 503; source event/submission IDs make retries safe.

## Public installation

Extract outside the web document root, using a private service directory. Create
its own virtual environment and install requirements.txt. Copy connect.env.example
to `.env.connect`, mode 600. Supply the private API CA certificate, dedicated API
secret, Tally signing secret and exact origins. No core environment file belongs
here. Private HTTPS is mandatory even though the IP is private.

Use the preinstalled Apache as a proxy to Uvicorn on 127.0.0.1:8013. Run
`sh start-connect.sh` for a foreground check only. Then install an appropriate
process supervisor. The public service has NO mail or cleanup worker.

On the dedicated Apache host, use ProxyPreserveHost On and forward to loopback.
Remove its conflicting WSGI alias only after taking a backup and testing the final
configuration. On NGINX permit only /, /webhooks/tally/registrations, /confirm and the
two confirmation assets, limit bodies to 128k, apply webhook/confirmation rate
limits and disable sensitive access logs. Preserve the existing Let's Encrypt
HTTP challenge and HTTP-to-HTTPS redirect. Reject unknown hostnames/routes.

## Private installation (separate Operations deployment)

The internal API is a separate ASGI process, not an unauthenticated route added
to the portal. Its only commands are POST /v1/registrations/submissions and POST
/v1/registrations/confirm. Both require the dedicated bearer secret; submissions
also require the original raw-body Tally signature, checked again internally.
Use the existing smvs_operations DB, applying migration 0041_registration_receipts
with the normal guarded migration mechanism. Merge registration-internal.env.example
into the INTERNAL configuration; REGISTRATION_DELIVERY_MODE=direct selects the
portal's direct delivery workflow, with local resend and no legacy pull worker.

Example private listener after CA/key/firewall configuration:

    .venv/bin/uvicorn app.registration.internal_gateway:from_environment --factory \
      --host 10.100.32.195 --port 8443 --no-access-log --no-proxy-headers \
      --ssl-certfile /PRIVATE/certs/registration-api.pem \
      --ssl-keyfile /PRIVATE/certs/registration-api.key

The private certificate must be valid for IP 10.100.32.195 (IP SAN), or configure
a matching internal DNS name instead. Trust the issuing private CA on Connect;
never set verify=False. Restrict this listener to the Connect node's actual source
IP at the firewall. Do not expose it via the public NGINX or forward all portal
routes. Do not open the database itself to Connect.

Run exactly one supervised internal mail/cleanup worker:

    .venv/bin/python -m app.registration.internal_worker --watch

This sends the existing SendGrid template and keeps the workflow mail status
current without a pull. Uncertain deliveries are not retried silently. The worker
also purges expired receipt payloads/tokens and temporary internal security values.
For cleanup without sending, use `--purge-only`, optionally with `--watch`.
Confirmed receipt payloads are removed in the confirmation/CRM transaction; the
remaining temporary question/answer is encrypted in the internal review record
until manual NMVS creation, rejection or the seven-day maximum deadline.

## Acceptance and cutover

First prove the private TLS boundary, authorised fixed routes and rejection of
wrong API keys/signatures without sending mail. Then use one synthetic Tally
submission, a single controlled mail and explicit confirmation. Check immediate
CRM creation, Awaiting email confirmation -> Needs review, replay without extra
rows, rollback on storage failure, resend/expiry and attributed review actions.
Do not enter a real security answer in a test.

Do not switch the existing Tally/PHP/Make/Airtable flow or activate the new mail
worker until that supervised acceptance is ready. Preserve outstanding old links
and their token store during a deliberate transition. The old local buffered
mail test and three-record demo are not production Connect processes.

## Deployment status — 2026-11-10

Public Connect and its NGINX/Apache boundary are active. The private Operations
database, TLS API listener and process supervision are installed. The user added
the private environment firewall rule for TCP 8443 from 10.100.37.97/32. Real
Connect-to-Operations TLS verification and API authentication passed. The public
synthetic webhook and identical replay both returned 200 with one internal CRM
registration. Exactly one test mail was accepted by SendGrid and the user completed
confirmation. Internal verification showed Needs review, an email_confirmed
audit event and erasure of the receipt payload and one-time token. Failed persistence/transport returns 503
rather than a false receipt.
On 2026-11-10 the user confirmed Airtable integration disabled / Connect webhook
active. The queue was empty. Operations registration-mail is now RUNNING and
autostarts; the separate purge-only worker is stopped. The actual-form smoke test
passed: linked CRM records, one automatic confirmation mail, confirmed by the
user and verified internally as Needs review with erased receipt/token. Keep the old PHP confirmation endpoint/token store for outstanding
legacy links. Make involvement in the old sender was never confirmed.

For one controlled mail after synthetic acceptance, run internally:

    .venv/bin/python -m app.registration.internal_worker --receipt-id RECEIPT_UUID

This sends only that receipt and cannot be combined with --watch or --purge-only.
Do not invoke the unfiltered worker while conducting a single-recipient test.

Local tests cover the direct pipeline and legacy buffered compatibility.
