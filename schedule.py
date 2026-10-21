import json
from pathlib import Path
from datetime import date


SCHEDULE_FILE = Path(__file__).parent / "data" / "schedule.json"


def load_schedule():
    """Загружает расписание из schedule.json."""

    if not SCHEDULE_FILE.exists():
        return {}

    with open(SCHEDULE_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


def get_star(target_date: date) -> str:
    """Определяет учебную неделю: * или **."""

    start_date = date(2026, 8, 31)

    days_passed = (target_date - start_date).days
    weeks_passed = days_passed // 7

    if weeks_passed % 2 == 0:
        return "*"

    return "**"


def get_schedule(group_name: str):
    """Возвращает расписание конкретной группы."""

    schedule = load_schedule()

    group_schedule = schedule.get(group_name, {})

    # JSON хранит ключи как строки.
    # Преобразуем дни недели в числа,
    # чтобы bot.py мог работать с weekday().

    result = {}

    for day, lessons in group_schedule.items():
        result[int(day)] = lessons

    return result