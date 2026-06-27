import streamlit as st
from pathlib import Path

POSTS_DIR = Path(__file__).parent.parent / "posts"

slug = st.query_params.get("post")

_, col, _ = st.columns([1, 4, 1])

with col:
    if slug:
        path = POSTS_DIR / f"{slug}.md"
        if not path.exists():
            st.warning("Статтю не знайдено.")
            st.stop()
        if st.button("← Назад до списку", type="primary"):
            del st.query_params["post"]
            st.rerun()
        audio = path.with_suffix(".mp3")
        if audio.exists():
            st.audio(str(audio))
        st.markdown(path.read_text(encoding="utf-8"))

    else:
        st.header("Блог")
        st.caption("Публічна політика 101. Ми пишемо про те, що робимо та що вивчаємо.")
        st.divider()

        for path in sorted(POSTS_DIR.glob("*.md"), reverse=True):
            lines = path.read_text(encoding="utf-8").strip().splitlines()
            title = lines[0].lstrip("# ").strip()
            excerpt = next((l for l in lines[1:] if l.strip() and not l.startswith("#")), "")
            with st.container(border=True):
                st.markdown(f"**{title}**")
                if excerpt:
                    st.caption(excerpt)
                audio = path.with_suffix(".mp3")
                if audio.exists():
                    st.audio(str(audio))
                if st.button("Читати →", key=path.stem):
                    st.query_params["post"] = path.stem
                    st.rerun()
