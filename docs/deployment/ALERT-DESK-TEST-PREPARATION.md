# Alert Desk — TEST deployment and access preparation

2026-11-26, CHG-021. Status: preparation; no TEST deployment or public opening
performed. The owner authorises transfer to a synthetic TEST environment.
The supplied target `env-1900268.jcloud.ik-server.com` currently serves VerifyIt;
the intended Operations target or coexistence needs clarification. Existing production
Operations (`9c04152`, schema 0054) and Connect must remain unchanged.

## Findings from the current implementation

The participant candidate is `f9245ba`, local schema `0055_comment_templates`.
The application is not yet configurable for a hosted TEST environment:

- `app/alert_desk/schema.py` fixes the participant origin to localhost:8014 and
  private API origin to loopback:8015. Invitation/update/reminder links use it.
- `web.py` accepts only that Host and loopback peers; origin checks and cookies
  use the local constant. Configuring a proxy alone is insufficient.
- `pilot_api.local_app()` and `collaboration_routes.pilot_enabled()` explicitly
  require development. Do not set an exposed server to development to bypass this.
- `pilot_mail.py` sends to a loopback capture mailbox on port 11025.
- Existing Connect is the registration relay; its packaging, minimal dependencies
  and proxy allowlist do not currently include Alert Desk. Do not route all paths
  to Operations or copy its database credentials to Connect.
- The standalone `test_workspace.py` is a local fixture/reset tool, not a remote
  deployment entrypoint. Do not expose its reset/role-switching routes publicly.

## Recommended access design

Keep the TEST Operations staff portal behind VPN and staff authentication.
External End User/MAH testers use a dedicated HTTPS TEST Connect hostname with
only the authenticated Alert Desk routes/assets enabled. Invitation plus mailbox
verification still applies: public network reachability is not public case access.
Testers following that participant path do not need an OpenVPN client. Staff
using private Operations require an authorised VPN connection/client profile.

| Option | Benefit | Cost/limitation | Suitable use |
| --- | --- | --- | --- |
| VPN-only TEST participant gateway | No internet opening; quick first internal pilot if VPN already exists | VPN account/profile/client on each test device; does not validate public Connect routing | Initial internal functional checks |
| Dedicated public TEST Connect | Representative external invitation/browser flow; no VPN for participants | Separate DNS/TLS, gateway packaging, private authenticated TLS route, rate limiting and access verification | Recommended external participant acceptance |

Both options need hosted configuration and a non-development feature gate.
Changing to VPN-only does not resolve localhost links or local mail constraints.
The public option is a proposal, not an approved change to production Connect.

Logical public TEST route:

`Tester → TEST HTTPS edge → stateless Alert Desk gateway → authenticated private TEST API → TEST database`

The edge exposes only reviewed `/alerts` routes/assets. Staff CRM, administration,
database, internal API, fixture resets and capturing-mailbox UI are not public.
Use a separate TEST hostname, keys, session cookies and backend configuration;
never reuse production invitations or database/source credentials.

## Implementation sequence once the target is known

1. Inspect target identity, existing code/processes, schema, synthetic dataset,
   private routing, TLS, DNS and SMTP. Record sanitised evidence. Preserve data.
2. Develop hosted settings locally: explicit TEST enablement independent of
   development, validated public/private origins, narrowly trusted proxy peers,
   secure host/origin/cookie handling and verified private TLS/authentication when
   crossing nodes. Preserve the existing production-off default. Reject unsafe
   configuration at startup; never weaken global authentication/DB safeguards.
3. Make all invitation/update/reminder links use the configured TEST origin.
   Specify capturing SMTP first. Real mail needs an approved test recipient list
   and enforced recipient boundary before any external delivery is activated.
   Inspect crash/access logs and response headers for token/code disclosure.
4. Provide supervised gateway/private-API processes with restart and liveness
   checks; package only required public code/assets/dependencies. Adapt TEST
   proxy allowlists deliberately. Keep API/data/secrets on the private side.
5. Run focused security/workflow tests, migration tests and relevant regression.
   Commit the tested source, identify the exact archive/manifest and backup the
   target code/database/configuration before installation. No uncommitted deploy.
6. Apply migrations only to the identified TEST store, verify 0055 and retained
   records. Activate authenticated staff TEST access first. Verify the private
   participant path before any selected public opening.
7. Execute installation/access cases AD-T01/02/03/20 from the
   [validation guide](../validation/ALERT-DESK-TEST-VALIDATION.md). Retain source,
   schema, process, routing and rollback evidence; mark unexecuted cases clearly.
8. Invite only agreed test identities, execute the remaining protocol and record
   findings. Preserve existing local workspaces and production services.

## Rollback and outstanding decisions

Before deployment establish the previous source/configuration, database snapshot
and tested restore procedure. Do not assume an Alembic downgrade is safe: retained
template/audit evidence must survive. Prefer disabling the TEST participant route
and restoring a compatible code/configuration version; database restore requires
explicit disposition of records created after the snapshot.

Pending: Operations target/coexistence in the supplied VerifyIt TEST environment;
public versus VPN-only access decision;
TEST Connect hostname/routing; approved test mail recipients/transport; deadline
policy; final release commit and scope (do not infer all development increments
are authorised for unrelated production systems); named testers/reviewer.
