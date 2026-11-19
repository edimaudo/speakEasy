from __future__ import annotations

import re
from typing import Any

PRIMARY_METRICS = ("content", "structure", "deliveryPacing", "confidence")
ALL_METRICS = PRIMARY_METRICS + ("hook", "fillerControl")
FILLER_TERMS = ("um", "uh", "like", "kind of", "basically", "you know")


def count_fillers(transcript: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for phrase in FILLER_TERMS:
        pattern = rf"(?<![\w]){re.escape(phrase).replace(r'\ ', r'\s+')}(?![\w])"
        counts[phrase] = len(re.findall(pattern, transcript, flags=re.IGNORECASE))
    return counts


def calculate_overall(metrics: dict[str, Any]) -> float:
    values = [float(metrics[name]) for name in PRIMARY_METRICS]
    if any(not 0 <= value <= 100 for value in values):
        raise ValueError("Primary metrics must be between 0 and 100.")
    return sum(values) / 4


def validate_scorecard(raw: Any, transcript: str, hot_take: bool) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("Coaching response must be a JSON object.")
    metrics = raw.get("metrics")
    if not isinstance(metrics, dict):
        raise ValueError("Coaching response is missing metrics.")
    clean_metrics: dict[str, int] = {}
    for name in ALL_METRICS:
        value = metrics.get(name)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 100:
            raise ValueError(f"Metric '{name}' must be a number between 0 and 100.")
        clean_metrics[name] = round(value)

    quote = str(raw.get("lineToFixQuote", "")).strip()
    if not quote or quote not in transcript:
        raise ValueError("The suggested line to fix must be an exact quote from the transcript.")

    annotations = []
    for item in (raw.get("annotations") or [])[:8]:
        if not isinstance(item, dict):
            continue
        phrase = str(item.get("phrase", "")).strip()
        if phrase and phrase in transcript:
            annotations.append({
                "phrase": phrase,
                "reason": str(item.get("reason", ""))[:500],
                "replacement": str(item.get("replacement", ""))[:500],
            })

    for required in ("lineToFixDiagnosis", "openingRewrite", "nextFocus"):
        if not str(raw.get(required, "")).strip():
            raise ValueError(f"Coaching response is missing '{required}'.")

    scorecard = {
        "metrics": clean_metrics,
        "annotations": annotations,
        "lineToFixQuote": quote,
        "lineToFixDiagnosis": str(raw["lineToFixDiagnosis"])[:1000],
        "openingRewrite": str(raw["openingRewrite"])[:1000],
        "strengths": [str(x)[:300] for x in (raw.get("strengths") or [])[:3]],
        "nextFocus": str(raw["nextFocus"])[:1000],
        "overallScore": calculate_overall(clean_metrics),
    }
    if hot_take:
        stance = raw.get("stanceClarity")
        if isinstance(stance, bool) or not isinstance(stance, (int, float)) or not 0 <= stance <= 100:
            raise ValueError("Hot Take coaching must include stanceClarity from 0 to 100.")
        scorecard.update({
            "stanceClarity": round(stance),
            "stanceVerdict": str(raw.get("stanceVerdict", ""))[:1000],
            "punchierHookRewrite": str(raw.get("punchierHookRewrite", ""))[:1000],
        })
    return scorecard
