"""
log.py — відстеження змін у таблиці депутатів Київради.

Використання:
    from log import check_deputies_changes
    check_deputies_changes()   # порівнює поточну таблицю зі знімком, фіксує зміни

Файли:
    rep_shot.json — останній відомий стан таблиці {id: name}
    rep_log.json  — хронологія всіх змін
"""

import json
import requests
import io
import pandas as pd
from datetime import datetime, timezone
from pathlib import Path
from data import DEPUTIES_URL, UA

SNAPSHOT_FILE = Path(__file__).parent / "rep_shot.json"
LOG_FILE = Path(__file__).parent / "rep_log.json"


def _fetch_current() -> dict[int, str]:
    """Завантажує актуальну таблицю депутатів → {id: name}."""
    r = requests.get(DEPUTIES_URL, headers=UA, timeout=20)
    df = pd.read_excel(io.BytesIO(r.content), header=1)
    df = df.dropna(subset=["ПІБ"]).rename(columns={"№ з/п": "id", "ПІБ": "name"})
    return {int(row["id"]): row["name"].strip() for _, row in df.iterrows()}


def _load_snapshot() -> dict[int, str]:
    """Читає збережений знімок. Повертає порожній dict якщо файл відсутній."""
    if not SNAPSHOT_FILE.exists():
        return {}
    with open(SNAPSHOT_FILE, encoding="utf-8") as f:
        return {int(k): v for k, v in json.load(f).items()}


def _save_snapshot(data: dict[int, str]):
    with open(SNAPSHOT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _load_log() -> list[dict]:
    if not LOG_FILE.exists():
        return []
    with open(LOG_FILE, encoding="utf-8") as f:
        return json.load(f)


def _save_log(log: list[dict]):
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)


def check_deputies_changes(silent: bool = False) -> list[dict]:
    """
    Порівнює поточну таблицю зі знімком. Якщо є зміни — записує до лог-файлу.
    Повертає список змін цього запуску (порожній якщо змін немає).
    """
    current = _fetch_current()
    snapshot = _load_snapshot()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    changes = []

    if not snapshot:
        # Перший запуск — просто зберігаємо знімок
        _save_snapshot(current)
        if not silent:
            print(f"[{now}] Початковий знімок збережено ({len(current)} депутатів).")
        return []

    all_ids = set(current) | set(snapshot)

    for dep_id in sorted(all_ids):
        old = snapshot.get(dep_id)
        new = current.get(dep_id)

        if old == new:
            continue
        elif old is None:
            changes.append({"id": dep_id, "type": "added", "name": new})
        elif new is None:
            changes.append({"id": dep_id, "type": "removed", "name": old})
        else:
            changes.append({"id": dep_id, "type": "renamed", "old_name": old, "new_name": new})

    if changes:
        log = _load_log()
        log.append({"timestamp": now, "changes": changes})
        _save_log(log)
        _save_snapshot(current)
        if not silent:
            print(f"[{now}] Зафіксовано {len(changes)} змін:")
            for c in changes:
                if c["type"] == "added":
                    print(f"  + [{c['id']}] {c['name']}")
                elif c["type"] == "removed":
                    print(f"  - [{c['id']}] {c['name']}")
                else:
                    print(f"  ~ [{c['id']}] {c['old_name']} → {c['new_name']}")
    else:
        if not silent:
            print(f"[{now}] Змін не виявлено.")

    return changes


if __name__ == "__main__":
    check_deputies_changes()
