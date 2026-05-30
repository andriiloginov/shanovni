# Shanovni

Інструмент громадського контролю за Київською міською радою — голосування депутатів, рішення ради, декларації та зарплати чиновників у зручному форматі.

## Що можна дізнатись

- **Як голосував твій депутат** — поіменні результати за кожним рішенням
- **Що означає рішення** — ШІ пояснює документи простою мовою
- **Скільки отримують чиновники** — зарплати керівництва КМДА з розбивкою по складових
- **Декларації** — майно та доходи депутатів через реєстр НАЗК

## Джерела даних

| Дані | Джерело |
|---|---|
| Склад ради та депутати | [data.gov.ua](https://data.gov.ua) |
| Поіменні голосування | [data.gov.ua](https://data.gov.ua) |
| Рішення Київради (PDF) | [kmr.gov.ua](https://kmr.gov.ua) |
| Зарплати керівництва КМДА | [data.gov.ua](https://data.gov.ua) |
| Декларації | [НАЗК](https://nazk.gov.ua) |

Всі дані — офіційні відкриті реєстри. Shanovni не зберігає жодної інформації.

## Запустити локально

```bash
git clone https://github.com/your-username/shanovni.git
cd shanovni
pip install -r requirements.txt
streamlit run app.py
```

Додай файл `.streamlit/secrets.toml`:

```toml
ANTHROPIC_API_KEY = "your-api-key"
```

## Стек

Streamlit · pandas · Claude API (Anthropic) · pypdf · data.gov.ua
