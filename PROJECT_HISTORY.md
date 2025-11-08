# Collagen Project History

## Timeline of Development

### Phase 0: Research & Setup (2025-10-05)
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

### Phase 1: EC2 Direct Webhook (Dev Testing)
- [x] EC2 webhook processor implemented with dual-size storage
- [x] Webhook signature validation (SHA-1 + timestamp)
- [x] Campaign-specific logging to EFS
- [x] Format normalization (f_jpg for all inputs)
- [x] Email sanitization for test campaigns
- [x] Grid optimization algorithm for 4K collages
- [x] Redrive mechanism for backfills
- [x] Performance validation (35-49s collage generation)

### Phase 2A: Production Infrastructure (2025-10-20)
- [x] Lambda signature validation
- [x] API Gateway + SQS architecture
- [x] Public ID migration (26 images: test_prototype/ → sayno/ prefix)
- [x] Terminology adoption (ingestor, sources, tiles, renders)
- [x] Sayno campaign enabled + backfilled (238 tiles ingested)

### Phase 2B: Collage Generation Web UI (2025-10-23)
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

### Phase 3: Tracking Infrastructure (2025-10-25)
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

### Social Share Tracking (2025-10-27)
- [x] Lambda share routes (5 platforms: Facebook, Twitter, WhatsApp, LinkedIn, Reddit)
- [x] SQLite shares table with migration script
- [x] Tracking worker share intent handling
- [x] End-to-end testing on test_prototype campaign
- [x] Lambda deployed to AWS

### Collage Derivatives Optimization (2025-10-29)
- [x] DERIVATIVE_SIZES constant [4096, 1024, 400]
- [x] JPEG quality optimization (90 → 85)
- [x] Upload script handles all three sizes

### Website Integration (2025-10-29)
- [x] Open Graph metadata with collage images for social sharing
- [x] S3 image integration on /sayno and book pages
- [x] Contextual messaging for email tracking links (validate/subscribe)
- [x] pauseai-website PR #521 (merged)

### Production Deployment (2025-10-31)
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

### A/B Testing Framework (2025-11-05)
- [x] **X001 Experiment** - CTA positioning A/B test
  - Treatment variant launched as default (streamlined layout won on all metrics)
- [x] **X002 Experiment** - Post-action sharing A/B test
  - X002 launched to 40 users (20v20, control hides sharing via x002 parameter)
  - Treatment won decisively (21.4% vs 0.0% share rate)
  - Deployed to all users

### Bot Detection (2025-11-07)
- [x] BOT_SECS=10 threshold implemented
- [x] Human opens backfilled from Lambda logs
- [x] True open rate analysis (65.5% human vs 78% with bots)

### Production Protection (2025-11-08)
- [x] AWS Backup configured for EFS (daily/weekly/monthly)
- [x] System logs redirected to EFS for backup coverage
- [x] Backup strategy validated and documented

## Webhook Test Results (Phase 0 - 2025-10-05)

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

## Key Learnings from Bootstrap Session (#500)

Applied from successful email to 142 users:
1. **Cloudinary API**: Use `resources/image/moderations/manual/approved` endpoint
2. **Email Success**: 2-second rate limiting, multipart (plain+HTML), personal tone
3. **Email Capture**: 93.4% capture rate achieved
4. **Data Safety**: Don't commit sensitive data (emails, caches)
5. **User Engagement**: One user asked about newsletter signup → include in emails

## Performance Benchmarks

- **Collage from sources**: 163s for 999 images (too slow)
- **Collage from tiles**: 49s for 999 images (acceptable)
- **Production build (266 images)**: ~2m23s
- **Ingestion overhead**: +0.2s per tile

## Architecture Evolution

**Phase 1A: EC2 Direct**
```
Cloudinary → EC2 Flask app → EFS
```

**Phase 2A: Production (Current)**
```
Cloudinary → API Gateway → Lambda (sig validation) → SQS → EC2 Ingestor → EFS
                                ↓                      ↓ 14-day retention
                           Validates signatures    Per-campaign routing
```