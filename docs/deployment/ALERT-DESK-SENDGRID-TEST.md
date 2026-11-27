# Alert Desk TEST — SendGrid configuration

2026-11-26, CHG-025. Implementation/preparation does not imply external delivery.
Use the dedicated TEST environment and sender `alerts@smvs-gmbh.ch`, display name
`SMVS Alert Desk TEST`. The approved TEST recipients are Nicolas Florin (End User,
`nicolas.florin@smvo.ch`) and Reinhold Sojer (MAH, `reinhold.sojer@smvo.ch`). CRM
test organisations remain synthetic. Do not change production CRM or SendGrid setup.

## One dynamic template for all five message types

Create **SMVS Alert Desk TEST** under SendGrid **Email API → Dynamic Templates**.
Add an active Code Editor version. Set the subject to `{{subject}}`; paste
[HTML](../../deploy/alert-desk-test/sendgrid-template.html) and
[plain text](../../deploy/alert-desk-test/sendgrid-template.txt) into the corresponding
fields. The application supplies escaped `subject`, `heading`, `message` and a
`links` array with `label`/`url`. It uses the same template for invitation,
verification code, case update, findings request and reminder; content differs.
Activate the version, then copy its `d-…` Template ID to the protected configuration.
Never use a real invitation/code as SendGrid sample data or template-editor content.

Example preview data (not a valid invitation):

```json
{
  "subject": "[TEST] SMVS Alert Desk | Findings requested",
  "heading": "Findings requested",
  "message": "Please share your findings for synthetic alert DEMO-A3-1.\n\nKind regards,\nSMVS",
  "environment": "TEST",
  "links": [{"label": "Open case", "url": "https://node221862-env-1900268.jcloud.ik-server.com/alerts/3"}]
}
```

Reference: [SendGrid dynamic templates](https://www.twilio.com/docs/sendgrid/ui/sending-email/how-to-send-an-email-with-dynamic-templates),
[Mail Send API](https://www.twilio.com/docs/sendgrid/api-reference/mail-send/mail-send).

## Secret and activation

Create a dedicated API key restricted to **Mail Send**. Template editing can be
done in the SendGrid UI; it does not require broad template-management rights on
the runtime key. Use the protected local `.env.alert-desk-test-sendgrid`, mode 600,
based on [the example](../../config/alert-desk-test-mail.env.example). Never paste
the key into the chat, Git or command arguments. Supply the key and Template ID;
keep `ALERT_DESK_MAIL_MODE=capture` while preparing. A configured API key alone
does not activate external mail. The sender must be verified in SendGrid.

Transfer only the allowlisted mail settings over the trusted SSH channel into
the TEST runtime's owner-only `private/runtime.json`; preserve all other private
configuration. Enable `sendgrid` only once sender/key/active template and approved
recipients are complete. The participant gateway and capturing SMTP process do
not receive SendGrid credentials. Restart the TEST portal/private API to load
the configuration. Capture mode remains an immediate configuration rollback;
never discard the delivery table or accepted findings during rollback.

Updating CRM contact emails increments contact versions, invalidating old access.
Fresh invitations/mailbox verification are required for the new addresses. Existing
findings, templates, staff passkeys and source records are preserved. No automatic
bulk invitation is part of configuration; the owner selects recipients in Operations.

## Verification and outcomes

Mail Send uses one approved recipient per request, fixed HTTPS endpoint, disabled
click/open tracking, no redirects and suppressed credentialed transport diagnostics.
There is no automatic retry. Before network I/O, retain a delivery attempt in
`alert_desk_mail_deliveries`; retain outcome/provider reference afterwards. Do not
store the body, code, invitation URL or key. The fingerprint is keyed so a short
verification code cannot be recovered by hashing guesses. Pending/uncertain
attempts require staff review. A 202/accepted result means provider acceptance,
not inbox delivery. Delivery/uncertainty UI is private to TEST staff at
`/workflows/alert-desk/deliveries`.

SendGrid-mode messages do not appear in the capturing SMTP inbox. That inbox
retains earlier captures. Verify actual inbox/spam delivery of invitation and
verification code for each approved role, source/role isolation, request/update/
reminder content, expiry and failed/uncertain outcomes before accepting this flow.
Record actor/build/configuration/evidence without exposing capabilities.


## Supporting development verification — 2026-11-26

602 automated tests passed (one existing Starlette/httpx deprecation warning);
13 mail/private-UI tests passed again after final UI wording changes. Ruff checks
for the new transport/configuration/launcher/tests passed. Native local MySQL
upgrade from 0055 to 0056 succeeded. Hosted rollout and contact updates require
protected TEST backup and are recorded separately after execution. Actual SendGrid
acceptance/inbox verification is pending; no external messages were sent by these checks.


## 2026-11-27 — Correct the invitation button (CHG-027)

The observed active email contained a `codex-workspace-link.invalid` button URL,
which is not an Alert Desk address. The application supplies the real destination
in `links[].url`; do not paste a rendered chat/workspace link into the template.
The provided Mail Send key returns HTTP 403 for template retrieval, so template
editing must be done in the SendGrid UI with an authorised account. No broader
runtime key is required. Replace the HTML/plain-text version from the repository
assets, retain subject `{{subject}}`, and activate the edited version.

The corrected HTML uses `{{message_text}}` (body without duplicated destinations),
`{{brand_logo_url}}` and exactly one CTA per `links` element:

```handlebars
{{#each links}}
<a href="{{url}}">{{label}}</a>
{{/each}}
```

The destination is dynamic; do not enter a fixed invitation or any
`codex-workspace-link.invalid` URL. The original `message` field remains available
for backwards compatibility until the active template is updated. Captured SMTP
messages retain their complete plain-text destination. Verification-code emails
have no CTA, reminders may deliberately have multiple distinct case links.
This does not change the current 8-hour access policy or implement passkeys.
