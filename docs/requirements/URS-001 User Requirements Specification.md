# User Requirements Specification

# URS-001: User Requirements Specification

| Attribute          | Value                           |
| ------------------ | ------------------------------- |
| **Document ID**    | URS-001                         |
| **Title**          | User Requirements Specification |
| **Status**         | Draft                           |
| **Version**        | 0.9                             |
| **Classification** | Internal                        |
| **Owner**          | SMVS GmbH                       |
| **Author**         | Reinhold Sojer                  |
| **Reviewers**      | TBD                             |
| **Approver**       | TBD                             |

---

# Revision History

| Version | Date       | Author         | Description   |
| ------- | ---------- | -------------- | ------------- |
| 0.9     | 2026-06-27 | Reinhold Sojer | Initial draft |

---

# 1. Purpose

This document defines the user requirements for the SMVS Operations platform.

It specifies **what** the system shall provide from the perspective of its intended users, independently of the underlying technical implementation.

The User Requirements Specification serves as the basis for the Functional Requirements Specifications (FRS), Software Design Specifications (SDS), testing and validation activities.

---

# 2. Intended Use

SMVS Operations is an Operational Intelligence Platform supporting the operation of the Swiss National Medicines Verification System (NMVS).

The platform enables authorised users to integrate Operational Information from multiple authoritative Operational Information Sources, perform operational investigations, establish Operational Assessments and obtain evidence-based Decision Support.

The platform is intended to support operational investigations, reporting, analytics and continuous organisational learning. It does not replace operational systems such as the Swiss NMVS or the EMVS Alert Management System (AMS) Hub and shall not modify production NMVS data.

---

# 3. Scope

This specification defines the user requirements for:

- Core Platform
- Operational Information Integration
- Operational Information
- Operational Investigations
- Operational Assessment
- Operational Decision Support
- Reporting & Analytics
- AI-assisted Investigation Support
- Audit & Compliance

Implementation details are intentionally excluded and are specified in the corresponding Functional Requirements Specifications (FRS) and Software Design Specifications (SDS).

# Core Platform

## URS-001

The system shall provide a central operational platform for SMVS to support evidence-based operational investigations.

## URS-002

The system shall provide role-based access control appropriate to user responsibilities.

## URS-003

The system shall maintain an audit trail of relevant user and system activities.

## URS-004

The system shall provide a web-based user interface.

## URS-005

The system shall provide search, filtering and sorting capabilities across Operational Information.

## URS-006

The system shall provide capabilities for accessing Operational Information, Operational Intelligence, Operational Assessments, Decision Support and Investigation Management according to the user's role and permissions.

# Operational Information Integration

## URS-010

The system shall integrate Operational Information originating from multiple authoritative Operational Information Sources.

## URS-011

The system shall support both scheduled and manually initiated information integration processes.

## URS-012

The system shall validate Operational Information before making it available to the platform.

## URS-013

The system shall maintain a historical record of integrated Operational Information.

## URS-014

The system shall record the status, outcome and traceability of each information integration process.

## URS-015

The system shall support the integration of additional Operational Information Sources without affecting existing functionality.

## URS-016

The system shall preserve traceability between integrated Operational Information and the originating Operational Information Source.

## URS-017

The system shall maintain Operational Information independently of source-specific data structures and interfaces.

# Product & Batch Investigation

## URS-020

The system shall provide access to Product and Batch information relevant to operational investigations.

## URS-021

The system shall provide visibility of Product information imported from authoritative Operational Information Sources.

## URS-022

The system shall provide visibility of Batch information associated with Products.

## URS-023

The system shall support searching and navigation of Product and Batch information.

## URS-024

The system shall present relationships between Products, Batches, Marketing Authorisation Holders (MAHs), Onboarding Partners (OBPs) and other related Operational Information.

## URS-025

The system shall support identifying newly onboarded Products.

## URS-026

The system shall support identifying Product ownership changes.

## URS-027

The system shall support identifying Products associated with Marketing Authorisation Holders (MAHs) without a contractual relationship with SMVS.

## URS-028

The system shall support operational verification of Batch availability.

## URS-029

The system shall present Product and Batch information as part of the Investigation Context where relevant.

---

# Organisation & Location Investigation

## URS-030

The system shall provide access to Organisation and Location information relevant to operational investigations.

## URS-031

The system shall provide visibility of Organisations, Locations and related Operational Information obtained from authoritative Operational Information Sources.

## URS-032

The system shall support searching and navigation of Organisation and Location information.

## URS-033

The system shall present operational relationships between Organisations, Locations and other relevant Operational Information.

## URS-034

The system shall present Organisation and Location information as part of the Investigation Context where relevant.

## URS-035

The system shall support identifying operational relationships between Organisations involved in an investigation.

## URS-036

The system shall support correlating operational activities associated with Organisations and Locations.

---

# Operational Events

## URS-040

The system shall provide access to Operational Events relevant to operational investigations.

## URS-041

The system shall provide visibility of Alerts, Exceptions and future Operational Event types.

## URS-042

The system shall support searching, filtering and navigation of Operational Events.

## URS-043

The system shall correlate Operational Events with related Operational Information.

## URS-044

The system shall maintain historical Operational Event information.

## URS-045

The system shall present Operational Events as part of the Investigation Context where relevant.



# Operational Investigations

## URS-050

The system shall support creating and maintaining operational investigations.

## URS-051

The system shall establish and maintain an Investigation Context for each operational investigation.

## URS-052

The system shall support associating Operational Information, Operational Events and supporting Evidence with an investigation.

## URS-053

The system shall support documenting investigation findings.

## URS-054

The system shall support recording investigation outcomes.

## URS-055

The system shall support maintaining the lifecycle and status of an investigation.

## URS-056

The system shall support assigning investigations to authorised users.

## URS-057

The system shall maintain a complete history of investigation activities.

## URS-058

The system shall support recording decisions and follow-up actions associated with an operational investigation.

# Operational Assessment



## URS-059

The system shall present Operational Assessments together with the supporting Operational Intelligence and Evidence.



## URS-060

The system shall support Operational Assessments based on the current Investigation Context.

## URS-061

The system shall present Operational Assessments together with the supporting Operational Intelligence and Evidence.

# Reporting & Analytics

## URS-070

The system shall support Operational Assessments based on the current Investigation Context.

## URS-071

The system shall present Operational Assessments together with the supporting Operational Intelligence and Evidence.

## URS-072

The system shall support exporting Operational Information where appropriate.

## URS-073

The system shall support analytical views across multiple Operational Information Sources.

## URS-074

The system shall support historical analysis of Operational Information and Operational Events.

## URS-075

The system shall support reporting on Operational Information, investigations, Operational Assessments and operational trends.

# AI-assisted Investigation Support

## URS-080

The system shall support AI-assisted operational investigations.

## URS-081

The system shall support AI-assisted generation of operational observations, recommendations and investigation summaries.

## URS-082

The system shall clearly distinguish AI-generated content from user-generated content.

## URS-083

The system shall ensure that operational decisions remain under the control of authorised users.

## URS-084

The system shall provide explainable AI-assisted recommendations by presenting the supporting Operational Information, Operational Intelligence and Operational Assessments.

## URS-085

The system shall support explainable AI recommendations where AI-assisted Decision Support is provided.

## URS-086

The system shall clearly distinguish AI-generated recommendations from system-generated information and user-provided information.

# Audit & Compliance

## URS-090

The system shall maintain complete traceability of Operational Information, investigations and user activities.

## URS-091

The system shall record user actions relevant to operational investigations.

## URS-092

The system shall record system events relevant to operational investigations.

## URS-093

The system shall maintain traceability between Operational Information, Operational Intelligence, Operational Assessment, Decision Support, user decisions and Investigation Management activities.

## URS-094

The system shall support reconstruction of operational investigations for audit and regulatory purposes.
