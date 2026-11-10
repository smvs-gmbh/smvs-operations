# NMVO guidance comparison and Swiss investigation decisions

Reviewed 2026-11-10. Design evidence, not an implementation of foreign national procedures.

## Source precedence and provenance

The owner-confirmed EMVO-00306 supplied copy remains the baseline. The SMVS policy
is that the responsible NMVO controls and closes an investigation. A participant
finding, local Operations work completion and an external AMS acknowledgement are
separate events. Foreign guidance can improve checks and communication; its legal
rules, deadlines, dispensing instructions and closure permissions do not become
Swiss rules automatically. The reviewed editions are identified below; this review
is not a claim that each is the latest available edition.

## Austria: AMVO-005-2.0

Source: `amvo-005-20-guidance-alert-management-system.pdf`, supplied by the owner;
13 PDF pages, version 2.0 dated 2025-12-09, applicable from 2026-02-09.
SHA-256: `66a51bbb1775cd694354fadf63c44db017b68260af406bc2b12f6439cc098450`.

The cover says the German version is authoritative and this English version is
informative. This file does not include the operational appendices. The separately supplied
ADAM User Guide has now been reviewed below; it demonstrates one workflow and
does not enumerate the complete question catalogue.
Section 7.2.2 refers to Appendix ./1, whereas section 10 lists Appendix ./4. Obtain
those actual documents before implementing any appendix-based rules.

### Abbreviations in plain language

| Source term | Meaning | Relevance for SMVS |
| --- | --- | --- |
| AMVO | Austrian Medicines Verification Organisation; the association | Distinguish association from operating company |
| AMVS GmbH | Austrian Medicines Verification System GmbH; repository operator | NMVO operational counterpart |
| AMVSystem | Austrian national verification repository | The verification system, not the investigation portal |
| ADAM | AMVS Digital Alert Managementsystem | Austria's national investigation application |
| VDL / VAS | Verifying or Dispensing Location / verifizierende oder abgebende Stelle | Includes pharmacies and wholesalers; use familiar participant names in Connect |
| RPC / VPU | Responsible Pharmaceutical Company / Verantwortliches Pharmazeutisches Unternehmen | Austrian contractual role; not automatically identical to our Swiss MAH record |
| OBP | Onboarding Partner contracted with EMVO | Upload/Hub participant; distinguish from MAH and wholesaler |
| MAH | Marketing Authorisation Holder | Use Swiss SAI identity and reviewed CRM affiliation |
| BASG | Bundesamt für Sicherheit im Gesundheitswesen | Austrian authority; no automatic Swiss authority routing |
| AMS Hub | European alert communications hub | Later MAH connection; reuse instead of duplicating communications |
| ATD | Anti-tampering device | Physical packaging check distinct from data comparison |

### Process findings and derivation

Sections 5–6 separate the national application used by VDL/AMVS/BASG from the AMS
Hub used by OBP/MAH/RPC. Section 7 uses alert-specific guided questions, participant
findings and coordination by AMVS. On the Hub side it distinguishes cause on one's
own side from no cause found on one's side, plus corrective-action timing. These
are useful inputs to a shared investigation, rather than isolated closure claims.

Sections 7.1 and 7.5 prescribe three working days and automatic escalation if a
process error is not confirmed or processing is incomplete, followed by BASG
involvement. This is a material national difference: keep the EMVO-aligned initial
two-working-day findings/progress baseline in our concept, with Swiss calendar and
escalation policy still to approve. Neither automatic authority escalation nor a
three-day deadline is enabled by this comparison.

Sections 5 and 8 retain fallback procedures when the system cannot resolve a case,
and separate expiry/recall and ATD checks from this L5 application workflow. Keep
fallback communication and pack-handling instructions explicit; a closed local
work item does not itself authorise dispensing or reverse a pack state.

## Austria: ADAM End-user User Guide AMVS-UG-1015 v2.0

Source: `amvs-ug-1015-userguide-verwendung-adam-endbenutzer-v200.pdf`, supplied
by the owner; 42 pages, valid from 2025-12-01, reviewed 2026-11-10.
SHA-256: `69e3b2982a536497606d104be516721eb82a14b12dc2d41841e5a2204f9d3c5c`.
The [official AMVS ADAM resource page](https://www.amvs-medicines.at/infothek/alarm-management-adam/)
also lists this guide. Text was extracted and the pack-comparison and guided-step
screens on pages 24–26 were visually inspected. This is an operational guide;
it complements AMVO-005 and does not supersede the EMVO baseline.

### What the guide actually establishes

- **Access and integration (sections 3–4.2, pages 6–14):** End-users can enter from
  their software or a browser, using their AMVSystem credentials/certificate.
  Entry can lead to a dashboard, alarm list or directly to an alarm. This is not
  evidence that ADAM uses the same authentication or architecture as Connect.
- **Suggested cause, not final finding (4.3.2, pages 18–19):** ADAM automatically
  proposes a potential cause and uses it to select the investigation workflow.
  The guide explicitly allows the eventual finding to differ from that proposal.
  It does not disclose the algorithm, model, confidence calibration or training
  data. Do not describe it as proven machine learning or generative AI.
- **Pack comparison (4.3.8 and 4.4.1, pages 24–26):** submitted identifiers are
  displayed, together with stored pack data where a discrepancy exists. The
  participant compares these with the physical pack. The screenshot includes a
  complete transmitted serial, batch, product code and transmitted/stored expiry.
- **Guided work (4.4, pages 25–31):** more than fifteen workflows are mentioned,
  but only one is demonstrated: a suggested missing-serial upload cause followed
  by pack-data comparison, photo evidence and handling information. Do not infer
  all A7/wholesaler branches from that single example. The guide says a workflow
  can be run only once and cannot go back a step; completed answers can be read.
- **Different audiences (4.3.3–4.3.5, pages 19–21):** workflow answers are visible
  to the End-user, AMVS and BASG. Comments default to all involved parties, with
  a checkbox to restrict them to AMVS/BASG. Attachments and mobile photo upload
  via QR are supported. Do not assume every field or attachment shares exactly
  the same audience or that the manual proves upload-token security properties.
- **Trace and coordination (4.3.6, 4.5–4.6, pages 22, 31–40):** alarm activities
  have timestamps; notifications can use inbox, push or email. Several email
  addresses can be registered and verified, with email intervals. Delegation
  across locations is granted/revoked explicitly within the same tenant; the
  originating End-user remains distinguishable from the delegate.

### SMVS design decisions derived from this guide

| ADAM observation | SMVS proposal | Priority |
| --- | --- | --- |
| Potential cause selects guided work | Versioned rule/evidence analysis suggests checks; participant can disagree, state uncertainty or request help. Preserve the suggestion and eventual finding separately. | Initial contributions |
| Complete identifiers support physical comparison | Keep exact submitted serial and provided/stored identifiers in the authorised case; add Snapshot constraints and evidence dates. Stored serial/expiry must come from an actual supported source, never be manufactured from an inferred match. | Initial contributions |
| Over fifteen specialised workflows | Start with shared reusable checks plus alert/operation/role conditions. Begin with repeated-state A7 and A2/A3/A52/A68 identifier discrepancies; do not build fifteen speculative flows. | Initial contributions |
| One pass with no backward step | Support saved drafts, resume, back navigation before submission and subsequent attributed amendments. Preserve submitted answer versions; material changes invalidate dependent checks/decisions for review. | Initial contributions |
| Restricted workflow answers and shared comments | Show the audience before submission and require intentional publication. Default new investigation contributions to End-user + SMVS; later MAH sharing is explicit. A private contribution must not leak via summaries, attachments or notification previews. | Before external access |
| Mobile pack photos | Later issue an expiring case-bound upload-only grant, not an investigation/session token inside the QR. Apply the existing private inspection/quarantine design before releasing images. No routine photo requirement when existing evidence suffices. | After text pilot |
| Tenant-bounded delegation | Later support reviewed CRM organisation/location mandates, scope, expiry and revocation; mere CRM linkage or a shared mailbox is not delegation. Record the actor and the organisation represented separately. | After initial pilot |
| Notification options | Reuse reviewed SPOCs/contacts and verified recipient addresses; support useful event summaries and urgent updates separately. Keep identifiers and sensitive findings out of email. | After scoped contributions |

Shared investigation is not a claim to have invented multi-party collaboration;
ADAM and other AMS products already support communication. The intended SMVS
improvement is reusable evidence, fewer repeated questions, explicit collaborative
findings, and NMVO-owned closure with editable, traceable contributions.

### Reported success: evidence and limits

The [BASG safety-features page](https://www.basg.gv.at/fuer-unternehmen/zulassung-life-cycle/zulassungsverfahren/sicherheitsmerkmale)
reports Austrian L5 error-rate ranges of 0.0–0.1% as of 2024-06-17 and
0.00–0.01% as of 2025-11-12. These are reported Austrian system figures, not a
controlled evaluation of ADAM. The page does not isolate ADAM's contribution,
provide a consistent transaction denominator/time series or prove reduction of
alerts across Europe. Preserve the owner's positive experience as context;
do not turn it into an independently validated causal claim.

For our evaluation, record baseline and follow-up with stable definitions:
L5 alerts per 1,000 eligible operations, repeat alerts after confirmed corrective
action, time to first contribution and NMVO decision, participant effort, and
reopened/incorrectly resolved cases. Distinguish local from IMT events and count
coverage/source changes. More completed cases or fewer displayed alerts alone do
not establish prevention or safety. Anomaly analysis of successful Verify events
remains a separate deferred stream.

## Ireland: IMVO Alert Management Guidance v1.0, June 2023

[Official IMVO PDF](https://www.imvo.ie/wp-content/uploads/2023/06/IMVO-Alert-Management-Guidance-v1.0-Jun-2023.pdf),
sections 6–9. The inspected PDF has 37 physical pages; printed numbering differs.

It separates procedural, scanner/software, upload and EMVS causes. End-users check
matters under their control; correction effectiveness and findings must be
recorded. MAH feedback includes progress if unresolved. Wholesaler handling sits
within its quality system and relevant technical agreements, rather than a
pharmacy-only scan dialogue.

Design derivation: make checks conditional on role and evidence, reuse existing
findings, and capture correction plus effectiveness separately. Do not copy Irish
stock-release instructions or jurisdiction-specific obligations into Swiss guidance.

## Germany: securPharm-hosted ABDA FAQ v5, 2024-09-13

[Official securPharm-hosted FAQ](https://www.securpharm.de/wp-content/uploads/2024/09/FAQ_securPharmCD_V5_20240913.pdf),
particularly questions 4.39–4.41. This is an ABDA document hosted by securPharm,
not an independently authored NMVO standard.

It distinguishes later successful technical transactions from alarm-status
updates; the former do not generally update the latter. It also distinguishes
alarm communications from authority notification. Its report catalogue includes
successful-operation investigations by product/location, beyond alert-only data.

Design derivation: retain explicit auditable closure, keep escalation/reporting
separate, and investigate successful-Verify data coverage before implementing
behavioural detection. Do not adopt German closure automation or seven-day
procedures as SMVS policy.

## Case-specific serial and batch evidence

Decision: an authorised End-user needs the complete transmitted serial for the
specific published case to compare it against the physical pack. Preserve leading
zeros, case and characters. This is the submitted value, not a claim that the
serial exists or is authentic. Show character count as an observation.

Do not put serials in notification email, URLs, logs, public lists or unrestricted
exports. Future case grants must restrict organisation/location, case membership
and publication audience on every request. The current staff-only preview is not
public access and does not yet implement those grants.

Verified current model: `Batch.pack_count` and `Batch.active_pack_count` are typed
fields populated by the mapping. `Markets`, `Min SN Length`, `Max SN Length`,
`SN Format`, `Batch Length` and `Batch Format` remain in `Batch.evidence`, retained
from Snapshot. They have not been lost. The preview extracts only these six keys
into a bounded reference, using the exact product identity, namespace and batch.
It labels provided versus stored batch separately. Counts are not necessary for
participant scanner comparison and remain outside this projection.

Snapshot constraints describe the retained snapshot, not necessarily alert-time
contents. For A2/A68, a known stored batch must not validate an unknown/different
provided batch. A matching serial length does not prove correctness or authenticity;
a mismatch is an investigation lead, not a counterfeit verdict. Raw `N` or other
format codes remain labelled source codes pending an authoritative schema/code
mapping. Do not silently assume a character set or automatically normalise values.

Next structured-evidence increment: promote constraints into typed, nullable,
source-traceable fields (or a versioned evidence projection), retain mapping-run/
Snapshot timestamp and raw values, validate code semantics against the NMVS source
specification, backfill idempotently and test missing/unknown/historical data. No
schema migration or retrospective cause assignment is made in this increment.

## A7: participant confirmation and prevention

For the owner's repeated-export example, procedural error is the working
assessment. The participant must confirm from local records. The same alert type
can also result from a retry/software defect, automated robot process, repeat
Destroy/Sample/Stolen operation or work performed for a principal. A7 alone does
not select the cause or prove benign handling.

Proposed participant fields:

- Finding: **Root cause on my side**, **No root cause identified on my side**, or
  **Investigation in progress**. The middle choice does not assign blame elsewhere.
- Cause type: procedural / technical / unresolved, with short supporting findings.
- Independent optional **Known issue in our process or software** flag, scoped to
  location/software/operation and linked to a maintained issue, not a blanket exemption.
- Corrective action, planned date and effectiveness check; reuse an existing issue
  or CAPA reference where appropriate rather than duplicating evidence.

NMVO reviews the contribution and decides closure. Issue remediation can remain
open after a reasoned case decision. Every decision retains actor, time, evidence
version, reason and individual/bulk membership; reopened cases return to the list.
IMT responsibility remains with the responsible NMVO; SMVS can finish its local
work without claiming to close the other NMVO's investigation.

## Deferred: successful Verify pattern analysis

Explicitly deferred; no detector, automatic accusation or closure rule is enabled.
Exceptions cannot measure all successful verifications. A high count does not
establish serial harvesting. Candidate analysis needs successful transaction
coverage, location, time, operation, distinct-pack/repeat counts and historical
baseline. Aggregated UserActivity data may support volume monitoring but cannot
necessarily establish distinct-serial behaviour; check the actual reports/API and
coverage before choosing a data source.

Compare rate changes and diversity with the location's role, software, routine
warehouse/export activity and known validated processes (for example Farmamondo).
Use reviewed, bounded exceptions with owner, reason and expiry. Country alone,
including Bulgaria, is not evidence of abuse; a market records transaction context,
not physical travel. Internal contextual knowledge, such as a B. Braun delivery to
Kantonsspital Aarau, must be attributed as staff knowledge rather than inferred
from NMVS events. Suspicious combinations generate a review lead, never an
automatic falsification finding. Evidence access and jurisdiction must be checked.

## Next implementation sequence

1. Review the revised staff-only participant preview, including full serial and
   role-labelled Snapshot constraints.
2. Implement persistent case/publication scope and the minimal dedicated Connect
   API/access grant protocol before external access.
3. Implement guided participant contributions and known-issue references; preserve
   NMVO-only decisions, reopening and audit provenance.
4. Add reviewed reminders, monthly prevention reports and CAPA follow-up. Obtain
   the remaining Austrian operational appendices and workflow catalogue where useful. Defer successful-Verify detection
   until source coverage and an evaluation set exist.

## NMVS Alerts Origin and predefined comments — follow-up

The supplied NMVO R5.1 manual (page 45) distinguishes Origin, formerly Suspected
reason, from AMS Hub Reason and supports predefined comments. The SMVS design
adopts that separation while adding a compact local role attribution and reusable
improvement-action catalogue. Proposed roles/actions are SMVS design choices,
not values asserted to exist verbatim in the source product. See
[Origin and predefined actions](Shared-Alerts-Management-End-User-Pilot.md#origin-and-predefined-improvement-actions--owner-clarification-2026-11-10)
for review states, causal attribution, action ownership and versioning.

## Which proposed measures are actually defined by the reviewed sources?

Review clarification, 2026-11-10: the documents contain investigation steps and
specific corrective measures, but no single exhaustive ready-made action dropdown
catalogue for SMVS. Keep source instructions distinct from our preventive/CAPA
extensions and record their provenance in the future catalogue.

| Candidate action | Evidence in reviewed sources | Classification / limit |
| --- | --- | --- |
| Check/correct scanner configuration or keyboard settings; use a different scanner | EMVO section 3.3, End-User-02b | Explicit corrective measure when scanner error is established |
| Contact internal IT, software provider or scanner supplier | EMVO section 3.3, End-User-02b/02c | Explicit investigation/support step; not confirmation of supplier responsibility |
| Verify the effect of a scanner/IT correction | EMVO section 3.3, End-User-02b/02c | Explicit verification following correction under the applicable handling procedure; not repeated decommissioning and not a complete long-term CAPA effectiveness programme |
| Document a confirmed procedural error and its investigation | EMVO section 3.3, End-User-02a | Explicit documentation/feedback step, not itself a preventive organisational change |
| Investigate upload timing/data errors; involve EMVO Helpdesk for a Hub issue | EMVO section 3.5, MAH-03 | Explicit investigation/routing; correction follows the established problem and responsible party's procedure, not A2 alone |
| Indicate whether/when corrective action will be taken | AMVO-005-2.0, section 7.2.2 | Explicit action follow-up for OBP/MAH/RPC; not a complete predefined measure catalogue |
| Brief staff; redesign the local process to prevent repeated operations | SMVS design derived from procedural-error findings | Sensible prevention proposals; not claimed to be enumerated EMVO measures |
| Reuse a known issue/action; owner/date, long-term recurrence review, external CAPA reference | SMVS design | Our efficiency and organisational-learning extension |
| No further action required | EMVO section 3.5, MAH-02, in its stated MAH/known End-user-error context | Role- and condition-specific; not a universal option proving an alert safe or closed |

The EMVO scope section explicitly excludes the wider alert-prevention/reduction
programme while expecting it to run alongside investigation. Therefore identify
our CAPA workflow as an SMVS extension consistent with investigation findings,
not as a mandatory catalogue copied from EMVO. The ADAM guide demonstrates
comparison/photo/handling steps for one example but does not disclose all fifteen-
plus workflow definitions or an exhaustive corrective/preventive action list.

For implementation, catalogue entries should carry source document/version/step,
whether they are investigation, immediate correction or preventive follow-up,
applicability and the evidence needed to mark them completed. This prevents a
support request, an unimplemented plan and a verified correction from being
counted as the same outcome.
