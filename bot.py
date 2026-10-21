import asyncio
import sqlite3
from datetime import date, timedelta

from schedule import get_schedule

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
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
# БАЗА ДАННЫХ
# ============================================================

conn = sqlite3.connect(DB_NAME)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    telegram_id INTEGER PRIMARY KEY,
    course INTEGER,
    faculty TEXT,
    group_name TEXT
)
""")

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
    cursor.execute(
        """
        SELECT course, faculty, group_name
        FROM users
        WHERE telegram_id = ?
        """,
        (telegram_id,)
    )

    return cursor.fetchone()


def save_user(
    telegram_id: int,
    course: int,
    faculty: str,
    group_name: str
):
    cursor.execute(
        """
        INSERT OR REPLACE INTO users
        (telegram_id, course, faculty, group_name)
        VALUES (?, ?, ?, ?)
        """,
        (
            telegram_id,
            course,
            faculty,
            group_name
        )
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

    user = get_user(
        message.from_user.id
    )

    if user is not None:
        return user

    await send_new_message(
        message,
        "👋 Сначала выбери свой профиль.",
        reply_markup=course_keyboard()
    )

    return None


# ============================================================
# /START
# ============================================================

@dp.message(Command("start"))
async def start_command(message: Message):

    user = get_user(
        message.from_user.id
    )

    if user is not None:

        course, faculty, group_name = user

        await send_new_message(
            message,
            f"👋 С возвращением!\n\n"
            f"🎓 {course} курс · {faculty}\n"
            f"👥 {group_name}\n\n"
            f"/today — сегодня\n"
            f"/tomorrow — завтра\n"
            f"/week — неделя\n"
            f"/whatstar — текущая звезда\n"
            f"/profile — мой профиль\n"
            f"/settings — изменить группу\n"
            f"/help — помощь"
        )

        return

    await send_new_message(
        message,
        "👋 Привет!\n\n"
        "Я бот с расписанием студентов ВФ ВолГУ.\n\n"
        "Сначала выбери свой курс:",
        reply_markup=course_keyboard()
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
async def profile_command(message: Message):

    user = get_user(
        message.from_user.id
    )

    if user is None:

        await send_new_message(
            message,
            "❌ Профиль ещё не настроен.",
            reply_markup=course_keyboard()
        )

        return

    course, faculty, group_name = user

    await send_new_message(
        message,
        f"👤 Твой профиль\n\n"
        f"🎓 Курс: {course}\n"
        f"🏫 Направление: {faculty}\n"
        f"👥 Группа: {group_name}"
    )


# ============================================================
# /SETTINGS
# ============================================================

@dp.message(Command("settings"))
async def settings_command(message: Message):

    await send_new_message(
        message,
        "⚙️ Настройки\n\n"
        "Выбери курс:",
        reply_markup=course_keyboard()
    )


# ============================================================
# /WHATSTAR
# ============================================================

@dp.message(Command("whatstar"))
async def whatstar_command(message: Message):

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
# /TODAY
# ============================================================

@dp.message(Command("today"))
async def today_command(message: Message):

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
async def tomorrow_command(message: Message):

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
async def week_command(message: Message):

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
async def help_command(message: Message):

    await send_new_message(
        message,
        "📚 Команды бота:\n\n"
        "/today — расписание на сегодня\n"
        "/tomorrow — расписание на завтра\n"
        "/week — расписание на неделю\n"
        "/whatstar — текущая звезда\n"
        "/profile — мой профиль\n"
        "/settings — изменить группу\n"
        "/help — помощь"
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