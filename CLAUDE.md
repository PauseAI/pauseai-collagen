# Collagen - AI Assistant Context

## Project Overview

Automated collage pipeline for campaign photos. Currently driving: "Say No" campaign.
Named "collagen" to support multiple future campaigns beyond "sayno".

## Current Status

**Phase**: Production deployment complete - Phased rollout in progress
**Branch**: main
**Last Updated**: 2025-10-31
**Production Build**: 20251024T230728Z,266=19x14 (266 images, 281 tiles available)
**Tracking Infrastructure**: Deployed and operational at collagen.pauseai.info
**Email Sending**: Production emails sent to 12 users (trusted members), 233 remaining
**Share Tracking**: Deployed to production sayno campaign, first share tracked (#11)
**Website Integration**: Deployed to production (PR #526 merged, /join and /sayno fixes committed to main)

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
- [x] **Phase 2A: Production webhook pipeline**
- [x] Lambda signature validation
- [x] API Gateway + SQS architecture
- [x] Public ID migration (26 images: test_prototype/ → sayno/ prefix)
- [x] Terminology adoption (ingestor, sources, tiles, renders)
- [x] Sayno campaign enabled + backfilled (238 tiles ingested)
- [x] **Phase 2B: Collage generation web UI**
- [x] Core library modules (grid_optimizer, collage_generator, workflow)
- [x] CLI tool for interactive collage building
- [x] FastAPI webapp with Bootstrap 5 templates
- [x] Simplified route structure (no /campaign/ prefix)
- [x] Build ID format: YYYYMMDDTHHMMSSZ,N=CxR
- [x] Transparent PNG padding, cropped JPEG derivatives
- [x] Local testing successful (test_prototype, 20 tiles, 5×4 grid)
- [x] **Phase 2B validation complete** (2025-10-23)
- [x] JPEG crop bug fixed (centered padding handling)
- [x] Tile selection bug fixed (montage pagination issue resolved)
- [x] Production collage built (266 images, clean email uniqueness)
- [x] Deployed to EC2 with COLLAGEN_DATA_DIR environment config
- [x] **Phase 3: Tracking infrastructure** (2025-10-25)
- [x] SQLite tracking database (users + collages tables)
- [x] TrackingDB library with UID generation and idempotent updates
- [x] S3 bucket for collage images (pauseai-collagen)
- [x] Upload script (build_id + latest)
- [x] SQS queue (collagen-tracking-queue)
- [x] Lambda + API Gateway (collagen.pauseai.info)
- [x] EC2 tracking worker (systemd service)
- [x] Custom domain with ACM cert + DNS
- [x] End-to-end testing with real collage data
- [x] Inspection tools (check_tracking_stats.py)
- [x] **SMTP setup and testing** (2025-10-25)
- [x] DKIM enabled for pauseai.info domain
- [x] sayno@pauseai.info account created (2FA + app password)
- [x] SMTP tested locally and from EC2 (all auth passing)
- [x] **Social share tracking** (2025-10-27) - #11
- [x] Lambda share routes (5 platforms: Facebook, Twitter, WhatsApp, LinkedIn, Reddit)
- [x] SQLite shares table with migration script
- [x] Tracking worker share intent handling
- [x] End-to-end testing on test_prototype campaign
- [x] Lambda deployed to AWS
- [x] **Collage derivatives optimization** (2025-10-29)
- [x] DERIVATIVE_SIZES constant [4096, 1024, 400]
- [x] JPEG quality optimization (90 → 85)
- [x] Upload script handles all three sizes
- [x] **Website integration** (2025-10-29) - pauseai-website PR #521
- [x] Open Graph metadata with collage images for social sharing
- [x] S3 image integration on /sayno and book pages
- [x] Contextual messaging for email tracking links (validate/subscribe)
- [x] **Production deployment** (2025-10-31) - #6, #7, #11
- [x] Share tracking migration on production sayno campaign
- [x] Email template refactored (HTML + plain text in parallel)
- [x] Email parameter added to subscribe URLs for auto-fill
- [x] Allowlist created for phased rollout (11 trusted PauseAI members)
- [x] Production emails sent (12 users: 1 test + 11 trusted members)
- [x] End-to-end tracking validated (emailed, opened, validated, subscribed, shared)
- [x] /join page fixed for collagen users (banner + pre-fill, no auto-submit)
- [x] /sayno validation bug fixed (added 'validated' state)
- [x] Duplicate email detection improved in manifest generation
- [x] First production share tracked (Tom Bibby - Twitter)

### Next Steps
- [ ] Monitor feedback from trusted members
- [ ] Full production rollout to remaining 233 sayno users
- [ ] UX improvements (score breakdown, custom grid live preview)
- [ ] AWS Backup for EFS
- [ ] Monitoring and handoff documentation

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

**Ingestion approach (Phase 2A - implemented):**
1. Webhook arrives with public_id, secure_url
2. Lambda validates Cloudinary signature → queues to SQS
3. EC2 ingestor polls SQS, fetches metadata via API (asset_folder, email) + downloads image to /tmp as JPG (parallel)
4. Filter by asset_folder (test_prototype and sayno campaigns)
5. Sanitize email for test campaigns only (→ collagen-test+...@antb.me)
6. Embed email in EXIF UserComment
7. Save source JPEG to `sources/`
8. Generate 300×400 PNG tile to `tiles/`
9. Log to campaign-specific `ingestor.log`

**Rejection handling:**
- Delete both source JPEG and tile PNG
- Pending webhooks ignored by ingestor (limbo state, not rejection)

### Why Webhooks Won

- **Event-driven**: Instant sync on moderation events (vs 30-60 min polling lag)
- **Zero polling overhead**: No API calls when nothing changes
- **Scalable**: 142 or 5000 photos, same architecture
- **Backfill viable**: API can trigger webhooks via status toggle
- **Production-grade**: SQS provides retries, DLQ, at-least-once delivery (Cloudinary: 3 retries over 9 min)
- **Simpler logic**: No state diffing, filesystem is append-only (delete on reject)

### Sync Architecture Evolution

**Phase 1A: EC2 Direct (Completed - Dev Testing)**
```
Cloudinary → EC2 Flask app → EFS
```
- Fast iteration, simple debugging
- Filtered: only ingested `asset_folder=test_prototype`
- Risk: Lost webhooks if EC2 down during Cloudinary's 9-min retry window

**Phase 2A: API Gateway + Lambda + SQS (Completed - Production)**
```
Cloudinary → API Gateway → Lambda (sig validation) → SQS → EC2 Ingestor → EFS
                                ↓ extracts campaign      ↓ 14-day retention
                           Validates signatures    Per-campaign routing
```
- API Gateway routes to Lambda (AWS_PROXY)
- Lambda validates Cloudinary SHA-1 signature, rejects invalid (401)
- Lambda extracts campaign from `public_id` prefix, sets as SQS MessageAttribute
- SQS provides durability (14-day retention), DLQ for failed ingestion
- EC2 ingestor polls SQS, downloads images, writes sources/ + tiles/ to EFS
- Per-campaign CloudWatch metrics via SQS MessageAttributes

## Filesystem Structure (Campaign-Agnostic)

```
/mnt/efs/
├── test_prototype/       # Dev campaign (asset_folder from API)
│   ├── sources/          # Archive: 1500×2000 JPEG with EXIF metadata (~200KB each)
│   │   ├── selfie_abc123.jpg
│   │   └── selfie_def456.jpg
│   ├── tiles/            # Tile inputs: 300×400 PNG (~175KB each)
│   │   ├── selfie_abc123.png  # Generated from source JPEG during ingestion
│   │   └── selfie_def456.png  # Email preserved in EXIF of source
│   ├── collages/         # Generated collages + manifests (Phase 2B)
│   │   ├── 20251012T143022Z,20=5x4/  # Build ID: timestamp,images=colsxrows
│   │   │   ├── renders/       # Grid-sized renders (generated during composition)
│   │   │   ├── 4096.png       # 4K PNG collage (transparent padding)
│   │   │   ├── 4096.jpg       # 4K JPEG (cropped to actual collage size)
│   │   │   ├── 1024.jpg       # JPEG derivative (1024px, cropped)
│   │   │   └── manifest.json  # Manifest: layout, tiles included, publish status
│   │   └── 20251013T091500Z,238=17x14/
│   │       └── [same structure]
│   └── logs/
│       ├── ingestor.log  # Main events: INGESTED/DELETED/ERROR
│       ├── webhooks/     # Cloudinary webhook logs (archived from Lambda)
│       │   └── YYYYMMDD/
│       │       └── HHMMSS.{status}.{public_id}.json
│       └── email-v1.log  # Email send logs per collage (Phase 3)
├── sayno/                # Production campaign (Phase 2A)
│   └── [same structure]
└── future_campaign/      # Future campaigns
    └── [same structure]
```

**Dual-size ingestion:**
- Source JPEG (1500×2000): Archive quality, EXIF metadata preservation
- Tile PNG (300×400): Pre-generated base for collage rendering
- Path convention: `tile_for_source(source_path)` enforces consistency

**Ingestor routing:** `asset_folder` from API → `/mnt/efs/{asset_folder}/`

**Why dual storage:**
- Collage from sources: 163s for 999 images (too slow)
- Collage from tiles: 49s for 999 images (tiles → renders → montage within HTTP timeout)
- Ingestion overhead: +0.2s per tile (acceptable)

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

- **Secrets**: Cloudinary API secret, SMTP app password in .env (not committed), AWS keys in ~/.aws/credentials
- **SSH**: Key-based auth only on EC2 (dynamic IP requires security group updates)
- **EFS**: Security group restricts NFS (port 2049) to self-referencing
- **Email Data**: Never commit to Git
- **Webhook Validation**: Verify Cloudinary signatures on webhook payloads (X-Cld-Signature header)
- **SMTP Auth**: App password (16 chars), requires 2FA on sayno@pauseai.info

## Cost Target

| Service | Monthly Cost |
|---------|--------------|
| EC2 t3.micro (free tier 12mo) | $0 → $7 |
| EFS (30GB) | $9 |
| API Gateway | ~$0 at our scale |
| Lambda | ~$0 at our scale |
| SQS | ~$0 at our scale |
| Google Workspace (nonprofit) | $0 (free tier, <2000 users) |
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

**Email sending (SMTP via Google Workspace):**
- Free tier limit: 2,000 emails/day per user
- Current need: 266 emails per collage (well under limit)
- No API calls, direct SMTP connection ✅

**Backfill (one-time operations):**
- 142 photos × 2 API calls (pending + approved) = 284 calls
- Plus 142 metadata fetches = 426 total calls
- Runtime: ~5 minutes (with 0.5s sleep between calls)
- Well under 2000/hour limit ✅

## Development Quick Reference

**Python environment:**
```bash
cd pauseai-collagen
source venv/bin/activate  # Python 3.10.12 via pyenv
```

**Common tools:**
```bash
# Sync tiles from EC2 to local
./tools/sync_tiles_from_ec2.py test_prototype

# Build collage interactively (CLI)
./tools/build_collage.py test_prototype      # Use all tiles
./tools/build_collage.py test_prototype 20   # Use 20 oldest tiles

# Run webapp locally
python webapp/main.py                        # Port 8000
# or
uvicorn webapp.main:app --reload --port 8000

# Toggle single test image (approve/reject)
./venv/bin/python3 tools/toggle_test_image.py

# Redrive entire folder (re-sync all approved images)
./venv/bin/python3 tools/redrive_folder.py test_prototype

# List all Cloudinary images with metadata
./venv/bin/python3 tools/list_all_images.py

# Grid optimizer (edit OMIT_BASE_COST, PAD_COST, CLIP_COST at top)
./venv/bin/python3 tools/optimize_grid_v3.py

# Test SMTP sending (local or EC2)
./tools/test_smtp.py recipient@example.com

# Production tools (run on EC2)
./tools/sqlite_exec.py sayno "SELECT uid, email FROM users WHERE email LIKE '%example%'"
./scripts/check_tracking_stats.py sayno
./scripts/check_tracking_stats.py sayno --email user@example.com
./scripts/send_notifications.py sayno BUILD_ID --dry-run
./scripts/send_notifications.py sayno BUILD_ID --uid ABC123
./scripts/publish_collage.py sayno BUILD_ID
./scripts/migrate_add_shares_table.py sayno
```

**Check EFS on EC2:**
```bash
ssh -i ~/.ssh/collagen-server-key.pem ubuntu@3.85.173.169 "ls /mnt/efs/test_prototype/{sources,tiles}"

# Ingestor logs
ssh -i ~/.ssh/collagen-server-key.pem ubuntu@3.85.173.169 "sudo journalctl -u collagen-processor -n 50"

# Campaign log
ssh -i ~/.ssh/collagen-server-key.pem ubuntu@3.85.173.169 "tail /mnt/efs/test_prototype/logs/ingestor.log"
```

**Deploy ingestor changes:**
```bash
scp -i ~/.ssh/collagen-server-key.pem scripts/processor.py ubuntu@3.85.173.169:~/collagen/scripts/
ssh -i ~/.ssh/collagen-server-key.pem ubuntu@3.85.173.169 "sudo systemctl restart collagen-processor"
```

**Environment variables:**
- `.env` file (not committed): CLOUDINARY_*, GMAIL_APP_PASSWORD
- `.env.example` template in repo

**Current ingested data:**
- test_prototype: 20 tiles (sources + tiles with sanitized emails)
- sayno: 281 tiles (sources + tiles with real emails preserved)
- Production collage: 20251024T230728Z,266=19x14 (266 images, ~2m23s build time)

**Webapp routes:**
```
GET  /                               Dashboard (campaign list)
GET  /{campaign}                     Campaign page with embedded build form
POST /{campaign}/new                 Create new collage build
GET  /{campaign}/{build_id}          View completed build
GET  /{campaign}/{build_id}/{filename}  Serve images (4096.png, 4096.jpg, 1024.jpg)
```

## References

- Issues: #436, #437, #488, #500 (pauseai-website), #2, #3, #5, #6, #7, #8, #9, #11 (pauseai-collagen)
- Session summaries: pauseai-l10n/notes/summary/
- Bootstrap summary: `20251001T00.sayno-bootstrap-collage-notification.summary.md`
- Phase 2B summary: `20251013T00.phase2b-collage-webapp.summary.md`
- Phase 3 SMTP summary: `20251025T13.smtp-setup.summary.md`
- Production deployment summary: `20251031T14.email-tracking-validation-fixes.summary.md`
- FastAPI docs: https://fastapi.tiangolo.com/
- ImageMagick montage: https://imagemagick.org/script/montage.php
- Cloudinary moderation docs: https://cloudinary.com/documentation/moderate_assets
- Cloudinary webhooks docs: https://cloudinary.com/documentation/notifications
