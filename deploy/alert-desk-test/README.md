# Hosted Alert Desk TEST

This deployment is separate from VerifyIt and production Operations. It supports
the explicitly enabled `ENVIRONMENT=test` feature, not production activation.

- Public participant origin: `https://node221862-env-1900268.jcloud.ik-server.com`.
- Same-node loopback services: Operations 8016, private API 8017, participant
  gateway 8018, capturing SMTP 11025. No database/source credentials in gateway
  or SMTP process environments. These are separate processes, not separate OS users.
- Private Operations initially uses an SSH tunnel, `http://localhost:8025`.
  Staff passkey authentication remains enabled. External participants do not need
  this tunnel or a VPN client. A future VPN-only HTTPS staff hostname can replace
  it through reviewed origin configuration; no public staff route is installed.
- Existing TEST database account `smvsops_test` accesses only `smvs_operations`
  on the TEST MySQL node. Standard runtime database guards remain unchanged.
- TEST-only SMTP captures mail as owner-only files, without external delivery or
  a public inbox. Review these files through the trusted staff connection. Real
  participant onboarding needs an approved recipient/delivery configuration later.

Set protected `private/runtime.json` outside DocumentRoot. Required settings:
`ENVIRONMENT=test`, `ALERT_DESK_TEST_ENABLED=true`, a fresh
`ALERT_DESK_PILOT_SECRET`, validated `ALERT_DESK_PUBLIC_ORIGIN` and loopback
`ALERT_DESK_PRIVATE_ORIGIN`, authenticated `PORTAL_AUTH_ORIGIN`, and the dedicated
TEST database/TLS settings. Never copy production/source secrets.

`run_service.py` loads one committed release from `current` and is invoked with
`portal`, `api`, `gateway` or `mail` under separate supervised processes. The
parent launcher supplies `SMVS_TEST_ROOT`; it does not emit runtime configuration.
Gateway HTTP peers remain restricted to loopback; a local Apache vhost preserves
the exact public Host. Do not enable Uvicorn trust of arbitrary forwarded headers.
An aggregate limit of 120 POSTs/minute bounds commands per gateway process;
this is not a per-person distributed rate limit or a production capacity claim.

The seed script refuses a nonempty or non-TEST store and uses reviewed synthetic
A2/A3/A7/A24 content. It retains no pre-authenticated fixture sessions and exposes
no reset or role-switching route. Bootstrap the synthetic staff account via the
trusted console; invitations/codes/session values are protected data.

Before installation record code/configuration/database state, archive/manifest,
rollback, and VerifyIt service/configuration/data fingerprints. Use the
[validation protocol](../../docs/validation/ALERT-DESK-TEST-VALIDATION.md) and
retain actual results separately. Public network access does not imply authority
to see a case. Disable the TEST vhost/services for containment; do not discard
post-installation findings/templates/audit records by restoring a stale backup.
