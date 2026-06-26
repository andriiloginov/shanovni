import re
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import json
import zipfile
import requests
import io
from datetime import datetime as dt
from utils import load_deputies, to_short_name, simplify_data, render_data_footer, get_party_badge, get_badge, deputy_avatar
from data import CITIES, UA

_kyiv = CITIES["kyiv"]
VOTING_QUARTERS = _kyiv["voting_quarters"]
from ui import EMPTY_VOTE_MESSAGES, VOTE_COLORS, get_vote_marker, get_voting_list_marker
from docs import render_doc_buttons

BARRIER = 61
PAGE_SIZE = 50


@st.cache_data
def load_voting_archive(url):
    try:
        r = requests.get(url, headers=UA, timeout=30)
        if r.status_code != 200 or r.content[:2] != b'PK':
            return None
        return r.content
    except Exception:
        return None


@st.cache_data
def get_voting_metadata(archive_bytes):
    """Читає всі JSON у ZIP → [{filename, title, date, count_za, passed}]."""
    items = []
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as z:
        files = sorted(
            (f for f in z.namelist() if f.endswith('.json') and not f.startswith('__')),
            key=lambda f: int(m.group(1)) if (m := re.search(r'_(\d+)\.json$', f)) else 0,
        )
        for filename in files:
            with z.open(filename) as f:
                data = json.load(f)
            try:
                dp = pd.DataFrame(data.get('DPList', [])).iloc[:, :2]
                dp.columns = ['raw_name', 'vote_result']
                count_za = int((dp['vote_result'].str.replace('.', '').str.strip() == 'За').sum())
            except Exception:
                count_za = 0
            gl_time = data.get('GLTime') or ''
            try:
                dt_val = dt.strptime(gl_time, '%d.%m.%Y %H:%M:%S')
            except ValueError:
                dt_val = dt.min
            items.append({
                "filename": filename,
                "title": data.get('GL_Text', filename),
                "date": dt_val.strftime('%d.%m.%Y') if dt_val != dt.min else '',
                "datetime": dt_val,
                "count_za": count_za,
                "passed": count_za >= BARRIER,
            })
    return items


def merge_votes(data, reps_lookup):
    votes_df = pd.DataFrame(data['DPList'])
    votes_df.columns = ['raw_name', 'vote_result']
    votes_df['match_key'] = votes_df['raw_name'].str.replace(r'\s+', ' ', regex=True).str.strip()
    votes_df['vote_clean'] = votes_df['vote_result'].str.replace(".", "").str.strip().replace("", "Не голосував")
    votes_df = simplify_data(pd.merge(votes_df, reps_lookup, on='match_key', how='left'))
    votes_df['full_name'] = votes_df['full_name'].fillna(votes_df['raw_name'])
    return votes_df


# --- Дані ---

reps_df = load_deputies()
if reps_df.empty:
    st.error("Не вдалося завантажити дані з data.gov.ua — портал може бути тимчасово недоступний. Спробуйте пізніше.")
    st.stop()

reps_df['match_key'] = reps_df['name'].apply(to_short_name)
reps_lookup = reps_df[['id', 'match_key', 'name', 'party']].rename(columns={'name': 'full_name'})

# --- Routing ---

selected_filename = st.query_params.get("voting")

if not selected_filename:
    st.header("Результати поіменних голосувань")

if selected_filename:

    # ── Детальний вид ──────────────────────────────────────────────────────

    if st.session_state.pop("scroll_top", False):
        components.html(
            "<script>var el=window.parent.document.querySelector('[data-testid=\"stMain\"]');if(el)el.scrollTop=0;</script>",
            height=0,
        )

    if st.button("← Назад до списку", type="primary"):
        del st.query_params["voting"]
        st.rerun()

    with st.spinner("Завантажую..."):
        archive_map: dict[str, bytes] = {}
        for url in VOTING_QUARTERS.values():
            archive_data = load_voting_archive(url)
            if archive_data:
                for item in get_voting_metadata(archive_data):
                    archive_map[item["filename"]] = archive_data

    if selected_filename not in archive_map:
        st.warning("Голосування не знайдено.")
        st.stop()

    with zipfile.ZipFile(io.BytesIO(archive_map[selected_filename])) as z:
        with z.open(selected_filename) as f:
            data = json.load(f)

    votes_df = merge_votes(data, reps_lookup)

    count_za = len(votes_df[votes_df['vote_clean'] == "За"])
    count_proti = len(votes_df[votes_df['vote_clean'] == "Проти"])
    count_utrim = len(votes_df[votes_df['vote_clean'] == "Утримався"])
    passed = count_za >= BARRIER

    st.markdown(f"### {data.get('GL_Text', 'Деталі голосування')}")
    render_doc_buttons(data.get('GL_Text', ''), passed=passed)

    st.write("")
    delta_val = count_za - BARRIER
    delta_text = f"{delta_val:+d} від кворуму"

    st.write("#### Табло")
    m0, m1, m2, m3 = st.columns(4)
    with m0:
        with st.container(border=True, height=150):
            st.markdown(get_vote_marker("За" if passed else "Проти"), unsafe_allow_html=True)
            st.metric("Рішення", "Прийнято" if passed else "Не прийнято", delta=delta_text, delta_color="normal")
    with m1:
        with st.container(border=True, height=150):
            st.markdown(get_vote_marker("За"), unsafe_allow_html=True)
            st.metric("За", count_za)
    with m2:
        with st.container(border=True, height=150):
            st.markdown(get_vote_marker("Проти"), unsafe_allow_html=True)
            st.metric("Проти", count_proti)
    with m3:
        with st.container(border=True, height=150):
            st.markdown(get_vote_marker("Утримався"), unsafe_allow_html=True)
            st.metric("Утримались", count_utrim)
    st.caption(f"Кворум — мінімум {BARRIER} голосів «За»")

    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        st.write("#### Графік за типом голосу")
        chart_type = st.radio("", options=list(EMPTY_VOTE_MESSAGES.keys()), horizontal=True, label_visibility="collapsed")
        chart_data = votes_df[votes_df['vote_clean'] == chart_type].groupby('party').size().sort_values()
        if not chart_data.empty:
            st.bar_chart(chart_data, horizontal=True, color=VOTE_COLORS.get(chart_type))
        else:
            st.info(EMPTY_VOTE_MESSAGES.get(chart_type, "Дані відсутні."))
    with c2:
        st.write("#### Статистика по фракціях")
        crosstab = pd.crosstab(votes_df['party'], votes_df['vote_clean'])
        st.bar_chart(crosstab, color=[VOTE_COLORS.get(c, "#999") for c in crosstab.columns])

    st.divider()
    st.write("#### Поіменні результати")
    f_col1, f_col2, f_col3 = st.columns(3)
    with f_col1:
        search = st.text_input("Пошук за ПІБ", placeholder="Введіть ПІБ...")
    with f_col2:
        parties = st.multiselect("Фракція", options=sorted(votes_df['party'].unique()), placeholder="Оберіть фракцію")
    with f_col3:
        vote_types = st.multiselect("Тип голосу", options=sorted(votes_df['vote_clean'].unique()), placeholder="Оберіть тип голосу")

    filtered_df = votes_df.copy()
    if search:
        filtered_df = filtered_df[filtered_df['full_name'].str.contains(search, case=False)]
    if parties:
        filtered_df = filtered_df[filtered_df['party'].isin(parties)]
    if vote_types:
        filtered_df = filtered_df[filtered_df['vote_clean'].isin(vote_types)]

    st.caption(f"Відображено депутатів: {len(filtered_df)}")
    cols = st.columns(4)
    for i, row in enumerate(filtered_df.itertuples()):
        with cols[i % 4]:
            with st.container(border=True):
                st.markdown(get_vote_marker(row.vote_clean), unsafe_allow_html=True)
                deputy_avatar(int(row.id) if pd.notna(row.id) else 0, row.full_name, row.party, size=48)
                st.write(f"**{row.full_name}**")
                color = VOTE_COLORS.get(row.vote_clean, "#999999")
                st.markdown(get_party_badge(row.party) + " " + get_badge(row.vote_clean, color), unsafe_allow_html=True)

    render_data_footer({
        "Депутати Київради": _kyiv["deputies_url"],
        **{f"Поіменні голосування ({q})": VOTING_QUARTERS[q] for q in VOTING_QUARTERS},
    })

else:

    # ── Список голосувань ──────────────────────────────────────────────────

    st.caption("Як голосували обранці за кожне з рішень. З оригінальними документами, ШІ-аналізом та інтерактивними графіками.")

    selected_quarters = st.multiselect("Квартал", options=list(VOTING_QUARTERS.keys()), default=list(VOTING_QUARTERS.keys()))
    status_pills = st.pills("Статус", ["Усі", "Прийнято", "Не прийнято"], default="Усі", selection_mode="multi")
    selected_statuses = set(status_pills or [])
    title_search = st.text_input("Пошук за назвою", placeholder="Введіть назву питання...")
    sort_by = st.selectbox("Сортування", ["Найновіші", "Найстаріші", "Найближче до кворуму", "Найбільше «За»"])

    if not selected_quarters:
        st.warning("Оберіть хоча б один квартал.")
        st.stop()

    all_items = []
    for quarter in selected_quarters:
        archive_data = load_voting_archive(VOTING_QUARTERS[quarter])
        if archive_data:
            all_items.extend(get_voting_metadata(archive_data))

    if not all_items:
        st.error("Не вдалося завантажити дані з data.gov.ua — портал може бути тимчасово недоступний. Спробуйте пізніше.")
        st.stop()

    filtered_items = all_items
    if title_search:
        filtered_items = [i for i in filtered_items if all(w in i["title"].lower() for w in title_search.lower().split())]
    if selected_statuses and "Усі" not in selected_statuses:
        show_passed = "Прийнято" in selected_statuses
        show_failed = "Не прийнято" in selected_statuses
        filtered_items = [i for i in filtered_items if (i["passed"] and show_passed) or (not i["passed"] and show_failed)]

    if sort_by == "Найстаріші":
        filtered_items = sorted(filtered_items, key=lambda x: x["datetime"])
    elif sort_by == "Найближче до кворуму":
        filtered_items = sorted(filtered_items, key=lambda x: abs(x["count_za"] - BARRIER))
    elif sort_by == "Найбільше «За»":
        filtered_items = sorted(filtered_items, key=lambda x: x["count_za"], reverse=True)
    else:
        filtered_items = sorted(filtered_items, key=lambda x: x["datetime"], reverse=True)

    import math
    total_pages = max(1, math.ceil(len(filtered_items) / PAGE_SIZE))

    st.divider()
    st.caption(f"Знайдено: {len(filtered_items)}")

    page = st.pagination(total_pages, key="voting_page") if total_pages > 1 else 1
    start = (page - 1) * PAGE_SIZE
    visible_items = filtered_items[start:start + PAGE_SIZE]

    cols = st.columns(3)
    for i, item in enumerate(visible_items):
        status_pill = ":green-background[Прийнято]" if item["passed"] else ":red-background[Не прийнято]"

        with cols[i % 3]:
            with st.container(border=True):
                st.markdown(get_voting_list_marker(item["passed"]), unsafe_allow_html=True)
                st.markdown(status_pill)
                st.markdown(item['title'])
                if item["date"]:
                    st.caption(item["date"])
                if st.button("Відкрити →", key=item["filename"], use_container_width=True):
                    st.toast("Завантажую голосування...")
                    st.session_state["scroll_top"] = True
                    st.query_params["voting"] = item["filename"]
                    st.rerun()
