"""
test_scoring_engine.py
======================
Pytest unit tests for the WellRing scoring engine:
    - scoring_engine/baseline.py   (RiskLevel, get_risk_level)
    - scoring_engine/rules.py      (SYMPTOM_WEIGHTS, SEVERITY_BONUS, categories)
    - scoring_engine/scoring.py    (calculate_score — the main public function)
    - scoring_engine/alerts.py     (determine_action)

All 11 clinical scenarios from the original test_cases.py are ported here
as proper parametrized pytest cases.

Run with:
    python -m pytest tests/test_scoring_engine.py -v
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest

from scoring_engine.baseline import RiskLevel, get_risk_level
from scoring_engine.rules    import (
    SYMPTOM_WEIGHTS,
    SEVERITY_BONUS,
    SYMPTOM_CATEGORIES,
    CATEGORY_PRIORITY,
)
from scoring_engine.scoring  import calculate_score, _resolve_category
from scoring_engine.alerts   import (
    determine_action,
    ACTION_MONITOR,
    ACTION_FOLLOW_UP,
    ACTION_NOTIFY_CAREGIVER,
    ACTION_EMERGENCY,
)


# ═══════════════════════════════════════════════════════════════════════════════
# baseline.py — RiskLevel & get_risk_level
# ═══════════════════════════════════════════════════════════════════════════════

class TestBaseline:

    def test_score_0_is_low(self):
        assert get_risk_level(0) == RiskLevel.LOW

    def test_score_30_is_low(self):
        assert get_risk_level(30) == RiskLevel.LOW

    def test_score_31_is_medium(self):
        assert get_risk_level(31) == RiskLevel.MEDIUM

    def test_score_60_is_medium(self):
        assert get_risk_level(60) == RiskLevel.MEDIUM

    def test_score_61_is_high(self):
        assert get_risk_level(61) == RiskLevel.HIGH

    def test_score_100_is_high(self):
        assert get_risk_level(100) == RiskLevel.HIGH

    def test_score_101_is_critical(self):
        assert get_risk_level(101) == RiskLevel.CRITICAL

    def test_score_999_is_critical(self):
        assert get_risk_level(999) == RiskLevel.CRITICAL

    def test_risk_level_values_are_strings(self):
        for level in RiskLevel:
            assert isinstance(level.value, str)

    def test_all_four_risk_levels_exist(self):
        assert {l.value for l in RiskLevel} == {"LOW", "MEDIUM", "HIGH", "CRITICAL"}


# ═══════════════════════════════════════════════════════════════════════════════
# rules.py — Weights, bonuses, categories
# ═══════════════════════════════════════════════════════════════════════════════

class TestRules:

    def test_all_symptom_weights_are_positive(self):
        assert all(v > 0 for v in SYMPTOM_WEIGHTS.values())

    def test_critical_symptoms_have_highest_weights(self):
        assert SYMPTOM_WEIGHTS["unconscious"]     >= 80
        assert SYMPTOM_WEIGHTS["stroke_symptoms"] >= 80
        assert SYMPTOM_WEIGHTS["chest_pain"]      >= 40

    def test_severity_bonus_ordering(self):
        assert SEVERITY_BONUS["low"] < SEVERITY_BONUS["medium"]
        assert SEVERITY_BONUS["medium"] < SEVERITY_BONUS["high"]
        assert SEVERITY_BONUS["high"] < SEVERITY_BONUS["critical"]

    def test_all_four_severities_in_bonus(self):
        assert set(SEVERITY_BONUS.keys()) == {"low", "medium", "high", "critical"}

    def test_cardiac_has_highest_category_priority(self):
        assert CATEGORY_PRIORITY["CARDIAC"] == max(CATEGORY_PRIORITY.values())

    def test_unknown_has_lowest_priority(self):
        assert CATEGORY_PRIORITY["UNKNOWN"] == 0

    def test_all_symptom_keys_have_category(self):
        for symptom in SYMPTOM_WEIGHTS:
            assert symptom in SYMPTOM_CATEGORIES, \
                f"Symptom '{symptom}' in SYMPTOM_WEIGHTS has no SYMPTOM_CATEGORIES entry"


# ═══════════════════════════════════════════════════════════════════════════════
# scoring.py — _resolve_category
# ═══════════════════════════════════════════════════════════════════════════════

class TestResolveCategory:

    def test_single_cardiac_symptom(self):
        assert _resolve_category(["chest_pain"]) == "CARDIAC"

    def test_single_neurological(self):
        assert _resolve_category(["dizziness"]) == "NEUROLOGICAL"

    def test_cardiac_beats_neurological(self):
        # CARDIAC priority > NEUROLOGICAL
        assert _resolve_category(["dizziness", "chest_pain"]) == "CARDIAC"

    def test_cardiac_beats_fall(self):
        assert _resolve_category(["fall_detected", "unconscious"]) == "CARDIAC"

    def test_empty_symptoms_returns_unknown(self):
        assert _resolve_category([]) == "UNKNOWN"

    def test_unrecognised_symptom_returns_unknown(self):
        assert _resolve_category(["sneeze"]) == "UNKNOWN"

    def test_mixed_known_unknown_uses_known(self):
        # "sneeze" is unknown; "chest_pain" is CARDIAC
        result = _resolve_category(["sneeze", "chest_pain"])
        assert result == "CARDIAC"


# ═══════════════════════════════════════════════════════════════════════════════
# scoring.py — calculate_score (clinical scenario parametrize)
# ═══════════════════════════════════════════════════════════════════════════════

# Each tuple: (symptoms, severity, confidence, expected_risk_level, expected_category)
_CLINICAL_SCENARIOS = [
    # Case 1 — mild dizziness, low confidence
    (["dizziness"],                              "low",      0.6, "LOW",      "NEUROLOGICAL"),
    # Case 2 — missed medicine, full confidence
    (["medicine_missed"],                        "low",      1.0, "LOW",      "MEDICATION"),
    # Case 3 — fever + dizziness, medium
    (["fever", "dizziness"],                     "medium",   0.9, "MEDIUM",   "NEUROLOGICAL"),
    # Case 4 — medicine + fever, medium, 0.85 confidence → score ≈ 30 → LOW
    (["medicine_missed", "fever"],               "medium",   0.85,"LOW",      "MEDICATION"),
    # Case 5 — breathing problem, high severity, 0.95 confidence → score≈57 → MEDIUM
    (["breathing_problem"],                      "high",     0.95,"MEDIUM",   "RESPIRATORY"),
    # Case 6 — fall detected, medium → score = 70 → HIGH
    (["fall_detected"],                          "medium",   1.0, "HIGH",     "FALL"),
    # Case 7 — chest pain, high severity → score = 70 → HIGH
    (["chest_pain"],                             "high",     1.0, "HIGH",     "CARDIAC"),
    # Case 8 — chest pain + breathing, high severity → score ≈ 105 → CRITICAL
    (["chest_pain", "breathing_problem"],        "high",     0.95,"CRITICAL", "CARDIAC"),
    # Case 9 — stroke, critical severity → score ≈ 139 → CRITICAL
    (["stroke_symptoms"],                        "critical", 0.99,"CRITICAL", "NEUROLOGICAL"),
    # Case 10 — multiple critical → score = 300 → CRITICAL, CARDIAC wins priority
    (["unconscious", "stroke_symptoms",
      "fall_detected"],                          "critical", 1.0, "CRITICAL", "CARDIAC"),
    # Case 11 — chest pain + breathing, 50% confidence → score=55 → MEDIUM
    (["chest_pain", "breathing_problem"],        "high",     0.5, "MEDIUM",   "CARDIAC"),
]

@pytest.mark.parametrize(
    "symptoms,severity,confidence,expected_level,expected_category",
    _CLINICAL_SCENARIOS,
    ids=[f"scenario_{i+1}" for i in range(len(_CLINICAL_SCENARIOS))],
)
def test_clinical_scenario(symptoms, severity, confidence,
                           expected_level, expected_category):
    result = calculate_score(symptoms, severity, confidence)
    assert result["risk_level"] == expected_level, (
        f"Expected {expected_level}, got {result['risk_level']} "
        f"(score={result['score']}, base={result['base_score']})"
    )
    assert result["category"] == expected_category, (
        f"Expected category {expected_category}, got {result['category']}"
    )


class TestCalculateScore:

    def test_returns_required_keys(self):
        r = calculate_score(["dizziness"], "low")
        for key in ("score", "base_score", "confidence", "risk_level",
                    "category", "symptoms", "severity"):
            assert key in r, f"Missing key: {key}"

    def test_score_is_int(self):
        r = calculate_score(["dizziness"], "medium")
        assert isinstance(r["score"], int)

    def test_base_score_always_gte_final_score(self):
        # base_score * confidence ≤ base_score (confidence ≤ 1.0)
        r = calculate_score(["chest_pain"], "high", confidence=0.7)
        assert r["base_score"] >= r["score"]

    def test_confidence_1_gives_score_equal_to_base(self):
        r = calculate_score(["chest_pain"], "high", confidence=1.0)
        assert r["score"] == r["base_score"]

    def test_confidence_0_gives_score_0(self):
        r = calculate_score(["chest_pain"], "high", confidence=0.0)
        assert r["score"] == 0

    def test_unknown_symptom_is_ignored(self):
        r_known   = calculate_score(["chest_pain"],           "low")
        r_unknown = calculate_score(["chest_pain", "sneeze"], "low")
        assert r_known["score"] == r_unknown["score"]

    def test_unknown_symptom_not_in_result_symptoms(self):
        r = calculate_score(["chest_pain", "sneeze"], "low")
        assert "sneeze" not in r["symptoms"]

    def test_empty_symptoms_only_severity_bonus(self):
        r = calculate_score([], "medium")
        assert r["score"] == SEVERITY_BONUS["medium"]

    def test_severity_normalised_lowercase(self):
        r = calculate_score(["dizziness"], "HIGH")
        assert r["severity"] == "high"

    def test_invalid_severity_raises_valueerror(self):
        with pytest.raises(ValueError, match="Unknown severity"):
            calculate_score(["dizziness"], "extreme")

    def test_confidence_above_1_raises_valueerror(self):
        with pytest.raises(ValueError, match="Confidence"):
            calculate_score(["dizziness"], "low", confidence=1.1)

    def test_confidence_below_0_raises_valueerror(self):
        with pytest.raises(ValueError, match="Confidence"):
            calculate_score(["dizziness"], "low", confidence=-0.1)

    def test_score_increases_with_more_symptoms(self):
        r1 = calculate_score(["dizziness"],            "medium", 1.0)
        r2 = calculate_score(["dizziness", "fever"],   "medium", 1.0)
        assert r2["score"] > r1["score"]

    def test_score_increases_with_higher_severity(self):
        r_low  = calculate_score(["chest_pain"], "low",  1.0)
        r_high = calculate_score(["chest_pain"], "high", 1.0)
        assert r_high["score"] > r_low["score"]

    def test_confidence_field_echoed(self):
        r = calculate_score(["dizziness"], "low", confidence=0.75)
        assert r["confidence"] == 0.75

    def test_all_risk_levels_reachable(self):
        # LOW: empty symptoms, low severity → score = 0
        low      = calculate_score([],                          "low",    1.0)["risk_level"]
        # MEDIUM: fever + dizziness, medium severity → score = 15+20+10 = 45
        medium   = calculate_score(["fever", "dizziness"],      "medium", 1.0)["risk_level"]
        # HIGH: fall detected, medium severity → score = 60+10 = 70
        high     = calculate_score(["fall_detected"],           "medium", 1.0)["risk_level"]
        # CRITICAL: chest pain + breathing, high severity → score = 50+40+20 = 110
        critical = calculate_score(["chest_pain",
                                    "breathing_problem"],       "high",   1.0)["risk_level"]
        assert low      == "LOW"
        assert medium   == "MEDIUM"
        assert high     == "HIGH"
        assert critical == "CRITICAL"


# ═══════════════════════════════════════════════════════════════════════════════
# alerts.py — determine_action
# ═══════════════════════════════════════════════════════════════════════════════

class TestAlerts:

    def test_score_0_returns_monitor(self):
        a = determine_action(0)
        assert a["action"] == ACTION_MONITOR

    def test_score_30_returns_monitor(self):
        assert determine_action(30)["action"] == ACTION_MONITOR

    def test_score_31_returns_follow_up(self):
        assert determine_action(31)["action"] == ACTION_FOLLOW_UP

    def test_score_60_returns_follow_up(self):
        assert determine_action(60)["action"] == ACTION_FOLLOW_UP

    def test_score_61_returns_notify_caregiver(self):
        assert determine_action(61)["action"] == ACTION_NOTIFY_CAREGIVER

    def test_score_100_returns_notify_caregiver(self):
        assert determine_action(100)["action"] == ACTION_NOTIFY_CAREGIVER

    def test_score_101_returns_emergency(self):
        assert determine_action(101)["action"] == ACTION_EMERGENCY

    def test_score_300_returns_emergency(self):
        assert determine_action(300)["action"] == ACTION_EMERGENCY

    def test_action_result_has_required_keys(self):
        a = determine_action(50)
        for key in ("action", "risk_level", "score", "message", "steps"):
            assert key in a, f"Missing key: {key}"

    def test_steps_is_non_empty_list(self):
        for score in (0, 40, 80, 150):
            assert isinstance(determine_action(score)["steps"], list)
            assert len(determine_action(score)["steps"]) > 0

    def test_score_echoed_in_result(self):
        assert determine_action(42)["score"] == 42

    def test_risk_level_is_string(self):
        assert isinstance(determine_action(0)["risk_level"], str)

    def test_message_is_non_empty_string(self):
        for score in (0, 40, 80, 150):
            assert len(determine_action(score)["message"]) > 0

    def test_emergency_message_contains_alert_word(self):
        msg = determine_action(150)["message"].upper()
        assert "CRITICAL" in msg or "EMERGENCY" in msg or "ALERT" in msg

    def test_action_escalation_order(self):
        """Higher scores must not produce lower-priority actions."""
        priority = {
            ACTION_MONITOR:          1,
            ACTION_FOLLOW_UP:        2,
            ACTION_NOTIFY_CAREGIVER: 3,
            ACTION_EMERGENCY:        4,
        }
        scores = [0, 31, 61, 101]
        actions = [determine_action(s)["action"] for s in scores]
        priorities = [priority[a] for a in actions]
        assert priorities == sorted(priorities), \
            f"Escalation not monotone: {list(zip(scores, actions))}"
