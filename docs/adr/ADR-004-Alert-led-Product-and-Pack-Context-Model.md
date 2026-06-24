# ADR-004: Alert-Led Product and Pack Context Model

## Status

Accepted

## Date

2026-06-23

## Context

The SMVS Operations platform is intended to become the central operational platform for monitoring, analysing and managing Swiss NMVS related operational activities.

In the NMVS ecosystem, operational investigations typically start from an alert or exception. Examples include:

- Serial Number Not Found
- Batch Number Not Found
- Expiry Date Mismatch
- Product Code Not Found

While alerts are often associated with a specific product (GTIN), the availability and reliability of pack-level identifiers may vary depending on the alert type and available data sources.

Additional contextual information may be obtained from:

- Product and MAH data
- Snapshot data
- Exception Audit Trail
- Pack Audit Trail
- Future VerifyIt scan events

The data model must support both current operational requirements and future AI-assisted investigations.

## Decision

SMVS Operations shall use an alert-led operational data model.

Alerts and exceptions shall serve as the primary entry points for operational investigations.

Products shall be used as the primary stable business reference for correlating operational events.

Where sufficient identifiers are available (e.g. GTIN, Serial Number, Batch Number and Expiry Date), the system shall enrich operational events with pack-level context.

The system shall maintain relationships between:

- Alerts
- Exceptions
- Products
- Packs (where identifiable)
- Audit Trail information
- Future VerifyIt events


## Rationale

The decision is based on the following considerations:

### Alignment with NMVS Operations

Operational investigations in NMVS environments typically begin with an alert or exception rather than with a specific pack.

An alert-led model therefore reflects the actual operational workflow of NMVS operators.

### Stable Product Reference

Products provide a reliable and persistent business entity across multiple operational events.

Many alerts can be correlated at product level even when pack-level information is incomplete or unavailable.

### Support for Pack-Level Intelligence

Certain investigations require analysis of individual pack histories.

The chosen model allows enrichment with pack-level information whenever sufficient identifiers are available without forcing all operational events into a pack-centric structure.

### Support for Future AI Capabilities

AI-assisted investigations will benefit from correlating multiple evidence sources.

The model allows future AI services to analyse:

- Alerts
- Exceptions
- Audit Trails
- Product information
- VerifyIt scan events

as a unified operational context.

### Separation of Evidence and Conclusions

Operational evidence such as audit trails and future AI recommendations shall remain distinguishable from operational decisions and user actions.

This supports transparency, traceability and future validation activities.

## Consequences

### Positive

- Reflects real NMVS operational workflows.
- Supports both product-level and pack-level investigations.
- Simplifies future alert correlation and case management.
- Provides a solid foundation for AI-assisted analysis.
- Accommodates future integrations such as AMS Hub and VerifyIt.

### Negative

- Additional correlation logic is required to establish pack-level context.
- Some operational events may remain product-level only.
- Data relationships become more complex than a purely alert-centric model.

## Related Documents

- DOC-001 System Charter
- URS-001 User Requirements Specification
- VP-001 Validation Plan
