"""
nazk.py — інтеграція з Public API НАЗК (public-api.nazk.gov.ua/v2).
Кешується на 24 год. Використання: from nazk import show_declaration
"""

import streamlit as st
from curl_cffi import requests
from urllib.parse import quote_plus
from data import UA, NAZK_API, NAZK_PUBLIC
from utils import get_badge


@st.cache_data(ttl=86400, show_spinner=False)
def search_declarations(query: str) -> list[dict]:
    """Пошук декларацій за ПІБ."""
    try:
        r = requests.get(
            f"{NAZK_API}/documents/list",
            params={"query": query},
            headers=UA,
            timeout=15,
            impersonate="chrome",
        )
        if r.status_code != 200:
            return []

        data = r.json()
        results = []

        for doc in data.get("data", []):
            decl_type = doc.get("declaration_type")
            if not decl_type or decl_type == 0:
                continue

            results.append({
                "id": doc.get("id", ""),
                "year": doc.get("declaration_year"),
                "type": _declaration_type_label(decl_type),
                "doc_type": _doc_type_label(doc.get("document_type")),
                "date": doc.get("date", "")[:10] if doc.get("date") else "",
                "url": f"{NAZK_PUBLIC}/{doc.get('id', '')}",
            })

        # Сортуємо: найновіша декларація першою
        results.sort(key=lambda x: x.get("year") or 0, reverse=True)
        return results

    except Exception:
        return []


@st.cache_data(ttl=86400, show_spinner=False)
def load_declaration(doc_id: str) -> dict:
    """Завантажує повну декларацію за uuid, повертає структурований dict."""
    try:
        r = requests.get(
            f"{NAZK_API}/documents/{doc_id}",
            headers=UA,
            timeout=15,
            impersonate="chrome",
        )
        if r.status_code != 200:
            return {}

        raw = r.json()
        data = raw.get("data", {})

        return {
            "meta": _parse_meta(raw, data),
            "realty": _parse_realty(data),
            "land": _parse_land(data),
            "vehicles": _parse_vehicles(data),
            "incomes": _parse_incomes(data),
            "cash": _parse_cash(data),
            "liabilities": _parse_liabilities(data),
            "total_income": _calc_total_income(data),
        }

    except Exception:
        return {}


def get_deputy_declarations(full_name: str) -> tuple[list[dict], dict]:
    """Повертає (список_декларацій, остання_розпарсена_декларація)."""
    parts = full_name.split() if full_name else []
    query = f"{parts[0]} {parts[1]}" if len(parts) >= 2 else full_name
    if not query.strip():
        return [], {}

    declarations = search_declarations(query)
    if not declarations:
        return [], {}

    latest_id = declarations[0]["id"]
    latest_parsed = load_declaration(latest_id) if latest_id else {}

    return declarations, latest_parsed


def build_llm_context(deputy_row, declarations: list[dict], parsed: dict) -> dict:
    """Збирає контекст депутата для LLM-сайдбару (session_state)."""
    return {
        "name": getattr(deputy_row, "name", ""),
        "party": getattr(deputy_row, "party", ""),
        "district": getattr(deputy_row, "district", ""),
        "phone": getattr(deputy_row, "phone", ""),
        "address": getattr(deputy_row, "address", ""),
        "declarations_count": len(declarations),
        "declaration_years": [d["year"] for d in declarations],
        "declaration_urls": {d["year"]: d["url"] for d in declarations},
        "declaration": parsed,   # повний структурований dict останньої декларації
    }


def show_declaration(full_name: str, deputy_row=None):
    """Секція «Декларація» з lazy-завантаженням з НАЗК."""
    state_key = f"decl_loaded_{full_name}"

    # Lazy: кнопка для першого завантаження
    if state_key not in st.session_state:
        if st.button("Дивитись ↙", key=f"decl_btn_{full_name}", use_container_width=True, type="primary"):
            st.session_state[state_key] = True
            st.rerun()
        return

    # Дані завантажуються тільки після кліку (кешуються на 24 год)
    with st.spinner("Шукаємо декларації..."):
        declarations, parsed = get_deputy_declarations(full_name)

    # Оновлюємо LLM-контекст якщо є рядок депутата
    if deputy_row is not None and parsed:
        st.session_state["deputy_context"] = build_llm_context(
            deputy_row, declarations, parsed
        )

    if not declarations:
        parts = full_name.split()
        search_query = f"{parts[0]} {parts[1]}" if len(parts) >= 2 else full_name
        nazk_url = f"https://public.nazk.gov.ua/documents/list?query={quote_plus(search_query)}"
        st.caption("Не вдалось завантажити автоматично.")
        st.link_button("Шукати в реєстрі НАЗК ↗", nazk_url, use_container_width=True)
        return

    # Вибір року якщо є кілька декларацій
    if len(declarations) > 1:
        year_options = {f"{d['year']} — {d['type']}": d for d in declarations}
        selected_label = st.selectbox(
            "Оберіть рік",
            options=list(year_options.keys()),
            key=f"decl_year_{full_name}",
        )
        selected_decl = year_options[selected_label]
        if selected_decl["id"] != declarations[0]["id"]:
            parsed = load_declaration(selected_decl["id"])
    else:
        selected_decl = declarations[0]

    # Мета
    meta = parsed.get("meta", {})
    decl_type = meta.get("type", "")
    decl_year = meta.get("year", "")
    submitted = meta.get("submitted", "")
    position = meta.get("position", "")

    tags = [decl_type, str(decl_year)] if decl_type else [str(decl_year)]
    if submitted:
        tags.append(f"подано {submitted}")
    st.markdown(" ".join(get_badge(t) for t in tags if t), unsafe_allow_html=True)
    if position:
        st.write(f"**Посада:** {position}")

    # Загальний дохід
    total = parsed.get("total_income", 0)
    if total:
        st.metric("Дохід (декларант)", f"{total:,.0f} грн")

    # Нерухомість
    realty = parsed.get("realty", [])
    if realty:
        st.write(f"**Нерухомість:** {len(realty)} об.")
        for obj in realty[:3]:
            area = obj.get("area", "")
            area_str = f", {area} м²" if area else ""
            st.write(f"· {obj.get('type', '—')}{area_str}")
        if len(realty) > 3:
            st.write(f"... та ще {len(realty) - 3}")

    # Транспорт
    vehicles = parsed.get("vehicles", [])
    if vehicles:
        st.write(f"**Транспорт:** {len(vehicles)} од.")
        for v in vehicles[:4]:
            st.write(f"· {v.get('brand', '—')} {v.get('year', '')}")
        if len(vehicles) > 4:
            st.write(f"... та ще {len(vehicles) - 4}")

    # Грошові активи
    cash = parsed.get("cash", [])
    if cash:
        total_uah = sum(c["amount"] for c in cash if c.get("currency") == "UAH")
        total_usd = sum(c["amount"] for c in cash if c.get("currency") == "USD")
        parts = []
        if total_uah:
            parts.append(f"{total_uah:,.0f} грн")
        if total_usd:
            parts.append(f"{total_usd:,.0f} USD")
        if parts:
            st.write(f"**Рахунки:** {', '.join(parts)}")

    st.link_button(
        "Повна декларація ↗",
        selected_decl["url"],
        use_container_width=True,
    )


def _get_step(data: dict, step_num: int) -> list:
    step = data.get(f"step_{step_num}", {})
    if isinstance(step, dict):
        result = step.get("data", []) or []
        if isinstance(result, dict):
            return [result]
        return result
    return []


def _parse_meta(raw: dict, data: dict) -> dict:
    position = ""
    step1 = _get_step(data, 1)
    if step1:
        s1 = step1[0] if isinstance(step1, list) and step1 else {}
        position = s1.get("workPost", "") or s1.get("postType", "")

    return {
        "year": raw.get("declaration_year"),
        "type": _declaration_type_label(raw.get("declaration_type")),
        "doc_type": _doc_type_label(raw.get("document_type")),
        "submitted": (raw.get("date", "") or "")[:10],
        "position": position,
    }


def _parse_realty(data: dict) -> list:
    result = []
    for obj in _get_step(data, 3):
        result.append({
            "type": obj.get("objectType", ""),
            "area": obj.get("totalArea", ""),
            "country": obj.get("country", {}).get("ukName", "") if isinstance(obj.get("country"), dict) else "",
            "ownership": obj.get("ownershipType", ""),
        })
    return result


def _parse_land(data: dict) -> list:
    result = []
    for obj in _get_step(data, 4):
        result.append({
            "area": obj.get("totalArea", ""),
            "purpose": obj.get("intendedPurpose", ""),
            "country": obj.get("country", {}).get("ukName", "") if isinstance(obj.get("country"), dict) else "",
            "ownership": obj.get("ownershipType", ""),
        })
    return result


def _parse_vehicles(data: dict) -> list:
    result = []
    for obj in _get_step(data, 6):
        result.append({
            "type": obj.get("objectType", ""),
            "brand": f"{obj.get('brand', '')} {obj.get('model', '')}".strip(),
            "year": obj.get("year", ""),
            "country": obj.get("country", {}).get("ukName", "") if isinstance(obj.get("country"), dict) else "",
        })
    return result


def _parse_incomes(data: dict) -> list:
    result = []
    for obj in _get_step(data, 11):
        if str(obj.get("person", "")) != "1":
            continue
        result.append({
            "source": obj.get("objectType", "") or obj.get("source", ""),
            "amount": float(obj.get("sizeIncome", 0) or 0),
            "currency": obj.get("currency", "UAH"),
        })
    return result


def _parse_cash(data: dict) -> list:
    result = []
    for obj in _get_step(data, 12):
        result.append({
            "bank": obj.get("organization", {}).get("ukName", "") if isinstance(obj.get("organization"), dict) else "",
            "amount": float(obj.get("sizeAssets", 0) or 0),
            "currency": obj.get("currency", {}).get("code", "UAH") if isinstance(obj.get("currency"), dict) else "UAH",
        })
    return result


def _parse_liabilities(data: dict) -> list:
    result = []
    for obj in _get_step(data, 13):
        result.append({
            "type": obj.get("objectType", ""),
            "amount": float(obj.get("sizeAssets", 0) or 0),
            "currency": obj.get("currency", {}).get("code", "UAH") if isinstance(obj.get("currency"), dict) else "UAH",
        })
    return result


def _calc_total_income(data: dict) -> float:
    return sum(
        float(obj.get("sizeIncome", 0) or 0)
        for obj in _get_step(data, 11)
        if str(obj.get("person", "")) == "1"
    )


def _declaration_type_label(val) -> str:
    return {1: "Щорічна", 2: "При звільненні", 3: "Щорічна (після звільнення)", 4: "Кандидата"}.get(val, "")


def _doc_type_label(val) -> str:
    return {1: "Декларація", 2: "Повідомлення про зміни", 3: "Виправлена декларація"}.get(val, "")