"""Re-export the API's feature pipeline so training and inference can never drift apart."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "api"))

from app.services.features import (  # noqa: E402
    CLASSES,
    CONTEXT_FEATURES,
    FEATURE_LABELS,
    FEATURES,
    ITEM_FEATURES,
    build_features,
    response_quality,
)

__all__ = [
    "CLASSES", "CONTEXT_FEATURES", "FEATURE_LABELS", "FEATURES", "ITEM_FEATURES",
    "build_features", "response_quality",
]
