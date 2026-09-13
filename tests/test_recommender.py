from __future__ import annotations

import pandas as pd

from src.catalog import SMALL_PRODUCT_IDS, get_small_catalog, load_products
from src.recommender import recommend, score_product

PRODUCTS = load_products()


def prefs(priority="prezo", flavor="chocolate", price_band="menos_3"):
    return {"priority": priority, "flavor": flavor, "price_band": price_band}


def test_full_match_scores_nine():
    row = PRODUCTS[PRODUCTS["id"] == "P01"].iloc[0]
    score, reasons = score_product(row, prefs())
    assert score == 9
    assert len(reasons) == 3


def test_zero_match_scores_zero():
    row = PRODUCTS[PRODUCTS["id"] == "P18"].iloc[0]
    score, reasons = score_product(row, prefs(priority="nutricion", flavor="chocolate", price_band="menos_3"))
    assert score == 0
    assert reasons[0].startswith("+0")


def test_recommend_returns_exactly_six_unique_products():
    result = recommend(PRODUCTS, prefs(priority="sabor", flavor="froitas", price_band="de_3_a_4"))
    assert len(result) == 6
    assert result["id"].nunique() == 6


def test_scores_are_sorted_descending():
    result = recommend(PRODUCTS, prefs(priority="sustentabilidade", flavor="neutro_avena", price_band="mais_4"))
    assert result["score"].tolist() == sorted(result["score"].tolist(), reverse=True)


def test_ties_break_by_product_id():
    toy = pd.DataFrame(
        [
            {"id": "P99", "priority_tag": "prezo", "flavor": "chocolate", "price_band": "menos_3"},
            {"id": "P98", "priority_tag": "prezo", "flavor": "chocolate", "price_band": "menos_3"},
        ]
    )
    result = recommend(toy, prefs(), top_n=2)
    assert result["id"].tolist() == ["P98", "P99"]


def test_small_catalog_is_fixed_and_covers_all_price_bands_and_flavors():
    small = get_small_catalog(PRODUCTS)
    assert small["id"].tolist() == SMALL_PRODUCT_IDS
    assert set(small["price_band"]) == {"menos_3", "de_3_a_4", "mais_4"}
    assert set(small["flavor"]) == {"chocolate", "froitas", "mel_froitos_secos", "neutro_avena"}
