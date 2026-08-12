"""docs.py — пошук офіційних документів за голосуваннями Київради"""

import base64
import io
import json
import re
import requests
import pandas as pd
import streamlit as st
import anthropic
from data import UA, CITIES, ASSISTANT_SYSTEM_PROMPT, CHAT_FAST_MODE


@st.cache_resource
def _client() -> anthropic.Anthropic:
    """Єдиний клієнт Anthropic на весь процес — cache_resource не перестворює між reruns."""
    return anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])


def _is_doc_url(url: str) -> bool:
    """old.kmr.gov.ua — проксі для PDF-рішень KMR; звичайні kmr.gov.ua URL документів не містять."""
    return url.endswith(".pdf") or "old.kmr.gov.ua" in url


@st.cache_data(ttl=86400, show_spinner=False)
def load_council_decisions(council: str) -> pd.DataFrame:
    sources = CITIES.get(council, {}).get("council_decisions", {})
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
    """Шукає рішення за текстом голосування: спочатку точний номер, потім схожість назви (поріг 0.65)."""
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


@st.cache_data(ttl=86400, show_spinner=False)
def fetch_pdf_bytes(url: str) -> bytes | None:
    """Завантажує PDF за URL. Повертає None при будь-якій помилці мережі чи HTTP."""
    try:
        r = requests.get(url, headers=UA, timeout=30)
        r.raise_for_status()
        return r.content
    except Exception:
        return None


def _doc_content(doc_url: str, prompt: str) -> list | str:
    """Повертає content для API: base64-документ або просто рядок."""
    if _is_doc_url(doc_url):
        pdf_bytes = fetch_pdf_bytes(doc_url)
        if pdf_bytes:
            return [
                {
                    "type": "document",
                    "source": {"type": "base64", "media_type": "application/pdf",
                               "data": base64.standard_b64encode(pdf_bytes).decode()},
                    "cache_control": {"type": "ephemeral"},
                },
                {"type": "text", "text": prompt},
            ]
    return prompt


def build_api_messages(messages: list, doc_url: str | None) -> list:
    """PDF прикріплюється до першого user-повідомлення, решта — plain text."""
    pdf_bytes = fetch_pdf_bytes(doc_url) if doc_url and _is_doc_url(doc_url) else None
    first, *rest = messages
    first_content = (
        [{"type": "document", "source": {"type": "base64", "media_type": "application/pdf",
           "data": base64.standard_b64encode(pdf_bytes).decode()}, "cache_control": {"type": "ephemeral"}},
         {"type": "text", "text": first["text"]}]
        if pdf_bytes else first["text"]
    )
    return [{"role": first["role"], "content": first_content}] + [{"role": m["role"], "content": m["text"]} for m in rest]


@st.cache_data(ttl=86400, show_spinner=False)
def get_doc_summary(doc_url: str, title: str) -> str:
    """1-2 речення про суть рішення через Haiku. Якщо PDF доступний — аналізує текст; інакше — лише назву."""
    content = _doc_content(
        doc_url,
        "Одним-двома реченнями поясни суть цього рішення. Тільки звичайний текст — без заголовків, без назви рішення, без емодзі, без списків."
    )
    if isinstance(content, str):
        content = f'Одним-двома реченнями поясни суть рішення з назвою: «{title}». Тільки звичайний текст — без заголовків, без назви рішення, без емодзі, без списків.'
    try:
        response = _client().messages.create(
            model="claude-haiku-4-5",
            system="Ти — редактор, який пише чистою літературною українською мовою без русизмів і суржику. Відповідай виключно українською.",
            max_tokens=150,
            messages=[{"role": "user", "content": content}],
        )
        text = response.content[0].text.strip()
        text = "\n".join(l for l in text.splitlines() if not l.startswith("#")).strip()
        return text
    except Exception:
        return "Не вдалося проаналізувати документ — ознайомтесь з оригіналом за посиланням нижче."


_GOSTIN_SYSTEM_PROMPT = """Ти — аналітик публічної політики. Проаналізуй рішення міської ради за фреймворком Gostin (5 кроків).
Відповідай ВИКЛЮЧНО валідним JSON-масивом із 5 об'єктів, без будь-якого тексту поза масивом:
[
  {"step": 1, "question": "...", "answer": "...", "verdict": "justified" | "uncertain" | "not_justified"},
  ...
]

Питання для кожного кроку:
1. Чи адресує рішення реальну підтверджену даними проблему?
2. Чи є розумний зв'язок між рішенням і проблемою — чи воно справді її вирішить?
3. Чи є економічні витрати виправданими порівняно з очікуваними вигодами?
4. Чи покладає рішення тягар на права мешканців — і чи виправданий цей тягар?
5. Чи справедливо розподілені вигоди і тягарі між різними групами мешканців?

answer — 1-2 речення українською. verdict — одне з трьох значень: justified, uncertain, not_justified."""

_GOSTIN_QUESTIONS = {
    1: "Чи адресує рішення реальну проблему на основі даних?",
    2: "Чи є зв'язок між засобом і метою?",
    3: "Чи є витрати розумними порівняно з вигодами?",
    4: "Чи є тягар на права мешканців виправданим?",
    5: "Чи справедливо розподілені вигоди і витрати між групами?",
}

_VERDICT_LABELS = {
    "justified": "Обгрунтовано",
    "uncertain": "Невизначено",
    "not_justified": "Не обгрунтовано",
}

_VERDICT_COLOR = {"justified": "green", "uncertain": "orange", "not_justified": "red"}


@st.cache_data(ttl=86400, show_spinner=False)
def get_gostin_analysis(doc_url: str, title: str) -> list:
    """Аналіз рішення за 5 кроками фреймворку Ґостіна. Повертає список з 5 об'єктів {step, question, answer, verdict}."""
    content = _doc_content(doc_url, "Проаналізуй це рішення за фреймворком Gostin. Відповідь — тільки JSON.")
    if isinstance(content, str):
        content = f'Проаналізуй рішення «{title}» за фреймворком Gostin. Відповідь — тільки JSON.'
    try:
        response = _client().messages.create(
            model="claude-haiku-4-5",
            system=_GOSTIN_SYSTEM_PROMPT,
            max_tokens=1024,
            messages=[{"role": "user", "content": content}],
        )
        raw = response.content[0].text.strip()
        # модель іноді загортає відповідь у ```json ... ```
        if raw.startswith("```"):
            raw = re.sub(r"^```[^\n]*\n?", "", raw).rstrip("`").strip()
        return json.loads(raw)
    except Exception:
        raise


PREMADE_QUESTIONS = [
    "Поясни мені це рішення простими словами",
    "Допоможи написати звернення до КМДА, стосовно цього рішення",
    "Які існують ризики в цьому документі",
]


@st.fragment(parallel=True)
def _render_summary_chat(result: dict, gl_text: str, passed: bool):
    num = result["legalActNum"]
    chat_key = f"chat_{hash(gl_text)}"
    if chat_key not in st.session_state:
        st.session_state[chat_key] = []
    messages = st.session_state[chat_key]

    with st.spinner("Аналізую документ..."):
        summary = get_doc_summary(result["doc_url"], result["title"])

    col_summary, col_chat = st.columns(2)

    with col_summary.container(border=True):
        st.write(":material/summarize: **Короткий опис людською мовою**")
        st.write(summary)
        if passed:
            st.success(f"Рішення прийнято, [оригінал рішення {num} ↗]({result['doc_url']})")
        else:
            st.warning(f"Рішення не прийнято, [переглянути проєкт {num} ↗]({result['doc_url']})")

    with col_chat.container(border=True):
        st.write(":material/smart_toy: **Чат з ШІ**")
        st.caption("Запитай, що тебе хвилює в цьому законопроєкті й цей чат допоможе тобі проаналізувати.")
        for msg in messages:
            with st.chat_message(msg["role"]):
                st.markdown(re.sub(r"^#{1,6}\s+", "**", msg["text"], flags=re.MULTILINE))

        pending = st.session_state.pop(f"{chat_key}_input", None)
        if pending:
            messages.append({"role": "user", "text": pending})
            with st.chat_message("user"):
                st.write(pending)
            doc_url = result["doc_url"] if _is_doc_url(result["doc_url"]) else None
            api_messages = build_api_messages(messages, doc_url)
            with st.chat_message("assistant"):
                try:
                    _model = "claude-opus-4-8" if CHAT_FAST_MODE else "claude-haiku-4-5"
                    _kwargs = {"speed": "fast", "betas": ["fast-mode-2026-02-01"]} if CHAT_FAST_MODE else {}
                    with _client().beta.messages.stream(
                        model=_model,
                        max_tokens=1024,
                        system=ASSISTANT_SYSTEM_PROMPT,
                        messages=api_messages,
                        **_kwargs,
                    ) as stream:
                        response_text = st.write_stream(stream.text_stream)
                except Exception:
                    response_text = "Документ завеликий для аналізу. Ознайомтесь з оригіналом за посиланням вище."
                    st.write(response_text)
            messages.append({"role": "assistant", "text": response_text})

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

        chat_input = st.chat_input("Запитай про це рішення...", key=f"{chat_key}_chat_input")
        if chat_input:
            st.session_state[f"{chat_key}_input"] = chat_input
            st.rerun()

        if messages:
            if st.button("Очистити чат", key=f"{chat_key}_clear"):
                st.session_state[chat_key] = []
                st.rerun()

        with st.expander(":material/info: Дисклеймер"):
            st.caption("Це не юридична консультація. Асистент пояснює рішення простими словами й допомагає скласти чернетку звернення на основі офіційних документів. Він може помилятися або неповно тлумачити документ. Перед поданням звернення чи ухваленням рішень перевіряйте першоджерело за посиланням і за потреби консультуйтеся з юристом.")


@st.fragment(parallel=True)
def _render_gostin(result: dict):
    with st.spinner("Gostin аналіз..."):
        try:
            gostin = get_gostin_analysis(result["doc_url"], result["title"])
        except Exception:
            gostin = []
    if gostin:
        with st.container(border=True):
            st.write(":material/balance: **Аналіз за Gostin Policy Justification Framework**")
            for n, chunk in [(3, gostin[:3]), (2, gostin[3:])]:
                for col, item in zip(st.columns(n), chunk):
                    with col:
                        st.caption(f"Крок {item['step']}")
                        st.markdown(f"**{_GOSTIN_QUESTIONS.get(item['step'], '')}**")
                        st.badge(_VERDICT_LABELS.get(item["verdict"], item["verdict"]), color=_VERDICT_COLOR.get(item["verdict"], "gray"))
                        st.caption(item["answer"])


def render_doc_buttons(gl_text: str, council: str = "kyiv", passed: bool = True):
    result = find_doc(gl_text, council)
    if not result:
        return
    _render_summary_chat(result, gl_text, passed)
    _render_gostin(result)


def _liga_zakon_url(legal_act_num: str, year: int) -> str:
    """Fallback-посилання на рішення через Liga:Zakon, якщо PDF відсутній у реєстрі."""
    seq = legal_act_num.split("/")[0]
    yy = str(year)[-2:]
    return f"https://kmr.ligazakon.net/document/MR{yy}{seq.zfill(4)}"


def _extract_title(gl_text: str) -> str:
    """Витягує назву рішення з тексту голосування, зрізаючи номер акту на початку (формат 08/231-NNN/ПР)."""
    cleaned = re.sub(r"^\s*08/231-\d+/[А-ЯҐЄІЇа-яґєії]+\s*", "", gl_text).strip()
    if not cleaned or cleaned == gl_text:
        cleaned = re.sub(r"^\s*\d+[/-][^\s]+\s*", "", gl_text).strip()
    return cleaned


def _extract_final_num(gl_text: str) -> str | None:
    """Шукає номер прийнятого рішення у форматі NNN/NNNNN (наприклад 100/10567)."""
    m = re.search(r"\b(\d{1,4}/\d{4,6})\b", gl_text)
    return m.group(1) if m else None


def _word_similarity(a: str, b: str) -> float:
    """Jaccard-подібність за словами (кириличними) між двома рядками. Нормується по меншій множині."""
    wa = set(re.findall(r"[а-яґєіїА-ЯҐЄІЇ']+", a.lower()))
    wb = set(re.findall(r"[а-яґєіїА-ЯҐЄІЇ']+", b.lower()))
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / min(len(wa), len(wb))


def _row_to_dict(row: pd.Series, score: float) -> dict:
    """Нормалізує рядок DataFrame у dict для render_doc_buttons. doc_url: PDF якщо є, інакше Liga:Zakon."""
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
