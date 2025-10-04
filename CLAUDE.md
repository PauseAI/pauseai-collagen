# Collagen - AI Assistant Context

## Project Overview

Automated collage pipeline for campaign photos. Currently driving: "Say No" campaign.
Named "collagen" to support multiple future campaigns beyond "sayno".

## Current Status

**Phase**: Repository initialization complete, ready for AWS setup
**Branch**: main
**Last Updated**: 2025-10-04

### Completed
- [x] Architecture planning (see ORIGINAL_PROJECT_PLAN.md)
- [x] Cloudinary capabilities research
- [x] Webhook vs polling analysis
- [x] Git repository initialized
- [x] .gitignore configured
- [x] Project documentation structured (README.md, CLAUDE.md)

### Next Steps
- [ ] Initial commit
- [ ] Create GitHub repo: `PauseAI/pauseai-collagen`
- [ ] Set up AWS account, configure credentials
- [ ] Provision EC2 + EFS infrastructure
- [ ] Test webhook behavior with Cloudinary
- [ ] Implement sync service (webhooks or polling based on test results)
- [ ] Build collage generation + webapp
- [ ] Implement email notification system

## Tech Stack

- **Python 3.12+**: Core language
- **FastAPI**: Web framework for admin UI
- **AWS EC2 + EFS**: Hosting + persistent storage
- **ImageMagick**: Collage generation (Phase 1)
- **exiftool**: Metadata management (email addresses in EXIF)
- **Sync Method**: TBD after webhook testing
  - Option A: API Gateway + SQS + Lambda (event-driven)
  - Option B: systemd timer + Python script (polling)
- **Google Workspace SMTP**: Email delivery (sayno@pauseai.info)

## Architecture Decision: Webhooks vs Polling

### Research Findings

**Cloudinary Capabilities:**
- ✅ Supports moderation webhooks via `notification_url` parameter
- ✅ Can configure global webhook URL via Console or Admin API triggers
- ✅ Admin API `update` method can change moderation status
- ❌ Collage generation deprecated (Sept 2025) - must use own tools
- ❌ Metadata limited (255 char total) - not suitable for state tracking

**Webhooks (if tests confirm):**
- Event-driven: approval → instant notification
- No API polling = zero rate limit concerns
- SQS provides: retries, DLQ, at-least-once delivery
- Simpler state: filesystem is write-only, no diffing needed
- Scales identically for 142 or 5000 photos

**Polling (fallback):**
- Simple: one Python script + systemd timer
- No AWS webhook infrastructure needed
- Works retroactively: first poll gets all approved photos
- API calls: ~7 calls per sync for 200 photos (max_results=30)
- 30-60 min latency (acceptable per requirements)

### Testing Plan (Phase 0)

1. Deploy simple webhook receiver on EC2
2. Configure Cloudinary global webhook to EC2 endpoint
3. Test:
   - Upload test image with `moderation=manual`
   - Manually approve → verify webhook fires
   - Re-approve same image → verify webhook fires again (for backfill)
   - Inspect payload for `context.custom.email` field
4. Make architecture decision based on results

### Critical Unknowns (to be tested)

- Does global webhook URL apply to manual moderation events?
- Will re-approving already-approved photos trigger webhooks?
- Does webhook payload include email metadata?

## Filesystem Structure (Planned)

```
/mnt/efs/
├── dev/
│   ├── approved/         # Synced photos with EXIF metadata
│   │   ├── sayno_abc123.jpg   # public_id embedded in filename
│   │   └── sayno_def456.jpg
│   ├── collages/         # Generated collages + manifests
│   │   ├── preview.jpg   # Working preview (not published)
│   │   ├── v1.jpg        # Published collages
│   │   ├── v1.json       # Manifest: photos included, emails sent
│   │   └── v2.jpg
│   └── logs/
│       └── sync.log
└── prod/
    └── [same structure]
```

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

## Open Questions / TK

1. **Webhook behavior**: Needs empirical testing (Phase 0)
2. **Admin Access**: How many admins? HTTP Basic Auth sufficient for MVP?
3. **Domain**: Where to host webapp? `collage-admin.pauseai.info`?
4. **Collage URLs**: Where to serve published images? `pauseai.info/collages/sayno_v1.jpg`?
5. **GDPR**: Email handling compliance, unsubscribe mechanism
6. **Backfill Strategy**: Re-moderate 142 existing photos or initial polling sync?

## Backfill Context

**142 existing approved photos** (from bootstrap session #500):
- Already emailed once via manual script
- Users **expect** to be contacted by production system
- These users are "test-in-production" before publicity ramp-up
- Need to be included in first production collage

**Backfill Options:**
1. **If webhooks work**: Use Admin API to re-approve → triggers webhooks → syncs to EFS
2. **If polling**: First poll sync gets all 142 automatically

## Security Notes

- **Secrets**: Cloudinary API keys, Google Workspace password in environment variables only
- **SSH**: Key-based auth only on EC2
- **EFS**: Security group restricts to EC2 instance
- **Email Data**: Never commit to Git
- **Webhook Validation**: Verify Cloudinary signatures on webhook payloads

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

**Polling at 30-min intervals:**
- 200 approved photos ÷ 30 per page = 7 API calls per sync
- 2 syncs/hour = 14 calls/hour
- Well under 2000/hour limit ✅

**Webhooks:**
- Zero Admin API calls for ongoing sync
- Only backfill uses API (one-time)

## References

- Issues: #436, #437, #488, #500
- Bootstrap summary: `20251001T00.sayno-bootstrap-collage-notification.summary.md`
- FastAPI docs: https://fastapi.tiangolo.com/
- ImageMagick montage: https://imagemagick.org/script/montage.php
- Cloudinary moderation docs: https://cloudinary.com/documentation/moderate_assets
- Cloudinary webhooks docs: https://cloudinary.com/documentation/notifications
