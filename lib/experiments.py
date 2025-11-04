"""
A/B testing experiment framework for collage email campaigns.

Supports defining experiments with custom variant names and assignment logic.
"""

from typing import Callable, List


def vowel_consonant_split(email: str) -> str:
    """
    Default assignment function: vowel = treatment, consonant = control.

    Args:
        email: User's email address

    Returns:
        "treatment" if email starts with vowel (a,e,i,o,u)
        "control" if email starts with consonant
    """
    first_char = email.lower()[0] if email else ''
    return "treatment" if first_char in 'aeiou' else "control"


class Experiment:
    """
    Represents an A/B test experiment.

    Experiments are named after their treatment condition (e.g., "CTAs above collage").
    By default, experiments use control/treatment variants with vowel/consonant split.
    """

    def __init__(
        self,
        name: str,
        experiment_id: str = None,
        variants: List[str] = None,
        assignment_fn: Callable[[str], str] = None
    ):
        """
        Create an experiment.

        Args:
            name: Human-readable experiment name (describe the treatment)
            experiment_id: Experiment ID (e.g., "X001_CTAS_ABOVE_COLLAGE"), auto-set by module
            variants: List of variant names (default: ['control', 'treatment'])
            assignment_fn: Function mapping email -> variant (default: vowel_consonant_split)
        """
        self.name = name
        self.experiment_id = experiment_id
        self.variants = variants if variants is not None else ['control', 'treatment']
        self.assignment_fn = assignment_fn if assignment_fn is not None else vowel_consonant_split

    def get_variant(self, email: str) -> str:
        """
        Get variant assignment for an email address.

        Args:
            email: User's email address

        Returns:
            Variant name (e.g., "control" or "treatment")
        """
        return self.assignment_fn(email)

    def get_sample_path(self, base_dir) -> "Path":
        """
        Get the sample file path for this experiment.

        Sample files track which users were assigned to this experiment.

        Args:
            base_dir: Base directory (typically scripts/ directory)

        Returns:
            Path like "scripts/X001_CTAS_ABOVE_COLLAGE.txt"

        Raises:
            ValueError: If experiment_id not set
        """
        from pathlib import Path

        if not self.experiment_id:
            raise ValueError(f"Experiment '{self.name}' has no experiment_id set")
        return Path(base_dir) / f"{self.experiment_id}.txt"


# Active experiments
X001_CTAS_ABOVE_COLLAGE = Experiment("CTAs above collage")


def get_experiment(identifier):
    """
    Get experiment by number or ID.

    Args:
        identifier: Experiment number (int or str "1") or full ID (str "X001_CTAS_ABOVE_COLLAGE")

    Returns:
        Experiment object (with experiment_id set if it wasn't already)

    Raises:
        ValueError: If experiment not found
    """
    import re
    import sys

    # Convert to int if possible
    if isinstance(identifier, str):
        try:
            identifier = int(identifier)
        except ValueError:
            pass

    # If we have an int, look for X{num:03d}_*
    if isinstance(identifier, int):
        pattern = f"^X{identifier:03d}_"
    else:
        # String ID - use as-is
        pattern = f"^{identifier}$"

    # Search module globals for matching experiment
    regex = re.compile(pattern, re.IGNORECASE)
    current_module = sys.modules[__name__]

    for name in dir(current_module):
        if regex.match(name):
            obj = getattr(current_module, name)
            if isinstance(obj, Experiment):
                # Set experiment_id if not already set
                if not obj.experiment_id:
                    obj.experiment_id = name
                return obj

    raise ValueError(f"Unknown experiment: {identifier}")
