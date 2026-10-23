import asyncio
import sqlite3
import re
from datetime import date, datetime, timedelta

from schedule import get_schedule

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
)


# ============================================================
# НАСТРОЙКИ
# ============================================================

TOKEN = "8726482040:AAHfrqdcFozMNRvJ7v2hgzSTzNAwHpOT3sA"
ADMIN_ID = 1746985964

DB_NAME = "bot.db"


# ============================================================
# БОТ
# ============================================================

bot = Bot(token=TOKEN)
dp = Dispatcher()


# ============================================================
# ГЛАВНОЕ МЕНЮ С ПОСТОЯННЫМИ КНОПКАМИ
# ============================================================

def main_menu_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📅 Сегодня"),
                KeyboardButton(text="📅 Завтра"),
            ],
            [
                KeyboardButton(text="🗓 Вся неделя"),
                KeyboardButton(text="📆 Расписание на дату"),
            ],
            [
                KeyboardButton(text="⭐ Какая неделя?"),
            ],
            [
                KeyboardButton(text="👤 Мой профиль"),
                KeyboardButton(text="⚙️ Настройки"),
            ],
            [
                KeyboardButton(text="ℹ️ Помощь"),
                KeyboardButton(text="🔄 Сменить профиль"),
            ],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выбери действие из меню",
    )


# Пользователи, которые сейчас вводят дату для просмотра расписания
awaiting_date = set()

DATE_MENU_BUTTONS = {
    "📅 Сегодня",
    "📅 Завтра",
    "🗓 Вся неделя",
    "📆 Расписание на дату",
    "⭐ Какая неделя?",
    "👤 Мой профиль",
    "⚙️ Настройки",
    "ℹ️ Помощь",
    "🔄 Сменить профиль",
}


# ============================================================
# БАЗА ДАННЫХ
# ============================================================

conn = sqlite3.connect(DB_NAME)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    telegram_id INTEGER PRIMARY KEY,
    course INTEGER,
    faculty TEXT,
    group_name TEXT,
    user_type TEXT NOT NULL DEFAULT 'student',
    teacher_name TEXT
)
""")

# Добавляем новые столбцы в существующую базу, не удаляя сохранённые профили.
cursor.execute("PRAGMA table_info(users)")
user_columns = {row[1] for row in cursor.fetchall()}

if "user_type" not in user_columns:
    cursor.execute("ALTER TABLE users ADD COLUMN user_type TEXT NOT NULL DEFAULT 'student'")

if "teacher_name" not in user_columns:
    cursor.execute("ALTER TABLE users ADD COLUMN teacher_name TEXT")

conn.commit()


# ============================================================
# ПОСЛЕДНЕЕ СООБЩЕНИЕ БОТА
# ============================================================

last_bot_message = {}


async def delete_last_bot_message(user_id: int):
    if user_id not in last_bot_message:
        return

    try:
        await last_bot_message[user_id].delete()
    except Exception:
        pass


async def send_new_message(message: Message, text: str, reply_markup=None):
    user_id = message.from_user.id

    await delete_last_bot_message(user_id)

    if reply_markup is None:
        reply_markup = main_menu_keyboard()

    new_message = await message.answer(
        text,
        reply_markup=reply_markup
    )

    last_bot_message[user_id] = new_message

    return new_message


async def send_new_callback_message(
    callback: CallbackQuery,
    text: str,
    reply_markup=None
):
    user_id = callback.from_user.id

    await delete_last_bot_message(user_id)

    if reply_markup is None:
        reply_markup = main_menu_keyboard()

    new_message = await callback.message.answer(
        text,
        reply_markup=reply_markup
    )

    last_bot_message[user_id] = new_message

    return new_message


# ============================================================
# РАБОТА С ПОЛЬЗОВАТЕЛЕМ
# ============================================================

def get_user(telegram_id: int):
    """Возвращает данные студенческого профиля (старый формат сохранён)."""
    cursor.execute(
        """
        SELECT course, faculty, group_name
        FROM users
        WHERE telegram_id = ? AND user_type = 'student'
        """,
        (telegram_id,)
    )
    return cursor.fetchone()


def get_user_type(telegram_id: int):
    cursor.execute(
        "SELECT user_type FROM users WHERE telegram_id = ?",
        (telegram_id,)
    )
    row = cursor.fetchone()
    return row[0] if row else None


def get_teacher_name(telegram_id: int):
    cursor.execute(
        "SELECT teacher_name FROM users WHERE telegram_id = ? AND user_type = 'teacher'",
        (telegram_id,)
    )
    row = cursor.fetchone()
    return row[0] if row else None


def save_user(
    telegram_id: int,
    course: int,
    faculty: str,
    group_name: str
):
    cursor.execute(
        """
        INSERT OR REPLACE INTO users
        (telegram_id, course, faculty, group_name, user_type, teacher_name)
        VALUES (?, ?, ?, ?, 'student', NULL)
        """,
        (telegram_id, course, faculty, group_name)
    )
    conn.commit()


def save_teacher(telegram_id: int, teacher_name: str):
    cursor.execute(
        """
        INSERT OR REPLACE INTO users
        (telegram_id, course, faculty, group_name, user_type, teacher_name)
        VALUES (?, NULL, NULL, NULL, 'teacher', ?)
        """,
        (telegram_id, teacher_name)
    )
    conn.commit()


# ============================================================
# ЗВЁЗДЫ
# ============================================================

START_DATE = date(2026, 8, 31)


def get_star(target_date: date) -> str:
    days_passed = (target_date - START_DATE).days
    weeks_passed = days_passed // 7

    if weeks_passed % 2 == 0:
        return "*"

    return "**"


# ============================================================
# ВРЕМЯ ПАР
# ============================================================

WEEKDAY_TIMES = {
    1: "08:30–10:00",
    2: "10:10–11:40",
    3: "12:10–13:40",
    4: "13:50–15:20",
    5: "15:30–17:00",
}


SATURDAY_TIMES = {
    1: "08:30–10:00",
    2: "10:10–11:40",
    3: "11:50–13:20",
    4: "13:30–15:00",
    5: "15:10–16:40",
}


def get_lesson_time(weekday: int, number: int) -> str:
    if weekday == 5:
        return SATURDAY_TIMES[number]

    return WEEKDAY_TIMES[number]


# ============================================================
# ФАКУЛЬТЕТЫ
# ============================================================

FACULTIES = [
    "ИСП",
    "РУПО",
    "ЗСП",
    "ЭСП",
    "ЮСП",
]


# ============================================================
# ГРУППЫ
# ============================================================

GROUPS = {

    # --------------------------------------------------------
    # РУПО — 1 курс
    # --------------------------------------------------------

    (1, "РУПО"): [
        "РУПО-261",
        "РУПО-262",
        "РУПО-263",
        "РУПО-264",
        "РУПО-265",
    ],


    # --------------------------------------------------------
    # ИСП — 2 курс
    # --------------------------------------------------------

    (2, "ИСП"): [
        "ИСП-251",
        "ИСП-252",
        "ИСП-253",
        "ИСП-254",
    ],


    # --------------------------------------------------------
    # ИСП — 3 курс
    # --------------------------------------------------------

    (3, "ИСП"): [
        "ИСП-241",
        "ИСП-242",
        "ИСП-243",
    ],


    # --------------------------------------------------------
    # ИСП — 4 курс
    # --------------------------------------------------------

    (4, "ИСП"): [
        "ИСП-231",
        "ИСП-232",
        "ИСП-233",
    ],


    # --------------------------------------------------------
    # ЗСП
    # --------------------------------------------------------

    (1, "ЗСП"): [
        "ЗСП-261",
        "ЗСП-262",
    ],

    (2, "ЗСП"): [
        "ЗСП-251",
        "ЗСП-252",
    ],

    (3, "ЗСП"): [
        "ЗСП-241",
    ],

    (4, "ЗСП"): [
        "ЗСП-231",
    ],


    # --------------------------------------------------------
    # ЭСП
    # --------------------------------------------------------

    (1, "ЭСП"): [
        "ЭСП-261",
    ],

    (2, "ЭСП"): [
        "ЭСП-251",
    ],

    (3, "ЭСП"): [
        "ЭСП-241",
    ],


    # --------------------------------------------------------
    # ЮСП
    # --------------------------------------------------------

    (1, "ЮСП"): [
        "ЮСП-261",
        "ЮСП-262",
    ],

    (2, "ЮСП"): [
        "ЮСП-251",
        "ЮСП-252",
        "ЮСП-263",
    ],

    (3, "ЮСП"): [
        "ЮСП-241",
        "ЮСП-242",
        "ЮСП-253",
    ],
}


# ============================================================
# ПРЕПОДАВАТЕЛИ: СПИСОК И РАСПИСАНИЕ ИЗ JSON
# ============================================================

TEACHER_PATTERN = re.compile(
    r"преп\.?\s*([А-ЯЁ][а-яё-]+\s+[А-ЯЁ]\.[А-ЯЁ]\.)",
    re.IGNORECASE,
)


def extract_teacher_name(lesson_text: str):
    match = TEACHER_PATTERN.search(lesson_text or "")
    return match.group(1).strip() if match else None


def all_group_names():
    names = []
    for groups in GROUPS.values():
        for group_name in groups:
            if group_name not in names:
                names.append(group_name)
    return names


def build_teacher_list():
    names = set()
    for group_name in all_group_names():
        try:
            schedule = get_schedule(group_name)
        except Exception:
            continue
        for lessons in schedule.values():
            for lesson in lessons:
                name = extract_teacher_name(lesson.get("text", ""))
                if name:
                    names.add(name)
    return sorted(names, key=lambda name: name.casefold())


TEACHERS = build_teacher_list()
TEACHER_PAGE_SIZE = 8
awaiting_teacher_search = set()
teacher_search_query = {}


def role_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎓 Я студент", callback_data="role_student")],
        [InlineKeyboardButton(text="👨‍🏫 Я преподаватель", callback_data="role_teacher")],
    ])


def teacher_keyboard(user_id: int, page: int = 0):
    query = teacher_search_query.get(user_id, "").strip().casefold()
    filtered = [name for name in TEACHERS if query in name.casefold()] if query else TEACHERS[:]
    total_pages = max(1, (len(filtered) + TEACHER_PAGE_SIZE - 1) // TEACHER_PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))
    start_index = page * TEACHER_PAGE_SIZE
    shown = filtered[start_index:start_index + TEACHER_PAGE_SIZE]

    buttons = []
    for name in shown:
        teacher_index = TEACHERS.index(name)
        buttons.append([InlineKeyboardButton(
            text=name,
            callback_data=f"teacher_select_{teacher_index}"
        )])

    navigation = []
    if page > 0:
        navigation.append(InlineKeyboardButton(text="⬅️", callback_data=f"teacher_page_{page - 1}"))
    navigation.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="teacher_page_noop"))
    if page + 1 < total_pages:
        navigation.append(InlineKeyboardButton(text="➡️", callback_data=f"teacher_page_{page + 1}"))
    if navigation:
        buttons.append(navigation)

    buttons.append([InlineKeyboardButton(text="🔎 Найти по фамилии", callback_data="teacher_search")])
    buttons.append([InlineKeyboardButton(text="↩️ Назад", callback_data="role_back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def lesson_is_for_date(lesson_data: dict, target_date: date) -> bool:
    lesson_dates = lesson_data.get("dates")
    if lesson_dates is not None and target_date.isoformat() not in lesson_dates:
        return False
    lesson_star = lesson_data.get("star")
    if lesson_star is not None and lesson_star != get_star(target_date):
        return False
    return True


def get_teacher_day_schedule(teacher_name: str, target_date: date):
    weekday = target_date.weekday()
    merged = {}

    for group_name in all_group_names():
        schedule = get_schedule(group_name)
        for lesson_data in schedule.get(weekday, []):
            if not lesson_is_for_date(lesson_data, target_date):
                continue

            full_text = lesson_data.get("text", "")
            if extract_teacher_name(full_text) != teacher_name:
                continue

            subject = full_text.split("преп.", 1)[0].strip().lstrip("* ").strip()
            if not subject:
                subject = full_text.strip()

            teacher_match = TEACHER_PATTERN.search(full_text)
            room = ""
            if teacher_match:
                room = full_text[teacher_match.end():].strip(" ,")

            number = lesson_data["number"]
            lesson_type = re.search(r"\((?:л\.|пр\.)\)", subject, re.IGNORECASE)
            can_merge = lesson_type is not None

            # Общие лекции и практики объединяем, лабораторные оставляем по группам.
            base_key = (
                number,
                subject.casefold(),
                room.casefold(),
                lesson_data.get("star"),
                tuple(lesson_data.get("dates", [])),
            )
            key = base_key if can_merge else base_key + (group_name,)

            if key not in merged:
                merged[key] = {
                    "number": number,
                    "subject": subject,
                    "room": room,
                    "groups": [],
                }
            if group_name not in merged[key]["groups"]:
                merged[key]["groups"].append(group_name)

    if not merged:
        return "Пар нет 🎉"

    lessons = sorted(merged.values(), key=lambda item: (item["number"], item["subject"].casefold(), item["room"].casefold()))
    result = []
    for lesson in lessons:
        time_text = get_lesson_time(weekday, lesson["number"])
        lines = [f"{lesson['number']}. ⏰ {time_text} — {lesson['subject']}"]
        lines.append("   👥 " + ", ".join(sorted(lesson["groups"])))
        if lesson["room"]:
            lines.append("   📍 " + lesson["room"])
        result.append("\n".join(lines))

    return "\n\n".join(result)


# ============================================================
# РАСПИСАНИЕ
# ============================================================

# Сюда будем добавлять расписание.
#
# Структура:
#
# "ИСП-241": {
#     0: [...],  # понедельник
#     1: [...],  # вторник
#     2: [...],  # среда
#     3: [...],  # четверг
#     4: [...],  # пятница
#     5: [...],  # суббота
# }
#
# Пока оставляем пустым.
# Следующим шагом сюда перенесём расписание из PDF.



# ============================================================
# КЛАВИАТУРА КУРСА
# ============================================================

def course_keyboard():

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="1 курс",
                    callback_data="course_1"
                ),
                InlineKeyboardButton(
                    text="2 курс",
                    callback_data="course_2"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="3 курс",
                    callback_data="course_3"
                ),
                InlineKeyboardButton(
                    text="4 курс",
                    callback_data="course_4"
                ),
            ],
        ]
    )


# ============================================================
# КЛАВИАТУРА ФАКУЛЬТЕТА
# ============================================================

def faculty_keyboard(course):

    buttons = []

    for faculty in FACULTIES:

        if (course, faculty) in GROUPS:

            buttons.append(
                InlineKeyboardButton(
                    text=faculty,
                    callback_data=f"faculty_{course}_{faculty}"
                )
            )

    rows = []

    for i in range(0, len(buttons), 2):
        rows.append(buttons[i:i + 2])

    return InlineKeyboardMarkup(
        inline_keyboard=rows
    )


# ============================================================
# КЛАВИАТУРА ГРУПП
# ============================================================

def group_keyboard(course, faculty):

    groups = GROUPS.get(
        (course, faculty),
        []
    )

    buttons = []

    for group in groups:

        buttons.append([
            InlineKeyboardButton(
                text=group,
                callback_data=f"group_{group}"
            )
        ])

    if not buttons:

        buttons.append([
            InlineKeyboardButton(
                text="Групп пока нет",
                callback_data="nothing"
            )
        ])

    return InlineKeyboardMarkup(
        inline_keyboard=buttons
    )


# ============================================================
# ФОРМАТИРОВАНИЕ ПАРЫ
# ============================================================

def format_lesson(lesson, number, weekday):

    time = get_lesson_time(
        weekday,
        number
    )

    return (
        f"{number}. {time}\n"
        f"{lesson}"
    )


# ============================================================
# ПОЛУЧЕНИЕ РАСПИСАНИЯ
# ============================================================


# ============================================================
# РАСПИСАНИЕ НА ДЕНЬ
# ============================================================

def get_day_schedule(
    group_name: str,
    target_date: date
):
    schedule = get_schedule(group_name)

    weekday = target_date.weekday()

    lessons = schedule.get(
        weekday,
        []
    )

    if not lessons:
        return "Пар нет."

    star = get_star(target_date)

    result = []

    for lesson_data in lessons:

        number = lesson_data["number"]
        lesson_text = lesson_data["text"]

        lesson_star = lesson_data.get("star")
        lesson_dates = lesson_data.get("dates")

        # ----------------------------------------------------
        # Если у пары указаны конкретные даты,
        # показываем её только в эти даты.
        # ----------------------------------------------------

        if lesson_dates is not None:

            target_date_string = target_date.isoformat()

            if target_date_string not in lesson_dates:
                continue

        # ----------------------------------------------------
        # Проверяем звёздную неделю
        # ----------------------------------------------------

        if lesson_star is not None:

            if lesson_star != star:
                continue

        result.append(
            format_lesson(
                lesson_text,
                number,
                weekday
            )
        )

    if not result:
        return "Пар нет."

    return "\n\n".join(result)


# ============================================================
# ПРОВЕРКА ПРОФИЛЯ
# ============================================================

async def require_profile(message: Message):
    user = get_user(message.from_user.id)
    if user is not None:
        return user

    await send_new_message(
        message,
        "👋 Сначала выбери, кто ты — студент или преподаватель.",
        reply_markup=role_keyboard()
    )
    return None


# ============================================================
# /START
# ============================================================

@dp.message(Command("start"))
async def start_command(message: Message):
    user_id = message.from_user.id
    awaiting_date.discard(user_id)
    awaiting_teacher_search.discard(user_id)

    user_type = get_user_type(user_id)
    if user_type == "teacher":
        teacher_name = get_teacher_name(user_id)
        await send_new_message(
            message,
            f"👋 С возвращением!\n\n👨‍🏫 Преподаватель: {teacher_name}\n\n"
            "Выбирай в меню «Сегодня», «Завтра» или «Вся неделя».",
        )
        return

    if user_type == "student":
        user = get_user(user_id)
        if user is not None:
            course, faculty, group_name = user
            await send_new_message(
                message,
                f"👋 С возвращением!\n\n"
                f"🎓 {course} курс · {faculty}\n"
                f"👥 {group_name}\n\n"
                "Выбирай расписание в меню ниже.",
            )
            return

    await send_new_message(
        message,
        "👋 Привет!\n\nЯ бот с расписанием студентов и преподавателей ВФ ВолГУ.\n\n"
        "Сначала выбери, кто ты:",
        reply_markup=role_keyboard(),
    )


@dp.callback_query(F.data == "role_student")
async def role_student_selected(callback: CallbackQuery):
    user_id = callback.from_user.id
    awaiting_date.discard(user_id)
    awaiting_teacher_search.discard(user_id)
    teacher_search_query.pop(user_id, None)
    await callback.answer()
    await send_new_callback_message(
        callback,
        "🎓 Режим студента\n\nСначала выбери курс:",
        reply_markup=course_keyboard(),
    )


@dp.callback_query(F.data == "role_teacher")
async def role_teacher_selected(callback: CallbackQuery):
    user_id = callback.from_user.id
    awaiting_date.discard(user_id)
    awaiting_teacher_search.discard(user_id)
    teacher_search_query.pop(user_id, None)
    await callback.answer()
    if not TEACHERS:
        await send_new_callback_message(callback, "❌ Не удалось найти преподавателей в schedule.json.")
        return
    await send_new_callback_message(
        callback,
        f"👨‍🏫 Режим преподавателя\n\nВыбери себя из списка ({len(TEACHERS)} преподавателей):",
        reply_markup=teacher_keyboard(user_id),
    )


@dp.callback_query(F.data == "role_back")
async def role_back(callback: CallbackQuery):
    user_id = callback.from_user.id
    awaiting_teacher_search.discard(user_id)
    teacher_search_query.pop(user_id, None)
    await callback.answer()
    await send_new_callback_message(
        callback,
        "Выбери, кто ты:",
        reply_markup=role_keyboard(),
    )


@dp.callback_query(F.data.startswith("teacher_page_"))
async def teacher_page_selected(callback: CallbackQuery):
    await callback.answer()
    if callback.data == "teacher_page_noop":
        return
    page = int(callback.data.rsplit("_", 1)[1])
    await send_new_callback_message(
        callback,
        "👨‍🏫 Выбери преподавателя:",
        reply_markup=teacher_keyboard(callback.from_user.id, page),
    )


@dp.callback_query(F.data == "teacher_search")
async def teacher_search_start(callback: CallbackQuery):
    user_id = callback.from_user.id
    awaiting_teacher_search.add(user_id)
    await callback.answer()
    await send_new_callback_message(
        callback,
        "🔎 Напиши фамилию или часть фамилии преподавателя.\n\n"
        "Например: Леонтьев. Чтобы вернуться к полному списку, отправь «все».",
    )


@dp.message(lambda message: message.text and message.from_user.id in awaiting_teacher_search and message.text not in DATE_MENU_BUTTONS)
async def teacher_search_receive(message: Message):
    user_id = message.from_user.id
    query = message.text.strip()
    awaiting_teacher_search.discard(user_id)
    teacher_search_query[user_id] = "" if query.casefold() == "все" else query
    filtered = [name for name in TEACHERS if teacher_search_query[user_id].casefold() in name.casefold()]
    if not filtered:
        await send_new_message(
            message,
            "❌ Никого не нашёл. Попробуй другую фамилию или нажми поиск ещё раз.",
            reply_markup=teacher_keyboard(user_id),
        )
        return
    await send_new_message(
        message,
        f"🔎 Найдено преподавателей: {len(filtered)}. Выбери себя:",
        reply_markup=teacher_keyboard(user_id),
    )


@dp.callback_query(F.data.startswith("teacher_select_"))
async def teacher_selected(callback: CallbackQuery):
    try:
        teacher_index = int(callback.data.rsplit("_", 1)[1])
        teacher_name = TEACHERS[teacher_index]
    except (ValueError, IndexError):
        await callback.answer("Не удалось выбрать преподавателя", show_alert=True)
        return

    save_teacher(callback.from_user.id, teacher_name)
    awaiting_teacher_search.discard(callback.from_user.id)
    teacher_search_query.pop(callback.from_user.id, None)
    await callback.answer()
    await send_new_callback_message(
        callback,
        f"✅ Профиль преподавателя сохранён!\n\n"
        f"👨‍🏫 {teacher_name}\n\n"
        "Теперь можно смотреть расписание кнопками «Сегодня», «Завтра» и «Вся неделя».",
    )


# ============================================================
# ВЫБОР КУРСА
# ============================================================

@dp.callback_query(
    F.data.startswith("course_")
)
async def course_selected(
    callback: CallbackQuery
):

    course = int(
        callback.data.split("_")[1]
    )

    await callback.answer()

    await send_new_callback_message(
        callback,
        f"🎓 {course} курс\n\n"
        f"Теперь выбери направление:",
        reply_markup=faculty_keyboard(course)
    )


# ============================================================
# ВЫБОР ФАКУЛЬТЕТА
# ============================================================

@dp.callback_query(
    F.data.startswith("faculty_")
)
async def faculty_selected(
    callback: CallbackQuery
):

    parts = callback.data.split("_")

    course = int(parts[1])
    faculty = parts[2]

    await callback.answer()

    await send_new_callback_message(
        callback,
        f"🏫 {faculty}\n\n"
        f"Теперь выбери группу:",
        reply_markup=group_keyboard(
            course,
            faculty
        )
    )


# ============================================================
# ВЫБОР ГРУППЫ
# ============================================================

@dp.callback_query(
    F.data.startswith("group_")
)
async def group_selected(
    callback: CallbackQuery
):

    group_name = callback.data.replace(
        "group_",
        ""
    )

    await callback.answer()

    found = None

    for (course, faculty), groups in GROUPS.items():

        if group_name in groups:
            found = (
                course,
                faculty
            )
            break

    if found is None:

        await send_new_callback_message(
            callback,
            "❌ Не удалось определить группу."
        )

        return

    course, faculty = found

    save_user(
        callback.from_user.id,
        course,
        faculty,
        group_name
    )

    await send_new_callback_message(
        callback,
        f"✅ Профиль сохранён!\n\n"
        f"🎓 Курс: {course}\n"
        f"🏫 Направление: {faculty}\n"
        f"👥 Группа: {group_name}\n\n"
        f"Теперь бот будет запоминать твою группу."
    )


# ============================================================
# /PROFILE
# ============================================================

@dp.message(Command("profile"))
@dp.message(F.text == "👤 Мой профиль")
async def profile_command(message: Message):
    awaiting_date.discard(message.from_user.id)
    awaiting_teacher_search.discard(message.from_user.id)
    user_type = get_user_type(message.from_user.id)

    if user_type == "teacher":
        teacher_name = get_teacher_name(message.from_user.id)
        await send_new_message(
            message,
            f"👤 Твой профиль\n\n👨‍🏫 Роль: преподаватель\n📚 {teacher_name}",
        )
        return

    user = get_user(message.from_user.id)
    if user is None:
        await send_new_message(
            message,
            "❌ Профиль ещё не настроен. Выбери тип профиля:",
            reply_markup=role_keyboard(),
        )
        return

    course, faculty, group_name = user
    await send_new_message(
        message,
        f"👤 Твой профиль\n\n🎓 Роль: студент\n🎓 Курс: {course}\n🏫 Направление: {faculty}\n👥 Группа: {group_name}",
    )

# ============================================================
# /SETTINGS
# ============================================================

@dp.message(Command("settings"))
@dp.message(F.text == "⚙️ Настройки")
@dp.message(F.text == "🔄 Сменить профиль")
async def settings_command(message: Message):
    awaiting_date.discard(message.from_user.id)
    awaiting_teacher_search.discard(message.from_user.id)
    await send_new_message(
        message,
        "⚙️ Настройки профиля\n\nВыбери тип профиля. Если сменишь роль, бот сохранит новый выбор.",
        reply_markup=role_keyboard(),
    )

# ============================================================
# /WHATSTAR
# ============================================================

@dp.message(Command("whatstar"))
@dp.message(F.text == "⭐ Какая неделя?")
async def whatstar_command(message: Message):
    awaiting_date.discard(message.from_user.id)
    awaiting_teacher_search.discard(message.from_user.id)

    today = date.today()

    star = get_star(today)

    if star == "*":
        text = "⭐ Сейчас идёт неделя *"
    else:
        text = "⭐⭐ Сейчас идёт неделя **"

    await send_new_message(
        message,
        text
    )


# ============================================================
# РАСПИСАНИЕ НА ВЫБРАННУЮ ДАТУ
# ============================================================

@dp.message(F.text == "📆 Расписание на дату")
async def choose_schedule_date(message: Message):
    user_id = message.from_user.id
    awaiting_teacher_search.discard(user_id)
    user_type = get_user_type(user_id)
    if user_type is None:
        await send_new_message(
            message,
            "👋 Сначала выбери, кто ты — студент или преподаватель.",
            reply_markup=role_keyboard(),
        )
        return

    awaiting_date.add(user_id)
    await send_new_message(
        message,
        "📆 На какую дату показать расписание?\n\n"
        "Введи дату в формате ДД.ММ.ГГГГ, например: 04.12.2026\n\n"
        "Можно выбрать другую кнопку меню, чтобы отменить ввод.",
    )


@dp.message(lambda message: message.text and message.from_user.id in awaiting_date and message.text not in DATE_MENU_BUTTONS)
async def receive_schedule_date(message: Message):
    user_id = message.from_user.id
    try:
        selected_date = datetime.strptime(message.text.strip(), "%d.%m.%Y").date()
    except ValueError:
        await send_new_message(
            message,
            "❌ Не удалось распознать дату.\n\n"
            "Введи её строго в формате ДД.ММ.ГГГГ, например: 04.12.2026.",
        )
        return

    awaiting_date.discard(user_id)
    user_type = get_user_type(user_id)
    weekday_names = ["понедельник", "вторник", "среду", "четверг", "пятницу", "субботу", "воскресенье"]
    header = (
        f"📅 Расписание на {selected_date.strftime('%d.%m.%Y')} "
        f"({weekday_names[selected_date.weekday()]})\n"
        f"⭐ Неделя {get_star(selected_date)}\n\n"
    )

    if user_type == "teacher":
        teacher_name = get_teacher_name(user_id)
        result_text = header + f"👨‍🏫 {teacher_name}\n\n" + get_teacher_day_schedule(teacher_name, selected_date)
    elif user_type == "student":
        user = get_user(user_id)
        if user is None:
            await send_new_message(message, "👋 Сначала выбери свой профиль.", reply_markup=role_keyboard())
            return
        _, _, group_name = user
        result_text = header + f"👥 {group_name}\n\n" + get_day_schedule(group_name, selected_date)
    else:
        await send_new_message(message, "👋 Сначала выбери свой профиль.", reply_markup=role_keyboard())
        return

    await send_new_message(message, result_text)

# ============================================================
# /TODAY
# ============================================================

@dp.message(Command("today"))
@dp.message(F.text == "📅 Сегодня")
async def today_command(message: Message):
    awaiting_date.discard(message.from_user.id)
    awaiting_teacher_search.discard(message.from_user.id)

    user_id = message.from_user.id
    if get_user_type(user_id) == "teacher":
        teacher_name = get_teacher_name(user_id)
        today = date.today()
        weekday_names = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
        text = (
            f"📚 Расписание · {teacher_name}\n\n"
            f"📅 {weekday_names[today.weekday()]} · {today.strftime('%d.%m')}\n"
            f"⭐ Неделя: {get_star(today)}\n\n"
            f"{get_teacher_day_schedule(teacher_name, today)}"
        )
        await send_new_message(message, text)
        return

    user = await require_profile(
        message
    )

    if user is None:
        return

    course, faculty, group_name = user

    today = date.today()

    weekday_names = [
        "Понедельник",
        "Вторник",
        "Среда",
        "Четверг",
        "Пятница",
        "Суббота",
        "Воскресенье",
    ]

    text = (
        f"📅 Сегодня — "
        f"{weekday_names[today.weekday()]}\n"
        f"⭐ Неделя {get_star(today)}\n\n"
        f"👥 {group_name}\n\n"
    )

    text += get_day_schedule(
        group_name,
        today
    )

    await send_new_message(
        message,
        text
    )


# ============================================================
# /TOMORROW
# ============================================================

@dp.message(Command("tomorrow"))
@dp.message(F.text == "📅 Завтра")
async def tomorrow_command(message: Message):
    awaiting_date.discard(message.from_user.id)
    awaiting_teacher_search.discard(message.from_user.id)

    user_id = message.from_user.id
    if get_user_type(user_id) == "teacher":
        teacher_name = get_teacher_name(user_id)
        tomorrow = date.today() + timedelta(days=1)
        weekday_names = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
        text = (
            f"📚 Расписание · {teacher_name}\n\n"
            f"📅 {weekday_names[tomorrow.weekday()]} · {tomorrow.strftime('%d.%m')}\n"
            f"⭐ Неделя: {get_star(tomorrow)}\n\n"
            f"{get_teacher_day_schedule(teacher_name, tomorrow)}"
        )
        await send_new_message(message, text)
        return

    user = await require_profile(
        message
    )

    if user is None:
        return

    course, faculty, group_name = user

    tomorrow = date.today() + timedelta(days=1)

    weekday_names = [
        "Понедельник",
        "Вторник",
        "Среда",
        "Четверг",
        "Пятница",
        "Суббота",
        "Воскресенье",
    ]

    text = (
        f"📅 Завтра — "
        f"{weekday_names[tomorrow.weekday()]}\n"
        f"⭐ Неделя {get_star(tomorrow)}\n\n"
        f"👥 {group_name}\n\n"
    )

    text += get_day_schedule(
        group_name,
        tomorrow
    )

    await send_new_message(
        message,
        text
    )


# ============================================================
# /WEEK
# ============================================================

@dp.message(Command("week"))
@dp.message(F.text == "🗓 Вся неделя")
async def week_command(message: Message):
    awaiting_date.discard(message.from_user.id)
    awaiting_teacher_search.discard(message.from_user.id)

    user_id = message.from_user.id
    if get_user_type(user_id) == "teacher":
        teacher_name = get_teacher_name(user_id)
        today = date.today()
        monday = today - timedelta(days=today.weekday())
        weekday_names = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
        result = [f"📚 Расписание на неделю · {teacher_name}", ""]
        for i in range(6):
            current_date = monday + timedelta(days=i)
            if i > 0:
                result.extend(["────────────", ""])
            result.append(f"📅 {weekday_names[current_date.weekday()]} · {current_date.strftime('%d.%m')}")
            result.append(f"⭐ Неделя: {get_star(current_date)}")
            result.append("")
            result.append(get_teacher_day_schedule(teacher_name, current_date))
            result.append("")
        await send_new_message(message, "\n".join(result).rstrip())
        return

    user = await require_profile(
        message
    )

    if user is None:
        return

    course, faculty, group_name = user

    today = date.today()

    monday = today - timedelta(
        days=today.weekday()
    )

    weekday_names = [
        "Понедельник",
        "Вторник",
        "Среда",
        "Четверг",
        "Пятница",
        "Суббота",
        "Воскресенье",
    ]

    result = [
        f"📅 Неделя {get_star(monday)}",
        f"👥 {group_name}",
        ""
    ]

    for i in range(6):

        current_date = monday + timedelta(
            days=i
        )

        day_name = weekday_names[
            current_date.weekday()
        ]

        day_schedule = get_day_schedule(
            group_name,
            current_date
        )

        result.append(
            f"━━ {day_name} ━━"
        )

        result.append(
            day_schedule
        )

        result.append("")

    await send_new_message(
        message,
        "\n".join(result)
    )


# ============================================================
# /HELP
# ============================================================

@dp.message(Command("help"))
@dp.message(F.text == "ℹ️ Помощь")
async def help_command(message: Message):
    awaiting_date.discard(message.from_user.id)
    awaiting_teacher_search.discard(message.from_user.id)

    await send_new_message(
        message,
        "📚 Возможности бота:\n\n"
        "📅 Сегодня — расписание на сегодня\n"
        "📅 Завтра — расписание на завтра\n"
        "🗓 Вся неделя — расписание на неделю\n"
        "📆 Расписание на дату — выбрать конкретную дату\n"
        "⭐ Какая неделя? — текущая звезда\n"
        "👤 Мой профиль — выбранная группа или преподаватель\n"
        "⚙️ Настройки — сменить тип профиля или группу\n\n"
        "Расписание преподавателя собирается автоматически из расписания групп."
    )


# ============================================================
# BROADCAST
# ============================================================

async def broadcast_message(text: str):

    cursor.execute(
        "SELECT telegram_id FROM users"
    )

    users = cursor.fetchall()

    success = 0
    failed = 0

    for (telegram_id,) in users:

        try:

            await bot.send_message(
                telegram_id,
                text
            )

            success += 1

        except Exception:

            failed += 1

        await asyncio.sleep(0.05)

    return success, failed


@dp.message(Command("broadcast"))
async def broadcast_handler(message: Message):

    if message.from_user.id != ADMIN_ID:

        await message.answer(
            "❌ У вас нет доступа к этой команде."
        )

        return

    text = message.text.replace(
        "/broadcast",
        "",
        1
    ).strip()

    if not text:

        await message.answer(
            "Использование:\n\n"
            "/broadcast Текст сообщения"
        )

        return

    status_message = await message.answer(
        "📤 Начинаю рассылку..."
    )

    success, failed = await broadcast_message(
        text
    )

    await status_message.edit_text(
        f"✅ Рассылка завершена!\n\n"
        f"📨 Отправлено: {success}\n"
        f"❌ Не удалось отправить: {failed}"
    )


# ============================================================
# ЗАПУСК
# ============================================================

async def main():

    print("Бот запущен!")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())