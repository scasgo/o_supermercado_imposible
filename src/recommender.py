from __future__ import annotations

from typing import Mapping

import pandas as pd

from src.catalog import FLAVOR_LABELS, PRICE_BAND_LABELS, PRIORITY_LABELS

VALID_PRIORITIES = set(PRIORITY_LABELS)
VALID_FLAVORS = set(FLAVOR_LABELS)
VALID_PRICE_BANDS = set(PRICE_BAND_LABELS)


def validate_preferences(preferences: Mapping[str, str]) -> None:
    if preferences.get("priority") not in VALID_PRIORITIES:
        raise ValueError("Prioridade non válida")
    if preferences.get("flavor") not in VALID_FLAVORS:
        raise ValueError("Sabor non válido")
    if preferences.get("price_band") not in VALID_PRICE_BANDS:
        raise ValueError("Rango de prezo non válido")


def score_product(product: Mapping[str, object], preferences: Mapping[str, str]) -> tuple[int, list[str]]:
    """Return transparent score and Galician explanation lines.

    Rules:
    - +4 if the product's main profile matches the participant's main priority.
    - +3 if flavour family matches.
    - +2 if price band matches.
    No secondary +1 is used.
    """
    validate_preferences(preferences)
    score = 0
    reasons: list[str] = []

    if str(product["priority_tag"]) == preferences["priority"]:
        score += 4
        reasons.append(f"+4 pola prioridade principal ({PRIORITY_LABELS[preferences['priority']]})")

    if str(product["flavor"]) == preferences["flavor"]:
        score += 3
        reasons.append(f"+3 polo sabor ({FLAVOR_LABELS[preferences['flavor']]})")

    if str(product["price_band"]) == preferences["price_band"]:
        score += 2
        reasons.append(f"+2 polo prezo ({PRICE_BAND_LABELS[preferences['price_band']]})")

    if not reasons:
        reasons.append("+0: non coincidiu cos tres criterios usados pola regra")

    return score, reasons


def recommend(products: pd.DataFrame, preferences: Mapping[str, str], top_n: int = 6) -> pd.DataFrame:
    """Score all products and return the top N, ties broken by product id."""
    validate_preferences(preferences)
    scored = products.copy()
    scored["score"] = scored.apply(lambda row: score_product(row, preferences)[0], axis=1)
    scored = scored.sort_values(["score", "id"], ascending=[False, True], kind="stable")
    return scored.head(top_n).reset_index(drop=True)


def explain_preferences(preferences: Mapping[str, str]) -> str:
    validate_preferences(preferences)
    return (
        "Ti dixeches que valoras máis "
        f"{PRIORITY_LABELS[preferences['priority']].lower()}, que prefires "
        f"{FLAVOR_LABELS[preferences['flavor']].lower()} e que o teu rango é "
        f"{PRICE_BAND_LABELS[preferences['price_band']].lower()}."
    )


def explain_product_score(product: Mapping[str, object], preferences: Mapping[str, str]) -> str:
    score, reasons = score_product(product, preferences)
    joined = "; ".join(reasons)
    return f"Para {product['name']}, o algoritmo sumou {joined}. Total: {score} puntos."
