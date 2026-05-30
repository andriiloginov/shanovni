"""
docs.py — пошук офіційних документів за голосуваннями рад

Зараз підтримує: Київська міська рада (KMR)
Масштабування: додай нову раду в COUNCIL_DECISIONS і council_id у виклику
"""

import io
import re
import base64
import requests
import pandas as pd
import streamlit as st
import anthropic
from pypdf import PdfReader, PdfWriter
from data import UA, COUNCIL_DECISIONS, ASSISTANT_SYSTEM_PROMPT

PDF_MAX_PAGES = 20


def _truncate_pdf(pdf_bytes: bytes) -> bytes:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    if len(reader.pages) <= PDF_MAX_PAGES:
        return pdf_bytes
    writer = PdfWriter()
    for page in reader.pages[:PDF_MAX_PAGES]:
        writer.add_page(page)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


@st.cache_data(ttl=86400, show_spinner=False)
def load_council_decisions(council: str) -> pd.DataFrame:
    sources = COUNCIL_DECISIONS.get(council, {})
    frames = []
    for key, url in sources.items():
        try:
            r = requests.get(url, headers=UA, timeout=30)
            r.raise_for_status()
            df = pd.read_excel(io.BytesIO(r.content))
            df = df.rename(columns={"legalActDateAccepted": "date_accepted", "url": "pdf_url"})
            if "pdf_url" in df.columns:
                df["pdf_url"] = df["pdf_url"].str.replace(
                    "https://kmr.gov.ua/", "https://old.kmr.gov.ua/", regex=False
                )
            keep = [c for c in ["legalActNum", "title", "date_accepted", "pdf_url"] if c in df.columns]
            frames.append(df[keep].copy())
        except Exception:
            continue
    if not frames:
        return pd.DataFrame(columns=["legalActNum", "title", "date_accepted", "pdf_url"])
    return pd.concat(frames, ignore_index=True)


def find_doc(gl_text: str, council: str = "kyiv") -> dict | None:
    df = load_council_decisions(council)
    if df.empty:
        return None
    final_num = _extract_final_num(gl_text)
    if final_num:
        exact = df[df["legalActNum"] == final_num]
        if not exact.empty:
            return _row_to_dict(exact.iloc[0], score=1.0)
    title = _extract_title(gl_text)
    if not title or len(title) < 10 or not title.lower().startswith("про"):
        return None
    best_score, best_row = 0.0, None
    for _, row in df.iterrows():
        score = _word_similarity(title, str(row.get("title", "")))
        if score > best_score:
            best_score, best_row = score, row
    if best_score < 0.65 or best_row is None:
        return None
    return _row_to_dict(best_row, score=best_score)


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_pdf_bytes(url: str) -> bytes | None:
    try:
        r = requests.get(url, headers=UA, timeout=30)
        r.raise_for_status()
        return _truncate_pdf(r.content)
    except Exception:
        return None


def build_api_messages(messages: list, pdf_bytes: bytes | None) -> list:
    result = []
    for i, msg in enumerate(messages):
        if msg["role"] == "user" and i == 0 and pdf_bytes:
            result.append({"role": "user", "content": [
                {
                    "type": "document",
                    "source": {
                        "type": "base64",
                        "media_type": "application/pdf",
                        "data": base64.standard_b64encode(pdf_bytes).decode(),
                    },
                    "cache_control": {"type": "ephemeral"},
                },
                {"type": "text", "text": msg["text"]},
            ]})
        else:
            result.append({"role": msg["role"], "content": msg["text"]})
    return result


@st.cache_data(ttl=86400, show_spinner=False)
def get_doc_summary(doc_url: str, title: str) -> str:
    pdf_bytes = (
        fetch_pdf_bytes(doc_url)
        if doc_url.endswith(".pdf") or "old.kmr.gov.ua" in doc_url
        else None
    )
    client = anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])
    if pdf_bytes:
        content = [
            {
                "type": "document",
                "source": {
                    "type": "base64",
                    "media_type": "application/pdf",
                    "data": base64.standard_b64encode(pdf_bytes).decode(),
                },
                "cache_control": {"type": "ephemeral"},
            },
            {"type": "text", "text": "Одним-двома реченнями поясни суть цього рішення. Тільки звичайний текст — без заголовків, без назви рішення, без емодзі, без списків."},
        ]
    else:
        content = f'Одним-двома реченнями поясни суть рішення з назвою: «{title}». Тільки звичайний текст — без заголовків, без назви рішення, без емодзі, без списків.'
    try:
        response = client.messages.create(
            model="claude-haiku-4-5",
            system="Ти — редактор, який пише чистою літературною українською мовою без русизмів і суржику. Відповідай виключно українською.",
            max_tokens=150,
            messages=[{"role": "user", "content": content}],
        )
        return response.content[0].text.strip()
    except Exception:
        if pdf_bytes:
            try:
                response = client.messages.create(
                    model="claude-haiku-4-5",
                    system="Ти — редактор, який пише чистою літературною українською мовою без русизмів і суржику. Відповідай виключно українською.",
                    max_tokens=150,
                    messages=[{"role": "user", "content": f'Одним-двома реченнями поясни суть рішення з назвою: «{title}». Тільки звичайний текст — без заголовків, без назви рішення, без емодзі, без списків.'}],
                )
                return response.content[0].text.strip()
            except Exception:
                pass
        return "Документ завеликий для автоматичного аналізу — ознайомтесь з оригіналом за посиланням нижче."


PREMADE_QUESTIONS = [
    "Поясни мені це рішення простими словами",
    "Допоможи написати звернення до КМДА, стосовно цього рішення",
    "Які існують ризики в цьому документі",
]


def render_doc_buttons(gl_text: str, council: str = "kyiv", passed: bool = True):
    """Контейнер з назвою, саммері, кнопками та вбудованим чатом."""
    result = find_doc(gl_text, council)
    if not result:
        return

    num = result["legalActNum"]
    score = result["score"]
    doc_label = f"Читати оригінал рішення {num} ↗" if score == 1.0 else f"Читати оригінал рішення {num} (~{int(score * 100)}% збіг) ↗"
    chat_key = f"chat_{hash(gl_text)}"

    if chat_key not in st.session_state:
        st.session_state[chat_key] = []
    messages = st.session_state[chat_key]

    with st.container(border=True):
        st.write(":gray-background[Огляд документа від ШІ]")
        with st.spinner("Генерую огляд..."):
            st.write(get_doc_summary(result["doc_url"], result["title"]))
        if passed:
            st.success(f"Рішення прийнято, [оригінал рішення {num} ↗]({result['doc_url']})")
        else:
            st.warning(f"Рішення не прийнято, [переглянути проєкт {num} ↗]({result['doc_url']})")

        # Історія чату + стрімінг нової відповіді
        for msg in messages:
            with st.chat_message(msg["role"]):
                st.write(msg["text"])

        pending = st.session_state.pop(f"{chat_key}_input", None)
        if pending:
            messages.append({"role": "user", "text": pending})
            with st.chat_message("user"):
                st.write(pending)
            pdf_bytes = (
                fetch_pdf_bytes(result["doc_url"])
                if result["doc_url"].endswith(".pdf") or "old.kmr.gov.ua" in result["doc_url"]
                else None
            )
            api_messages = build_api_messages(messages, pdf_bytes)
            client = anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])
            with st.chat_message("assistant"):
                try:
                    with client.messages.stream(
                        model="claude-haiku-4-5",
                        max_tokens=1024,
                        system=ASSISTANT_SYSTEM_PROMPT,
                        messages=api_messages,
                    ) as stream:
                        response_text = st.write_stream(stream.text_stream)
                except Exception:
                    response_text = "Документ завеликий для аналізу. Ознайомтесь з оригіналом за посиланням вище."
                    st.write(response_text)
            messages.append({"role": "assistant", "text": response_text})
            st.rerun()

        # Інпут та піли — тільки збирають значення і роблять rerun
        chat_input = st.chat_input("Запитай про це рішення...", key=f"{chat_key}_chat_input")
        if chat_input:
            st.session_state[f"{chat_key}_input"] = chat_input
            st.rerun()

        if not messages:
            selected_pill = st.pills(
                "Питання",
                options=PREMADE_QUESTIONS,
                label_visibility="collapsed",
                key=f"{chat_key}_pills",
            )
            if selected_pill:
                st.session_state[f"{chat_key}_input"] = selected_pill
                st.rerun()


def _liga_zakon_url(legal_act_num: str, year: int) -> str:
    seq = legal_act_num.split("/")[0]
    yy = str(year)[-2:]
    return f"https://kmr.ligazakon.net/document/MR{yy}{seq.zfill(4)}"


def _extract_title(gl_text: str) -> str:
    cleaned = re.sub(r"^\s*08/231-\d+/[А-ЯҐЄІЇа-яґєії]+\s*", "", gl_text).strip()
    if not cleaned or cleaned == gl_text:
        cleaned = re.sub(r"^\s*\d+[/-][^\s]+\s*", "", gl_text).strip()
    return cleaned


def _extract_final_num(gl_text: str) -> str | None:
    m = re.search(r"\b(\d{1,4}/\d{4,6})\b", gl_text)
    return m.group(1) if m else None


def _word_similarity(a: str, b: str) -> float:
    wa = set(re.findall(r"[а-яґєіїА-ЯҐЄІЇ']+", a.lower()))
    wb = set(re.findall(r"[а-яґєіїА-ЯҐЄІЇ']+", b.lower()))
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / min(len(wa), len(wb))


def _row_to_dict(row: pd.Series, score: float) -> dict:
    year = row["date_accepted"].year if pd.notna(row.get("date_accepted")) else 2025
    pdf_url = row.get("pdf_url")
    doc_url = pdf_url if pd.notna(pdf_url) else _liga_zakon_url(row.get("legalActNum", ""), year)
    return {
        "legalActNum": row.get("legalActNum", ""),
        "title": row.get("title", ""),
        "date_accepted": row.get("date_accepted"),
        "doc_url": doc_url,
        "score": score,
    }
