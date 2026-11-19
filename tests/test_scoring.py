import pytest
from app.scoring import calculate_overall, count_fillers, validate_scorecard


def valid_scorecard(transcript: str, hot_take: bool = False):
    data = {
        "metrics": {
            "content": 80,
            "structure": 70,
            "deliveryPacing": 75,
            "confidence": 85,
            "hook": 60,
            "fillerControl": 90,
        },
        "annotations": [{
            "phrase": "I think we should simplify the process",
            "reason": "The opening is tentative.",
            "replacement": "We should simplify the process.",
        }],
        "lineToFixQuote": "I think we should simplify the process",
        "lineToFixDiagnosis": "The opening could be more direct.",
        "openingRewrite": "We should simplify the process because it reduces handoffs.",
        "strengths": ["You made a clear recommendation."],
        "nextFocus": "Lead with the result.",
    }
    if hot_take:
        data.update({"stanceClarity": 82, "stanceVerdict": "A clear stance.", "punchierHookRewrite": "The old approach no longer works."})
    return data


def test_overall_is_arithmetic_mean():
    assert calculate_overall({"content": 80, "structure": 70, "deliveryPacing": 75, "confidence": 85}) == 77.5


def test_fillers_are_counted_by_phrase_and_word_boundary():
    assert count_fillers("Um, uh. I like it, kind of. Basically, you know.") == {
        "um": 1, "uh": 1, "like": 1, "kind of": 1, "basically": 1, "you know": 1
    }


def test_line_to_fix_must_be_exact_transcript_quote():
    transcript = "I think we should simplify the process because it reduces handoffs."
    scorecard = valid_scorecard(transcript)
    scorecard["lineToFixQuote"] = "We should simplify this process"
    with pytest.raises(ValueError, match="exact quote"):
        validate_scorecard(scorecard, transcript, False)


def test_unweighted_mean_is_recomputed_by_python():
    transcript = "I think we should simplify the process because it reduces handoffs."
    scorecard = validate_scorecard(valid_scorecard(transcript), transcript, False)
    assert scorecard["overallScore"] == 77.5


def test_hot_take_requires_stance_fields():
    transcript = "I think we should simplify the process because it reduces handoffs."
    data = valid_scorecard(transcript, hot_take=True)
    assert validate_scorecard(data, transcript, True)["stanceClarity"] == 82
