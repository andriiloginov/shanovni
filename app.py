import streamlit as st
from ui import get_all_css

st.set_page_config(page_title="Shanovni.org", layout="wide")
st.markdown(get_all_css(), unsafe_allow_html=True)

with st.sidebar:
    try:
        st.image("images/logo.svg", width=86)
    except:
        pass
    st.markdown("# Shanovni.org :gray-background[beta]")
    st.caption("Інструмент прозорості для міських рад")

page_home = st.Page("pages/home.py", title="Головна", default=True)
page_reps = st.Page("pages/reps.py", title="Депутати")
page_voting = st.Page("pages/voting.py", title="Результати голосувань")
page_salaries = st.Page("pages/salaries.py", title="Зарплати")

pg = st.navigation([page_home, page_reps, page_voting, page_salaries])
pg.run()

with st.sidebar:
    st.divider()
    with st.container(border=True):
        st.write("""
Цей інструмент дозволяє аналізувати склад місцевої ради, результати поіменних голосувань
та їх рішення у зручному форматі. Наразі мій фокус на КМДА, але планую розширити його на інші міста та рівні влади.
        """)
