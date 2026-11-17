# VP-001: Validation Plan

| Attribute          | Value           |
| ------------------ | --------------- |
| **Document ID**    | VP-001          |
| **Title**          | Validation Plan |
| **Status**         | Draft           |
| **Version**        | 0.11            |
| **Classification** | Internal        |
| **Owner**          | SMVS GmbH       |
| **Author**         | Reinhold Sojer  |
| **Reviewers**      | TBD             |
| **Approver**       | TBD             |

---

# Revision History

| Version | Date       | Author         | Description   |
| ------- | ---------- | -------------- | ------------- |
| 0.9     | 2026-06-29 | Reinhold Sojer | Initial draft |
| 0.10    | 2026-11-16 | SMVS Operations project | Planned validation of the existing implementation and initial gap assessment |
| 0.11    | 2026-11-17 | SMVS Operations project | Added release approval points and evidence requirements using the NMVS Release 19 plan as a reference |

---

# 1. Purpose

This Validation Plan defines the validation strategy, responsibilities, deliverables and activities required to demonstrate that the SMVS Operations platform is fit for its intended use.

Validation shall follow a documented, risk-based approach consistent with the principles of GAMP® 5 and shall provide objective evidence that the system consistently fulfils its User Requirements Specification (URS).

---

# 2. Scope

This Validation Plan applies to the complete lifecycle of the SMVS Operations platform, including development, testing, deployment, operation and subsequent controlled changes.

The plan defines:

- the validation strategy
- validation responsibilities
- validation deliverables
- lifecycle documentation
- requirements traceability
- risk management
- testing strategy
- acceptance criteria
- change management
- validation maintenance

Implementation details, test procedures and technical specifications are defined in the corresponding Functional Requirements Specifications (FRS), Software Design Specifications (SDS), Test Specifications and related validation documentation.

---

# 3. Validation Strategy

SMVS Operations shall be validated using a pragmatic, risk-based validation approach consistent with the principles of GAMP® 5.

Validation activities shall be commensurate with the intended use of the platform, its complexity and the potential impact on operational processes, data integrity and business continuity.

Validation shall be based on:

- documented User Requirements
- documented functional specifications
- documented design specifications, where applicable
- documented testing
- complete requirements traceability
- documented review and approval activities
- objective evidence demonstrating that the platform is fit for its intended use

The validation approach emphasises documented evidence, traceability and maintainability throughout the system lifecycle rather than exhaustive documentation.

Reference for the approach: [ISPE GAMP 5 Guide, Second Edition](https://ispe.org/publications/guidance-documents/gamp-5-guide-2nd-edition/).

# 4. Validation of the existing implementation

Use Git commit `d446f5d` as the first candidate for the local implementation
inventory. Identify the deployed release, database migration level, relevant
configuration and connected services separately for each environment. Confirm the
release candidate before formal test execution.

1. Confirm the intended use, users, process boundaries and applicable SMVS and
   external obligations with the system and process owners and the designated
   approver. Review operational functions and external boundaries, including
   Connect, NMVS imports, CRM contacts used for routing and the local Alert
   Desk pilot. Assess AMS Hub production integration when preparing its release.
2. Reconcile
   [URS-001](requirements/URS-001%20User%20Requirements%20Specification.md) with
   the agreed workflows. Use the implementation to discover gaps. Record the
   required behaviour independently and classify gaps as requirements changes,
   implementation changes or items outside the release scope.
3. Update the relevant FRS and record the design where it helps explain or verify
   risk controls. Assess the impact of failures on operational decisions and
   data integrity to determine the depth of testing.
4. Maintain a traceability matrix from URS through FRS and risk controls to test
   cases, evidence and deviations. The test plan describes the environment,
   data, prerequisites, expected outcomes and evidence to retain. Use existing
   tests and pilot results where the tested version, behaviour and outcome can
   be established.
5. Execute missing checks against the identified release, record deviations and
   their disposition, and prepare a validation summary for approval. Keep the
   validated state through change control, impact assessment and proportionate
   regression testing.

## Initial gaps for review

The current requirements and test inventory is in [RTM-001](validation/RTM-001.md).
The preliminary impact and control assessment is in [RA-001](validation/RA-001.md).
Reconcile the stated external use of Connect and the Alert Desk pilot with the
internal-use wording in [DOC-001](requirements/DOC-001%20System%20Charter.md)
when SMVS confirms the release scope.

| Area | Existing evidence or behaviour | Work before acceptance |
| --- | --- | --- |
| Requirements and release scope | URS-001, existing FRS and design documents, and a consolidated local Git baseline | Verify intended use and deployed versions. Reconcile participant access, external interfaces and local Case decisions with the controlled requirements. |
| Alert Desk pilot | Owner reports pilot testing complete apart from response deadlines and reminders. The default is three weekdays from the response request, excluding weekends. | Agree which clock the workflow must display and monitor. The [EMVO alignment](architecture/EMVO-Alert-Handling-Alignment.md#timing-and-monitoring) describes a two-working-day feedback target starting at the Alert. Confirm the applicable calendar and test due dates, overdue views, receipt of progress updates and reviewed reminders. |
| Investigation, access and audit | Local RCA, participant Findings and local closure are available. The baseline has 498 passing automated tests. | Trace and verify critical cases, including participant scope and revocation, single and batch closure scope, inter-market responsibility and audit attribution. Review which automated and pilot evidence is suitable for the release record. |
| Interfaces and operational controls | NMVS imports, Connect and the local test workspace have documented behaviour. Direct AMS Hub checks have run in UAT. | Verify source-data integrity, replay and failure handling, environment isolation and recovery for the release scope. Record UAT checks as interface evidence for the future Hub integration. |

# 5. Release approval points

Use a release record for each validation scope. Record the release identifier,
included and excluded functions and interfaces, relevant changes and known
deviations, and the application, database and configuration versions by
environment. Identify the system owner, process owner, test lead, deployment
lead and quality reviewer before formal execution. Named assignments and
approval responsibilities remain for SMVS to confirm.
Track pre-release changes in the [change register](validation/CHANGE-REGISTER.md).

| Approval point | Evidence for the decision |
| --- | --- |
| Start validation | Agreed intended use and release scope, applicable obligations, URS/FRS, impact and risk assessment, and an agreed validation plan. |
| Start business acceptance testing | Identified build and test environment, approved test cases and data, technical test results for the relevant workflows, and a decision on open defects that could affect acceptance testing. |
| Authorise production deployment | Business acceptance results, requirements traceability, assessed deviations, release configuration, migration verification where applicable, and a reviewed deployment and rollback procedure. |
| Close validation for the release | Deployment and post-deployment checks, recorded final versions, disposition of deviations, and the approved validation summary. |

## Test and deployment records

- Record technical verification and business acceptance separately, with the
  tested version, environment, expected and actual results, evidence references
  and deviations. The test plan defines entry and exit criteria for each.
- Use the risk assessment to select migration, interface and recovery tests.
  Include NMVS, Connect and other interface checks where they are in scope.
  Where a migration affects investigation or audit records, verify their
  integrity after migration and describe how data will be recovered if
  reverting the application alone is insufficient.
- Keep the deployment procedure and deployment record with the release. Record
  actual application and database versions, relevant configuration, deviations,
  verification results and any rollback or recovery actions.

Reference for the release structure: Solidsoft Reply, EMVS3973, *Validation Plan
for NMVS Release 19*, v1.0, sections 2–11 and Appendix B.
