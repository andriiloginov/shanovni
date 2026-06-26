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


def _party_card_css() -> str:
    rules = []
    for color in LABEL_COLORS.values():
        cid = color.replace("#", "")
        rules.append(
            f'[data-testid="stColumn"] [data-testid="stLayoutWrapper"]>'
            f'[data-testid="stVerticalBlock"]:has(.pc-{cid})'
            f'{{border:none !important;background:{color}18 !important;border-radius:12px !important;}}'
        )
        rules.append(
            f'[data-testid="stColumn"] [data-testid="stLayoutWrapper"]>'
            f'[data-testid="stVerticalBlock"]:has(.pc-{cid}) '
            f'[data-testid="stLayoutWrapper"]>[data-testid="stVerticalBlock"]'
            f'{{border:none !important;background:{color}14 !important;border-radius:8px !important;'
            f'padding:0.5rem !important;}}'
        )
    return "".join(rules)


def _vote_card_css() -> str:
    rules = []
    for vote, color in VOTE_COLORS.items():
        cid = vote.replace(" ", "-")
        rules.append(
            f'[data-testid="stColumn"] [data-testid="stLayoutWrapper"]>'
            f'[data-testid="stVerticalBlock"]:has(.vc-{cid})'
            f'{{border:none !important;background:{color}18 !important;border-radius:12px !important;}}'
        )
    # Voting list cards
    rules.append(
        '[data-testid="stColumn"] [data-testid="stLayoutWrapper"]>'
        '[data-testid="stVerticalBlock"]:has(.vl-p)'
        '{border:none !important;background:#46A75818 !important;border-radius:12px !important;}'
    )
    rules.append(
        '[data-testid="stColumn"] [data-testid="stLayoutWrapper"]>'
        '[data-testid="stVerticalBlock"]:has(.vl-f)'
        '{border:none !important;background:#E93D8218 !important;border-radius:12px !important;}'
    )
    return "".join(rules)


def get_voting_list_marker(passed: bool) -> str:
    return f'<span class="{"vl-p" if passed else "vl-f"}" style="display:none"></span>'


def get_all_css() -> str:
    return f"<style>{_party_card_css()}{_vote_card_css()}</style>"


def get_card_marker(party: str) -> str:
    color = LABEL_COLORS.get(party, "#757575")
    cid = color.replace("#", "")
    return f'<span class="pc-{cid}" style="display:none"></span>'


def get_vote_marker(vote: str) -> str:
    cid = vote.replace(" ", "-")
    return f'<span class="vc-{cid}" style="display:none"></span>'


