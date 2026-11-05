# Evidence guided alert investigation

Discussion proposal recorded on 2026-11-05. The NMVO workspace should assemble evidence and propose the next investigation step. The operator reviews the proposal, records the decision and adds only findings that are missing from the available sources.

## Sources and traceability

| Reference | Scope |
| --- | --- |
| EMVO-00306 supplied Word document | Sections 3.3 and 3.4 cover End-user and wholesaler investigations. Sections 3.5, 3.6 and 3.10 cover MAH and NMVO roles, IMT, systematic monitoring and closure. Appendix 2 provides alert descriptions. SMVS confirmed that this supplied copy contains the latest content. Retain the original file identity in the source record. |
| VerifyIt Guides runtime knowledge base | GS-001 Pack Data Not Found and GS-002 Pack Data Mismatch provide reusable checks. Operation 41020005 maps A52 to an expiry mismatch. VerifyIt starts with a pharmacy scan. Operations starts with the NMVO case, available evidence and the actual transaction process. |
| SMVS discussion and supplied A7 screenshot | Project proposals for proportionate investigation, explicit local resolution and a Monthly Alert Report. The screenshot illustrates one pack. The reported wider batch pattern needs its own query and supporting results. |

## Proposed investigation flow

**RCA-01 Evidence first.** At case opening, present a concise timeline and findings with links to the underlying alert observation, exact pack audit events, matching upload rows, Snapshot batch and relevant historical observations. Each finding identifies its source version, date, scope and whether it is observed, inferred or unresolved. Preserve the evidence references used at decision time. Reassess when relevant source data changes. Missing or incomplete reports surface as open checks. Reuse accepted reports and offer targeted retrieval through the existing queue.

**RCA-02 Proportionate review.** Offer a short decision with prefilled evidence when the sequence explains the alert and the operator has no unresolved concern. Offer a directed investigation when a specific participant needs to answer an open question. Keep the full guided RCA for unresolved discrepancies and uncertain cases. The user confirms the findings, can correct the interpretation and records any rationale absent from the evidence. A human conclusion can reference assembled findings in place of duplicating them in a mandatory text field. Keep the existing guided form as the fallback.

| Alert pattern | Evidence and proposed next step |
| --- | --- |
| A7 / A99 after Export | Show the successful Active → Exported event and the later failed Export for the same serial. Compare source-scoped location, requesting market, operation and transaction identifiers. Show the number of distinct packs in the matching batch pattern and the period covered. The example has a successful change at 18:30:49 UTC and an A7 / A99 at 18:51:53 UTC on 2026-11-04. Same-location repetition supports a short local disposition if the operator confirms the sequence and responsibilities. Keep the reason for the second call open as a process or interface question. |
| A2 Batch not found | Compare provided batch with the Snapshot and the upload history for the expected product and market. Show pre-alert and later events, upload outcome and coverage. If a plausible upload or synchronisation gap remains after checking the submitted values, prepare a MAH investigation request with those evidence references and the specific question about upload timing or market availability. An empty search with limited coverage is an open question. Retain the End-user check where a reading or entry error is plausible. |
| A3 Pack not found | Establish whether the exact product and provided batch exist in the available Snapshot and whether the serial has its own pack evidence. Continue with full RCA. Compare submitted serial and human-readable pack values, check scanner and interface behaviour, and inspect previous comparable errors at the same location. Ask the MAH for serial-level evidence where the discrepancy persists. |
| A68 Batch ID mismatch | Show provided and stored batch side by side and compare both with the human-readable pack data and transmitted request. Check scanner configuration, software parsing and earlier comparable location events. A confirmed mismatch after these checks needs deeper investigation with the appropriate party. |
| A52 Expiry mismatch | Preserve the original message and operation code. Compare submitted expiry, human-readable pack data and stored expiry. Check scanner and software parsing, date representation and recurring location patterns. If the discrepancy persists after an independent comparison, investigate possible serialisation, packaging or master-data quality with the appropriate party. |

**RCA-03 Patterns as supporting context.** Correlate by verified organisation and source-scoped location, transaction process and time range. Compare recurring discrepancies across products or scanners when reliable device or client identifiers exist. Distinguish a location-wide pattern from evidence about an individual scanner. Historical repetition supports a hypothesis and guides questions. Similar-case resolution still requires explicit selection, a common rationale and review of individual exceptions with open work.

**RCA-04 Responsibilities and outcomes.** For IMT, determine initiating and fulfilling market from transaction evidence. A German location identifier is a clue whose scope needs verification. If Germany initiated the alert and SMVS is fulfilling, provide a local disposition such as No further local action where supported and retain the reason. Formal closure stays with the responsible party under the applicable workflow. For a Swiss-initiated alert, keep the agreed NMVO decision and the documented evidence for closure. Record local work status separately from formal alert outcome and any remaining prevention action. Keep suspicious or unexplained cases on the applicable investigation or escalation path. Restrict shared evidence and reports to authorised recipients and permitted location information.

## Monthly Alert Report per End-user

**REP-01 Scope and audience.** Prepare a reviewable report per verified End-user organisation for the completed calendar month, with a breakdown by its authorised locations and workflow. Record the reporting time zone, data coverage, exclusions and generation time. Foreign IMT observations with unverified ownership remain internal. The monthly report complements timely case-specific follow-up and escalation.

**REP-02 Patterns and prevention.** Count distinct alerts and affected packs separately, group recurring patterns by process and evidence-supported cause, and compare with the previous period where coverage is comparable. Show rates only where a compatible transaction denominator is available. Include concrete recommendations, the cases or evidence behind them, open actions and, where agreed, owners and a way to check effectiveness next month.

For the repeated-export example, propose that the wholesaler check whether its approved export workflow should verify the pack before the state change. Ask it to investigate why the Export operation was issued twice, including application retries and repeated operator actions. Track that prevention task separately from the local disposition of the individual alert. Recurrent confirmed process issues can feed the existing CAPA proposal.

**REP-03 Delivery.** Start with a draft for NMVO review. Use validated organisation and SPOC links to determine the audience before any later distribution. The report should summarise prevention actions without disclosing other organisations or locations.

## Monthly Alert Report per MAH

Prepare a reviewable draft for each MAH with assigned A2 or A3 alerts in the
completed month. Group A2 by product and batch with upload evidence and report
coverage. Keep A3 pack-level findings and outstanding checks visible. Route
uncertain MAH assignments to an internal review list. Show the MAH contract
status to SMVS during review, including unknown status. Use verified Alert
SPOC assignments from the CRM for later SendGrid delivery after approval.
The [CRM proposal](Shared-Investigation-and-CRM-Proposal.md) describes the
planned Excel import and contact relationships.

## Operational knowledge and participant roles

**CTX-01 B. Braun export workflow.** SMVS reports a recurring pattern of repeated export operations associated with B. Braun. In this workflow B. Braun acts as an End-user exporting medicines from the EU for Kantonsspital Aarau. The destination comes from internal operational knowledge. Store it as an attributed, scoped and reviewable assertion. The NMVS transactions can support the repeat pattern, timing and location association. The cause of the repeat remains a process or software hypothesis until investigated. Use the historical comparison and the Monthly Alert Report to request investigation of duplicate calls and check the preventive workflow.

**CTX-02 MAH relationship.** Record the Swiss MAH's contract relationship with SMVS GmbH, its status, effective dates, scope and source. Track the expected serialisation and Hub upload role separately from observed upload activity. Keep unknown status explicit. The same organisation can have different roles in different workflows, including MAH and End-user. Use the applicable role and agreement to direct an investigation.

## Rules and pattern analysis

**RULE-01 Local completion.** Record a local resolution for eligible cases, including foreign-initiated IMT cases where SMVS has completed its own review. Hide the case from the open Exceptions list and retain it in Resolved and All. The audit entry records the local action, actor or service, time, reason, previous status and source references. Keep the external alert status as a separate field. For rule-based completion also record the rule identifier and version, evaluated conditions and exceptions, evidence versions and decision rationale.

**RULE-02 Repeated state changes.** Start with two distinct patterns: repeated Export and repeated Decommission. Require the same exact pack, an earlier successful matching state change and a later rejected repeat, with the same verified source-scoped location for the relevant operations. Treat missing history, conflicting or different locations, other relevant state changes or unresolved concerns as review cases. A shared batch or matching alert code alone does not qualify. Protect pending investigation work. Consider automatic local completion only for a validated, explicitly enabled rule. Retain the source-specific outcome and the explanation that supports each decision.

**RULE-03 Guidance catalogue.** Use the Verify Guidance approach of versioned rules and explicit outcomes. Each rule declares its applicable roles, operations and markets, required evidence, exclusions and action. Outcomes are a proposed short decision, a review task or notification, and local completion. Evaluate the rules against retained cases in shadow mode before enabling actions. Use replay-safe decisions, deduplicate notifications, and retain a path to reopen a case when new evidence changes the assessment.

**PAT-01 Verification patterns.** Analyse bursts of verification of distinct packs by market, location and time window where event-level coverage supports it. A possible serial collection pattern should create a review signal with counts, baseline, source coverage and the reason it stands out. Compare like workflows and take the transaction volume into account where available. A market such as Bulgaria is contextual information, with the signal grounded in the observed activity and its deviation from the expected workflow.

**PAT-02 Known workflows.** Record exceptions to pattern rules with an owner, rationale, evidence, scope and review date. Farmamondo's known export verification workflow is an example. Limit the exception to the verified organisation or location and the relevant operations. Unusual activity outside the documented scope can still generate a signal. Preserve the applied exception in the audit. Validate availability of distinct-pack verification events and their location attribution before implementing the detector. Aggregate counts alone cannot establish the number of distinct packs.

## Proposed implementation order

1. Build the A7 evidence summary and retrospective comparison for the B. Braun case. Show distinct packs, period, source coverage and exact same-location evidence. Capture the Aarau workflow separately as internal knowledge. Use the existing local resolution and audit flow and expose the distinction from external closure.
2. Add a versioned rule catalogue and shadow evaluation for repeated Export and same-location Double Decommissioning. Review matches and misses across same, different and unknown locations and incomplete timelines. Enable local automation per rule after the sample review. Keep the A2 upload evidence path and MAH investigation request as the next evidence panel.
3. Add organisation roles, scoped workflow notes and contract status in CRM. Use verified relationships for MAH routing, approved workflow exceptions and the first Monthly Alert Report draft.
4. Check verification-event coverage, build geographic and workflow baselines and produce review signals with explicit exceptions. Review the signals before enabling notifications. Extend the investigation panels to A3, A68 and A52 and use location history in their checks.

The proposal complements [Shared investigation and CRM](Shared-Investigation-and-CRM-Proposal.md) and the [current local review workflow](../integration/exception-review.md).

## Repeated operations across roles

Use a versioned operation catalogue keyed by alert type and source operation.
Each entry defines the expected state transition, success and rejection evidence,
and allowed review actions. Export and Destroy are the first A7 entries. Candidate
extensions include Decommission as Sample and Stolen. Verify the source operation,
state mapping and supported transitions against the relevant contract and retained
examples before adding them to the catalogue.

A wholesaler may perform a state change on behalf of a MAH or manufacturer.
Record the observed executing organisation and location separately from the
declared principal and the scope of its delegation. Keep the source and validity
of that delegation in the operational context. An operation code or shared
product association cannot establish the principal or the authority to act.

For an End-user robot issuing repeated decommission requests, group requests by
exact pack, operation, source, location and relevant time window. Show the first
successful state change and later rejected attempts with distinct transaction
identifiers. Compare other packs and, where available, client or device history
to identify whether the pattern is isolated or recurring. A software retry is
a hypothesis for the operator or software supplier to check. An intervening
state change, conflicting locations, missing evidence or a different operation
requires individual review. Keep prevention actions and any supplier follow-up
separate from the local disposition.

Implement additional entries after replaying labelled examples. Start with
evidence and a short local decision. Validate any proposed grouped action
against its own scope and observed exceptions before enabling it.

## First Intelligence rule

**Intelligence → Rules** lists the supported source operations and expected
states. The first rule uses a code-versioned A7 evaluator for Export and Destroy.
Operations can save a new scope version by operation and requesting market.
The Operations catalogue and required evidence checks remain code-defined.

The read-only preview evaluates up to the latest 100 candidates in the chosen
period. In **Exceptions → Actions**, preview the rule for up to 40 selected
cases. Each case needs its own matching audit sequence. Cases with pending
work or an existing resolution remain visible in the preview. Confirmation
rechecks scope, selected versions and evidence. The resulting local audit
records the rule ID, scope version, evaluator version and source report.

Optional natural language interpretation uses the Responses API with a
structured filter schema. Set OPENAI_API_KEY and OPENAI_SEARCH_MODEL on the
server to enable it. The explicit interpretation action sends the typed
question and a fixed schema. The user reviews the proposed filters before
running the local search. The interpreter supports A7 Export or Destroy,
requesting market, relative UTC period and evidence matches. More complex
patterns and automatic rule execution are future work.
