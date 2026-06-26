# --- Кольори ---

LABEL_COLORS = {
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

# --- CSS ---


_COL = '[data-testid="stColumn"] [data-testid="stLayoutWrapper"]>[data-testid="stVerticalBlock"]'


def _colored_card_css(items: list[tuple[str, str]]) -> str:
    rules = []
    for cls, color in items:
        rules.append(f'{_COL}:has(.{cls}){{border:none !important;background:{color}18 !important;border-radius:12px !important;}}')
    return "".join(rules)


def _party_inner_css() -> str:
    rules = []
    for color in LABEL_COLORS.values():
        cid = color.replace("#", "")
        rules.append(
            f'{_COL}:has(.pc-{cid}) [data-testid="stLayoutWrapper"]>[data-testid="stVerticalBlock"]'
            f'{{border:none !important;background:{color}14 !important;border-radius:8px !important;padding:0.5rem !important;}}'
        )
    return "".join(rules)


def get_voting_list_marker(passed: bool) -> str:
    return f'<span class="{"vl-p" if passed else "vl-f"}" style="display:none"></span>'


def get_all_css() -> str:
    party_items = [(f'pc-{c.replace("#","")}', c) for c in LABEL_COLORS.values()]
    vote_items = [(f'vc-{v.replace(" ","-")}', c) for v, c in VOTE_COLORS.items()]
    vl_items = [("vl-p", "#46A758"), ("vl-f", "#E93D82")]
    return f"<style>{_colored_card_css(party_items + vote_items + vl_items)}{_party_inner_css()}</style>"


def get_card_marker(party: str) -> str:
    color = LABEL_COLORS.get(party, "#757575")
    cid = color.replace("#", "")
    return f'<span class="pc-{cid}" style="display:none"></span>'


def get_vote_marker(vote: str) -> str:
    cid = vote.replace(" ", "-")
    return f'<span class="vc-{cid}" style="display:none"></span>'


