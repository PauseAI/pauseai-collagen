# Collagen - Automated Collage Pipeline

**Status**: Initial Setup
**Current Campaign**: Say No to Superintelligent AI

## What is Collagen?

Collagen is an automated pipeline for creating and managing photo collages from crowd-sourced campaign photos. While initially built for PauseAI's "Say No" campaign, it's designed to support multiple collage campaigns over time.

The system:
1. Syncs approved photos from Cloudinary to persistent storage
2. Generates collages (simple grids initially, photomosaics later)
3. Provides a web UI for preview/publish workflow
4. Emails first-time contributors when their photo appears in a published collage

## Architecture Overview

```
Cloudinary (moderation) → Sync Service → AWS EFS Storage
                              ↓
Admin Webapp (FastAPI) ← reads/writes → Filesystem + EXIF metadata
                              ↓
                  Collage Generation (ImageMagick/Python)
                              ↓
                  Email Notifications (Google Workspace SMTP)
```

**Sync Service** can be implemented as either:
- **Webhooks**: Cloudinary → API Gateway → SQS → Lambda → EFS (event-driven)
- **Polling**: systemd timer → Python script → Cloudinary API → EFS (30-min interval)

Architecture choice will be made after webhook testing in Phase 0.

## Tech Stack

- **Language**: Python 3.12+
- **Web Framework**: FastAPI
- **Server**: AWS EC2 (Ubuntu 24.04 LTS)
- **Storage**: AWS EFS (persistent across instance replacements)
- **Metadata**: Filesystem + EXIF (no database for MVP)
- **Email**: Google Workspace SMTP (sayno@pauseai.info)
- **Sync**: TBD (webhooks vs polling)
- **Deployment**: AWS CLI + shell scripts

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Single EC2 host** | Easy to reason about, sufficient for MVP |
| **Filesystem-based state** | Simple, inspectable, no DB complexity |
| **JSON manifests** | Version control friendly, human-readable |
| **EXIF metadata** | Queryable without database, standard tooling |
| **ImageMagick for MVP** | Simple grid generation, can upgrade to photomosaics later |

## Project Phases

**Phase 0**: AWS setup + webhook testing (1 day)
**Phase 1**: Sync implementation - webhooks or polling (1-2 days)
**Phase 2**: Collage generation + FastAPI webapp (2 days)
**Phase 3**: Email notification system (1 day)

**Total**: 5-6 days to production MVP

## Development Status

See [CLAUDE.md](CLAUDE.md) for current work status and next steps.

See [ORIGINAL_PROJECT_PLAN.md](ORIGINAL_PROJECT_PLAN.md) for detailed architecture planning.

## Related Issues

- #436 - Book campaign and photo collage (campaign origin)
- #437 - Architecture proposal
- #488 - Email content design
- #500 - Bootstrap notification (142 users successfully emailed)

## Cost Estimate

~$9-16/month (EC2 t3.micro + EFS + minimal Lambda/SQS if using webhooks)

## License

TBD
