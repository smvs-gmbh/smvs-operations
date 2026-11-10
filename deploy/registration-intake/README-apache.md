> Historical buffered design. Do not activate on the public node; use deploy/connect/README.md and scripts/package_connect.py for the selected stateless deployment.

# Registration intake on Jelastic Apache-Python

Use the preinstalled Apache-Python environment. A custom Docker image/registry is
not required. FastAPI runs as an ASGI application using a separate Uvicorn process;
Apache forwards HTTP requests to loopback. Do not point mod_wsgi at this app.

Topology: Internet HTTPS -> nginx -> private Apache -> 127.0.0.1:8013 Uvicorn.
nginx owns the public IP and valid TLS certificate. Use one dedicated hostname,
e.g. registration-test.smvs-gmbh.ch. Preserve this Host through both proxies.
Apache and Uvicorn ports must not be publicly accessible.

## Installation after the node is created

1. Inspect the actual Python version, Apache modules/vhosts, OS user and available
   process supervisor. Use Python 3.13 if offered (the isolated image was tested
   with 3.13); confirm any alternative interpreter before installing dependencies.
   This ZIP is a source bundle, not an automatically detected WSGI application.
2. Extract OUTSIDE the Apache document root in a directory accessible only to the
   dedicated service OS account. No existing Operations files or secrets go here.
   The example /srv/registration-intake is a placeholder, not a known Jelastic path.
3. In the extracted directory, create a virtual environment with the selected
   Python interpreter, then run `.venv/bin/pip install -r requirements.txt`.
4. Copy registration-intake.env.example to .env.registration-intake, owner-readable
   only (chmod 600). Supply separate production MySQL `smvs_registration` access,
   its readable CA certificate, dedicated encryption/exchange/Tally-signing keys,
   the chosen HTTPS origin and SendGrid key. No Operations DB or NMVS credentials.
5. Initialise the separate DB using `.venv/bin/python -m app.registration init` and
   installation privileges, then use the restricted runtime DB account.
6. Run `sh start-intake.sh` for the initial foreground check. Verify GET /confirm
   with the configured public Host forwarded to port 8013. Register the Uvicorn
   process with the node's actual supervisor for reliable startup/restart; the
   supplied Supervisor file is optional and requires adjusted user/paths. Do not
   use a permanently open SSH terminal as the process manager.
7. Add the Apache proxy directives to the dedicated virtual host only; remove
   conflicting WSGI mappings there. Check the resulting Apache configuration
   before reload. Preserve other hosted applications and their virtual hosts.
8. Apply nginx body/rate limits, TLS and exchange ACLs. nginx.conf.example uses
   PRIVATE_INTAKE_HOST:8080 for Docker; for this setup substitute the private
   Apache address and its actual listener port. Do not forward to loopback 8013
   on the nginx node unless nginx and Uvicorn actually share that node.
9. Keep exchange blocked until a verified worker-IP ACL exists at nginx; then
   permit that route through the dedicated Apache vhost so the bearer-authenticated
   internal worker can pull. A loopback Apache allow-rule is insufficient when
   public requests are also forwarded from loopback by nginx.

## Mail, cleanup and acceptance

Start only one supervised mail worker (`python -m app.registration mail-watch`)
when the synthetic test is ready. Periodically supervise `python -m
app.registration purge` independently of mail. The optional Supervisor example
leaves mail autostart disabled intentionally. Store logs outside the document root
with bounded retention; disable sensitive access/debug logging at both proxies.

Test public HTTPS /confirm and assets, unsigned webhook rejection, blocked exchange,
404 for /crm and /exceptions, one signed synthetic submission, one real test mail,
explicit confirmation and repeat-safe internal import. Never use a real security
answer for deployment acceptance. No NMVS organisation is created by this service.

Do not change the existing Tally/PHP/Airtable production flow before acceptance
and a deliberate cutover. Existing automations may also react to a Tally test.
The previous local tests passed for the isolated application and Docker image;
Apache/Jelastic configuration must still be tested on the real node.

References:
- https://www.infomaniak.com/en/support/faq/2257/discover-some-of-the-technologies-supported-by-jelastic-cloud
- https://www.modwsgi.org/en/latest/user-guides/configuration-guidelines.html
- https://uvicorn.dev/deployment/
