"""
Environment configuration for collagen.

Provides environment-aware paths for development and production.
"""
import os
from pathlib import Path


# Single source of truth for data directory
# Dev: /tmp/collagen-local (default)
# Prod: /mnt/efs (set via COLLAGEN_DATA_DIR environment variable)
DATA_DIR = Path(os.getenv('COLLAGEN_DATA_DIR', '/tmp/collagen-local'))


def get_campaign_dir(campaign: str) -> Path:
    """
    Get campaign directory path.

    Args:
        campaign: Campaign name (e.g., 'test_prototype', 'sayno')

    Returns:
        Path to campaign directory (e.g., /mnt/efs/sayno or /tmp/collagen-local/sayno)
    """
    return DATA_DIR / campaign
