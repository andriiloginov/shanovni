import re
import streamlit as st
from urllib.parse import quote
from utils import load_deputies, get_party_badge, geocode_postal_code, render_data_footer, deputy_avatar
from data import DEPUTIES_URL
from nazk import show_declaration
from ui import get_card_marker

reps_df = load_deputies()

if reps_df.empty:
    st.error("Не вдалося завантажити дані з data.gov.ua — портал може бути тимчасово недоступний. Спробуйте пізніше.")
    st.stop()

# Заголовок сторінки
st.title("Склад Київської міської ради")
st.subheader("Склад ради, контактні дані депутатів, їхні декларації пошук за індексом дільниці та інша корисна інформація для виборців")


# Фільтри
col_search, col_filter, col_zip = st.columns([2, 3, 2])

with col_search:
    search = st.text_input(
        "За прізвищем або ім'ям",
        placeholder="Введіть прізвище...",
        label_visibility="visible",
    )

with col_filter:
    parties_options = sorted(reps_df['party'].unique())
    parties = st.multiselect(
        "За фракціями",
        options=parties_options,
        placeholder="Оберіть одну або декілька фракцій",
    )

with col_zip:
    postal_code = st.text_input(
        "За поштовим індексом",
        placeholder="Напр. 01001",
        max_chars=5,
    )

# Геокодинг поштового індексу → район
zip_district = None
if postal_code:
    if not re.match(r'^0[1-6]\d{3}$', postal_code):
        st.warning("Сорі, невірний формат індексу. Введіть 5-значний індекс Києва (наприклад 04080).")
    else:
        zip_district = geocode_postal_code(postal_code)
        if zip_district:
            st.success(zip_district)
            st.caption(
                "Депутати, чиї громадські приймальні розташовані в цьому районі. "
            )
        else:
            st.error("Не вдалося визначити район за цим індексом. Спробуйте інший.")

st.divider()

# Логіка фільтрації
filtered_df = reps_df.copy()
if search:
    filtered_df = filtered_df[filtered_df['name'].str.contains(search, case=False)]
if parties:
    filtered_df = filtered_df[filtered_df['party'].isin(parties)]
if zip_district:
    filtered_df = filtered_df[filtered_df['district'] == zip_district]

# Показ кількості знайдених результатів
st.caption(f"Знайдено депутатів: {len(filtered_df)}")

# Картки
cols = st.columns(3)

if not filtered_df.empty:
    for i, dep in enumerate(filtered_df.itertuples()):
        with cols[i % 3]:
            with st.container(border=True):
                st.markdown(get_card_marker(dep.party), unsafe_allow_html=True)
                deputy_avatar(int(dep.id), dep.name, dep.party)
                st.markdown(f"#### {dep.name}")
                st.markdown(get_party_badge(dep.party), unsafe_allow_html=True)

                with st.container(border=True):
                    st.write("##### Контакти")
                    maps_url = f"https://www.google.com/maps/search/?api=1&query={quote(dep.address)}"
                    phone_clean = dep.phone.replace("(", "").replace(")", "").replace(" ", "").replace("-", "")
                    st.write(f"**Адреса:** {dep.address}")
                    st.link_button("На мапі ↗", maps_url)
                    st.write(f"**Телефон:** {dep.phone}")
                    st.link_button("Телефонувати ↗", f"tel:{phone_clean}")

                with st.container(border=True):
                    st.write("##### Декларація")
                    st.caption(
                        "Дані завантажуються напряму з реєстру НАЗК в реальному часі, тому аби не було затримок, ми показуємо лише основну інформацію. "
                    )
                    show_declaration(dep.name, dep)
else:
    st.info("Представників за вашим запитом не знайдено. Спробуйте змінити параметри фільтрації.")

render_data_footer({"Депутати Київради": DEPUTIES_URL})