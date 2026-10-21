"""
Загрузка расписания из data/schedule.json и фильтрация по дням/звёздным неделям.

Логика повторяет schedule.py вашего Telegram-бота (тот же формат JSON),
но написана независимо, чтобы VK-бот можно было запускать отдельно.

Формат одной записи занятия (как в вашем проекте):
    {"number": 2, "text": "...", "star": "**"}          — только во ** недели
    {"number": 3, "text": "...", "dates": ["10.10"]}    — только в конкретные даты
    {"number": 4, "text": "..."}                         — постоянные занятия

ЕСЛИ структура вашего реального schedule.json отличается (другие имена
полей, другой формат дат) — правьте функции is_lesson_for_date() и
format_lesson(), остальной код менять не нужно.
"""

import json
from datetime import date, timedelta
from pathlib import Path

# Путь: vk_bot/data/schedule.json (скопируйте сюда файл из TG-проекта)
SCHEDULE_FILE = Path(__file__).parent / "data" / "schedule.json"

# Начало учебного отсчёта: понедельник 31 августа 2026 — звёздная неделя '*'
START_DATE = date(2026, 8, 31)

# ВРЕМЯ ЗАНЯТИЙ (не меняем при переносе в VK)
TIME_WEEKDAY = [
    "08:30–10:00",  # 1
    "10:10–11:40",  # 2
    "12:10–13:40",  # 3
    "13:50–15:20",  # 4
    "15:30–17:00",  # 5
]
TIME_SATURDAY = [
    "08:30–10:00",  # 1
    "10:10–11:40",  # 2
    "11:50–13:20",  # 3
    "13:30–15:00",  # 4
    "15:10–16:40",  # 5
]

DAY_NAMES = {
    0: "Понедельник",
    1: "Вторник",
    2: "Среда",
    3: "Четверг",
    4: "Пятница",
    5: "Суббота",
    6: "Воскресенье",
}

# Сокращения типов занятий -> красивые названия (порядок важен: 'л.' проверяем после 'лаб.')
TYPE_ABBREVIATIONS = [
    ("лаб.", "Лабораторная"),
    ("л.", "Лекция"),
    ("пр.", "Практика"),
]


def load_schedule() -> dict:
    """Загружает весь schedule.json. Если файла нет — пустой словарь."""
    if not SCHEDULE_FILE.exists():
        return {}
    with open(SCHEDULE_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


def get_schedule(group_name: str) -> dict[int, list]:
    """Расписание одной группы: {номер_дня(0=пн): [занятия]}."""
    schedule = load_schedule()
    group_schedule = schedule.get(group_name, {})
    result = {}
    for day, lessons in group_schedule.items():
        try:
            result[int(day)] = lessons
        except (ValueError, TypeError):
            continue
    return result


def get_star(target_date: date) -> str:
    """
    Какая звёздная неделя у даты: '*' или '**'.
    31.08.2026 (понедельник) -> '*'. Далее чередование каждую неделю.
    Для дат ДО начала отсчёта считаем недели назад симметрично
    (// округляет вниз, поэтому логика корректна и для отрицательных значений).
    """
    days_passed = (target_date - START_DATE).days
    weeks_passed = days_passed // 7
    return "*" if weeks_passed % 2 == 0 else "**"


def _parse_dates(dates_value) -> set[date]:
    """
    Превращает поле 'dates' занятия в множество конкретных дат.
    Поддерживаем форматы: "10.10", "10.10.2026", "2026-10-10".
    Год по умолчанию — учебный год даты, к которой применяем (см. is_lesson_for_date).
    """
    result = set()
    if isinstance(dates_value, str):
        dates_value = [dates_value]
    for item in dates_value:
        item = str(item).strip()
        try:
            if "-" in item and len(item.split("-")[0]) == 4:  # 2026-10-10
                y, m, d = map(int, item.split("-"))
            elif item.count(".") == 2:                          # 10.10.2026
                d, m, y = map(int, item.split("."))
            elif item.count(".") == 1:                          # 10.10 (год подставим позже)
                d, m = map(int, item.split("."))
                y = None
            else:
                continue
            if y is None:
                result.add((d, m))  # временная метка без года
            else:
                result.add(date(y, m, d))
        except (ValueError, TypeError):
            continue
    return result


def is_lesson_for_date(lesson: dict, target_date: date) -> bool:
    """
    Главное правило достоверности: показываем занятие тогда и только тогда,
    когда оно должно быть в этот день.

    Приоритет проверок:
    1. Есть поле 'dates' -> показываем ТОЛЬКО в перечисленные даты
       (никакого автоматического повтора каждую неделю!).
    2. Есть 'star' '*' или '**' -> показываем только в соответствующую
       звёздную неделю.
    3. Ничего нет -> занятие постоянное, показываем всегда в этот день недели.
    """
    if not isinstance(lesson, dict):
        return False

    star = str(lesson.get("star", "") or "").strip()
    dates_field = lesson.get("dates")

    # 1. Конкретные даты
    if dates_field:
        parsed = _parse_dates(dates_field)
        for entry in parsed:
            if isinstance(entry, date) and entry == target_date:
                return True
            if isinstance(entry, tuple):  # (день, месяц) без года
                d, m = entry
                # пробуем текущий и предыдущий год учебного цикла
                for year in (target_date.year, target_date.year - 1, target_date.year + 1):
                    try:
                        if date(year, m, d) == target_date:
                            return True
                    except ValueError:
                        continue
        return False

    # 2. Звёздные недели
    if star in ("*", "**"):
        return star == get_star(target_date)

    # 3. Постоянное занятие
    return True


def abbrev_to_full(text: str) -> str:
    """Заменяет сокращения типов занятий на полные названия в начале строки."""
    stripped = text.strip()
    lower = stripped.lower()
    for abbr, full in TYPE_ABBREVIATIONS:
        if lower.startswith(abbr):
            rest = stripped[len(abbr):]
            if rest and rest[0] == " ":
                rest = rest[1:]
            return f"{full} {rest}".strip() if rest else full
    return text


def format_lesson(lesson: dict, target_date: date) -> str | None:
    """
    Одна строка вывода: "2. 10:10–11:40 Лекция Название, преп., ауд. **"
    Возвращает None, если занятие не подходит под дату или это пустая пара.
    """
    if not isinstance(lesson, dict):
        return None

    number = lesson.get("number")
    text = str(lesson.get("text", "")).strip()

    # Пустые пары не выводим
    if not text or text in ("-", "—", "нет", "ок"):
        return None

    if not is_lesson_for_date(lesson, target_date):
        return None

    time_str = ""
    if isinstance(number, int) and 1 <= number <= 5:
        times = TIME_SATURDAY if target_date.weekday() == 5 else TIME_WEEKDAY
        time_str = times[number - 1] + " "

    star = str(lesson.get("star", "") or "").strip()
    suffix = f"  {star}" if star in ("*", "**") else ""

    return f"{number}. {time_str}{abbrev_to_full(text)}{suffix}"


def get_day_lessons(group_name: str, target_date: date) -> list[str]:
    """Отформатированные строки занятий группы на конкретную дату."""
    schedule = get_schedule(group_name)
    lessons = schedule.get(target_date.weekday(), [])
    out = []
    for lesson in lessons:
        line = format_lesson(lesson, target_date)
        if line:
            out.append(line)
    return out


def get_week_days(today: date) -> list[date]:
    """Дни текущей учебной недели: с понедельника по субботу (вс. не включаем)."""
    monday = today - timedelta(days=today.weekday())
    return [monday + timedelta(days=i) for i in range(6)]


def render_day_header(target_date: date) -> str:
    star = get_star(target_date)
    return f"{DAY_NAMES[target_date.weekday()]}, {target_date.strftime('%d.%m.%Y')} ({star})"


def render_schedule_title(group_name: str, target_date: date) -> str:
    lines = get_day_lessons(group_name, target_date)
    header = render_day_header(target_date)
    if target_date.weekday() == 6 or not lines:
        return f"📌 {header}\n{group_name}: занятий нет 🎉"
    body = "\n\n".join(lines)
    return f"📌 {header}\n🎓 {group_name}\n\n{body}"


def render_week(group_name: str, today: date) -> str:
    parts = [f"📅 Расписание на неделю\n🎓 {group_name}\n"]
    has_any = False
    for day in get_week_days(today):
        lessons = get_day_lessons(group_name, day)
        header = render_day_header(day)
        if lessons:
            has_any = True
            parts.append(f"\n{header}\n" + "\n".join(lessons))
    if not has_any:
        return f"📅 Расписание на неделю\n🎓 {group_name}\n\nНа этой неделе занятий нет 🎉"
    return "\n\n".join(parts)
