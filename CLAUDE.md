# Collagen - AI Assistant Context

## Project Overview

Automated collage pipeline for "Say No" campaign photos. Users upload selfies with protest signs to Cloudinary, system generates collages, sends tracking emails, and monitors engagement.

**Production URL**: https://collagen.pauseai.info
**Current Status**: Live in production, 266 users emailed, 67 subscribed
**Repository**: https://github.com/PauseAI/pauseai-collagen

## Quick Start

```bash
# Local development
cd pauseai-collagen
source venv/bin/activate  # Python 3.10.12

# Run webapp locally
python webapp/main.py     # Port 8000

# SSH to production
ssh -i ~/.ssh/collagen-server-key.pem ubuntu@3.85.173.169

# Check production status
./scripts/check_tracking_stats.py sayno
```

## System Architecture

```
Photo Upload → Cloudinary → Webhook → API Gateway → Lambda → SQS → EC2 Worker
                                                                      ↓
Users ← Email ← Tracking System ← SQLite ← Collage Generator ← EFS Storage
```

**Key Components:**
- **Cloudinary**: Photo moderation and storage
- **AWS Lambda**: Webhook validation, tracking routes
- **EC2 + EFS**: Collage generation, data persistence
- **S3**: Published collage hosting
- **SMTP**: Email delivery via sayno@pauseai.info

## Current Production Metrics

- **Campaigns**: `sayno` (production), `test_prototype` (dev)
- **Total tiles**: 290 available, 266 used in latest collage
- **Email stats**: 78% open rate, 65.5% human opens (bot detection: 10s)
- **Engagement**: 76 validated, 67 subscribed, 15 shared
- **Active experiments**: None (X001/X002 complete)
- **Latest build**: 20251031T231001Z,285=19x15

## Filesystem Structure

```
/mnt/efs/
├── sayno/                    # Production campaign
│   ├── sources/              # Original JPEGs with EXIF
│   ├── tiles/                # 300×400 PNGs for collages
│   ├── collages/             # Generated collages
│   │   └── {build_id}/
│   │       ├── renders/      # Individual tile renders
│   │       ├── 4096.png      # Full resolution
│   │       ├── 4096.jpg      # Cropped JPEG
│   │       ├── 1024.jpg      # Web derivative
│   │       └── manifest.json # Metadata
│   ├── tracking.db           # SQLite engagement data
│   └── logs/
├── test_prototype/           # Dev campaign
└── system-logs/              # Service logs (backed up)
```

## Key Files & Tools

### Production Scripts
```bash
# Build new collage
./tools/build_collage.py sayno [num_tiles]

# Send email notifications
./scripts/send_notifications.py sayno BUILD_ID [--dry-run]

# Publish to S3
./scripts/publish_collage.py sayno BUILD_ID

# Check tracking statistics
./scripts/check_tracking_stats.py sayno [--email user@example.com]

# Database queries
./tools/sqlite_exec.py sayno "SELECT * FROM users WHERE validated = 1"
```

### Configuration
- **Environment**: `.env` file (not committed) - CLOUDINARY_*, GMAIL_APP_PASSWORD
- **AWS Config**: `.aws-config` file - Instance IDs, EFS ID, etc.
- **Constants**: `lib/constants.py` - DERIVATIVE_SIZES, BOT_SECS, etc.

## Development Workflow

1. **Testing changes locally**:
   ```bash
   ./tools/sync_tiles_from_ec2.py test_prototype
   python webapp/main.py  # Test webapp
   ```

2. **Deploying changes**:
   ```bash
   # Deploy ingestor changes
   scp -i ~/.ssh/collagen-server-key.pem scripts/sqs_ingestor.py ubuntu@3.85.173.169:~/collagen/scripts/
   ssh -i ~/.ssh/collagen-server-key.pem ubuntu@3.85.173.169 "sudo systemctl restart collagen-ingestor"

   # Deploy tracking worker changes
   scp -i ~/.ssh/collagen-server-key.pem scripts/tracking_worker.py ubuntu@3.85.173.169:~/collagen/scripts/
   ssh -i ~/.ssh/collagen-server-key.pem ubuntu@3.85.173.169 "sudo systemctl restart collagen-tracking-worker"
   ```

3. **Monitoring**:
   ```bash
   # Check service logs
   sudo journalctl -u collagen-ingestor -f
   sudo journalctl -u collagen-tracking-worker -f

   # View persisted logs on EFS
   tail -f /mnt/efs/system-logs/collagen-ingestor.log
   ```

## Tracking System

**User states**: emailed → opened → validated → subscribed
**Share platforms**: Facebook, Twitter, WhatsApp, LinkedIn, Reddit

**Database schema** (`tracking.db`):
- `users`: uid, email, build_id, states, timestamps
- `collages`: build_id, photo_count, grid, publish info
- `shares`: uid, platform, timestamp, referrer

**Tracking URLs**:
- Open: `https://collagen.pauseai.info/{campaign}/open/{uid}/{build_id}`
- Validate: `https://pauseai.info/sayno?uid={uid}&build={build_id}`
- Subscribe: `https://pauseai.info/join?uid={uid}&build={build_id}&email={email}`
- Share: `https://collagen.pauseai.info/{campaign}/share/{platform}/{uid}/{build_id}`

## Email System

- **SMTP**: Google Workspace via sayno@pauseai.info
- **Template**: HTML + plain text multipart
- **Rate limiting**: 2 seconds between sends
- **A/B testing**: Experiment framework via URL parameters

## AWS Resources

| Resource | ID | Purpose |
|----------|----|----|
| EC2 | i-05674280f86f51a75 | Ubuntu 22.04, services |
| EFS | fs-001b5fdce1b4db8c8 | Persistent storage |
| Lambda | collagen-webhook-validator | Cloudinary webhooks |
| Lambda | collagen-tracking-router | User tracking |
| S3 | pauseai-collagen | Collage hosting |
| SQS | collagen-webhook-queue | Webhook processing |
| SQS | collagen-tracking-queue | Tracking events |
| API Gateway | collagen-webhook-api | Public endpoints |

## Backup & Recovery

- **EFS Backup**: Daily (14d), Weekly (60d), Monthly (365d) via AWS Backup
- **System Logs**: Redirected to EFS (`/mnt/efs/system-logs/`)
- **EC2 Recreation**: Use scripts in `setup/` directory
- **Known Issue**: EC2 backup impossible (AWS policy bug - missing ec2:DescribeTags)

## Common Tasks

### Process new photos manually
```python
./tools/redrive_folder.py sayno  # Re-trigger webhooks for all approved
```

### Debug tracking issues
```bash
# Check specific user
./scripts/check_tracking_stats.py sayno --email user@example.com

# View share activity
./tools/sqlite_exec.py sayno "SELECT * FROM shares ORDER BY shared_at DESC LIMIT 10"
```

### Emergency rollback
```bash
# Restore from S3 if needed
aws s3 cp s3://pauseai-collagen/sayno/latest-4096.jpg /tmp/
aws s3 ls s3://pauseai-collagen/sayno/ --recursive
```

## Security Notes

- **Secrets**: Never commit `.env`, `.aws-config`, or email data
- **Webhook validation**: SHA-1 signatures verified
- **SSH**: Key-based auth only (dynamic IP requires SG update)
- **Email privacy**: EXIF metadata, not in manifests

## Cost Management

| Service | Monthly | Notes |
|---------|---------|-------|
| EC2 t3.micro | $7 | After free tier |
| EFS | $9 | ~30GB storage |
| S3 | <$1 | Minimal usage |
| Lambda/API/SQS | <$1 | Low volume |
| CloudWatch | <$0.01 | <1MB/month |
| **Total** | **~$17** | Well under $20 target |

## Active Development

See [Issue #13](https://github.com/PauseAI/pauseai-collagen/issues/13) for post-MVP enhancements:
- Automation improvements
- Web app enhancements
- Subscriber update system
- Operational improvements

## References

- **Project History**: See PROJECT_HISTORY.md for development timeline
- **Issues**: #7 (MVP complete), #12 (Backup complete), #13 (Enhancements)
- **Website Integration**: pauseai-website PR #526 (merged), #536 (pending)
- **Session Summaries**: pauseai-l10n/notes/summary/