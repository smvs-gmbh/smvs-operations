# SMVS Operations

SMVS Operations is the central operational platform of SMVS for monitoring, analysing and managing NMVS related operational activities.

## Planned Modules

- Core Platform
- Alerts Management NextGen
- Exceptions Monitoring
- IMT Intelligence
- Product Intelligence
- VerifyIt Integration
- AI Copilot

## Technology Stack

- FastAPI
- MySQL
- SQLAlchemy
- Jinja2 / HTMX
- OpenAI API

## Documentation

See `/docs`.


## Local imports and operational mapping

- [Daily Snapshot import](docs/integration/daily-snapshot.md)
- [SAI full-export import](docs/integration/sai.md)
- [Central import scheduler](docs/integration/scheduler.md)
- [Product / Batch / SAI mapping](docs/integration/product-batch-mapping.md)

Only `smvs_operations` is permitted. Apply the additive Alembic migrations before
running the corresponding import/mapping version. Source data and credentials
must not be committed.
