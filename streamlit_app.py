from __future__ import annotations

import random
import time
import uuid
from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from src.catalog import (
    FLAVOR_LABELS,
    PRICE_BAND_LABELS,
    PRIORITY_LABELS,
    deterministic_shuffle,
    get_small_catalog,
    load_products,
)
from src.db import condition_counts, fetch_completed, fetch_participant, upsert_participant
from src.recommender import explain_preferences, explain_product_score, recommend

st.set_page_config(
    page_title="O supermercado imposible",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="collapsed",
)

CSS = r"""
<style>
:root {
  --ink: #172126;
  --muted: #5E6A70;
  --paper: #F7F5F0;
  --white: #FFFFFF;
  --accent: #1F6F78;
  --accent-soft: #E8F2F3;
  --line: #D9DEDF;
  --focus: #F2B134;
  --danger: #A53A3A;
  --radius: 16px;
}
html, body, [class*="css"]  { font-family: "Inter", "Segoe UI", Arial, sans-serif; }
.stApp { background: var(--paper); color: var(--ink); }
.block-container { max-width: 1180px; padding-top: 1.4rem; padding-bottom: 3rem; }
h1 { font-size: clamp(2rem, 5vw, 3.4rem) !important; line-height: 1.04 !important; letter-spacing: -0.03em; }
h2 { font-size: clamp(1.45rem, 3vw, 2.1rem) !important; }
h3 { font-size: 1.15rem !important; }
p, li, label { font-size: 1rem; line-height: 1.5; }
[data-testid="stCaptionContainer"] p { color: var(--muted); }
[data-testid="stButton"] button {
  min-height: 46px;
  border-radius: 12px;
  border: 1px solid var(--accent);
  font-weight: 700;
}
[data-testid="stButton"] button:focus-visible,
[data-testid="stRadio"] input:focus-visible,
[data-testid="stCheckbox"] input:focus-visible {
  outline: 3px solid var(--focus) !important;
  outline-offset: 2px;
}
[data-testid="stButton"] button[kind="primary"] {
  background: var(--accent);
  color: white;
}
[data-testid="stVerticalBlockBorderWrapper"] {
  border-color: var(--line) !important;
  border-radius: var(--radius) !important;
  background: var(--white);
}
.os-badge {
  display: inline-block;
  padding: .28rem .62rem;
  border: 1px solid var(--line);
  border-radius: 999px;
  background: white;
  color: var(--muted);
  font-size: .86rem;
  font-weight: 700;
  margin-bottom: .4rem;
}
.os-price { font-size: 1.55rem; font-weight: 800; margin: .15rem 0 .55rem 0; }
.os-kicker { color: var(--accent); font-weight: 800; text-transform: uppercase; letter-spacing: .08em; font-size: .78rem; }
.os-hero { max-width: 820px; }
.os-rule {
  background: var(--accent-soft);
  border-left: 4px solid var(--accent);
  border-radius: 10px;
  padding: .8rem 1rem;
  margin: .8rem 0 1rem 0;
}
.os-demo {
  background: #FFF3CD;
  border: 2px solid #D39E00;
  border-radius: 12px;
  padding: .8rem 1rem;
  font-weight: 800;
  margin-bottom: 1rem;
}
@media (max-width: 640px) {
  .block-container { padding-left: .9rem; padding-right: .9rem; padding-top: .8rem; }
  [data-testid="stButton"] button { min-height: 50px; font-size: 1rem; }
  h1 { margin-bottom: .5rem !important; }
}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

PRODUCTS = load_products()
CONDITIONS = ["small", "large", "algorithm"]
CONDITION_PUBLIC_LABELS = {
    "small": "6 opcións",
    "large": "24 opcións",
    "algorithm": "6 recomendadas + acceso ás 24",
}


def setting(name: str, default=None):
    try:
        return st.secrets.get(name, default)
    except (FileNotFoundError, KeyError):
        return default


def as_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on", "si", "sí"}


APP_MODE = "production"
DASHBOARD_DEMO = False
KIOSK_MODE = False
IS_DEMO_PARTICIPANT = APP_MODE != "production"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_defaults() -> None:
    defaults = {
        "initialized": True,
        "participant_id": None,
        "timestamp_utc": None,
        "total_start": None,
        "stage": "welcome",
        "age_band": None,
        "online_purchase_frequency": None,
        "condition": None,
        "pref_priority": None,
        "pref_flavor": None,
        "pref_price": None,
        "recommendation_ids": [],
        "show_full_catalog": False,
        "opened_full_catalog": False,
        "decision_start": None,
        "decision_perf_start": None,
        "decision_end": None,
        "decision_seconds": None,
        "product_selected": None,
        "no_choice": False,
        "difficulty": None,
        "confidence": None,
        "satisfaction": None,
        "continue_searching": None,
        "completed_at": None,
        "total_seconds": None,
        "status": None,
        "decision_locked": False,
        "db_last_error": None,
        "db_row_seen": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def hydrate_from_row(row: dict) -> None:
    st.session_state.participant_id = str(row["participant_id"])
    st.session_state.timestamp_utc = row.get("timestamp_utc")
    st.session_state.total_start = row.get("total_start") or row.get("timestamp_utc")
    st.session_state.age_band = row.get("age_band")
    st.session_state.online_purchase_frequency = row.get("online_purchase_frequency")
    st.session_state.condition = row.get("condition")
    st.session_state.pref_priority = row.get("pref_priority")
    st.session_state.pref_flavor = row.get("pref_flavor")
    st.session_state.pref_price = row.get("pref_price")
    st.session_state.recommendation_ids = row.get("recommendation_ids") or []
    st.session_state.opened_full_catalog = bool(row.get("opened_full_catalog", False))
    st.session_state.show_full_catalog = bool(row.get("opened_full_catalog", False))
    st.session_state.decision_start = row.get("decision_start")
    st.session_state.decision_end = row.get("decision_end")
    st.session_state.decision_seconds = row.get("decision_seconds")
    st.session_state.product_selected = row.get("product_selected")
    st.session_state.no_choice = bool(row.get("no_choice", False))
    st.session_state.difficulty = row.get("difficulty")
    st.session_state.confidence = row.get("confidence")
    st.session_state.satisfaction = row.get("satisfaction")
    st.session_state.continue_searching = row.get("continue_searching")
    st.session_state.completed_at = row.get("completed_at")
    st.session_state.total_seconds = row.get("total_seconds")
    st.session_state.status = row.get("status")
    st.session_state.db_row_seen = True

    status = row.get("status")
    condition = row.get("condition")
    if status == "completed":
        st.session_state.stage = "result"
    elif status == "decision_made":
        st.session_state.stage = "post"
    elif condition == "algorithm" and status == "assigned":
        st.session_state.stage = "algo_intro"
    else:
        st.session_state.stage = "catalog"
        # A hard page reload creates a new Streamlit session. A previous monotonic
        # clock cannot be trusted, so the timed segment restarts from the next
        # catalogue render. The participant id and condition remain the same.
        if st.session_state.decision_end is None:
            st.session_state.decision_start = None
            st.session_state.decision_perf_start = None


def try_restore_from_query() -> None:
    if st.session_state.participant_id:
        return
    pid = st.query_params.get("pid")
    if not pid:
        return
    try:
        uuid.UUID(str(pid))
    except ValueError:
        st.query_params.pop("pid", None)
        return
    row, error = fetch_participant(str(pid))
    if row:
        hydrate_from_row(row)
    elif error:
        st.session_state.db_last_error = error
        # We cannot safely reconstruct demographics/condition without the row.
        # Start again instead of guessing and corrupting the record.
        st.query_params.pop("pid", None)


init_defaults()
try_restore_from_query()


def snapshot() -> dict:
    return {
        "participant_id": st.session_state.participant_id,
        "timestamp_utc": st.session_state.timestamp_utc,
        "age_band": st.session_state.age_band,
        "online_purchase_frequency": st.session_state.online_purchase_frequency,
        "condition": st.session_state.condition,
        "pref_priority": st.session_state.pref_priority,
        "pref_flavor": st.session_state.pref_flavor,
        "pref_price": st.session_state.pref_price,
        "decision_start": st.session_state.decision_start,
        "decision_end": st.session_state.decision_end,
        "decision_seconds": st.session_state.decision_seconds,
        "product_selected": st.session_state.product_selected,
        "no_choice": bool(st.session_state.no_choice),
        "difficulty": st.session_state.difficulty,
        "confidence": st.session_state.confidence,
        "satisfaction": st.session_state.satisfaction,
        "continue_searching": st.session_state.continue_searching,
        "opened_full_catalog": bool(st.session_state.opened_full_catalog),
        "recommendation_ids": st.session_state.recommendation_ids or None,
        "status": st.session_state.status,
        "total_start": st.session_state.total_start,
        "completed_at": st.session_state.completed_at,
        "total_seconds": st.session_state.total_seconds,
        "is_demo": IS_DEMO_PARTICIPANT,
    }


def persist() -> bool:
    if not st.session_state.participant_id:
        return False
    ok, error = upsert_participant(snapshot())
    st.session_state.db_last_error = error
    if ok:
        st.session_state.db_row_seen = True
    return ok


def choose_balanced_condition() -> str:
    counts, error = condition_counts(include_demo=IS_DEMO_PARTICIPANT)
    if counts is None:
        st.session_state.db_last_error = error
        return random.SystemRandom().choice(CONDITIONS)
    minimum = min(counts.values())
    candidates = [name for name, count in counts.items() if count == minimum]
    return random.SystemRandom().choice(candidates)


def begin_participant(age_band: str, frequency: str) -> None:
    st.session_state.participant_id = str(uuid.uuid4())
    st.session_state.timestamp_utc = utc_now_iso()
    st.session_state.total_start = st.session_state.timestamp_utc
    st.session_state.age_band = age_band
    st.session_state.online_purchase_frequency = frequency
    st.session_state.condition = choose_balanced_condition()
    st.session_state.status = "assigned"
    st.query_params["pid"] = st.session_state.participant_id
    persist()
    if st.session_state.condition == "algorithm":
        st.session_state.stage = "algo_intro"
    else:
        st.session_state.stage = "catalog"


def preference_dict() -> dict[str, str]:
    return {
        "priority": st.session_state.pref_priority,
        "flavor": st.session_state.pref_flavor,
        "price_band": st.session_state.pref_price,
    }


def get_recommendations() -> pd.DataFrame:
    prefs = preference_dict()
    if st.session_state.recommendation_ids:
        order = {pid: i for i, pid in enumerate(st.session_state.recommendation_ids)}
        existing = PRODUCTS[PRODUCTS["id"].isin(order)].copy()
        if len(existing) == len(order):
            existing["_order"] = existing["id"].map(order)
            scored = recommend(PRODUCTS, prefs, top_n=24)[["id", "score"]]
            existing = existing.merge(scored, on="id", how="left")
            return existing.sort_values("_order").drop(columns="_order").reset_index(drop=True)
    recs = recommend(PRODUCTS, prefs, top_n=6)
    st.session_state.recommendation_ids = recs["id"].tolist()
    return recs


def ensure_decision_timer() -> None:
    if st.session_state.decision_perf_start is None:
        st.session_state.decision_perf_start = time.perf_counter()
        st.session_state.decision_start = utc_now_iso()


def choose_product(product_id: str | None) -> None:
    if st.session_state.decision_locked:
        return
    st.session_state.decision_locked = True
    if st.session_state.decision_perf_start is None:
        # Defensive fallback; in normal flow the timer starts before buttons render.
        st.session_state.decision_perf_start = time.perf_counter()
        st.session_state.decision_start = utc_now_iso()
    st.session_state.decision_end = utc_now_iso()
    elapsed = time.perf_counter() - st.session_state.decision_perf_start
    st.session_state.decision_seconds = round(max(0.0, elapsed), 3)
    st.session_state.product_selected = product_id
    st.session_state.no_choice = product_id is None
    st.session_state.status = "decision_made"
    persist()
    st.session_state.stage = "post"


def open_full_catalog() -> None:
    # Do not write to Supabase here: a network call would add group-specific
    # latency to decision_seconds. The flag is saved with the final choice.
    st.session_state.opened_full_catalog = True
    st.session_state.show_full_catalog = True


def product_card(product: pd.Series) -> None:
    flavor_label = FLAVOR_LABELS[str(product["flavor"])]
    price = f"{float(product['price_eur']):.2f}".replace(".", ",") + " €"
    with st.container(border=True):
        st.markdown(f'<span class="os-badge">{flavor_label}</span>', unsafe_allow_html=True)
        st.markdown(f"### {product['name']}")
        st.markdown(f'<div class="os-price">{price}</div>', unsafe_allow_html=True)
        st.write(f"**Nutrición:** {product['nutrition_text']}")
        st.write(f"**Sustentabilidade:** {product['sustainability_text']}")
        st.button(
            f"Escoller {product['name']}",
            key=f"choose_{product['id']}",
            on_click=choose_product,
            args=(str(product["id"]),),
            use_container_width=True,
            type="primary",
            disabled=st.session_state.decision_locked,
        )


def render_catalog(products: pd.DataFrame) -> None:
    for start in range(0, len(products), 3):
        cols = st.columns(3, gap="small", wrap=True)
        batch = products.iloc[start : start + 3]
        for col, (_, product) in zip(cols, batch.iterrows()):
            with col:
                product_card(product)


def participant_header() -> None:
    st.markdown('<div class="os-kicker">O supermercado imposible</div>', unsafe_allow_html=True)


def render_welcome() -> None:
    participant_header()
    st.markdown('<div class="os-hero">', unsafe_allow_html=True)
    st.title("O supermercado imposible")
    st.subheader("Máis opcións fannos máis libres… ou necesitamos que un algoritmo elixa por nós?")
    st.markdown("### Netflix, Amazon, Spotify… elixes ti ou elixe o algoritmo?")
    st.write("En poucos minutos entrarás nun supermercado ficticio de cereais. A túa tarefa é escoller un produto —ou decidir que non mercarías ningún.")
    st.markdown('</div>', unsafe_allow_html=True)
    if st.button("Comezar", type="primary", use_container_width=True):
        st.session_state.stage = "consent"
        st.rerun()


def render_consent() -> None:
    participant_header()
    st.header("Antes de empezar")
    st.write(
        "Esta é unha **actividade divulgativa** sobre como tomamos decisións cando temos poucas opcións, moitas opcións ou unha recomendación automática."
    )
    st.write(
        "Non che pediremos nome, correo, teléfono nin usuario de ningunha plataforma. Gardaremos un identificador aleatorio, unha franxa de idade, as túas respostas e os tempos necesarios para a actividade."
    )
    st.write(
        "Os resultados poden mostrarse **agrupados e de forma anónima** na pantalla do stand. Podes abandonar cando queiras pechando esta páxina."
    )
    accepted = st.checkbox("Lin esta información e quero participar.")
    if st.button("Continuar", type="primary", use_container_width=True, disabled=not accepted):
        st.session_state.stage = "demographics"
        st.rerun()
    st.button("Volver", on_click=lambda: st.session_state.update(stage="welcome"))


def render_demographics() -> None:
    participant_header()
    st.header("Dúas preguntas rápidas")
    with st.form("demographics_form"):
        age = st.radio(
            "En que franxa de idade estás?",
            [
                "Menos de 14",
                "14–17",
                "18–24",
                "25–34",
                "35–49",
                "50–64",
                "65 ou máis",
                "Prefiro non dicilo",
            ],
            index=None,
        )
        frequency = st.radio(
            "Con que frecuencia mercas produtos por internet?",
            [
                "Nunca ou case nunca",
                "Menos dunha vez ao mes",
                "1–3 veces ao mes",
                "Unha vez á semana ou máis",
                "Prefiro non dicilo",
            ],
            index=None,
        )
        submitted = st.form_submit_button("Entrar no supermercado", type="primary", use_container_width=True)
    if submitted:
        if age is None or frequency is None:
            st.error("Responde as dúas preguntas para continuar.")
        elif age == "Menos de 14":
            st.session_state.stage = "under14"
            st.rerun()
        else:
            begin_participant(age, frequency)
            st.rerun()


def render_under14() -> None:
    participant_header()
    st.header("Esta versión está pensada para persoas de 14 anos ou máis")
    st.write("Podes mirar a explicación e a pantalla colectiva co persoal do stand, pero nesta versión non gardaremos unha participación túa.")
    if st.button("Volver ao inicio", use_container_width=True):
        st.session_state.stage = "welcome"
        st.rerun()


def render_algo_intro() -> None:
    participant_header()
    st.header("Antes de ver os cereais")
    st.write("Imos facerche tres preguntas para ordenar o catálogo segundo as túas preferencias.")
    st.write("A recomendación usarase só nesta actividade. Non hai perfís persoais nin contas reais.")
    if st.button("Responder as 3 preguntas", type="primary", use_container_width=True):
        st.session_state.stage = "algo_questions"
        st.rerun()


def render_algo_questions() -> None:
    participant_header()
    st.header("As túas preferencias")
    with st.form("algo_form"):
        priority_label = st.radio(
            "1. Que valoras máis ao escoller cereais?",
            ["Prezo", "Sabor", "Nutrición", "Sustentabilidade"],
            index=None,
        )
        flavor_label = st.radio(
            "2. Que sabor prefires?",
            ["Chocolate", "Froitas", "Mel / froitos secos", "Neutro / avea"],
            index=None,
        )
        price_label = st.radio(
            "3. Canto pagarías?",
            ["Menos de 3 €", "3–4 €", "Máis de 4 €"],
            index=None,
        )
        submitted = st.form_submit_button("Continuar", type="primary", use_container_width=True)
    if submitted:
        if priority_label is None or flavor_label is None or price_label is None:
            st.error("Responde as tres preguntas para continuar.")
            return
        reverse_priority = {value: key for key, value in PRIORITY_LABELS.items()}
        reverse_flavor = {value: key for key, value in FLAVOR_LABELS.items()}
        reverse_price = {value: key for key, value in PRICE_BAND_LABELS.items()}
        st.session_state.pref_priority = reverse_priority[priority_label]
        st.session_state.pref_flavor = reverse_flavor[flavor_label]
        st.session_state.pref_price = reverse_price[price_label]
        recs = recommend(PRODUCTS, preference_dict(), top_n=6)
        st.session_state.recommendation_ids = recs["id"].tolist()
        st.session_state.status = "preferences_done"
        persist()
        with st.spinner("Analizando as túas preferencias…"):
            time.sleep(1.0)
        st.session_state.stage = "catalog"
        st.rerun()


def render_catalog_screen() -> None:
    participant_header()
    condition = st.session_state.condition
    if condition == "algorithm" and not st.session_state.show_full_catalog:
        st.header("Seleccionamos 6 para ti")
        st.write("Escolle un produto ou indica que non mercarías ningún.")
        catalog = get_recommendations().drop(columns=["score"], errors="ignore")
    elif condition == "algorithm" and st.session_state.show_full_catalog:
        st.header("Os 24 produtos")
        st.write("Agora podes revisar todo o catálogo. O teu tempo de decisión segue contando.")
        catalog = deterministic_shuffle(PRODUCTS, st.session_state.participant_id)
    elif condition == "small":
        st.header("Escolle un cereal")
        st.write("Escolle un produto ou indica que non mercarías ningún.")
        catalog = deterministic_shuffle(get_small_catalog(PRODUCTS), st.session_state.participant_id)
    else:
        st.header("Escolle un cereal")
        st.write("Escolle un produto ou indica que non mercarías ningún.")
        catalog = deterministic_shuffle(PRODUCTS, st.session_state.participant_id)

    # This line is deliberately immediately before the selectable catalogue.
    ensure_decision_timer()
    render_catalog(catalog)

    st.divider()
    if condition == "algorithm" and not st.session_state.show_full_catalog:
        st.button(
            "Ver os 24 produtos",
            on_click=open_full_catalog,
            use_container_width=True,
            disabled=st.session_state.decision_locked,
        )
    st.button(
        "Ningún me convence / non compraría ningún",
        on_click=choose_product,
        args=(None,),
        use_container_width=True,
        disabled=st.session_state.decision_locked,
    )
    st.caption("A tarefa é escoller unha única opción. Non hai resposta correcta.")


def render_post() -> None:
    participant_header()
    st.header("Como foi decidir?")
    st.write("Estas preguntas son iguais para todas as persoas participantes.")
    with st.form("post_form"):
        difficulty = st.radio("Que dificultade tivo a decisión?", list(range(1, 8)), index=None, horizontal=True)
        st.caption("1 = moi fácil · 7 = moi difícil")
        confidence = st.radio("Que confianza tes na túa elección?", list(range(1, 8)), index=None, horizontal=True)
        st.caption("1 = ningunha confianza · 7 = moita confianza")
        satisfaction = st.radio("Que satisfacción tes coa túa elección?", list(range(1, 8)), index=None, horizontal=True)
        st.caption("1 = nada satisfeito/a · 7 = moi satisfeito/a")
        continue_label = st.radio(
            "Se fose unha compra real, seguirías buscando antes de mercar?",
            ["Si", "Non"],
            index=None,
            horizontal=True,
        )
        submitted = st.form_submit_button("Ver o meu resultado", type="primary", use_container_width=True)
    if submitted:
        if None in (difficulty, confidence, satisfaction, continue_label):
            st.error("Responde as catro preguntas para continuar.")
            return
        st.session_state.difficulty = int(difficulty)
        st.session_state.confidence = int(confidence)
        st.session_state.satisfaction = int(satisfaction)
        st.session_state.continue_searching = continue_label == "Si"
        st.session_state.completed_at = utc_now_iso()
        try:
            start = datetime.fromisoformat(str(st.session_state.total_start))
            end = datetime.fromisoformat(str(st.session_state.completed_at))
            st.session_state.total_seconds = round(max(0.0, (end - start).total_seconds()), 3)
        except Exception:
            st.session_state.total_seconds = None
        st.session_state.status = "completed"
        persist()
        st.session_state.stage = "result"
        st.rerun()


def selected_product_row() -> pd.Series | None:
    product_id = st.session_state.product_selected
    if not product_id:
        return None
    matches = PRODUCTS[PRODUCTS["id"] == product_id]
    return None if matches.empty else matches.iloc[0]


def reset_for_next_participant() -> None:
    st.query_params.clear()
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()


def render_result() -> None:
    participant_header()
    st.header("O teu resultado")
    if st.session_state.no_choice:
        st.write("Decidiches **non mercar ningún cereal**.")
    else:
        row = selected_product_row()
        if row is not None:
            st.write(f"Escolliches **{row['name']}**.")
    if st.session_state.decision_seconds is not None:
        st.metric("Tempo de decisión", f"{float(st.session_state.decision_seconds):.1f} s")

    st.markdown("### Que experiencia che tocou?")
    condition = st.session_state.condition
    if condition == "small":
        st.write("Viches **6 produtos fixos**, elixidos para formar un catálogo curto e equilibrado.")
    elif condition == "large":
        st.write("Viches **os 24 produtos** desde o principio.")
    else:
        st.write("Viches primeiro **6 produtos recomendados** a partir de tres respostas, e podías abrir os 24.")
        st.markdown('<div class="os-rule"><strong>Non había maxia nin unha IA que “pensase”.</strong> Era unha regra de puntos: +4 pola prioridade principal, +3 polo sabor e +2 polo rango de prezo. En caso de empate, ordenouse polo ID do produto.</div>', unsafe_allow_html=True)
        prefs = preference_dict()
        st.write(explain_preferences(prefs))
        row = selected_product_row()
        if row is not None:
            st.write(explain_product_score(row, prefs))
        else:
            top = get_recommendations().iloc[0]
            st.write("Como exemplo, a primeira recomendación calculouse así:")
            st.write(explain_product_score(top, prefs))
        if st.session_state.opened_full_catalog:
            st.write("Durante a decisión **abriches o catálogo completo**.")
        else:
            st.write("Durante a decisión **non abriches o catálogo completo**.")

    st.info("Agora mira a pantalla colectiva e compara a túa experiencia coa do resto. A pregunta final é: quen foi máis libre?")
    if st.session_state.db_last_error:
        st.warning("A actividade rematou, pero houbo un problema ao gardar os datos. A persoa facilitadora pode comprobar a conexión.")
        if st.button("Tentar gardar de novo", use_container_width=True):
            if persist():
                st.success("Datos gardados.")
                st.session_state.db_last_error = None
    if KIOSK_MODE or APP_MODE != "production":
        st.divider()
        st.caption("Control visible só en modo de proba/quiosco.")
        st.button("Preparar para a seguinte persoa", on_click=reset_for_next_participant, use_container_width=True)


def demo_dataframe(n: int = 90) -> pd.DataFrame:
    rng = random.Random(20260905)
    rows = []
    for i in range(n):
        condition = CONDITIONS[i % 3]
        if condition == "small":
            decision = max(4.0, rng.gauss(18, 7))
            difficulty = min(7, max(1, round(rng.gauss(3.0, 1.1))))
            confidence = min(7, max(1, round(rng.gauss(5.0, 1.0))))
        elif condition == "large":
            decision = max(4.0, rng.gauss(28, 12))
            difficulty = min(7, max(1, round(rng.gauss(4.2, 1.2))))
            confidence = min(7, max(1, round(rng.gauss(4.3, 1.1))))
        else:
            decision = max(4.0, rng.gauss(20, 9))
            difficulty = min(7, max(1, round(rng.gauss(3.4, 1.2))))
            confidence = min(7, max(1, round(rng.gauss(5.1, 1.0))))
        rows.append(
            {
                "participant_id": f"DEMO-{i:03d}",
                "condition": condition,
                "decision_seconds": round(decision, 2),
                "difficulty": difficulty,
                "confidence": confidence,
                "satisfaction": min(7, max(1, round(rng.gauss(4.8, 1.1)))),
                "no_choice": rng.random() < (0.12 if condition == "large" else 0.08),
                "opened_full_catalog": (rng.random() < 0.38) if condition == "algorithm" else False,
                "status": "completed",
            }
        )
    return pd.DataFrame(rows)


def dashboard_data() -> tuple[pd.DataFrame | None, str | None]:
    if DASHBOARD_DEMO:
        return demo_dataframe(), None
    rows, error = fetch_completed(include_demo=False)
    if rows is None:
        return None, error
    return pd.DataFrame(rows), None


def render_dashboard_body() -> None:
    df, error = dashboard_data()

    if error:
        st.error(
            "Non se puideron cargar os datos reais. "
            "Revisa a conexión con Supabase."
        )
        return

    if df is None or df.empty:
        st.info(
            "Aínda non hai participacións completadas."
        )
        return
    if df is None or df.empty:
        st.info(
            "Aínda non hai participacións completadas."
        )
        return
    if df is None or df.empty:
        st.info("Aínda non hai participacións completadas.")
        return

    numeric_cols = ["decision_seconds", "difficulty", "confidence", "satisfaction"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["no_choice"] = df["no_choice"].fillna(False).astype(bool)
    df["opened_full_catalog"] = df["opened_full_catalog"].fillna(False).astype(bool)

    group_order = ["small", "large", "algorithm"]
    summary = (
        df.groupby("condition", dropna=False)
        .agg(
            participantes=("participant_id", "count"),
            tempo_mediano=("decision_seconds", "median"),
            dificultade_mediana=("difficulty", "median"),
            confianza_mediana=("confidence", "median"),
            satisfaccion_mediana=("satisfaction", "median"),
            non_eleccion=("no_choice", "mean"),
        )
        .reindex(group_order)
    )
    summary.index = [CONDITION_PUBLIC_LABELS[c] for c in group_order]

    top = st.columns(4, wrap=True)
    top[0].metric("Participantes", int(len(df)))
    top[1].metric("Non elección", f"{100 * df['no_choice'].mean():.0f} %")
    alg = df[df["condition"] == "algorithm"]
    opened = 100 * alg["opened_full_catalog"].mean() if len(alg) else 0
    top[2].metric("Algoritmo: abriu os 24", f"{opened:.0f} %")
    top[3].metric("Actualización", "cada 10 s")

    st.subheader("Participación por experiencia")
    st.bar_chart(summary[["participantes"]], height=260)

    st.subheader("Tempo de decisión")
    st.caption("Usamos a mediana porque uns poucos tempos moi longos poden distorsionar a media.")
    st.bar_chart(summary[["tempo_mediano"]].rename(columns={"tempo_mediano": "segundos (mediana)"}), height=280)

    c1, c2, c3 = st.columns(3, wrap=True)
    with c1:
        st.subheader("Dificultade")
        st.bar_chart(summary[["dificultade_mediana"]], height=260)
    with c2:
        st.subheader("Confianza")
        st.bar_chart(summary[["confianza_mediana"]], height=260)
    with c3:
        st.subheader("Satisfacción")
        st.bar_chart(summary[["satisfaccion_mediana"]], height=260)

    st.subheader("Liberdade vs esforzo")
    st.write(
        "Non poñemos ‘número de opcións’ nun eixo numérico porque o grupo algoritmo ve 6 recomendadas pero pode acceder ás 24. Mantemos as tres experiencias como categorías e comparamos o esforzo observado."
    )
    effort = summary[["tempo_mediano", "dificultade_mediana"]].copy()
    effort.columns = ["Tempo mediano (s)", "Dificultade mediana (1–7)"]
    st.dataframe(effort.round(1), use_container_width=True)

    st.subheader("¿Renunciarías a ver todas as opcións?")
    st.caption("Comportamento observado no grupo algoritmo: abrir ou non abrir o catálogo completo. Isto non mide unha preferencia xeral fóra do taller.")
    if len(alg):
        behavior = pd.DataFrame(
            {
                "porcentaxe": [100 * (~alg["opened_full_catalog"]).mean(), 100 * alg["opened_full_catalog"].mean()]
            },
            index=["Non abriu os 24", "Abriu os 24"],
        )
        st.bar_chart(behavior, height=260)
    else:
        st.info("Aínda non hai participantes no grupo algoritmo.")

    st.subheader("Resumo numérico")
    table = summary.copy()
    table["non_eleccion"] = table["non_eleccion"] * 100
    table = table.rename(
        columns={
            "participantes": "n",
            "tempo_mediano": "Tempo mediano (s)",
            "dificultade_mediana": "Dificultade (mediana)",
            "confianza_mediana": "Confianza (mediana)",
            "satisfaccion_mediana": "Satisfacción (mediana)",
            "non_eleccion": "Non elección (%)",
        }
    )
    st.dataframe(table.round(1), use_container_width=True)


def render_dashboard() -> None:
    st.markdown('<div class="os-kicker">Pantalla colectiva</div>', unsafe_allow_html=True)
    st.title("O supermercado imposible — resultados en directo")
    if DASHBOARD_DEMO:
        st.markdown('<div class="os-demo">DEMO — estes datos son simulados e non proceden de participantes reais.</div>', unsafe_allow_html=True)

    @st.fragment(run_every="10s")
    def live_fragment():
        render_dashboard_body()

    live_fragment()


if st.query_params.get("view") == "dashboard":
    render_dashboard()
    st.stop()

stage = st.session_state.stage
if stage == "welcome":
    render_welcome()
elif stage == "consent":
    render_consent()
elif stage == "demographics":
    render_demographics()
elif stage == "under14":
    render_under14()
elif stage == "algo_intro":
    render_algo_intro()
elif stage == "algo_questions":
    render_algo_questions()
elif stage == "catalog":
    render_catalog_screen()
elif stage == "post":
    render_post()
elif stage == "result":
    render_result()
else:
    st.error("Estado de navegación non recoñecido. Volve ao inicio.")
    if st.button("Reiniciar"):
        reset_for_next_participant()
