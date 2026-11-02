"""
EcoCart Eco-Score methodology v1.

    eco_score = 0.40 * material_score
              + 0.25 * packaging_score
              + 0.20 * recyclability_pct
              + 0.15 * durability_score

All four inputs are on a 0-100 scale:
  material_score   - assumed relative impact class of the main raw material
  packaging_score  - how recyclable / minimal the retail packaging is
  recyclability_pct- share of the product that can be recycled at end of life
  durability_score - expected useful life / reusability (single-use items score low)

The same formula is implemented in Oracle as FN_COMPUTE_ECO_SCORE so that the
database and the application can never disagree. Scores computed from assumed
inputs are labelled DATA_ORIGIN = 'SYNTHETIC' and described in the UI as demo
estimates, never as certified or measured environmental performance.
"""

METHODOLOGY_VERSION = "EcoCart methodology v1"

WEIGHTS = {"material": 0.40, "packaging": 0.25, "recyclability": 0.20, "durability": 0.15}

GRADE_BANDS = [(80, "A"), (65, "B"), (50, "C"), (35, "D"), (0, "E")]


def compute_eco_score(material_score, packaging_score, recyclability_pct, durability_score) -> int:
    v = (WEIGHTS["material"] * (material_score or 0)
         + WEIGHTS["packaging"] * (packaging_score or 0)
         + WEIGHTS["recyclability"] * (recyclability_pct or 0)
         + WEIGHTS["durability"] * (durability_score or 0))
    # Oracle ROUND() rounds halves away from zero; mirror that instead of Python's banker's rounding.
    return max(0, min(100, int(v + 0.5)))


def eco_grade(score) -> str:
    if score is None:
        return "N/A"
    for threshold, grade in GRADE_BANDS:
        if score >= threshold:
            return grade
    return "E"


def grade_label(grade: str) -> str:
    return {
        "A": "Excellent", "B": "Good", "C": "Moderate", "D": "Below average", "E": "Poor", "N/A": "Not assessed",
    }.get(grade, "Not assessed")
