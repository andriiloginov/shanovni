import streamlit as st
import pandas as pd
import json
import zipfile
import requests
import io
from utils import load_deputies, to_short_name, simplify_data, render_data_footer, get_party_badge, get_badge, deputy_avatar
from data import VOTING_QUARTERS, DEPUTIES_URL, UA
from ui import EMPTY_VOTE_MESSAGES, VOTE_COLORS, get_vote_marker
from docs import render_doc_buttons

# --- Завантаження даних ---

@st.cache_data
def load_voting_archive(url):
    """Завантажує ZIP-архів поіменних голосувань з data.gov.ua. Повертає bytes або None."""
    try:
        r = requests.get(url, headers=UA, timeout=30)
        if r.status_code != 200 or r.content[:2] != b'PK':
            return None
        return r.content
    except:
        return None

@st.cache_data
def get_voting_titles(archive_bytes):
    """Витягує назви питань з кожного JSON у ZIP → {скорочена_назва: filename}."""
    titles_map = {}
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as z:
        files = sorted([f for f in z.namelist() if f.endswith('.json') and not f.startswith('__')])
        for filename in files:
            with z.open(filename) as f:
                data = json.load(f)
                full_title = data.get('GL_Text', filename)
                short_title = (full_title[:100] + '...') if len(full_title) > 100 else full_title
                titles_map[short_title] = filename
    return titles_map

def merge_votes(data, reps_lookup):
    """JSON одного голосування + довідник представників → DataFrame з повним ПІБ, фракцією та результатом."""
    votes_df = pd.DataFrame(data['DPList'])
    votes_df.columns = ['raw_name', 'vote_result']
    votes_df['match_key'] = votes_df['raw_name'].str.replace(r'\s+', ' ', regex=True).str.strip()
    votes_df['vote_clean'] = votes_df['vote_result'].str.replace(".", "").str.strip().replace("", "Не голосував")
    votes_df = simplify_data(pd.merge(votes_df, reps_lookup, on='match_key', how='left'))
    votes_df['full_name'] = votes_df['full_name'].fillna(votes_df['raw_name'])
    return votes_df

# --- Підготовка даних: депутати + архів голосувань ---

reps_df = load_deputies()
if reps_df.empty:
    st.error("Не вдалося завантажити дані з data.gov.ua — портал може бути тимчасово недоступний. Спробуйте пізніше.")
    st.stop()

reps_df['match_key'] = reps_df['name'].apply(to_short_name)
reps_lookup = reps_df[['id', 'match_key', 'name', 'party']].rename(columns={'name': 'full_name'})

# --- UI: вибір голосування, показ результатів, фільтри ---

st.title("Результати поіменних голосувань Київради")
st.subheader("Як голосували обранці за кожне з рішень з оригінальними документами та ШІ-поясненнями")

top_col1, top_col2 = st.columns([1, 3])
with top_col1:
    selected_quarters = st.multiselect("Квартал", options=list(VOTING_QUARTERS.keys()), default=list(VOTING_QUARTERS.keys()))
with top_col2:
    title_search = st.text_input("Пошук за назвою", placeholder="Введіть назву питання...")

if not selected_quarters:
    st.warning("Оберіть хоча б один квартал.")
    st.stop()

# Завантажуємо архіви для всіх вибраних кварталів та об'єднуємо питання
combined_titles = {}  # title -> (archive_bytes, filename)
for quarter in selected_quarters:
    archive_data = load_voting_archive(VOTING_QUARTERS[quarter])
    if archive_data:
        for title, filename in get_voting_titles(archive_data).items():
            combined_titles[title] = (archive_data, filename)

if not combined_titles:
    st.error("Не вдалося завантажити дані з data.gov.ua — портал може бути тимчасово недоступний. Спробуйте пізніше.")
    st.stop()

filtered_titles = {k: v for k, v in combined_titles.items() if title_search.lower() in k.lower()} if title_search else combined_titles
if not filtered_titles:
    st.warning("Нічого не знайдено за вашим запитом.")
    st.stop()

selected_display_title = st.selectbox("Питання", options=list(filtered_titles.keys()))
selected_archive, selected_filename = filtered_titles[selected_display_title]

with zipfile.ZipFile(io.BytesIO(selected_archive)) as z:
    with z.open(selected_filename) as f:
        data = json.load(f)

votes_df = merge_votes(data, reps_lookup)

barrier = 61
count_za = len(votes_df[votes_df['vote_clean'] == "За"])
count_proti = len(votes_df[votes_df['vote_clean'] == "Проти"])
count_utrim = len(votes_df[votes_df['vote_clean'] == "Утримався"])
passed = count_za >= barrier

st.markdown(f"### {data.get('GL_Text', 'Деталі голосування')}")
render_doc_buttons(data.get('GL_Text', ''), passed=passed)

# --- Табло: прийнято/не прийнято + метрики За/Проти/Утримались ---

st.write("")
st.write("")
delta_val = count_za - barrier
delta_text = f"{delta_val} від кворуму" if delta_val >= 0 else f"{delta_val} до кворуму"

m0, m1, m2, m3 = st.columns(4)
vote_key = "За" if count_za >= barrier else "Проти"
result_label = "Прийнято" if count_za >= barrier else "Не прийнято"

with m0:
    with st.container(border=True, height=150):
        st.markdown(get_vote_marker(vote_key), unsafe_allow_html=True)
        st.metric("Рішення", result_label, delta=delta_text, delta_color="normal")
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
st.caption(f"Кворум — мінімум {barrier} голосів «За»")

# --- Графік голосів за фракціями + крос-таблиця ---

st.divider()
c1, c2 = st.columns(2)

with c1:
    vote_options = list(EMPTY_VOTE_MESSAGES.keys())
    st.write("#### Графік за типом голосу")
    chart_type = st.radio("", options=vote_options, horizontal=True, label_visibility="collapsed")
    chart_data = votes_df[votes_df['vote_clean'] == chart_type].groupby('party').size().sort_values()

    if not chart_data.empty:
        st.bar_chart(chart_data, horizontal=True, color=VOTE_COLORS.get(chart_type))
    else:
        st.info(EMPTY_VOTE_MESSAGES.get(chart_type, "Дані відсутні."))

with c2:
    st.write("#### Статистика по фракціях")
    crosstab = pd.crosstab(votes_df['party'], votes_df['vote_clean'])
    crosstab.index.name = "Фракція"
    st.dataframe(crosstab, use_container_width=True)

# --- Фільтри + список карток депутатів ---

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
            st.markdown(
                get_party_badge(row.party) + " " +
                get_badge(row.vote_clean, color),
                unsafe_allow_html=True,
            )

render_data_footer({
    "Депутати Київради": DEPUTIES_URL,
    **{f"Поіменні голосування ({q})": VOTING_QUARTERS[q] for q in selected_quarters},
})
