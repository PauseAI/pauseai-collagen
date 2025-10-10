"""
Campaign-specific logger for processor actions.

Logs main events (synced/deleted/error) to campaign-specific files,
independent of webhook vs SQS source.
"""

import logging
from pathlib import Path


class CampaignLogger:
    """
    Wrapper for campaign-specific persistent logging.

    Logs processor actions to /mnt/efs/{campaign}/logs/processor.log
    Delegates to Python's logging system for actual log management.
    """

    def __init__(self, campaign: str, efs_base: Path):
        """
        Initialize campaign logger.

        Args:
            campaign: Campaign name (e.g., 'test_prototype', 'sayno')
            efs_base: Base path for EFS mounts
        """
        self.campaign = campaign

        # Get or create logger via Python's logging system
        logger_name = f'processor.{campaign}'
        self._logger = logging.getLogger(logger_name)

        # If already configured, skip setup
        if self._logger.handlers:
            return

        # Set up file handler for this campaign
        log_dir = efs_base / campaign / 'logs'
        log_dir.mkdir(parents=True, exist_ok=True)

        log_file = log_dir / 'processor.log'

        handler = logging.FileHandler(log_file)
        handler.setLevel(logging.INFO)

        # Format: timestamp - level - message
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)

        self._logger.addHandler(handler)
        self._logger.setLevel(logging.INFO)

        # Don't propagate to parent (avoid duplicate console logs)
        self._logger.propagate = False

    def info(self, message: str):
        """Log info message."""
        self._logger.info(message)

    def error(self, message: str):
        """Log error message."""
        self._logger.error(message)

    def warning(self, message: str):
        """Log warning message."""
        self._logger.warning(message)
