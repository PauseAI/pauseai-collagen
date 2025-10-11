#!/usr/bin/env python3
"""Toggle test_prototype image to trigger webhook ingestion."""

import cloudinary
import cloudinary.api
import os
import subprocess
import time
from dotenv import load_dotenv

load_dotenv()
cloudinary.config(
    cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
    api_key=os.getenv('CLOUDINARY_API_KEY'),
    api_secret=os.getenv('CLOUDINARY_API_SECRET')
)

public_id = 'test_prototype/bs8psp5fvlylptdqmxmh'

# Check current status
resource = cloudinary.api.resource(public_id, moderation=True, context=True)
current_status = resource.get('moderation', [{}])[0].get('status', 'none')

print(f"Toggling: {public_id} (currently: {current_status})")

# Toggle moderation status (fires webhooks)
cloudinary.api.update(public_id, moderation_status='pending')
time.sleep(0.5)
cloudinary.api.update(public_id, moderation_status='approved')

print(f"✓ Moderation toggled in Cloudinary (approved)")
print(f"  Webhooks should have fired to API Gateway")

# Optionally restart ingestor for immediate processing (skips 20s polling delay)
try:
    result = subprocess.run(
        ['ssh', '-i', os.path.expanduser('~/.ssh/collagen-server-key.pem'),
         'ubuntu@3.85.173.169', 'sudo systemctl restart collagen-ingestor'],
        capture_output=True,
        timeout=10
    )
    if result.returncode == 0:
        print(f"  Restarted ingestor service (immediate processing)")
    else:
        print(f"  Note: Ingestor will process on next poll (~20s)")
except Exception:
    print(f"  Note: Ingestor will process on next poll (~20s)")
