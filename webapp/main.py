"""
Collagen webapp - FastAPI application for building and managing collages.

Main routes:
- GET /: Dashboard (campaign list, stats)
- GET /{campaign}: Campaign detail with embedded build form
- POST /{campaign}/new: Create new collage build
- GET /{campaign}/{build_id}: View build details
- GET /{campaign}/{build_id}/{filename}: Serve image files
"""

import sys
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime
import json

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# Add parent directory to path for lib imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.workflow import get_layout_options, validate_custom_layout
from lib.grid_optimizer import format_layout_description
from lib.collage_generator import build_collage


# Configuration
LOCAL_BASE = Path("/tmp/collagen-local")
CAMPAIGNS = ["test_prototype", "sayno"]  # Available campaigns

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(title="Collagen", description="Collage generation tool for campaigns")

# Templates and static files
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")


# Helper functions

def get_campaign_stats(campaign: str) -> Dict[str, Any]:
    """Get stats for a campaign."""
    campaign_dir = LOCAL_BASE / campaign

    if not campaign_dir.exists():
        return {
            "exists": False,
            "tiles": 0,
            "builds": []
        }

    tiles_dir = campaign_dir / "tiles"
    collages_dir = campaign_dir / "collages"

    tile_count = len(list(tiles_dir.glob("*.png"))) if tiles_dir.exists() else 0

    # List builds
    builds = []
    if collages_dir.exists():
        for build_dir in sorted(collages_dir.iterdir(), reverse=True):
            if build_dir.is_dir() and build_dir.name.startswith("build_"):
                manifest_path = build_dir / "manifest.json"
                if manifest_path.exists():
                    with open(manifest_path) as f:
                        manifest = json.load(f)

                    builds.append({
                        "id": build_dir.name,
                        "created_at": manifest["created_at"],
                        "photo_count": manifest["photo_count"],
                        "layout": manifest["layout"],
                        "published": manifest.get("published_at") is not None
                    })

    return {
        "exists": True,
        "tiles": tile_count,
        "builds": builds
    }


# Routes

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Dashboard: Show all campaigns."""
    campaign_stats = {}
    for campaign in CAMPAIGNS:
        campaign_stats[campaign] = get_campaign_stats(campaign)

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "campaigns": CAMPAIGNS,
        "stats": campaign_stats
    })


@app.get("/{campaign}", response_class=HTMLResponse)
async def campaign_detail(request: Request, campaign: str, n_images: Optional[int] = None):
    """Campaign detail with embedded build form."""
    if campaign not in CAMPAIGNS:
        raise HTTPException(status_code=404, detail="Campaign not found")

    campaign_dir = LOCAL_BASE / campaign
    stats = get_campaign_stats(campaign)

    if not stats["exists"]:
        raise HTTPException(status_code=404, detail=f"Campaign directory not found: {LOCAL_BASE / campaign}")

    # Default to all tiles if not specified
    if n_images is None:
        n_images = stats["tiles"]

    # Get layout options for build form
    layout_options = None
    if stats["tiles"] > 0:
        try:
            options = get_layout_options(campaign_dir, n_images)

            # Format layout descriptions
            layout_descriptions = []
            for i, layout in enumerate(options["top_layouts"], 1):
                layout_descriptions.append({
                    "index": i,
                    "description": format_layout_description(layout),
                    "data": layout
                })

            layout_options = {
                "n_images": n_images,
                "available_tiles": options["available_tiles"],
                "layouts": layout_descriptions
            }
        except ValueError as e:
            logger.warning(f"Could not get layout options: {e}")

    return templates.TemplateResponse("campaign.html", {
        "request": request,
        "campaign": campaign,
        "stats": stats,
        "layout_options": layout_options
    })


@app.post("/{campaign}/new")
async def create_build(
    campaign: str,
    n_images: int = Form(...),
    layout_choice: str = Form(...),
    custom_cols: Optional[int] = Form(None),
    custom_rows: Optional[int] = Form(None)
):
    """Create a new collage build."""
    if campaign not in CAMPAIGNS:
        raise HTTPException(status_code=404, detail="Campaign not found")

    campaign_dir = LOCAL_BASE / campaign

    # Get layout
    if layout_choice == "custom":
        if not custom_cols or not custom_rows:
            raise HTTPException(status_code=400, detail="Custom grid requires cols and rows")

        layout = validate_custom_layout(custom_cols, custom_rows, n_images)
        if not layout:
            raise HTTPException(status_code=400, detail="Invalid custom grid (clipping exceeds limits)")

    else:
        # Get from pre-computed options
        try:
            options = get_layout_options(campaign_dir, n_images)
            layout_index = int(layout_choice) - 1

            if layout_index < 0 or layout_index >= len(options["top_layouts"]):
                raise HTTPException(status_code=400, detail="Invalid layout choice")

            layout = options["top_layouts"][layout_index]

        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    # Build collage
    try:
        build_dir = build_collage(campaign_dir, layout, n_images, logger=logger)
        build_id = build_dir.name

        logger.info(f"Build complete: {campaign}/{build_id}")

        return RedirectResponse(
            url=f"/{campaign}/{build_id}",
            status_code=303
        )

    except Exception as e:
        logger.error(f"Build failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Build failed: {str(e)}")


@app.get("/{campaign}/{build_id}", response_class=HTMLResponse)
async def view_build(request: Request, campaign: str, build_id: str):
    """View a specific build."""
    if campaign not in CAMPAIGNS:
        raise HTTPException(status_code=404, detail="Campaign not found")

    build_dir = LOCAL_BASE / campaign / "collages" / build_id

    if not build_dir.exists():
        raise HTTPException(status_code=404, detail="Build not found")

    # Load manifest
    manifest_path = build_dir / "manifest.json"
    if not manifest_path.exists():
        raise HTTPException(status_code=404, detail="Manifest not found")

    with open(manifest_path) as f:
        manifest = json.load(f)

    # Check which files exist
    files = {
        "png_4k": (build_dir / "4096.png").exists(),
        "jpg_4k": (build_dir / "4096.jpg").exists(),
        "jpg_1k": (build_dir / "1024.jpg").exists()
    }

    return templates.TemplateResponse("build.html", {
        "request": request,
        "campaign": campaign,
        "build_id": build_id,
        "manifest": manifest,
        "files": files,
        "created_at_formatted": datetime.fromtimestamp(manifest["created_at"]).strftime("%Y-%m-%d %H:%M:%S")
    })


@app.get("/{campaign}/{build_id}/{filename}")
async def serve_image(campaign: str, build_id: str, filename: str):
    """Serve image files from builds."""
    if campaign not in CAMPAIGNS:
        raise HTTPException(status_code=404, detail="Campaign not found")

    # Validate filename (security)
    allowed_files = ["4096.png", "4096.jpg", "1024.jpg"]
    if filename not in allowed_files:
        raise HTTPException(status_code=404, detail="File not found")

    file_path = LOCAL_BASE / campaign / "collages" / build_id / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(file_path)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
