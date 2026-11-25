# SMVS Operations FRS diagram sources

Figures 1 to 4: solid arrows show processing or data flow; dashed links without arrowheads associate explanatory notes. A standalone scope/legend box is not a process node. Figures 5 and 6 show selected physical relationships: the PNG arrows run from parent to child, while Mermaid uses ER cardinalities. These are alternative layouts of the same selected relationships, not full schema exports.

Figure 6 context: mapping_runs references the selected Snapshot and SAI processing_runs; current_publications selects the accepted Product/Batch mapping. Participant and other report publications have separate transaction boundaries.

Copy each Mermaid block separately into your Mermaid editor. The source is editable; final layout depends on the renderer.

## Figure 1 passkeys

```mermaid
flowchart TB
  %% Solid arrows are process sequence. Dashed links associate notes only.
  P1["Administrator creates named user<br/>Select Administrator and/or NMVO User"]
  P2["Single-use enrolment invitation<br/>24-hour lifetime; trusted delivery channel"]
  P3["Recipient registers a passkey<br/>Discoverable credential and user verification"]
  P4["Server verifies WebAuthn response<br/>Browser challenge, RP ID, origin and verification"]
  P5["Consume challenge and invitation<br/>Store public credential and issue session"]
  P6["Server-side session and role checks<br/>8-hour lifetime; protect reads and changes"]
  P1 --> P2
  P2 --> P3
  P3 --> P4
  P4 --> P5
  P5 --> P6
  N1["Bootstrap first administrator through the trusted server console."]:::note
  P1 -.- N1
  N2["Later sign-in: new challenge and passkey assertion; no password login."]:::note
  P4 -.- N2
  N3["Invalid, expired or replayed response: refuse sign-in; no session."]:::note
  P4 -.- N3
  N4["Disable user or change roles: revoke tokens and sessions. A backup passkey requires recent sign-in."]:::note
  P6 -.- N4
  classDef note fill:#fff,stroke:#555,stroke-dasharray:5 4;
```

## Figure 2 connect

```mermaid
flowchart TB
  %% Solid arrows are process sequence. Dashed links associate notes only.
  P1["Registrant submits Tally form<br/>Signed webhook reaches public Connect relay"]
  P2["Relay checks signature and format<br/>Fixed TLS route to the private registration API"]
  P3["Private API checks peer and bearer<br/>Validate signature and commit receipt plus CRM"]
  P4["Awaiting email confirmation<br/>Internal mail process sends single-use link"]
  P5["Recipient confirms by explicit POST<br/>Consume token; move registration to Needs review"]
  P6["Staff reviews identity and duplicates<br/>Approve to Ready for NMVS; record external ID"]
  P1 --> P2
  P2 --> P3
  P3 --> P4
  P4 --> P5
  P5 --> P6
  N1["Public relay is stateless: no database or mail credentials."]:::note
  P2 -.- N1
  N2["Failed or uncertain internal commit: return unavailable, never received. Retry is deduplicated."]:::note
  P3 -.- N2
  N3["Reject with reason; expire private security data; resend only through controlled internal workflow."]:::note
  P6 -.- N3
  N4["NMVS creation is external. Recording its organisation ID does not call an NMVS create operation."]:::note
  P6 -.- N4
  classDef note fill:#fff,stroke:#555,stroke-dasharray:5 4;
```

## Figure 3 rca

```mermaid
flowchart TB
  %% Solid arrows are process sequence. Dashed links associate notes only.
  P1["Select Alert and source revision<br/>Retain source identity, pack and market context"]
  P2["Confirm responsibility and evidence<br/>CH / LI / foreign / unconfirmed; read-only checks"]
  P3["Review evidence and applicable Findings<br/>End User and/or MAH, Pack Audit Trail, upload scope"]
  P4["Authorised staff records assessment<br/>Origin, reason and follow-up; individual or batch"]
  P5["Recheck source, Findings and review state<br/>Reject stale confirmation; lock affected records"]
  P6["Save local decision and event history<br/>Source revision, actor, Findings and resolution basis"]
  P1 --> P2
  P2 --> P3
  P3 --> P4
  P4 --> P5
  P5 --> P6
  N1["Unconfirmed responsibility blocks closure. Foreign support completion is distinct from local closure."]:::note
  P2 -.- N1
  N2["Snapshot counts are supporting context, not proof of a historical upload or pack status."]:::note
  P3 -.- N2
  N3["Batch action: preview exact groups, select explicitly, then revalidate the confirmed scope."]:::note
  P5 -.- N3
  N4["No change to NMVS pack state. External Hub status remains separately attributed."]:::note
  P6 -.- N4
  classDef note fill:#fff,stroke:#555,stroke-dasharray:5 4;
```

## Figure 4 information flow

```mermaid
flowchart TB
  NMVS["NMVS reports<br/>Daily Snapshot / Exceptions / activity<br/>Pack Audit Trail / upload"]
  SAI["Refdata SAI<br/>Swiss product names and MAH"]
  A["Acquire and retain raw bytes<br/>Job, hash, source and report metadata"]
  B["Parse and validate source structure<br/>Record attempt and failure stage"]
  C["Stage accepted datasets and rows<br/>Headers, order, raw JSON and row hashes"]
  D["Validate mapping and publish<br/>Product/Batch plus SAI; separate report paths"]
  E["Operational views and RCA<br/>Source scope, coverage and provenance"]
  N["Other paths<br/>Connect and staff CRM use separate workflows.<br/>Hub and VerifyIt feed scope is release-dependent."]:::note
  NMVS --> A
  SAI --> A
  A --> B --> C --> D --> E
  classDef note fill:#fff,stroke:#555,stroke-dasharray:5 4;
```

## Figure 5 staging model

```mermaid
erDiagram
  integration_jobs ||--o{ acquired_artifacts : acquisition
  artifact_contents ||--o{ acquired_artifacts : retained_content
  acquired_artifacts ||--o{ processing_runs : processing_attempt
  processing_runs ||--o{ staging_datasets : extracted_dataset
  acquired_artifacts ||--o{ staging_datasets : source_artifact
  staging_datasets ||--o{ staging_rows : source_rows
  integration_jobs {
    int id PK
  }
  artifact_contents {
    int id PK
    string sha256 UK
    binary artifact_bytes
  }
  acquired_artifacts {
    int id PK
    int integration_job_id FK
    int content_id FK
  }
  processing_runs {
    int id PK
    int artifact_id FK
    string parser_version
    string status
  }
  staging_datasets {
    int id PK
    int processing_run_id FK
    int artifact_id FK
  }
  staging_rows {
    int id PK
    int staging_dataset_id FK
    int source_row_number
    string source_record_hash
    json raw_row_json
  }
```

## Figure 6 product model

```mermaid
erDiagram
  products ||--o{ product_source_records : source_identity
  product_source_records ||--o{ product_versions : versions
  product_source_records ||--o{ batches : source_batches
  product_versions ||--o{ batches : version_batches
  sai_holders |o--o{ sai_preparations : optional_holder
  sai_preparations ||--o{ sai_packages : packages
  products ||--o| product_reference_matches : match_record
  sai_packages |o--o{ product_reference_matches : optional_package
  products {
    int id PK
  }
  product_source_records {
    int id PK
    int product_id FK
    string source_namespace
    string source_code
  }
  product_versions {
    int id PK
    int product_source_id FK
  }
  batches {
    int id PK
    int product_source_id FK
    int product_version_id FK
    string batch_code
  }
  sai_holders {
    int id PK
  }
  sai_preparations {
    int id PK
    int holder_id FK
  }
  sai_packages {
    int id PK
    int preparation_id FK
  }
  product_reference_matches {
    int product_id PK, FK
    int sai_package_id FK
    string match_status
  }
```
