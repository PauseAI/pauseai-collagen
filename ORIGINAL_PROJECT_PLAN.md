q# Say No Campaign - Automated Collage Pipeline Architecture

**Status**: Planning document for implementation
**Date**: 2025-10-01
**Related Issues**: #437 (architecture proposal), #488 (email content), #500 (bootstrap notification)

## Executive Summary

Build an automated pipeline to:
1. Likely: sync approved photos from Cloudinary to Pause AI storage e.g. copy images with metadata to AWS EFS
 - {tk: rather than alternative: all state stays in Cloudinary - explore capabilities amd costs}
2. Generate collages (simple grids → photomosaics over time) using image libraries
 - {tk: rather than alternative: more processing through Cloudinary transformations}
3. Support audited define/preview/publish workflow for trusted users
4. Email contributors on their first appearance in published collage

**Timeline**: MVP in a week, full features over months
**Cost**: ~$20-30/month (EC2 + EFS + Google Workspace email)

Even after we resolve "tk" to-know issues,
- there's a large space of possibilities, this is one sample point in it according to current guesses.
- many fine details are very arbitrary. Most will change.
- we will check in regularly about how to refine this target.


---

## Architecture Overview

```
Cloudinary (moderation) → Polling Sync (cron) → EFS Storage
                                                    ↓
Admin Webapp (FastAPI) ← reads/writes → Filesystem + EXIF metadata
                                                    ↓
                                        ImageMagick / Python libraries
                                                    ↓
                                        Collage Generation (preview → publish)
                                                    ↓
                                        Email Service (Google Workspace SMTP)
```

---

## Tech Stack Decisions

| Component | Choice | Rationale |
|-----------|--------|-----------|
| **Language** | Python 3.12+ | Team knows it, excellent image libraries |
| **Web Framework** | FastAPI | Minimal, modern, auto-generates docs |
| **Server** | AWS EC2 (Ubuntu 24.04 LTS) | Single host, easy to reason about |
| **Instance Type** | t3.micro → t3.small → t3.medium | Start free tier, upgrade as needed |
| **Storage** | AWS EFS | Persistent across instance replacements |
| **Metadata** | Filesystem + EXIF | Simple, inspectable, no DB complexity for MVP |
| **Collage State** | JSON manifests | Easy to read/edit, version control friendly |
| **Email** | Google Workspace SMTP | Already have it, 2000/day limit sufficient |
| **Deployment** | AWS CLI + shell scripts | Simple, direct, no new DSL |
| **Sync Mechanism** | Polling (cron every 5 min) | Reliable, simple, adequate latency |

---

## Component Breakdown

### 1. Sync Service

**Purpose**: Keep local EFS storage in sync with Cloudinary approved photos

**Implementation**: Python script run via systemd timer (cron replacement)

```python
# scripts/sync-cloudinary.py
import os
import requests
import json
from pathlib import Path
from datetime import datetime

def fetch_approved_photos(folder='sayno'):
    """
    Use Cloudinary moderation endpoint (learned from bootstrap session)
    Endpoint: resources/image/moderations/manual/approved
    """
    # Call Cloudinary API with Basic Auth
    # Filter to folder locally (API params unreliable)
    pass

def download_photo(cloudinary_url, local_path, metadata):
    """
    Download photo with metadata and embed email in EXIF
    """
    # Download file
    # exiftool -Comment="email@example.com" local_path
    # exiftool -Subject="photo_public_id" local_path
    pass

def sync(env='dev'):
    base = f'/mnt/efs/{env}'
    approved_dir = f'{base}/approved'

    # Get remote approved list
    remote = fetch_approved_photos(folder=f'sayno-{env}' if env == 'dev' else 'sayno')

    # Get local list (scan directory)
    local = set(os.listdir(approved_dir))

    # Download new ones
    for photo in remote:
        filename = f"{photo['public_id'].replace('/', '_')}.jpg"
        if filename not in local:
            download_photo(
                photo['secure_url'],
                f'{approved_dir}/{filename}',
                {'email': photo.get('context', {}).get('custom', {}).get('email')}
            )
            print(f"✓ Synced {filename}")
```

**Systemd Timer** (`/etc/systemd/system/collage-sync.timer`):
```ini
[Unit]
Description=Sync Cloudinary approved photos every 5 minutes

[Timer]
OnBootSec=1min
OnUnitActiveSec=5min

[Install]
WantedBy=timers.target
```

**Rate Limiting**: 2-second delay between downloads (per bootstrap session experience)

---

### 2. Filesystem Structure

```
/mnt/efs/
├── dev/
│   ├── approved/              # Synced photos with EXIF metadata
│   │   ├── sayno_abc123.jpg   # public_id embedded in filename
│   │   ├── sayno_def456.jpg
│   │   └── ...
│   ├── collages/
│   │   ├── preview.jpg        # Working preview (not published)
│   │   ├── v1.jpg             # Published collages
│   │   ├── v1.json            # Manifest (see below)
│   │   ├── v2.jpg
│   │   └── v2.json
│   └── logs/
│       └── sync.log
│
└── prod/
    └── [same structure]
```

**Collage Manifest Format** (`v1.json`):
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

**Metadata Extraction** (query EXIF without database):
```bash
# Get email from photo
exiftool -Comment sayno_abc123.jpg

# List all photos with emails
exiftool -Comment -csv approved/*.jpg | grep '@'

# Find photos not in any published collage
# (compare approved/*.jpg against all vN.json manifests)
```

---

### 3. Web Application

**Framework**: FastAPI with Jinja2 templates for simple HTML UI

**Routes**:

| Route | Method | Purpose |
|-------|--------|---------|
| `/` | GET | Dashboard: photo count, collage list, sync status |
| `/photos` | GET | Grid view of synced photos |
| `/collages` | GET | List all collages (published + previews) |
| `/collages/new` | POST | Generate new preview collage |
| `/collages/{id}/preview` | GET | View collage image |
| `/collages/{id}/publish` | POST | Publish collage → trigger emails |
| `/sync` | POST | Manual sync trigger (calls sync script) |
| `/health` | GET | Health check |

**Example Webapp Code**:
```python
# webapp/main.py
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from pathlib import Path
import subprocess

app = FastAPI()
templates = Jinja2Templates(directory="templates")

EFS_BASE = Path("/mnt/efs/prod")

@app.get("/")
async def dashboard(request: Request):
    approved = list((EFS_BASE / "approved").glob("*.jpg"))
    collages = list((EFS_BASE / "collages").glob("v*.json"))

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "photo_count": len(approved),
        "collage_count": len(collages)
    })

@app.post("/collages/new")
async def generate_preview():
    # Call ImageMagick montage
    subprocess.run([
        "montage",
        f"{EFS_BASE}/approved/*.jpg",
        "-tile", "20x20",
        "-geometry", "100x100+2+2",
        "-background", "#ffffff",
        f"{EFS_BASE}/collages/preview.jpg"
    ])
    return {"status": "preview generated"}

@app.post("/collages/{version}/publish")
async def publish_collage(version: str):
    # 1. Copy preview.jpg → v{N}.jpg
    # 2. Create manifest v{N}.json
    # 3. Upload to permanent URL
    # 4. Find new contributors (compare with previous manifests)
    # 5. Send emails
    pass
```

**Templates**: Simple Bootstrap 5 HTML for MVP

---

### 4. Collage Generation

**Phase 1 (MVP): ImageMagick Simple Grid**

```bash
# Generate 20x20 grid collage
montage /mnt/efs/prod/approved/*.jpg \
  -tile 20x20 \
  -geometry 100x100+2+2 \
  -background '#ffffff' \
  /mnt/efs/prod/collages/preview.jpg
```

**Phase 2: Photomosaic Libraries**

Investigate Python libraries:
- **`photomosaic`** (Python): Creates photomosaics from image collection
- **`foto-mosaik-edda`** (Python): Andrea Mosaic alternative
- **Custom PIL/Pillow**: Full control over tinting, positioning

Example investigation script:
```python
# Try photomosaic library
from photomosaic import mosaic

mosaic(
    target_image='pauseai_logo.png',
    tile_directory='/mnt/efs/prod/approved/',
    output_path='/mnt/efs/prod/collages/mosaic_preview.jpg',
    tile_size=(50, 50),
    enlargement=10
)
```

**Phase 3: Multiple Algorithms**

Support multiple algorithms in webapp dropdown:
- Simple grid (fast, always works)
- Photomosaic with "NO" text
- Photomosaic with Pause AI logo
- Random artistic layout

---

### 5. Email Notification Service

**Adapt Bootstrap Script** (`scripts/send-collage-notifications.ts` → Python)

**Key Changes from Bootstrap**:
1. Use Google Workspace SMTP (sayno@pauseai.info)
2. Only email NEW contributors (not in previous published collages)
3. Include engagement mechanisms per issue #488:
   - Email validation link
   - Newsletter signup
   - Petition links
   - Social sharing
4. Track bounces, opens (tracking pixel)

**Email Template** (draft):
```
Subject: Your photo is now in the Say No campaign collage

Hi there,

Great news! Your photo is now featured in version {N} of the Say No to
Superintelligent AI collage:

https://pauseai.info/collages/sayno_v{N}.jpg

You can see the full campaign page here:
https://pauseai.info/sayno

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Help us grow this campaign:

[ ] ✓ Validate my email (click here - helps us prove legitimacy)
[ ] ✓ Subscribe to PauseAI newsletter
[ ] ✓ Sign our main proposal petition
[ ] ✓ Share on social media [Twitter] [Facebook] [LinkedIn]

Or just confirm your participation: [Validate Email Only]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Thanks for standing with us,
The PauseAI Team

P.S. This is the single automated notification we promised. 

<img src="https://pauseai.info/api/track?email={hash}&collage=v{N}" width="1" height="1" />
```

**Implementation**:
```python
# scripts/send-notifications.py
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import json
import time

def get_new_contributors(current_manifest, previous_manifests):
    """
    Return emails of contributors in current collage but not in any previous
    """
    current_emails = {p['email'] for p in current_manifest['photos'] if p['email']}

    previous_emails = set()
    for manifest_path in previous_manifests:
        with open(manifest_path) as f:
            manifest = json.load(f)
            previous_emails.update(p['email'] for p in manifest['photos'] if p['email'])

    return current_emails - previous_emails

def send_email(to, version, smtp_config):
    """
    Send notification email via Google Workspace
    """
    msg = MIMEMultipart('alternative')
    msg['Subject'] = 'Your photo is now in the Say No campaign collage'
    msg['From'] = 'sayno@pauseai.info'
    msg['To'] = to

    # HTML and plain text versions
    # ... email content ...

    with smtplib.SMTP('smtp.gmail.com', 587) as server:
        server.starttls()
        server.login(smtp_config['user'], smtp_config['password'])
        server.send_message(msg)

    time.sleep(2)  # Rate limiting (per bootstrap session)
```

---

### 6. Deployment

**AWS Setup Script** (`setup/provision-aws.sh`):

```bash
#!/bin/bash
set -e

# Variables
REGION="us-east-1"
INSTANCE_TYPE="t3.micro"
AMI_ID="ami-0c7217cdde317cfec"  # Ubuntu 24.04 LTS
KEY_NAME="collage-server-key"
SECURITY_GROUP="collage-server-sg"

# 1. Create EFS
echo "Creating EFS..."
EFS_ID=$(aws efs create-file-system \
  --region $REGION \
  --performance-mode generalPurpose \
  --throughput-mode bursting \
  --encrypted \
  --tags Key=Name,Value=collage-storage \
  --query 'FileSystemId' \
  --output text)

echo "EFS created: $EFS_ID"
echo "Waiting for EFS to become available..."
aws efs wait file-system-available --file-system-id $EFS_ID

# 2. Create mount target (need VPC subnet)
SUBNET_ID=$(aws ec2 describe-subnets --region $REGION --query 'Subnets[0].SubnetId' --output text)

aws efs create-mount-target \
  --file-system-id $EFS_ID \
  --subnet-id $SUBNET_ID \
  --region $REGION

# 3. Create security group
SG_ID=$(aws ec2 create-security-group \
  --group-name $SECURITY_GROUP \
  --description "Collage server access" \
  --region $REGION \
  --query 'GroupId' \
  --output text)

# Allow SSH (22), HTTP (80), EFS (2049)
aws ec2 authorize-security-group-ingress \
  --group-id $SG_ID \
  --protocol tcp \
  --port 22 \
  --cidr 0.0.0.0/0

aws ec2 authorize-security-group-ingress \
  --group-id $SG_ID \
  --protocol tcp \
  --port 80 \
  --cidr 0.0.0.0/0

aws ec2 authorize-security-group-ingress \
  --group-id $SG_ID \
  --protocol tcp \
  --port 2049 \
  --source-group $SG_ID

# 4. Create key pair
aws ec2 create-key-pair \
  --key-name $KEY_NAME \
  --region $REGION \
  --query 'KeyMaterial' \
  --output text > ~/.ssh/$KEY_NAME.pem

chmod 400 ~/.ssh/$KEY_NAME.pem

# 5. Launch EC2 instance with user-data
aws ec2 run-instances \
  --image-id $AMI_ID \
  --instance-type $INSTANCE_TYPE \
  --key-name $KEY_NAME \
  --security-group-ids $SG_ID \
  --region $REGION \
  --user-data file://setup/cloud-init.sh \
  --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=collage-server-dev}]" \
  --block-device-mappings 'DeviceName=/dev/sda1,Ebs={VolumeSize=20}'

echo "Instance launching. Save these IDs:"
echo "EFS_ID=$EFS_ID"
echo "INSTANCE_ID=<from output above>"
```

**Cloud Init Script** (`setup/cloud-init.sh`):

```bash
#!/bin/bash
# Runs on first boot

set -e

# Update system
apt-get update
apt-get upgrade -y

# Install dependencies
apt-get install -y \
  python3.12 \
  python3-pip \
  imagemagick \
  exiftool \
  git \
  nfs-common \
  nginx

# Mount EFS (replace fs-xxxxx with actual ID)
EFS_ID="fs-xxxxx"  # Passed via environment or config
mkdir -p /mnt/efs
mount -t nfs4 -o nfsvers=4.1 ${EFS_ID}.efs.us-east-1.amazonaws.com:/ /mnt/efs

# Add to fstab for persistence
echo "${EFS_ID}.efs.us-east-1.amazonaws.com:/ /mnt/efs nfs4 nfsvers=4.1,rsize=1048576,wsize=1048576,hard,timeo=600,retrans=2,_netdev 0 0" >> /etc/fstab

# Create directory structure
mkdir -p /mnt/efs/{dev,prod}/{approved,collages,logs}

# Clone repository
git clone https://github.com/pauseai/sayno-collage-tool.git /opt/collage
cd /opt/collage

# Install Python dependencies
pip3 install -r requirements.txt

# Setup systemd services
cp setup/systemd/*.service /etc/systemd/system/
cp setup/systemd/*.timer /etc/systemd/system/

systemctl daemon-reload
systemctl enable collage-sync.timer
systemctl enable collage-webapp.service
systemctl start collage-sync.timer
systemctl start collage-webapp.service

# Configure nginx reverse proxy
cp setup/nginx/collage.conf /etc/nginx/sites-available/
ln -s /etc/nginx/sites-available/collage.conf /etc/nginx/sites-enabled/
systemctl restart nginx

echo "Setup complete!"
```

**Upgrade Instance Type**:
```bash
# Stop instance
aws ec2 stop-instances --instance-ids i-xxxxx

# Modify instance type
aws ec2 modify-instance-attribute \
  --instance-id i-xxxxx \
  --instance-type t3.small

# Start instance (EFS data persists!)
aws ec2 start-instances --instance-ids i-xxxxx
```

---

### 7. Development Workflow

**Separate Environments**:

| Aspect | Dev | Prod |
|--------|-----|------|
| **Cloudinary Folder** | `sayno-test/` | `sayno/` |
| **EFS Path** | `/mnt/efs/dev/` | `/mnt/efs/prod/` |
| **Webapp Port** | 8001 | 8000 |
| **Email** | Test mode (--dry-run) | Real sends |
| **Instance** | Shared dev server | Dedicated prod |

**Local Development** (before AWS):
```bash
# Mock EFS locally
mkdir -p /tmp/fake-efs/{dev,prod}/{approved,collages,logs}

# Run sync script
python scripts/sync-cloudinary.py --env=dev --efs-base=/tmp/fake-efs

# Run webapp
uvicorn webapp.main:app --reload --port 8000
```

**Testing Workflow**:
1. Upload test photos to `sayno-test/` folder in Cloudinary
2. Approve in Cloudinary moderation UI
3. Wait 5 min for sync (or trigger manually)
4. Generate preview collage in webapp
5. Verify appearance
6. Test publish (email in dry-run mode)
7. Once confident, promote to prod

---

### 8. Key Learnings from Bootstrap Session

**Applied to This Architecture**:

1. **Cloudinary API Quirks**:
   - ✓ Use `resources/image/moderations/manual/approved` endpoint (reliable)
   - ✓ Fetch all, filter locally (don't trust parameter combinations)
   - ✓ Email stored in `context.custom.email`

2. **Email Success Patterns**:
   - ✓ 2-second rate limiting between sends
   - ✓ Plain text + HTML multipart emails
   - ✓ Personal tone works well
   - ✓ Clear opt-out / preferences link

3. **Data Management**:
   - ✓ Dual caching strategy (raw + filtered) helpful for debugging
   - ✓ Cache files in .gitignore (sensitive data)
   - ✓ Authoritative records off-box (Gmail sent folder)

4. **Operational Insights**:
   - ✓ 93.4% email capture rate (excellent)
   - ✓ Zero bounces with careful handling
   - ✓ Users appreciate being notified as promised
   - ✓ One user wanted newsletter signup → include in automated emails

---

## Phase Breakdown

### Phase 1: MVP

**Goal**: Functional sync → collage → email pipeline

**Deliverables**:
- [ ] AWS EC2 + EFS provisioned
- [ ] Sync script working (cron every 5 min)
- [ ] Simple grid collage with ImageMagick
- [ ] Basic webapp (preview, publish, view photos)
- [ ] Email notification (Google Workspace SMTP)
- [ ] Track first-time contributors (JSON manifests)

**Success Criteria**:
- Admin can approve photo in Cloudinary → see it sync within 5 min
- Admin can generate preview collage → review → publish
- New contributors receive email within 10 min of publish

### Phase 2: Enhancements

**Goal**: Better collages, engagement tracking

**Deliverables**:
- [ ] Photomosaic algorithm (investigate libraries)
- [ ] Multiple algorithm options in UI
- [ ] Email tracking pixel (opens)
- [ ] Email validation link (engagement)
- [ ] Newsletter signup integration
- [ ] Social sharing features
- [ ] Bounce handling

### Phase 3: Advanced Features (Future)

**Possible Extensions**:
- [ ] Image map on website (zoom to individual faces)
- [ ] Multiple collage variants for social media
- [ ] Themed collages (by city, country, etc.)
- [ ] User dashboard (view collages you're in)
- [ ] A/B testing email content
- [ ] Analytics dashboard

---

## Cost Breakdown

| Service | Tier | Monthly Cost |
|---------|------|--------------|
| **Cloudinary** | Paid non-profit | $50 { tk: limits, fees } |
| **EC2 t3.micro** | Free tier (12 mo) | $0 → $7 |
| **EC2 t3.small** | Paid | $15 |
| **EC2 t3.medium** | Paid (if needed) | $30 |
| **EFS Storage** | 30GB | $9 |
| **EFS Requests** | Negligible | ~$1 |
| **Email (Google Workspace)** | Existing | $0 |
| **Data Transfer** | <100GB/mo | ~$5 |
| **Total (t3.micro start)** | | **$15/month** |
| **Total (t3.small production)** | | **$30/month** |

---

## Security Considerations

1. **Cloudinary API Keys**: Store in environment variables, never commit
2. **Google Workspace Password**: Use app-specific password, rotate regularly
3. **EC2 SSH Access**: Key-based only, no password auth
4. **EFS Access**: Security group restricts to EC2 instance only
5. **User Emails**: { tk, needs refinement: GDPR compliance, clear unsubscribe mechanism }
6. **Rate Limiting**: Prevent abuse of sync/email endpoints

---

## Other TK Questions / Decisions Needed

1. **GitHub Repository**:
   - New org repo: `pauseai/sayno-collage-tool`?
   - Public or private initially?

2. **Domain / URL**:
   - Where to host webapp? `collage-admin.pauseai.info`?
   - Where to serve published collages? `pauseai.info/collages/sayno_v1.jpg`?

3. **Admin Access**:
   - How many admins initially? (affects auth complexity)
   - Simple HTTP Basic Auth sufficient for MVP?

4. **Cloudinary Approval UI**:
   - Embed iframe in webapp, or keep as separate tab?

5. **Testing Strategy**:
   - How many test photos needed for dev testing?
   - Who approves test photos?

---

## Next Steps

**This Session** (documentation):
- [x] Define architecture
- [x] Choose tech stack
- [x] Document deployment approach
- [ ] Review and refine this document

**Next Session** (implementation start):
1. Create GitHub repository
2. Set up AWS account / credentials
3. Provision EC2 + EFS (run setup scripts)
4. Implement sync script
5. Test with sayno-test/ folder

---

## References

- **Issues**: #437 (architecture), #488 (email content), #500 (bootstrap)
- **Bootstrap Summary**: `20251001T00.sayno-bootstrap-collage-notification.summary.md`
- **Cloudinary Docs**: (referenced in bootstrap session)
- **FastAPI Docs**: https://fastapi.tiangolo.com/
- **ImageMagick Montage**: https://imagemagick.org/script/montage.php
