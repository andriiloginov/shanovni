import streamlit as st
import anthropic
from docs import find_doc, fetch_pdf_bytes, build_api_messages, get_doc_summary

PREMADE_QUESTIONS = [
    "Поясни мені це рішення простими словами",
    "Як це рішення впливає саме на мене",
    "Які існують ризики в цьому документі",
]

SYSTEM_PROMPT = (
    "Ти — помічник, який допомагає громадянам України розібратися в рішеннях Київської міської ради. "
    "Відповідай українською мовою, чітко і стисло, без зайвого юридичного жаргону. "
    "Якщо до повідомлення прикріплено PDF-документ, спирайся насамперед на його зміст. "
    "Правила форматування: не використовуй емодзі; якщо потрібні заголовки — використовуй лише рівень #### і нижче; "
    "відповідь має бути стислою."
)


# --- Сторінка чату ---

if "chat_doc" not in st.session_state:
    st.info("Спочатку оберіть голосування на сторінці результатів.")
    if st.button("Повернутись до голосувань"):
        st.switch_page("pages/voting.py")
    st.stop()

result = st.session_state["chat_doc"]
gl_text = st.session_state.get("chat_gl_text", "")
chat_key = f"chat_{hash(gl_text)}"

if chat_key not in st.session_state:
    st.session_state[chat_key] = []
messages = st.session_state[chat_key]

st.markdown(f"### {result['title'] or gl_text}")
st.link_button(f"Читати оригінал рішення {result['legalActNum']} ↗", result["doc_url"])
st.divider()

if not messages:
    st.markdown("##### Запитай про це рішення")
    cols = st.columns(len(PREMADE_QUESTIONS))
    for i, q in enumerate(PREMADE_QUESTIONS):
        if cols[i].button(q, use_container_width=True, key=f"premade_{i}"):
            st.session_state["chat_initial_question"] = q
            st.rerun()

initial_q = st.session_state.pop("chat_initial_question", None)

for msg in messages:
    with st.chat_message(msg["role"]):
        st.write(msg["text"])

user_input = st.chat_input("Запитай про це рішення...") or initial_q
if user_input:
    messages.append({"role": "user", "text": user_input})
    with st.chat_message("user"):
        st.write(user_input)

    pdf_bytes = (
        fetch_pdf_bytes(result["doc_url"])
        if result["doc_url"].endswith(".pdf") or "old.kmr.gov.ua" in result["doc_url"]
        else None
    )
    api_messages = build_api_messages(messages, pdf_bytes)

    client = anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])
    with st.chat_message("assistant"):
        with client.messages.stream(
            model="claude-haiku-4-5",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=api_messages,
        ) as stream:
            response_text = st.write_stream(stream.text_stream)
    messages.append({"role": "assistant", "text": response_text})
