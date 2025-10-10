# Collagen - AI Assistant Context

## Project Overview

Automated collage pipeline for campaign photos. Currently driving: "Say No" campaign.
Named "collagen" to support multiple future campaigns beyond "sayno".

## Current Status

**Phase**: Phase 0 complete (webhook testing), ready for Phase 1 (processor implementation)
**Branch**: main
**Last Updated**: 2025-10-05

### Completed
- [x] Architecture planning (see ORIGINAL_PROJECT_PLAN.md)
- [x] Cloudinary capabilities research
- [x] Webhook vs polling analysis
- [x] Git repository initialized and pushed to GitHub
- [x] .gitignore configured
- [x] Project documentation structured (README.md, CLAUDE.md)
- [x] GitHub issues created for project tracking
- [x] AWS account "PauseAI" created and configured
- [x] AWS billing alerts set at $20/month
- [x] IAM admin user created with CLI access
- [x] EC2 instance provisioned (i-05674280f86f51a75, Ubuntu 22.04, t3.micro)
- [x] EFS filesystem provisioned and mounted (fs-001b5fdce1b4db8c8)
- [x] Webhook receiver deployed and tested
- [x] Cloudinary webhook behavior empirically tested
- [x] **Architecture decision: Use webhook-based sync**
- [x] EC2 webhook processor implemented with dual-size storage
- [x] Webhook signature validation (SHA-1 + timestamp)
- [x] Campaign-specific logging to EFS
- [x] Format normalization (f_jpg for all inputs)
- [x] Email sanitization for test campaigns
- [x] Grid optimization algorithm for 4K collages
- [x] Redrive mechanism for backfills
- [x] Performance validation (35-49s collage generation)

### Next Steps (Revised Plan)
- [ ] Migrate to API Gateway + SQS architecture (Phase 2A)
- [ ] Enable sayno campaign + backfill 229 images (Phase 2A)
- [ ] Collage generation web UI with preview (Phase 2B)
- [ ] Email notification system with dry-run mode (Phase 3)
- [ ] Allowlist testing with pauseai.info addresses (Phase 3)
- [ ] Production rollout: phased (test group → full users) (Phase 3)
- [ ] AWS Backup for EFS (Phase 3)
- [ ] Monitoring and handoff (MVP)

## Tech Stack

- **Python 3.10+**: Core language (Ubuntu 22.04 default)
- **FastAPI**: Web framework for admin UI
- **AWS EC2 + EFS**: Hosting + persistent storage
- **ImageMagick**: Collage generation
- **exiftool**: Metadata management (email addresses in EXIF)
- **Sync Method**: **Webhook-based** (confirmed via testing)
  - Phase 1: EC2 direct webhook receiver (for dev testing)
  - Phase 2: API Gateway → SQS → Lambda (for production)
- **Google Workspace SMTP**: Email delivery (sayno@pauseai.info)
- **Nginx**: Reverse proxy (port 80 → Flask on 8080)

## Architecture Decision: Webhook-Based Sync ✅

### Decision

**Use webhook-based sync** for all photo synchronization (not polling).

### Test Results (Phase 0 - 2025-10-05)

**✅ Cloudinary moderation webhooks fully functional:**

| Test | Result |
|------|--------|
| Global webhook with `event_type: "moderation"` | ✅ Works |
| Webhook fires on UI approval | ✅ Yes |
| Webhook fires on UI rejection | ✅ Yes |
| Webhook fires on API status change | ✅ Yes |
| Webhook fires on approved→approved (no change) | ❌ No |
| Backfill via pending→approved toggle | ✅ Works |
| Email in webhook payload | ❌ No (must fetch separately) |

**State transitions that trigger webhooks:**
- Pending → Approved ✅
- Pending → Rejected ✅
- Approved → Rejected ✅
- Rejected → Approved ✅
- Approved → Pending ✅
- Approved → Approved (no change) ❌

**Webhook payload includes:**
- public_id, asset_id, version
- secure_url (for downloading image)
- moderation_status ("approved", "rejected", "pending")
- moderation_kind, moderation_updated_at
- notification_type ("moderation")
- Does NOT include: email metadata

**Processing approach (Phase 1 - implemented):**
1. Webhook arrives with public_id, secure_url
2. **Parallel**: Fetch metadata via API (asset_folder, email) + download image to /tmp as JPG
3. Filter by asset_folder (only test_prototype in Phase 1)
4. Sanitize email for test campaigns (→ collagen-test+...@antb.me)
5. Embed email in EXIF UserComment
6. Save full-size JPEG to `approved/`
7. Generate 300×400 PNG thumbnail to `thumbnails/`
8. Log to campaign-specific `processor.log`

**Rejection handling:**
- Delete both approved JPEG and thumbnail PNG
- Pending webhooks ignored (limbo state, not rejection)

### Why Webhooks Won

- **Event-driven**: Instant sync on moderation events (vs 30-60 min polling lag)
- **Zero polling overhead**: No API calls when nothing changes
- **Scalable**: 142 or 5000 photos, same architecture
- **Backfill viable**: API can trigger webhooks via status toggle
- **Production-grade**: SQS provides retries, DLQ, at-least-once delivery (Cloudinary: 3 retries over 9 min)
- **Simpler logic**: No state diffing, filesystem is append-only (delete on reject)

### Sync Architecture Evolution

**Phase 1: EC2 Direct (Dev Testing)**
```
Cloudinary → EC2 Flask app → EFS
```
- Fast iteration, simple debugging
- Filters: only process `asset_folder=test_prototype`
- Risk: Lost webhooks if EC2 down during Cloudinary's 9-min retry window

**Phase 2: API Gateway + SQS (Production)**
```
Cloudinary → API Gateway → SQS → EC2 Processor → EFS
              ↓ VTL mapping      ↓
         Sets campaign attr   14-day retention
```
- API Gateway returns 200 immediately (Cloudinary considers delivered)
- VTL mapping extracts `asset_folder` as SQS message attribute `campaign`
- Enables per-campaign CloudWatch alarms (dev vs prod separation)
- EC2 processor polls SQS, processes messages, writes to EFS
- DLQ for failed processing
- No Lambda needed (EC2 already has EFS mounted)

## Filesystem Structure (Campaign-Agnostic)

```
/mnt/efs/
├── test_prototype/       # Dev campaign (asset_folder from API)
│   ├── approved/         # Archive: 1500×2000 JPEG with EXIF metadata (~200KB each)
│   │   ├── selfie_abc123.jpg
│   │   └── selfie_def456.jpg
│   ├── thumbnails/       # Collage-ready: 300×400 PNG (~175KB each)
│   │   ├── selfie_abc123.png  # Generated from approved JPEG
│   │   └── selfie_def456.png  # Email preserved in EXIF
│   ├── collages/         # Generated collages + manifests (Phase 2)
│   │   ├── preview.png   # Working preview (not published)
│   │   ├── v1_master.png # 4K PNG master with transparency
│   │   ├── v1_1920.jpg   # JPEG derivative (1920px)
│   │   ├── v1_1024.jpg   # JPEG derivative (1024px)
│   │   └── v1.json       # Manifest: photos included, emails sent
│   └── logs/
│       ├── processor.log # Main events: SYNCED/DELETED/ERROR
│       ├── webhooks/     # Cloudinary webhook logs (Phase 2)
│       │   └── YYYYMMDD/
│       │       └── HHMMSS.{status}.{public_id}.json
│       └── email-v1.log  # Email send logs per collage (Phase 3)
├── sayno/                # Production campaign (Phase 2)
│   └── [same structure]
└── future_campaign/      # Future campaigns
    └── [same structure]
```

**Dual-size strategy:**
- Full JPEG (1500×2000): Archive quality, EXIF metadata source
- PNG thumbnail (300×400): Pre-generated for fast collage assembly
- Path convention: `thumb_for_approved(approved_path)` enforces consistency

**Processor routing:** `asset_folder` from API → `/mnt/efs/{asset_folder}/`

**Why dual storage:**
- Collage from full-size: 163s for 999 images (too slow)
- Collage from thumbnails: 49s for 999 images (fits HTTP timeout)
- Webhook overhead: +0.2s per photo (acceptable)

## Collage Manifest Format

```json
{
  "version": "v1",
  "created_at": 1727740800,
  "published_at": 1727741000,
  "algorithm": "montage-grid",
  "photo_count": 142,
  "photos": [
    {
      "filename": "sayno_abc123.jpg",
      "public_id": "sayno/abc123",
      "email": "user@example.com"
    }
  ],
  "permanent_url": "https://pauseai.info/collages/sayno_v1.jpg",
  "emails_sent": 142,
  "email_log": "logs/email-v1.log"
}
```

## Key Learnings from Bootstrap Session (#500)

Applied from successful email to 142 users:
1. **Cloudinary API**: Use `resources/image/moderations/manual/approved` endpoint
2. **Email Success**: 2-second rate limiting, multipart (plain+HTML), personal tone
3. **Email Capture**: 93.4% capture rate achieved
4. **Data Safety**: Don't commit sensitive data (emails, caches)
5. **User Engagement**: One user asked about newsletter signup → include in emails

## Backfill Strategy

**142+ existing approved photos in sayno/** (from bootstrap session #500):
- Already emailed once via manual script
- Users **expect** to be contacted by production system
- These users are "test-in-production" before publicity ramp-up
- Need to be included in first production collage

**Confirmed approach (using webhooks):**

```python
# Phase 4: One-time prod backfill
for photo in cloudinary.resources_by_moderation('manual', 'approved', prefix='sayno'):
    # Step 1: Set to pending (triggers webhook - ignored by processor)
    cloudinary.api.update(photo['public_id'], moderation_status='pending')
    time.sleep(0.5)  # Rate limiting

    # Step 2: Set back to approved (triggers webhook - processed)
    cloudinary.api.update(photo['public_id'], moderation_status='approved')
    # → Webhook → Lambda → Download image + fetch email → Save to /mnt/efs/prod/
```

**Total:** 284 Admin API calls (2 per photo), ~2 minutes runtime

**Same strategy for dev backfill** (Phase 3) using `prefix='test_prototype'`

## Open Questions / TK

1. **Admin Access**: How many admins? HTTP Basic Auth sufficient for MVP?
2. **Domain**: Where to host webapp? `collage-admin.pauseai.info`?
3. **Collage URLs**: Where to serve published images? `pauseai.info/collages/sayno_v1.jpg`?
4. **GDPR**: Email handling compliance, unsubscribe mechanism

## AWS Resources (Phase 0)

**Account**: PauseAI (719154425282)
**Region**: us-east-1

| Resource | ID | Details |
|----------|----|----|
| EC2 Instance | i-05674280f86f51a75 | Ubuntu 22.04, t3.micro, 3.85.173.169 |
| EFS Filesystem | fs-001b5fdce1b4db8c8 | Mounted at /mnt/efs |
| Security Group | sg-0373b27f58f4dfa48 | Ports 22, 80, 2049 |
| SSH Key | collagen-server-key | ~/.ssh/collagen-server-key.pem |

**Services running on EC2:**
- webhook-receiver.service (Flask on port 8080)
- nginx (reverse proxy 80 → 8080)

**Cloudinary webhook:**
- Trigger ID: `0784a23497ead91ace28a2564f2fdb130fe17df07b2e786a36900af404860ab7`
- URL: `http://3.85.173.169/webhook/moderation`
- Event type: `moderation`

## Security Notes

- **Secrets**: Cloudinary API secret in .env (not committed), AWS keys in ~/.aws/credentials
- **SSH**: Key-based auth only on EC2 (dynamic IP requires security group updates)
- **EFS**: Security group restricts NFS (port 2049) to self-referencing
- **Email Data**: Never commit to Git
- **Webhook Validation**: Verify Cloudinary signatures on webhook payloads (X-Cld-Signature header)

## Cost Target

| Service | Monthly Cost |
|---------|--------------|
| EC2 t3.micro (free tier 12mo) | $0 → $7 |
| EFS (30GB) | $9 |
| API Gateway (if webhooks) | ~$0 at our scale |
| Lambda (if webhooks) | ~$0 at our scale |
| SQS (if webhooks) | ~$0 at our scale |
| **Total** | **$9-16/month** |

## Rate Limit Analysis

**Cloudinary Admin API:**
- Free plan: 500 requests/hour
- Paid plans: 2000 requests/hour
- PauseAI is on standard paid plan

**Webhook-based sync (ongoing):**
- Zero Admin API calls (webhooks push to us)
- Only fetches: 1 API call per approved photo to get metadata
- At 5000 photos over months: ~1 call/hour average ✅

**Backfill (one-time operations):**
- 142 photos × 2 API calls (pending + approved) = 284 calls
- Plus 142 metadata fetches = 426 total calls
- Runtime: ~5 minutes (with 0.5s sleep between calls)
- Well under 2000/hour limit ✅

## References

- Issues: #436, #437, #488, #500
- Bootstrap summary: `20251001T00.sayno-bootstrap-collage-notification.summary.md`
- FastAPI docs: https://fastapi.tiangolo.com/
- ImageMagick montage: https://imagemagick.org/script/montage.php
- Cloudinary moderation docs: https://cloudinary.com/documentation/moderate_assets
- Cloudinary webhooks docs: https://cloudinary.com/documentation/notifications
