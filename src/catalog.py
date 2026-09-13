from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PRODUCTS_PATH = ROOT / "data" / "products.csv"

SMALL_PRODUCT_IDS = ["P02", "P07", "P09", "P15", "P17", "P23"]

FLAVOR_LABELS = {
    "chocolate": "Chocolate",
    "froitas": "Froitas",
    "mel_froitos_secos": "Mel / froitos secos",
    "neutro_avena": "Neutro / avea",
}

PRICE_BAND_LABELS = {
    "menos_3": "Menos de 3 €",
    "de_3_a_4": "3–4 €",
    "mais_4": "Máis de 4 €",
}

PRIORITY_LABELS = {
    "prezo": "Prezo",
    "sabor": "Sabor",
    "nutricion": "Nutrición",
    "sustentabilidade": "Sustentabilidade",
}


def load_products() -> pd.DataFrame:
    """Load the fixed fictional cereal catalogue."""
    df = pd.read_csv(PRODUCTS_PATH)
    required = {
        "id",
        "name",
        "flavor",
        "price_eur",
        "price_band",
        "nutrition_level",
        "nutrition_text",
        "sustainability_level",
        "sustainability_text",
        "priority_tag",
    }
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"Faltan columnas no catálogo: {sorted(missing)}")
    if len(df) != 24 or df["id"].nunique() != 24:
        raise ValueError("O catálogo debe conter exactamente 24 produtos con IDs únicos.")
    return df


def get_small_catalog(products: pd.DataFrame) -> pd.DataFrame:
    """Return the six fixed products used in the small condition."""
    result = products[products["id"].isin(SMALL_PRODUCT_IDS)].copy()
    if len(result) != 6:
        raise ValueError("A selección small non contén exactamente 6 produtos.")
    order = {product_id: i for i, product_id in enumerate(SMALL_PRODUCT_IDS)}
    result["_small_order"] = result["id"].map(order)
    return result.sort_values("_small_order").drop(columns="_small_order").reset_index(drop=True)


def deterministic_shuffle(products: pd.DataFrame, participant_id: str) -> pd.DataFrame:
    """Shuffle catalogue order reproducibly from the anonymous participant id."""
    digest = hashlib.sha256(participant_id.encode("utf-8")).hexdigest()
    seed = int(digest[:8], 16)
    return products.sample(frac=1, random_state=seed).reset_index(drop=True)
