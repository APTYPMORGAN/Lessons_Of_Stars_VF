"""
Кнопки и меню для VK-бота (Bots Long Poll API, keyboard в messages.send).

Важное ограничение VK: у кнопок может быть ТОЛЬКО текст ИЛИ только payload,
оба поля сразу — нельзя. Поэтому навигация по профилю строится на кнопках
с payload (невидимый код + видимый текст), а команды чата распознаются
и по тексту тоже.

Аналог "удаления предыдущего сообщения" из TG-бота: в VK сообщения
сообщества нельзя удалить из диалога пользователя через Bots Long Poll API,
поэтому используется edits_allowed=0 (пользователь не сможет отредактировать)
+ удаление последнего ответа бота через messages.delete — оно доступно,
пока сообщение не старше 24 часов. Если удалить не удалось (прошло >24 ч),
просто отправляем новое сообщение.
"""

import json


def kb_inline(buttons: list[list[tuple[str, str]]]) -> str:
    """
    Инлайн-клавиатура: кнопки под сообщением.
    buttons — список рядов; каждый элемент ряда = (text, payload).
    payload '' — обычная текстовая кнопка (отправит text как сообщение).
    """
    rows = []
    for row in buttons:
        vk_row = []
        for text, payload in row:
            if payload:
                vk_row.append({
                    "action": {"type": "text", "payload": json.dumps({"cmd": payload}, ensure_ascii=False), "label": text},
                    "color": "primary",
                })
            else:
                vk_row.append({
                    "action": {"type": "text", "label": text},
                    "color": "secondary",
                })
        rows.append(vk_row)
    return json.dumps({"inline_keyboard": rows}, ensure_ascii=False)


def kb_reply(buttons: list[list[tuple[str, str]]]) -> str:
    """Клавиатура сообщества (постоянное меню снизу чата)."""
    rows = []
    for row in buttons:
        vk_row = []
        for text, payload in row:
            action = {"type": "text", "label": text}
            if payload:
                action["payload"] = json.dumps({"cmd": payload}, ensure_ascii=False)
            vk_row.append({"action": action, "color": "secondary"})
        rows.append(vk_row)
    return json.dumps({"keyboard": rows, "one_time": False, "buttons": rows}, ensure_ascii=False)


# ---------- Основные экраны ----------

def main_menu_kb() -> str:
    """Главное меню: то же, что /today /tomorrow /week /whatstar /profile /settings /help."""
    return kb_inline([
        [("📅 Сегодня", "today"), ("📅 Завтра", "tomorrow")],
        [("📚 Неделя", "week"), ("⭐ Какая неделя?", "whatstar")],
        [("👤 Мой профиль", "profile"), ("⚙️ Настройки", "settings")],
        [("ℹ️ Помощь", "help"), ("🔄 Обновить меню", "menu")],
    ])


def reply_menu_kb() -> str:
    """Постоянная клавиатура сообщества (ставится при /start)."""
    return kb_reply([
        [("📅 Сегодня", "today"), ("📅 Завтра", "tomorrow"), ("📚 Неделя", "week")],
        [("⭐ Какая неделя?", "whatstar"), ("👤 Мой профиль", "profile")],
        [("⚙️ Настройки", "settings"), ("ℹ️ Помощь", "help")],
    ])


def back_home_kb() -> str:
    return kb_inline([[("🏠 В меню", "menu"), ("ℹ️ Помощь", "help")]])


# ---------- Экраны выбора профиля ----------

def courses_kb() -> str:
    rows = [[(f"{c} курс", f"course:{c}") ] for c in _courses_list()]
    return kb_inline(rows + [[("🏠 Отмена", "menu")]])


def faculties_kb(course: int) -> str:
    from groups import get_faculties
    rows = [[(fac, f"faculty:{course}:{fac}")] for fac in get_faculties(course)]
    return kb_inline(rows + [[("⬅️ К курсам", "courses"), ("🏠 Отмена", "menu")]])


def groups_kb(course: int, faculty: str) -> str:
    from groups import get_groups
    names = get_groups(course, faculty)
    rows = []
    row = []
    for name in names:
        row.append((name, f"group:{course}:{faculty}:{name}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([("⬅️ К направлениям", f"faculties:{course}"), ("🏠 Отмена", "menu")])
    return kb_inline(rows)


def settings_kb() -> str:
    """Меню настроек: сменить группу или вернуться."""
    return kb_inline([
        [("🔄 Сменить группу", "courses"), ("🏠 В меню", "menu")],
    ])


def need_profile_kb() -> str:
    """Если группа ещё не выбрана — предлагаем настроить профиль."""
    return kb_inline([
        [("👤 Настроить профиль", "courses"), ("ℹ️ Помощь", "help")],
    ])


def _courses_list() -> list[int]:
    from groups import get_courses
    return get_courses()
