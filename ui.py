# --- Кольори ---

PARTY_COLORS = {
    "УДАР": "#A35829",
    "ЄС": "#1F6692",
    "Слуга Народу": "#836A21",
    "Батьківщина": "#873356",
    "Голос": "#1E685F",
    "Свобода": "#5C7C2F",
    "Єдність": "#6E56CF",
    "ОПЗЖ": "#7D5E54",
    "Позафракційні": "#60646C",
}

VOTE_COLORS = {
    "За": "#46A758",
    "Проти": "#E93D82",
    "Утримався": "#978365",
    "Не голосував": "#646464",
}


# --- Текстові константи ---

EMPTY_VOTE_MESSAGES = {
    "За": "Ніхто не голосував за.",
    "Проти": "Ніхто не голосував проти.",
    "Утримався": "Ніхто не утримувався.",
    "Не голосував": "Всі присутні проголосували.",
}

VOTE_BADGES = {
    "За": ":gray-background[За]",
    "Проти": ":gray-background[Проти]",
    "Утримався": ":gray-background[Утримався]",
}

# --- CSS ---


def _global_css() -> str:
    """Стрілки expander."""
    return (
        "details:not([open]) [data-testid='stIconMaterial']::after"
        "{content:'\\25B8';font-size:16px;}"
        "details[open] [data-testid='stIconMaterial']::after"
        "{content:'\\25BE';font-size:16px;}"
    )


def _party_card_css() -> str:
    """Filled-картки депутатів з кольором фракції + темніші вкладені секції."""
    rules = []
    for color in PARTY_COLORS.values():
        cid = color.replace("#", "")
        # Фон картки (stColumn обмежує до рівня карток, не сторінки)
        rules.append(
            f'[data-testid="stColumn"] [data-testid="stLayoutWrapper"]>'
            f'[data-testid="stVerticalBlock"]:has(.pc-{cid})'
            f'{{border:none !important;background:{color}18 !important;border-radius:12px !important;}}'
        )
        # Вкладені контейнери (Контакти, Декларація) — темніший фон
        rules.append(
            f'[data-testid="stColumn"] [data-testid="stLayoutWrapper"]>'
            f'[data-testid="stVerticalBlock"]:has(.pc-{cid}) '
            f'[data-testid="stLayoutWrapper"]>[data-testid="stVerticalBlock"]'
            f'{{border:none !important;background:{color}14 !important;border-radius:8px !important;'
            f'padding:0.5rem !important;}}'
        )
    return "".join(rules)


def _vote_card_css() -> str:
    """Filled-картки результатів голосування за кольором голосу."""
    rules = []
    for vote, color in VOTE_COLORS.items():
        cid = vote.replace(" ", "-")
        rules.append(
            f'[data-testid="stColumn"] [data-testid="stLayoutWrapper"]>'
            f'[data-testid="stVerticalBlock"]:has(.vc-{cid})'
            f'{{border:none !important;background:{color}18 !important;border-radius:12px !important;}}'
        )
    return "".join(rules)


def get_all_css() -> str:
    """Повний <style> блок для st.markdown(unsafe_allow_html=True)."""
    return f"<style>{_global_css()}{_party_card_css()}{_vote_card_css()}</style>"


def get_card_marker(party: str) -> str:
    """Прихований маркер для CSS-стилізації картки за фракцією."""
    color = PARTY_COLORS.get(party, "#757575")
    cid = color.replace("#", "")
    return f'<span class="pc-{cid}" style="display:none"></span>'


def get_vote_marker(vote: str) -> str:
    """Прихований маркер для CSS-стилізації картки за результатом голосу."""
    cid = vote.replace(" ", "-")
    return f'<span class="vc-{cid}" style="display:none"></span>'
