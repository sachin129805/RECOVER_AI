from math import isfinite


def _offset_score(offset_a: int, offset_b: int) -> float:
    distance = abs(offset_a - offset_b)

    if distance <= 4096:
        return 25.0

    if distance <= 65536:
        return 15.0

    if distance <= 1024 * 1024:
        return 5.0

    return 0.0


def _entropy_score(entropy_a, entropy_b) -> float:
    if entropy_a is None or entropy_b is None:
        return 0.0

    try:
        entropy_a = float(entropy_a)
        entropy_b = float(entropy_b)
    except (TypeError, ValueError):
        return 0.0

    if not isfinite(entropy_a) or not isfinite(entropy_b):
        return 0.0

    difference = abs(entropy_a - entropy_b)

    if difference <= 0.5:
        return 15.0

    if difference <= 1.5:
        return 8.0

    return 0.0


def _size_score(size_a: int, size_b: int) -> float:
    if not size_a or not size_b:
        return 0.0

    larger = max(size_a, size_b)
    smaller = min(size_a, size_b)

    ratio = smaller / larger

    if ratio >= 0.75:
        return 10.0

    if ratio >= 0.40:
        return 5.0

    return 0.0


def match_fragments(fragment_a: dict, fragment_b: dict) -> dict:
    """
    Calculate an explainable relationship score between
    two candidate fragments.

    This is an engineering heuristic, not a forensic
    probability or legal conclusion.
    """

    reasons = []
    score = 0.0

    type_a = fragment_a.get("file_type")
    type_b = fragment_b.get("file_type")

    if type_a and type_b and type_a == type_b:
        score += 30.0
        reasons.append("Compatible file types")

    offset_score = _offset_score(
        int(fragment_a.get("offset", 0)),
        int(fragment_b.get("offset", 0)),
    )

    if offset_score > 0:
        score += offset_score

        if offset_score >= 25:
            reasons.append("Nearby storage offsets")
        elif offset_score >= 15:
            reasons.append("Moderately close storage offsets")
        else:
            reasons.append("Storage offsets within analysis range")

    entropy_score = _entropy_score(
        fragment_a.get("entropy"),
        fragment_b.get("entropy"),
    )

    if entropy_score > 0:
        score += entropy_score

        if entropy_score >= 15:
            reasons.append("Similar entropy characteristics")
        else:
            reasons.append(
                "Partially similar entropy characteristics"
            )

    size_score = _size_score(
        int(fragment_a.get("sample_size", 0)),
        int(fragment_b.get("sample_size", 0)),
    )

    if size_score > 0:
        score += size_score
        reasons.append("Compatible sample sizes")

    integrity_a = fragment_a.get("integrity_status")
    integrity_b = fragment_b.get("integrity_status")

    if (
        integrity_a == "Structurally Valid"
        and integrity_b == "Structurally Valid"
    ):
        score += 20.0
        reasons.append(
            "Both candidates passed structural validation"
        )

    score = min(round(score, 2), 100.0)

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
    }