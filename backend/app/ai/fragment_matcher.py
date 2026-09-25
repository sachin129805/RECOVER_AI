from math import isfinite


# ---------------------------------------------------------------------------
# Relationship scoring configuration
# ---------------------------------------------------------------------------
# These are engineering weights, not forensic probabilities.
# Keeping them here makes the matcher configurable instead of hiding
# assumptions inside the matching logic.

SCORING = {
    "same_file_type": 25.0,
    "same_signature": 10.0,
    "adjacent_fragments": 25.0,
    "nearby_fragments": 15.0,
    "entropy_very_similar": 15.0,
    "entropy_similar": 8.0,
    "size_high_compatibility": 10.0,
    "size_partial_compatibility": 5.0,
    "both_structurally_valid": 10.0,
}


# ---------------------------------------------------------------------------
# Safe conversion helpers
# ---------------------------------------------------------------------------

def _to_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _to_float(value, default=None):
    try:
        number = float(value)

        if not isfinite(number):
            return default

        return number

    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# Physical storage relationship
# ---------------------------------------------------------------------------

def _storage_relationship(fragment_a: dict, fragment_b: dict) -> dict:
    """
    Compare physical storage ranges.

    A fragment occupies:

        [offset, offset + sample_size)

    The relationship is based on the actual ranges rather than simply
    comparing the two starting offsets.
    """

    offset_a = _to_int(fragment_a.get("offset"))
    offset_b = _to_int(fragment_b.get("offset"))

    size_a = _to_int(fragment_a.get("sample_size"))
    size_b = _to_int(fragment_b.get("sample_size"))

    end_a = offset_a + max(size_a, 0)
    end_b = offset_b + max(size_b, 0)

    # Normalize ordering so A is the earlier fragment.
    if offset_b < offset_a:
        offset_a, offset_b = offset_b, offset_a
        end_a, end_b = end_b, end_a

    gap = offset_b - end_a

    if gap == 0:
        return {
            "score": SCORING["adjacent_fragments"],
            "relationship": "Adjacent storage ranges",
            "gap_bytes": 0,
            "overlap": False,
        }

    if gap > 0:
        if gap <= 4096:
            score = SCORING["nearby_fragments"]
            description = "Small gap between storage ranges"
        elif gap <= 65536:
            score = SCORING["nearby_fragments"] * 0.75
            description = "Moderate gap between storage ranges"
        elif gap <= 1024 * 1024:
            score = SCORING["nearby_fragments"] * 0.35
            description = "Larger gap within analysis range"
        else:
            score = 0.0
            description = None

        return {
            "score": round(score, 2),
            "relationship": description,
            "gap_bytes": gap,
            "overlap": False,
        }

    # Negative gap means the ranges overlap.
    overlap_bytes = abs(gap)

    return {
        "score": 0.0,
        "relationship": "Overlapping storage ranges",
        "gap_bytes": 0,
        "overlap": True,
        "overlap_bytes": overlap_bytes,
    }


# ---------------------------------------------------------------------------
# Entropy comparison
# ---------------------------------------------------------------------------

def _entropy_relationship(fragment_a: dict, fragment_b: dict) -> dict:
    entropy_a = _to_float(fragment_a.get("entropy"))
    entropy_b = _to_float(fragment_b.get("entropy"))

    if entropy_a is None or entropy_b is None:
        return {
            "score": 0.0,
            "description": None,
        }

    difference = abs(entropy_a - entropy_b)

    if difference <= 0.5:
        return {
            "score": SCORING["entropy_very_similar"],
            "description": "Very similar entropy characteristics",
        }

    if difference <= 1.5:
        return {
            "score": SCORING["entropy_similar"],
            "description": "Similar entropy characteristics",
        }

    return {
        "score": 0.0,
        "description": None,
    }


# ---------------------------------------------------------------------------
# Size compatibility
# ---------------------------------------------------------------------------

def _size_relationship(fragment_a: dict, fragment_b: dict) -> dict:
    size_a = _to_int(fragment_a.get("sample_size"))
    size_b = _to_int(fragment_b.get("sample_size"))

    if size_a <= 0 or size_b <= 0:
        return {
            "score": 0.0,
            "description": None,
        }

    larger = max(size_a, size_b)
    smaller = min(size_a, size_b)

    ratio = smaller / larger

    if ratio >= 0.75:
        return {
            "score": SCORING["size_high_compatibility"],
            "description": "Compatible fragment sizes",
        }

    if ratio >= 0.40:
        return {
            "score": SCORING["size_partial_compatibility"],
            "description": "Partially compatible fragment sizes",
        }

    return {
        "score": 0.0,
        "description": None,
    }


# ---------------------------------------------------------------------------
# File-type compatibility
# ---------------------------------------------------------------------------

def _type_relationship(fragment_a: dict, fragment_b: dict) -> dict:
    type_a = fragment_a.get("file_type")
    type_b = fragment_b.get("file_type")

    if not type_a or not type_b:
        return {
            "score": 0.0,
            "description": None,
        }

    if str(type_a).strip().lower() == str(type_b).strip().lower():
        return {
            "score": SCORING["same_file_type"],
            "description": "Compatible file classifications",
        }

    return {
        "score": 0.0,
        "description": None,
    }


# ---------------------------------------------------------------------------
# Signature compatibility
# ---------------------------------------------------------------------------

def _signature_relationship(fragment_a: dict, fragment_b: dict) -> dict:
    signature_a = fragment_a.get("signature")
    signature_b = fragment_b.get("signature")

    if not signature_a or not signature_b:
        return {
            "score": 0.0,
            "description": None,
        }

    if str(signature_a).lower() == str(signature_b).lower():
        return {
            "score": SCORING["same_signature"],
            "description": "Matching file signatures",
        }

    return {
        "score": 0.0,
        "description": None,
    }


# ---------------------------------------------------------------------------
# Structural compatibility
# ---------------------------------------------------------------------------

def _integrity_relationship(fragment_a: dict, fragment_b: dict) -> dict:
    integrity_a = fragment_a.get("integrity_status")
    integrity_b = fragment_b.get("integrity_status")

    if (
        integrity_a == "Structurally Valid"
        and integrity_b == "Structurally Valid"
    ):
        return {
            "score": SCORING["both_structurally_valid"],
            "description": "Both candidates passed structural validation",
        }

    return {
        "score": 0.0,
        "description": None,
    }


# ---------------------------------------------------------------------------
# Main relationship matcher
# ---------------------------------------------------------------------------

def match_fragments(fragment_a: dict, fragment_b: dict) -> dict:
    """
    Calculate an explainable relationship score between two candidate
    fragments.

    The matcher uses observable properties from the fragment records:

    - physical storage ranges
    - file classification
    - signatures
    - entropy
    - fragment size
    - structural validation

    It does not depend on specific filenames, fragment IDs, file sizes,
    demo offsets, or a particular file format.

    The resulting score is an engineering heuristic and must not be
    interpreted as a forensic probability or legal conclusion.
    """

    reasons = []
    score = 0.0

    # Physical storage relationship
    storage = _storage_relationship(fragment_a, fragment_b)

    score += storage["score"]

    if storage["relationship"]:
        reasons.append(storage["relationship"])

    if storage.get("gap_bytes", 0) > 0:
        reasons.append(
            f"Estimated storage gap: {storage['gap_bytes']:,} bytes"
        )

    if storage.get("overlap"):
        reasons.append(
            f"Storage ranges overlap by "
            f"{storage.get('overlap_bytes', 0):,} bytes"
        )

    # File classification
    type_result = _type_relationship(fragment_a, fragment_b)

    score += type_result["score"]

    if type_result["description"]:
        reasons.append(type_result["description"])

    # Signature
    signature_result = _signature_relationship(
        fragment_a,
        fragment_b,
    )

    score += signature_result["score"]

    if signature_result["description"]:
        reasons.append(signature_result["description"])

    # Entropy
    entropy_result = _entropy_relationship(
        fragment_a,
        fragment_b,
    )

    score += entropy_result["score"]

    if entropy_result["description"]:
        reasons.append(entropy_result["description"])

    # Size
    size_result = _size_relationship(
        fragment_a,
        fragment_b,
    )

    score += size_result["score"]

    if size_result["description"]:
        reasons.append(size_result["description"])

    # Structural validation
    integrity_result = _integrity_relationship(
        fragment_a,
        fragment_b,
    )

    score += integrity_result["score"]

    if integrity_result["description"]:
        reasons.append(integrity_result["description"])

    # Prevent duplicate explanations.
    reasons = list(dict.fromkeys(reasons))

    score = min(round(score, 2), 100.0)

    # Relationship classification.
    if score >= 70:
        relationship = "Strong Candidate Relationship"
    elif score >= 45:
        relationship = "Possible Candidate Relationship"
    elif score > 0:
        relationship = "Weak Candidate Relationship"
    else:
        relationship = "No Supported Relationship"

    return {
        "relationship_score": score,
        "relationship": relationship,
        "reasons": reasons,
        "analysis": {
            "storage": storage,
            "type_compatibility": type_result,
            "signature_compatibility": signature_result,
            "entropy_compatibility": entropy_result,
            "size_compatibility": size_result,
            "structural_compatibility": integrity_result,
        },
    }