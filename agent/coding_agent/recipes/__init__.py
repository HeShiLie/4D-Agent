"""Recipes — few-shot examples for code generation.

Recipes are selected by question content (keyword matching),
not by task labels.
"""
import os

RECIPES_DIR = os.path.dirname(os.path.abspath(__file__))


def load_recipe(name: str) -> str:
    path = os.path.join(RECIPES_DIR, f"{name}.py")
    if not os.path.exists(path):
        return ""
    with open(path) as f:
        return f.read()


# Each recipe: (keywords_in_question, keywords_in_spec, recipe_file)
RECIPE_RULES = [
    {
        "name": "relative_velocity",
        "q_keywords": ["faster", "moving faster", "speed", "velocity", "更快",
                        "vehicle is moving", "车.*移动", "moving or stationary",
                        "stationary"],
        "spec_keywords": ["colored_box", "compensate", "ego", "residual",
                          "green", "blue"],
        "file": "relative_velocity",
    },
    {
        "name": "fall_direction",
        "q_keywords": ["fall", "lean", "lie down", "get up", "倒", "摔",
                        "which side", "left-hand", "right-hand", "body"],
        "spec_keywords": ["pose", "keypoint", "body", "lean", "fall"],
        "file": "fall_direction",
    },
    {
        "name": "passage_feasibility",
        "q_keywords": ["pass through", "passage", "cone", "gate", "通过",
                        "gap", "fit"],
        "spec_keywords": ["cone", "gate", "gap", "vehicle_width", "passage"],
        "file": "passage_feasibility",
    },
    {
        "name": "soccer_shot",
        "q_keywords": ["goal", "kick", "soccer", "football", "free kick",
                        "enter the goal", "score"],
        "spec_keywords": ["ball", "trajectory", "goal"],
        "file": "soccer_shot",
    },
]


def select_recipe_by_content(question: str, analysis_spec: dict = None) -> str:
    """Select recipe by matching question text and analysis spec content.

    Returns recipe source code or empty string.
    """
    q_lower = question.lower()
    spec_str = ""
    if analysis_spec:
        spec_str = str(analysis_spec).lower()

    best_score = 0
    best_file = ""

    for rule in RECIPE_RULES:
        score = 0
        for kw in rule["q_keywords"]:
            if kw.lower() in q_lower:
                score += 2
        for kw in rule["spec_keywords"]:
            if kw.lower() in spec_str:
                score += 1
        if score > best_score:
            best_score = score
            best_file = rule["file"]

    if best_score >= 2:
        return load_recipe(best_file)
    return ""


# Keep backward compatibility
def select_recipe(task: str) -> str:
    """Legacy: select by task name. Use select_recipe_by_content instead."""
    mapping = {
        "Relative_Velocity": "relative_velocity",
        "Fall_Direction": "fall_direction",
        "Passage_Feasibility": "passage_feasibility",
        "Soccer_Shot": "soccer_shot",
        "Vehicle_Movement": "relative_velocity",
        "Rotation_Direction": "fall_direction",
    }
    name = mapping.get(task, "")
    return load_recipe(name) if name else ""
