"""
test_cases.py
=============
Health scenarios to validate the scoring and alert engine.

Run directly with:
    python src/scoring_engine/test_cases.py

Each test case includes:
    - symptoms          : list of symptom identifiers
    - severity          : "low" | "medium" | "high" | "critical"
    - confidence        : LLM confidence float [0.0–1.0]
    - description       : plain-English scenario description
    - expected_level    : the RiskLevel the test must produce to pass
    - expected_category : the primary clinical category expected
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from src.scoring_engine.scoring import calculate_score
from src.scoring_engine.alerts  import determine_action
from src.scoring_engine.baseline import RiskLevel

# ---------------------------------------------------------------------------
# Test case definitions
# ---------------------------------------------------------------------------

TEST_CASES = [
    # ── Case 1: Mild dizziness, low confidence ─────────────────────────────
    {
        "id":                1,
        "description":       "User reports mild dizziness with low-confidence detection.",
        "symptoms":          ["dizziness"],
        "severity":          "low",
        "confidence":        0.6,
        "expected_level":    RiskLevel.LOW,        # base=20, final=12 → LOW
        "expected_category": "NEUROLOGICAL",
    },
    # ── Case 2: Missed medicine, full confidence ───────────────────────────
    {
        "id":                2,
        "description":       "User forgot to take medicine this morning.",
        "symptoms":          ["medicine_missed"],
        "severity":          "low",
        "confidence":        1.0,
        "expected_level":    RiskLevel.LOW,        # score = 10 → LOW
        "expected_category": "MEDICATION",
    },
    # ── Case 3: Fever + dizziness, medium severity ────────────────────────
    {
        "id":                3,
        "description":       "User has a fever and feels dizzy.",
        "symptoms":          ["fever", "dizziness"],
        "severity":          "medium",
        "confidence":        0.9,
        "expected_level":    RiskLevel.MEDIUM,     # base=45, final=41 → MEDIUM
        "expected_category": "NEUROLOGICAL",
    },
    # ── Case 4: Medicine + fever, medium severity ─────────────────────────
    {
        "id":                4,
        "description":       "User missed medicine and has a fever.",
        "symptoms":          ["medicine_missed", "fever"],
        "severity":          "medium",
        "confidence":        0.85,
        # NOTE: 35 * 0.85 = 29.75 → rounds to 30 → LOW
        "expected_level":    RiskLevel.LOW,
        "expected_category": "MEDICATION",  # MEDICATION (pri 2) > GENERAL (pri 1)
    },
    # ── Case 5: Breathing problem, high severity ──────────────────────────
    {
        "id":                5,
        "description":       "User struggles to breathe after climbing stairs.",
        "symptoms":          ["breathing_problem"],
        "severity":          "high",
        "confidence":        0.95,
        "expected_level":    RiskLevel.MEDIUM,     # base=60, final=57 → MEDIUM
        "expected_category": "RESPIRATORY",
    },
    # ── Case 6: Fall detected, medium severity ────────────────────────────
    {
        "id":                6,
        "description":       "Sensor detected a fall; user says they are okay.",
        "symptoms":          ["fall_detected"],
        "severity":          "medium",
        "confidence":        1.0,
        "expected_level":    RiskLevel.HIGH,       # score = 70 → HIGH
        "expected_category": "FALL",
    },
    # ── Case 7: Chest pain, high severity ────────────────────────────────
    {
        "id":                7,
        "description":       "User reports chest pain and left-arm numbness.",
        "symptoms":          ["chest_pain"],
        "severity":          "high",
        "confidence":        1.0,
        "expected_level":    RiskLevel.HIGH,       # score = 70 → HIGH
        "expected_category": "CARDIAC",
    },
    # ── Case 8: Chest pain + breathing, high severity ─────────────────────
    {
        "id":                8,
        "description":       "User has chest pain and difficulty breathing.",
        "symptoms":          ["chest_pain", "breathing_problem"],
        "severity":          "high",
        "confidence":        0.95,
        "expected_level":    RiskLevel.CRITICAL,   # base=110, final=105 → CRITICAL
        "expected_category": "CARDIAC",
    },
    # ── Case 9: Stroke symptoms, critical severity ────────────────────────
    {
        "id":                9,
        "description":       "User shows classic stroke symptoms (face drooping, slurred speech).",
        "symptoms":          ["stroke_symptoms"],
        "severity":          "critical",
        "confidence":        0.99,
        "expected_level":    RiskLevel.CRITICAL,   # base=140, final=139 → CRITICAL
        "expected_category": "NEUROLOGICAL",
    },
    # ── Case 10: Multiple critical symptoms ──────────────────────────────
    {
        "id":                10,
        "description":       "User is unconscious with stroke symptoms and fall detected.",
        "symptoms":          ["unconscious", "stroke_symptoms", "fall_detected"],
        "severity":          "critical",
        "confidence":        1.0,
        "expected_level":    RiskLevel.CRITICAL,   # score = 300 → CRITICAL
        "expected_category": "CARDIAC",            # CARDIAC > NEUROLOGICAL > FALL
    },
    # ── Case 11: Confidence halves a CRITICAL to HIGH ────────────────────
    # This demonstrates why confidence matters: a high-symptom report with
    # only 50% LLM confidence should be treated more cautiously.
    {
        "id":                11,
        "description":       "Chest pain reported but LLM is only 50% confident.",
        "symptoms":          ["chest_pain", "breathing_problem"],
        "severity":          "high",
        "confidence":        0.5,
        # NOTE: 110 * 0.5 = 55 → MEDIUM
        "expected_level":    RiskLevel.MEDIUM,
        "expected_category": "CARDIAC",
    },
]

# ---------------------------------------------------------------------------
# Test runner
# ---------------------------------------------------------------------------

def run_tests() -> None:
    """Execute all test cases and print a pass/fail summary."""
    passed = 0
    failed = 0

    print("=" * 70)
    print("  WellRing — Scoring Engine Test Suite (with Confidence + Categories)")
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

        status = "✅ PASS" if ok else "❌ FAIL"
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
        print(f"  Next Steps : {alert['steps'][0]}")   # show first step only

    total = len(TEST_CASES)
    print("\n" + "=" * 70)
    print(f"  Results: {passed} passed, {failed} failed out of {total} tests")
    print("=" * 70)

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    run_tests()
