from __future__ import annotations

import re
from typing import Dict, Optional


def normalize_batting_hand(batting_style: Optional[str]) -> Optional[str]:
    """Normalize free-form batting style to RHB/LHB."""
    if not batting_style:
        return None

    value = batting_style.strip().lower()
    if "right" in value:
        return "RHB"
    if "left" in value:
        return "LHB"
    return None


def classify_bowling_style(bowling_style: Optional[str]) -> Dict[str, Optional[str]]:
    """
    Classify bowling style into canonical schema.

    Returns a dictionary with keys:
    arm, type, subtype, mechanism
    """
    result: Dict[str, Optional[str]] = {
        "arm": None,
        "type": None,
        "subtype": None,
        "mechanism": None,
    }

    if not bowling_style:
        return result

    normalized = re.sub(r"\s+", " ", bowling_style.strip().lower())

    if "left" in normalized:
        result["arm"] = "Left"
    elif "right" in normalized:
        result["arm"] = "Right"

    if any(token in normalized for token in ("fast", "medium", "seam")):
        result["type"] = "Pace"
        result["subtype"] = "Seam"
        result["mechanism"] = "None"
        return result

    if any(token in normalized for token in ("offbreak", "off spin", "off-spin", "off break")):
        result["arm"] = "Right"
        result["type"] = "Spin"
        result["subtype"] = "Right Arm Off Spin"
        result["mechanism"] = "Finger"
        return result

    if any(token in normalized for token in ("legbreak", "leg spin", "leg-spin", "leg break")):
        result["arm"] = "Right"
        result["type"] = "Spin"
        result["subtype"] = "Right Arm Leg Spin"
        result["mechanism"] = "Wrist"
        return result

    if "orthodox" in normalized:
        result["arm"] = "Left"
        result["type"] = "Spin"
        result["subtype"] = "Left Arm Orthodox"
        result["mechanism"] = "Finger"
        return result

    if any(token in normalized for token in ("chinaman", "left-arm wrist", "left arm wrist")):
        result["arm"] = "Left"
        result["type"] = "Spin"
        result["subtype"] = "Left Arm Chinaman"
        result["mechanism"] = "Wrist"
        return result

    if "spin" in normalized:
        result["type"] = "Spin"

    return result
