# Lore Health Tech Stack: Research Brief

## Document Purpose

A research-only summary of the Lore Health technology stack. This document does not propose architecture, schemas, or design patterns. It exists to inform technology choices in the BRD and ARD by capturing what is known, what is reasonably inferred, and what is plausible vendor-default for an organization with Lore's profile.

## Confidence Framework

Stack claims are tagged at three levels:

- **Confirmed**: Directly attested by employee public profiles, Lore's own materials, or affiliated entity content.
- **Inferred**: Strongly implied by team composition, role openings, or near-certain implications of confirmed elements (for example, Cloud Composer follows from confirmed Airflow plus confirmed GCP).
- **Plausible default**: Vendor-standard or industry-standard for a healthtech organization with Lore's profile. Reasonable to assume in a proposal but not directly evidenced.

This framework matters because the proposal will be evaluated by engineers (Jonathon Gaff, possibly Mike Griffin) who will know which is which. Overclaiming is a credibility risk.

## Confirmed Stack Elements

### Cloud Provider: Google Cloud Platform

Benjamin Lansdell (Staff Machine Learning Engineer at Lore) lists GCP in his public skill set on LinkedIn / RocketReach.

### Orchestration: Apache Airflow

Lansdell's public skill set also includes Airflow. On GCP this almost always means Cloud Composer (managed Airflow), but the deployment form (Composer vs self-managed) is not directly attested.

### Primary Programming Language: Python

Multiple engineers list Python as a core skill, including Lansdell, Michael Cusack (Staff Software Engineer), and Jonathon Gaff (Data Engineer). Open ML and NLP roles also imply Python.

### Engineering Practices: Domain-Driven Design and Test-Driven Development

The Lore Health (Philippines) LinkedIn page, operated under the affiliated Sequelae PH Inc entity, explicitly references DDD and TDD as engineering practices. Bryan Stober's career history confirms Sequelae PH is the Philippines engineering arm, not a separate company.

### Other Engineer-Disclosed Tools

- **Scikit-Learn** (Lansdell)
- **Elasticsearch** (Stober)
- **Git** (Stober and others)

## Inferred Stack Elements

These follow directly from confirmed elements or from team composition with high probability.

### Analytical Warehouse: Google BigQuery

The default warehouse for GCP-native shops, especially in healthtech. Lore's heavy ML and behavioral data workloads (Lansdell, Alexander Ruch) imply a serverless columnar warehouse for feature stores and historical aggregates. Snowflake on GCP is possible but less likely given the all-Google signal elsewhere.

### Operational Database: Postgres-Flavored

Cloud SQL for PostgreSQL or AlloyDB for PostgreSQL is the standard GCP-native choice. AlloyDB specifically is positioned for low-latency operational workloads with analytical integration to BigQuery, which fits Lore's profile. Not directly confirmed.

### Managed Workflow Layer: Cloud Composer

Confirmed Airflow plus confirmed GCP implies Cloud Composer with very high probability. Self-managed Airflow on GKE is technically possible but unusual at Lore's headcount.

### Streaming and Event Processing: Cloud Pub/Sub and Cloud Dataflow

Standard GCP-native pattern for event-driven ingestion. Lore's behavioral data and LoreBot conversation telemetry would naturally route through this combination. No direct confirmation, but inference is strong.

### Object Storage Landing Zone: Cloud Storage

Inevitable for any GCP-native data platform. Effectively confirmed by implication.

### ML / Data Science Tooling

The team profile (Lansdell, Ruch, plus open Staff ML and Staff NLP roles) implies sophisticated ML infrastructure. Vertex AI is the GCP-native option. Custom training and serving on GKE or Cloud Run is also plausible. Specific tooling not confirmed.

## Plausible Defaults

These are vendor-standard or industry-standard for an organization with Lore's profile. Reasonable to use as proposal assumptions but should be presented as proposed rather than current state.

### Transformation Layer: dbt or Dataform

For BigQuery shops, dbt is the dominant open-source choice and Dataform is Google's native equivalent (acquired and integrated into GCP). Either is defensible. dbt is more common at Lore's size.

### Identity Resolution: Splink

Splink is the dominant open-source probabilistic record linkage library, implementing Fellegi-Sunter with explainable match weights. It runs on DuckDB, Spark, or Athena backends. The presence of applied math and graph ML talent on staff (Lansdell, Ruch) makes Splink a natural fit, but it is not confirmed in use today.

### PII Handling: Cloud DLP plus Cloud KMS

Standard GCP pattern for HIPAA-grade PII detection, classification, tokenization, and key management. Not directly evidenced for Lore but strongly aligned with their compliance posture.

### Network Perimeter: VPC Service Controls

Standard GCP control for hardening data perimeters around regulated workloads. Reasonable assumption, not confirmed.

### Serverless API Layer: Cloud Run

Common GCP-native choice for stateless service hosting. Aligns with the Python and FastAPI patterns common in this kind of healthtech. Not confirmed.

### API Gateway: Cloud Endpoints, API Gateway, or Apigee

Three GCP options. Apigee is the enterprise-heavyweight choice and likely overkill for Lore's size. Cloud Endpoints or Cloud API Gateway is more proportionate. Specific gateway not confirmed.

### Governance: Dataplex

Google's data governance and lineage offering. Increasingly common for GCP-native data platforms but not yet ubiquitous. No direct evidence Lore uses it.

### Observability: Cloud Logging, Cloud Monitoring, plus Splunk or Datadog

GCP-native logging and monitoring is standard. Splunk or Datadog overlay is common in healthtech for security and compliance log aggregation. Not confirmed.

## Stack at a Glance

| Layer | Likely Tooling | Confidence |
| --- | --- | --- |
| Cloud provider | Google Cloud Platform | Confirmed |
| Primary language | Python | Confirmed |
| Orchestration | Airflow (likely Cloud Composer) | Confirmed (Airflow); Inferred (Composer) |
| Analytical warehouse | BigQuery | Inferred |
| Operational database | Cloud SQL or AlloyDB Postgres | Inferred |
| Streaming | Cloud Pub/Sub plus Cloud Dataflow | Inferred |
| Object storage | Cloud Storage | Inferred |
| Transformation | dbt or Dataform | Plausible default |
| Identity resolution | Splink | Plausible default |
| PII tokenization | Cloud DLP | Plausible default |
| Key management | Cloud KMS | Plausible default |
| Network perimeter | VPC Service Controls | Plausible default |
| Serverless API | Cloud Run | Plausible default |
| API gateway | Cloud Endpoints, API Gateway, or Apigee | Plausible default |
| Governance | Dataplex | Plausible default (lower) |

## Engineering Org Signals Relevant to Stack

- **42-employee company**, of which roughly 25 are in IT and engineering. Tooling choices should be proportionate. Heavy enterprise tooling like Apigee, Collibra, or full Informatica suites is unlikely.
- **Distributed footprint** across San Diego, Seattle area, Santa Cruz, Chicago, Ann Arbor, Dallas-Fort Worth, Toronto, and Philippines. Implies remote-friendly, cloud-native posture.
- **ML and applied math density**: Lansdell (PhD Applied Math), Ruch (PhD computational social science, Cornell, ex-S&P Graph ML Head). Suggests the team can and does use sophisticated probabilistic modeling rather than rule-based pipelines.
- **Open Staff DataOps Engineer role** alongside the Staff Data Engineer role being interviewed for. Indicates the data platform discipline is being formally established, not maintained against an already-mature platform. This affects what existing tooling can be assumed.
- **Cross-border engineering via Sequelae PH** is structural, not speculative. Any stack choice involving PII processing must address residency and access boundaries.

## What the Available Evidence Does Not Support

Stated for the record so these claims are not carried forward as if confirmed:

- An active "data mesh transition" at Lore. No evidence.
- Specific use of Dataplex. No evidence beyond GCP-default speculation.
- Specific use of Apigee. No evidence; size of company makes it unlikely.
- Specific use of Splink today. Reasonable fit, no evidence in use.
- A reverse-ETL pipeline pattern currently in production. No evidence.
- A specific monitoring or observability vendor.

## Sources

- Benjamin Lansdell public profile (RocketReach, LinkedIn): explicit GCP, Airflow, Scikit-Learn skills.
- Jonathon Gaff public profile (LinkedIn): data engineering background, prior datalake work at VIZIO and OneStudyTeam.
- Michael Cusack public profile (RocketReach): Python, MATLAB, prior Color and Alphabet experience.
- Bryan Stober public profile (RocketReach): Sequelae PH Inc career history confirms Philippines entity relationship.
- Lore Health (Philippines) LinkedIn page: DDD and TDD as stated engineering practices, data products and AI/ML focus.
- Lore Careers site (`careers.lore.co`): role openings include Staff Data Engineer, Staff DataOps Engineer, Staff Machine Learning Engineer, Senior Software Engineer (ML Focus), Staff NLP Machine Learning Engineer. Job description bodies are JS-rendered and were not extractable.
- RocketReach company profile: ~42 employees, ~25 in IT/engineering, San Diego-based.

## Key Assumption for the Proposal

The deliverable should be written as if Lore is GCP-native, Python-first, Airflow-orchestrated, with a Postgres operational layer and BigQuery analytical layer. All other technology choices should be presented as proposed components of the v1 design rather than as descriptions of current state, unless additional evidence surfaces.
