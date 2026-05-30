import streamlit as st
import pandas as pd
from utils import load_salaries, render_data_footer
from data import SALARY_COMPONENTS, SALARIES_URL

salaries_df = load_salaries()

if salaries_df.empty:
    st.error("Не вдалося завантажити дані з data.gov.ua — портал може бути тимчасово недоступний. Спробуйте пізніше.")
    st.stop()

st.title("Зарплати керівництва КМДA")
st.subheader("Нараховані виплати міському голові та заступникам голови КМДA за видами оплат")

# --- Фільтри ---

col_person, col_year = st.columns([3, 2])

with col_person:
    people = sorted(salaries_df['employeeName'].unique())
    person = st.selectbox(
        "Посадовець",
        options=["Всі"] + people,
        format_func=lambda x: x if x == "Всі" else f"{x} — {salaries_df[salaries_df['employeeName'] == x]['jobTitle'].iloc[-1]}",
    )

with col_year:
    years = sorted(salaries_df['year'].unique())
    selected_years = st.multiselect(
        "Рік",
        options=years,
        default=years,
        placeholder="Оберіть рік",
    )

if not selected_years:
    st.warning("Оберіть хоча б один рік.")
    st.stop()

filtered_df = salaries_df[salaries_df['year'].isin(selected_years)]
if person != "Всі":
    filtered_df = filtered_df[filtered_df['employeeName'] == person]

# --- Метрики ---

st.divider()

latest_date = filtered_df['date'].max()
prev_date = latest_date - pd.DateOffset(months=1)

latest_total = filtered_df[filtered_df['date'] == latest_date]['total'].sum()
prev_total = filtered_df[filtered_df['date'] == prev_date]['total'].sum()
delta = latest_total - prev_total if prev_total > 0 else None

m1, m2, m3 = st.columns(3)
m1.metric("Середня зарплата/міс.", f"{filtered_df['total'].mean():,.0f} грн")
m2.metric("Максимальна виплата", f"{filtered_df['total'].max():,.0f} грн")
m3.metric(
    f"Останній місяць ({latest_date.strftime('%m/%Y')})",
    f"{latest_total:,.0f} грн",
    delta=f"{delta:+,.0f} грн" if delta is not None else None,
)

# --- Порівняльний графік + Структура виплат ---

st.divider()

col_bar, col_struct = st.columns(2)

with col_bar:
    if person == "Всі":
        st.write(f"#### Порівняння зарплат за {latest_date.strftime('%m/%Y')}")
        st.caption("Хто отримує більше серед керівництва КМДА в останньому місяці.")
        bar_data = (
            salaries_df[salaries_df['date'] == latest_date]
            .groupby('employeeName')['total']
            .sum()
            .sort_values()
        )
        st.bar_chart(bar_data, horizontal=True, color=None)
    else:
        st.write(f"#### Зарплата по місяцях — {person}")
        st.caption("Як змінювались нарахування конкретного посадовця місяць за місяцем.")
        monthly = filtered_df.groupby('date')['total'].sum()
        st.bar_chart(monthly, color=None)

with col_struct:
    st.write("#### Структура виплат")
    st.caption("З чого складається зарплата — оклад, премії, надбавки та інші компоненти.")
    if person != "Всі":
        latest_row = filtered_df[filtered_df['date'] == latest_date]
    else:
        latest_row = salaries_df[salaries_df['date'] == latest_date]

    if not latest_row.empty:
        component_cols = list(SALARY_COMPONENTS.keys())
        totals = latest_row[component_cols].sum()
        nonzero = totals[totals > 0].rename(index=SALARY_COMPONENTS)
        st.bar_chart(nonzero, horizontal=True, color=None)
    else:
        st.info("Немає даних для відображення структури.")

# --- Динаміка ---

st.divider()
st.write("#### Динаміка")
st.caption("Тренд виплат у часі — зростають, падають чи залишаються стабільними.")
if person == "Всі":
    pivot = filtered_df.pivot_table(index='date', columns='employeeName', values='total', aggfunc='sum')
    st.line_chart(pivot)
else:
    line_data = filtered_df.set_index('date')['total']
    st.line_chart(line_data, color=None)

# --- Аномалії та викиди ---

# Автоматичне виявлення стрибків:
# - конкретний чиновник: порівнюємо його зарплату з його власним середнім
# - всі: порівнюємо середню зарплату по всіх з загальним середнім
MONTHS_UA = {1:"січні",2:"лютому",3:"березні",4:"квітні",5:"травні",6:"червні",7:"липні",8:"серпні",9:"вересні",10:"жовтні",11:"листопаді",12:"грудні"}

if person != "Всі":
    personal = filtered_df.set_index('date')['total']
    mean_p = personal.mean()
    std_p = personal.std()
    spikes = personal[personal > mean_p + 1.5 * std_p] if std_p > 0 else pd.Series(dtype=float)
    spike_items = [(date, (val - mean_p) / mean_p * 100) for date, val in spikes.items()]
else:
    avg_per_person = filtered_df.groupby('date').apply(lambda x: x['total'].mean())
    mean_a = avg_per_person.mean()
    std_a = avg_per_person.std()
    spikes = avg_per_person[avg_per_person > mean_a + 1.5 * std_a]
    spike_items = [(date, (val - mean_a) / mean_a * 100) for date, val in spikes.items()]

if spike_items:
    st.divider()
    st.write("#### Підвищення зарплатні")
    if person == "Всі":
        st.caption("Місяці, в які зарплатня чиновника зростала найбільше. В середньому для кожного чиновника.")
    else:
        st.caption(f"Місяці, в які зарплатня чиновника зростала найбільше. Для {person}.")
    spike_cols = st.columns(len(spike_items))
    for col, (date, pct) in zip(spike_cols, spike_items):
        month_str = MONTHS_UA[date.month]
        label = f"У {month_str} {date.year}"
        value = f"+{pct:.0f}%"
        if person != "Всі":
            col.metric(label, value)
        else:
            col.metric(label, value)

render_data_footer({"Зарплати керівництва КМДА": SALARIES_URL})
