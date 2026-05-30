import re
import pandas as pd
import requests
import io
import streamlit as st
from data import DEPUTIES_URL, SALARIES_URL, UA, SALARY_COMPONENTS
from ui import PARTY_COLORS

PARTY_MAP = {
    "удар": "УДАР",
    "європейська": "ЄС",
    "слуга": "Слуга Народу",
    "батьківщина": "Батьківщина",
    "голос": "Голос",
    "свобода": "Свобода",
    "єдність": "Єдність",
    "опозиційна": "ОПЗЖ",
    "позафракційн": "Позафракційні",
}

# Функції для обробки даних депутатів та голосувань, спрощуючи їх для зручності використання в інших сторінках

def clean_party(text):
    """'Скорочує Партія "УДАР Віталія Кличка"' до 'УДАР'. Використовується в simplify_data()."""
    if not isinstance(text, str) or text.strip() in ["None", "", "nan"]:
        return "Позафракційні"
    t = text.lower()
    for keyword, short_name in PARTY_MAP.items():
        if keyword in t:
            return short_name
    return text.strip()


def simplify_data(df):
    """Нормалізує колонки party та name/full_name у DataFrame. Використовується в reps.py, voting.py."""
    if 'party' in df.columns:
        df['party'] = df['party'].apply(clean_party)

    name_col = 'full_name' if 'full_name' in df.columns else 'name' if 'name' in df.columns else None
    if name_col:
        df[name_col] = df[name_col].str.strip().apply(
            lambda s: ' '.join(w.capitalize() for w in s.split()) if isinstance(s, str) else s
        )

    return df

# Функція для роботи з даними голосувань (скорочення імен для з'єднання з даними депутатів)

def to_short_name(full_name):
    """'Андронов Владислав Євгенович' → 'Андронов В. Є.' — ключ для з'єднання з даними голосувань. Використовується в voting.py."""
    parts = str(full_name).split()
    if len(parts) >= 3:
        return f"{parts[0]} {parts[1][0]}. {parts[2][0]}."
    if len(parts) == 2:
        return f"{parts[0]} {parts[1][0]}."
    return str(full_name).strip()


@st.cache_data(ttl=86400, show_spinner=False)
def _is_image_available(url: str) -> bool:
    try:
        r = requests.head(url, headers=UA, timeout=5)
        return r.status_code == 200 and "image" in r.headers.get("Content-Type", "")
    except Exception:
        return False


def deputy_avatar(deputy_id: int, name: str, party: str = "", size: int = 80):
    """Аватарка депутата: фото якщо є в DEPUTY_PHOTOS, інакше — ініціали."""
    import streamlit as st
    from photos import get_photo_url
    url = get_photo_url(deputy_id)
    parts = str(name).split()
    initials = (parts[0][0] + parts[1][0]).upper() if len(parts) >= 2 else parts[0][0].upper()
    color = PARTY_COLORS.get(party, "#757575")
    use_photo = url and _is_image_available(url)
    if use_photo:
        st.markdown(
            f'<img src="{url}" width="{size}" height="{size}" '
            f'style="border-radius:50%;object-fit:cover;display:block;margin-bottom:4px;">',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div style="width:{size}px;height:{size}px;border-radius:50%;background:{color};'
            f'display:flex;align-items:center;justify-content:center;'
            f'color:#fff;font-weight:700;font-size:{size // 3}px;margin-bottom:4px;">'
            f'{initials}</div>',
            unsafe_allow_html=True,
        )


def get_badge(text, color="#757575"):
    """HTML-бейдж з кольоровим фоном."""
    return (
        f'<span style="background:{color}20;color:{color};'
        f'padding:2px 10px;border-radius:12px;font-size:14px;font-weight:500;'
        f'display:inline-block;margin:0 2px 4px 0;">'
        f'{text}</span>'
    )


def get_party_badge(party):
    """HTML-бейдж фракції з кольором партії."""
    color = PARTY_COLORS.get(party, "#757575")
    return get_badge(party, color)


def extract_district(address):
    if not isinstance(address, str):
        return None
    m = re.search(r'\(([^)]*район)\)', address)
    if not m:
        return None
    return re.sub(r'\s+', ' ', m.group(1)).strip()


@st.cache_data(ttl=86400)
def geocode_postal_code(postal_code):
    if not re.match(r'^0[1-6]\d{3}$', postal_code):
        return None
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={
                "q": f"{postal_code}, Київ, Україна",
                "format": "json",
                "addressdetails": 1,
                "limit": 1,
                "accept-language": "uk",
            },
            headers=UA,
            timeout=10,
        )
        data = r.json()
        if not data:
            return None
        addr = data[0].get("address", {})
        return addr.get("borough") or addr.get("suburb") or addr.get("city_district")
    except (requests.RequestException, ValueError, KeyError):
        return None


# Функції для завантаження та кешування даних голосувань на 24 години
@st.cache_data(ttl=86400)
def load_deputies():
    """Завантажує список депутатів Київради з data.gov.ua, кешує на 24 год. Використовується в reps.py, voting.py."""
    try:
        r = requests.get(DEPUTIES_URL, headers=UA, timeout=20)
        df = pd.read_excel(io.BytesIO(r.content), header=1)
        df = df.dropna(subset=['ПІБ']).rename(columns={
            '№ з/п': 'id', 'ПІБ': 'name', 'Фракція': 'party',
            'Адреса громадської приймальні': 'address', 'Телефон': 'phone',
        })
        df = simplify_data(df)
        df['district'] = df['address'].apply(extract_district)
        return df
    except:
        return pd.DataFrame()


def render_data_footer(sources):
    st.divider()
    links = " | ".join(f"[{name}]({url})" for name, url in sources.items())
    st.caption(
        "Дані отримано з Єдиного державного вебпорталу відкритих даних "
        "(data.gov.ua), порталу КМДA та НАЗК відповідно до Закону України "
        "«Про доступ до публічної інформації» та відображено без змін. "
        f"Ліцензія: CC BY 4.0. Джерело: {links}"
    )


@st.cache_data(ttl=86400)
def load_salaries():
    try:
        r = requests.get(SALARIES_URL, headers=UA, timeout=20)
        df = pd.read_csv(io.StringIO(r.text))
        df['employeeName'] = (
            df['employeeName']
            .str.replace(r'\s+', ' ', regex=True)
            .str.replace(r'\.(?=[А-ЯІЇЄҐ])', '. ', regex=True)
            .str.strip()
        )
        pay_cols = list(SALARY_COMPONENTS.keys())
        df[pay_cols] = df[pay_cols].fillna(0)
        df['total'] = df[pay_cols].sum(axis=1)
        df['date'] = pd.to_datetime(
            df['year'].astype(str) + '-' + df['month'].astype(str).str.zfill(2) + '-01'
        )
        return df
    except:
        return pd.DataFrame()