from __future__ import annotations


def severity_from_score(score: int) -> str:
    """Deterministic mapping from numeric score to severity label."""
    if score >= 90:
        return "CRITICAL"
    if score >= 70:
        return "HIGH"
    if score >= 40:
        return "MEDIUM"
    return "LOW"
