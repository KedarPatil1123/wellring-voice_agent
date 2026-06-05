"""
test_cases.py
=============
Legacy script runner for the WellRing scoring engine.

The canonical test suite has been migrated to:
    tests/test_scoring_engine.py   (pytest — run with: pytest tests/test_scoring_engine.py -v)

This file is kept for quick command-line validation without pytest:
    python src/scoring_engine/test_cases.py

It uses the same 11 clinical scenarios as the pytest suite.
"""

import sys
import os

# Support both `python src/scoring_engine/test_cases.py` and pytest collection
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from src.scoring_engine.scoring  import calculate_score
from src.scoring_engine.alerts   import determine_action
from src.scoring_engine.baseline import RiskLevel

# ---------------------------------------------------------------------------
# Clinical test scenarios
# ---------------------------------------------------------------------------

TEST_CASES = [
    {
        "id":                1,
        "description":       "User reports mild dizziness with low-confidence detection.",
        "symptoms":          ["dizziness"],
        "severity":          "low",
        "confidence":        0.6,
        "expected_level":    RiskLevel.LOW,
        "expected_category": "NEUROLOGICAL",
    },
    {
        "id":                2,
        "description":       "User forgot to take medicine this morning.",
        "symptoms":          ["medicine_missed"],
        "severity":          "low",
        "confidence":        1.0,
        "expected_level":    RiskLevel.LOW,
        "expected_category": "MEDICATION",
    },
    {
        "id":                3,
        "description":       "User has a fever and feels dizzy.",
        "symptoms":          ["fever", "dizziness"],
        "severity":          "medium",
        "confidence":        0.9,
        "expected_level":    RiskLevel.MEDIUM,
        "expected_category": "NEUROLOGICAL",
    },
    {
        "id":                4,
        "description":       "User missed medicine and has a fever (confidence 0.85).",
        "symptoms":          ["medicine_missed", "fever"],
        "severity":          "medium",
        "confidence":        0.85,
        "expected_level":    RiskLevel.LOW,       # 35 * 0.85 ≈ 30 → LOW
        "expected_category": "MEDICATION",
    },
    {
        "id":                5,
        "description":       "User struggles to breathe after climbing stairs.",
        "symptoms":          ["breathing_problem"],
        "severity":          "high",
        "confidence":        0.95,
        "expected_level":    RiskLevel.MEDIUM,    # 60 * 0.95 ≈ 57 → MEDIUM
        "expected_category": "RESPIRATORY",
    },
    {
        "id":                6,
        "description":       "Sensor detected a fall; user says they are okay.",
        "symptoms":          ["fall_detected"],
        "severity":          "medium",
        "confidence":        1.0,
        "expected_level":    RiskLevel.HIGH,      # 70 → HIGH
        "expected_category": "FALL",
    },
    {
        "id":                7,
        "description":       "User reports chest pain and left-arm numbness.",
        "symptoms":          ["chest_pain"],
        "severity":          "high",
        "confidence":        1.0,
        "expected_level":    RiskLevel.HIGH,      # 70 → HIGH
        "expected_category": "CARDIAC",
    },
    {
        "id":                8,
        "description":       "User has chest pain and difficulty breathing.",
        "symptoms":          ["chest_pain", "breathing_problem"],
        "severity":          "high",
        "confidence":        0.95,
        "expected_level":    RiskLevel.CRITICAL,  # 110 * 0.95 ≈ 105 → CRITICAL
        "expected_category": "CARDIAC",
    },
    {
        "id":                9,
        "description":       "User shows classic stroke symptoms.",
        "symptoms":          ["stroke_symptoms"],
        "severity":          "critical",
        "confidence":        0.99,
        "expected_level":    RiskLevel.CRITICAL,  # 140 * 0.99 ≈ 139 → CRITICAL
        "expected_category": "NEUROLOGICAL",
    },
    {
        "id":                10,
        "description":       "User is unconscious with stroke and fall detected.",
        "symptoms":          ["unconscious", "stroke_symptoms", "fall_detected"],
        "severity":          "critical",
        "confidence":        1.0,
        "expected_level":    RiskLevel.CRITICAL,  # 300 → CRITICAL
        "expected_category": "CARDIAC",
    },
    {
        "id":                11,
        "description":       "Chest pain + breathing, only 50% LLM confidence.",
        "symptoms":          ["chest_pain", "breathing_problem"],
        "severity":          "high",
        "confidence":        0.5,
        "expected_level":    RiskLevel.MEDIUM,    # 110 * 0.5 = 55 → MEDIUM
        "expected_category": "CARDIAC",
    },
]


# ---------------------------------------------------------------------------
# Script runner
# ---------------------------------------------------------------------------

def run_tests() -> None:
    """Execute all test cases and print a pass/fail summary."""
    passed = 0
    failed = 0

    print("=" * 70)
    print("  WellRing — Scoring Engine Clinical Scenarios")
    print("  (canonical tests: pytest tests/test_scoring_engine.py)")
    print("=" * 70)

    for case in TEST_CASES:
        result = calculate_score(
            case["symptoms"],
            case["severity"],
            case.get("confidence", 1.0),
        )
        alert = determine_action(result["score"])

        actual_lvl  = result["risk_level"]
        actual_cat  = result["category"]
        expect_lvl  = case["expected_level"].value
        expect_cat  = case["expected_category"]

        lvl_ok = actual_lvl == expect_lvl
        cat_ok = actual_cat == expect_cat
        ok     = lvl_ok and cat_ok

        status  = "✅ PASS" if ok else "❌ FAIL"
        passed += ok
        failed += not ok

        print(f"\nCase {case['id']:02d}: {status}")
        print(f"  Scenario   : {case['description']}")
        print(f"  Symptoms   : {case['symptoms']}")
        print(f"  Severity   : {case['severity']}  |  Confidence: {case.get('confidence', 1.0)}")
        print(f"  Base Score : {result['base_score']}  →  Final Score: {result['score']}")
        print(f"  Category   : {actual_cat}  (expected {expect_cat}) {'✅' if cat_ok else '❌'}")
        print(f"  Risk Level : {actual_lvl}  (expected {expect_lvl}) {'✅' if lvl_ok else '❌'}")
        print(f"  Action     : {alert['action']}")
        print(f"  Next Step  : {alert['steps'][0]}")

    total = len(TEST_CASES)
    print("\n" + "=" * 70)
    print(f"  Results: {passed} passed, {failed} failed out of {total} tests")
    print("=" * 70)

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    run_tests()
