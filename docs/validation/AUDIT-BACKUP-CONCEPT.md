# Operations audit retention and recovery concept

Draft v0.1, 2026-11-17. Owner SMVS GmbH. Requirements are URS-003,
URS-096, URS-110 and FRS-CORE-006/007. Archive configuration, recovery targets,
storage provider and named operating roles remain to be selected.

## Retention basis

Operations URS-096 specifies a minimum of five years from the recorded
activity, with a longer documented requirement taking precedence.

Article 35(1)(g) of Delegated Regulation (EU) 2016/161 specifies the repositories'
audit trail for operations concerning unique identifiers. Its minimum end
date is the later of one year after pack expiry or five years after release
for sale or distribution under Article 51(3) of Directive 2001/83/EC.
Assess applicability to each Operations record category and the CH/LI workflow.
The repository rule and Operations' event-based minimum use different clocks.
Retain necessary pack/date references where the longer-period rule applies.
Missing release or expiry data requires review before automatic disposal.

EMVO-00470 v4.0 section 7.6 describes Hub archival after 180 days without an
update for New or Closed Alerts, and retention for five years from Alert
creation. It also cites the pack-based Delegated Regulation formula.
Record the policy and longer applicable end date locally so that Case evidence
remains explainable when an online Hub query no longer returns an archived Alert.

## Required protection and recovery

| Area | Concept and verification |
| --- | --- |
| Audit creation | Record each transaction under FRS-CORE-007. Verify atomic business changes and audit events, failed attempts, interface outcomes, reads, exports and configuration changes. |
| Archive | Keep an append-only audit history with restricted administrative permissions. Archive segments carry a manifest, record range, checksums, schema/version and retention category. Verify integrity and retrieval across archive boundaries. |
| Independent copy | Keep a protected copy in a separate failure and access domain. Select immutable or retention-locked storage and establish an emergency recovery procedure. |
| Backup | Back up the database, retained Case evidence and archive manifests consistently. Encrypt backup data and retain access to separately protected decryption keys. Define backup frequency and restore points from agreed RPO and RTO. |
| Retention | Preserve auditable records and referenced evidence for their approved end date, including any hold. Evaluate short-lived operational backups separately from the long-term archive. Confirm that backup rotation and source expiry preserve required archived records. |
| Monitoring | Record backup and archive outcomes, verify integrity, and assign a response for failure, overdue copies or unavailable keys. Make any missing interval explicit. |
| Restore exercise | Restore to an isolated environment and reconstruct representative Cases, actor attribution, external observations and automatic decisions. Verify completeness, integrity, queryability and the time achieved against RPO/RTO. |
| Release decisions | Confirm owners, category-specific retention and applicable obligations, RPO/RTO, schedule, provider, access separation, archive integrity mechanism and restore-test frequency. Record evidence and acceptance in the release record. |

## References

- [Delegated Regulation (EU) 2016/161, Article 35(1)(g)](https://eur-lex.europa.eu/eli/reg_del/2016/161/2022-01-01/eng).
- EMVO-00470 v4.0, sections 7.4 and 7.6, pp. 43–44 and 54–56.
- [VP-001](../VP-001%20Validation%20Plan.md),
  [RA-001](RA-001.md), [RTM-001](RTM-001.md).
