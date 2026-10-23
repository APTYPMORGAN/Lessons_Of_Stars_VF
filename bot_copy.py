import asyncio
import sqlite3
from datetime import date, timedelta
ADMIN_ID = 1746985964

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

bot = Bot(token=TOKEN)
dp = Dispatcher()
async def broadcast_message(text: str):
    conn = sqlite3.connect("bot.db")
    cursor = conn.cursor()

    cursor.execute("SELECT telegram_id FROM users")
    users = cursor.fetchall()

    conn.close()

    success = 0
    failed = 0

    for (telegram_id,) in users:
        try:
            await bot.send_message(
                chat_id=telegram_id,
                text=text
            )
            success += 1

        except Exception:
            failed += 1

        await asyncio.sleep(0.05)

    return success, failed

# ============================================================
# БАЗА ДАННЫХ
# ============================================================

DB_NAME = "bot.db"


def init_db():
    connection = sqlite3.connect(DB_NAME)
    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            telegram_id INTEGER PRIMARY KEY,
            course INTEGER,
            faculty TEXT,
            group_name TEXT
        )
    """)

    connection.commit()
    connection.close()


def get_user(telegram_id):
    connection = sqlite3.connect(DB_NAME)
    cursor = connection.cursor()

    cursor.execute(
        "SELECT course, faculty, group_name FROM users WHERE telegram_id = ?",
        (telegram_id,)
    )

    user = cursor.fetchone()

    connection.close()

    return user


def save_user(telegram_id, course, faculty, group_name):
    connection = sqlite3.connect(DB_NAME)
    cursor = connection.cursor()

    cursor.execute("""
        INSERT OR REPLACE INTO users
        (telegram_id, course, faculty, group_name)
        VALUES (?, ?, ?, ?)
    """, (
        telegram_id,
        course,
        faculty,
        group_name
    ))

    connection.commit()
    connection.close()


# ============================================================
# ПОСЛЕДНЕЕ СООБЩЕНИЕ БОТА
# ============================================================

last_bot_message = {}


async def send_new_message(message: Message, text: str):
    """
    Удаляет предыдущее сообщение бота этому пользователю
    и отправляет новое.
    """

    user_id = message.from_user.id

    # Удаляем старое сообщение бота
    if user_id in last_bot_message:
        try:
            await last_bot_message[user_id].delete()
        except Exception:
            pass

    # Отправляем новое
    new_message = await message.answer(text)

    # Запоминаем его
    last_bot_message[user_id] = new_message


async def send_new_callback_message(callback: CallbackQuery, text: str):
    """
    То же самое, но для нажатия inline-кнопки.
    """

    user_id = callback.from_user.id

    if user_id in last_bot_message:
        try:
            await last_bot_message[user_id].delete()
        except Exception:
            pass

    new_message = await callback.message.answer(text)

    last_bot_message[user_id] = new_message


# ============================================================
# ЗВЁЗДЫ
# ============================================================

# Первая учебная неделя — 31 августа 2026 года.
# Она является неделей "*".

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


def get_lesson_time(target_date, lesson_number):
    if target_date.weekday() == 5:
        return SATURDAY_TIMES[lesson_number]

    return WEEKDAY_TIMES[lesson_number]


# ============================================================
# НАЗВАНИЯ ДНЕЙ
# ============================================================

WEEKDAYS = [
    "Понедельник",
    "Вторник",
    "Среда",
    "Четверг",
    "Пятница",
    "Суббота",
    "Воскресенье",
]


# ============================================================
# РАСПИСАНИЕ ИСП-241
# ============================================================

SCHEDULE_ISP_241 = {

    "Понедельник": {
        1: None,

        2: {
            "subject": "Разработка мобильных приложений",
            "type": "Лабораторная",
            "teacher": "Леонтьев Д.А.",
            "room": "1-36",
        },

        3: {
            "subject": "Разработка программных модулей",
            "type": "Лабораторная",
            "teacher": "Донскова Д.А.",
            "room": "1-02",
        },

        4: {
            "subject": "Разработка программных модулей",
            "type": "Лекция",
            "teacher": "Донскова Д.А.",
            "room": "3-02",
        },

        5: {
            "subject": "Внедрение и поддержка компьютерных систем",
            "type": "Лабораторная",
            "teacher": "Ушакова М.А.",
            "room": "3-03",
        },
    },

    "Вторник": {
        1: None,

        2: {
            "**": {
                "subject": "Системное программирование",
                "type": "Лабораторная",
                "teacher": "Токаев Т.И.",
                "room": "1-36",
            }
        },

        3: {
            "subject": "Физическая культура",
            "type": "Практика",
            "teacher": "Ерохина О.А.",
            "room": "спортивный зал",
        },

        4: {
            "subject": "Иностранный язык в профессиональной сфере",
            "type": "Практика",
            "teacher": "Пенькова О.В.",
            "room": "2-22",
        },

        5: {
            "*": {
                "subject": "Разработка программных модулей",
                "type": "Лабораторная",
                "teacher": "Донскова Д.А.",
                "room": "3-03",
            },

            "**": {
                "subject": "Кураторский час",
                "type": "",
                "teacher": "Саблина Е.Е.",
                "room": "2-17",
            },
        },
    },

    "Среда": {
        1: None,

        2: {
            "subject": "Компьютерное 3D-моделирование",
            "type": "Лабораторная",
            "teacher": "Леонтьев Д.А.",
            "room": "1-02",
        },

        3: {
            "subject": "Системное программирование",
            "type": "Лабораторная",
            "teacher": "Токаев Т.И.",
            "room": "3-03",
        },

        4: {
            "subject": "Технология разработки программного обеспечения",
            "type": "Лекция",
            "teacher": "Катунов Д.А.",
            "room": "2-20",
        },

        5: None,
    },

    "Четверг": {
        1: {
            "**": {
                "subject": "Инструментальные средства разработки программного обеспечения",
                "type": "Лабораторная",
                "teacher": "Леонтьев Д.А.",
                "room": "1-36",
            }
        },

        2: {
            "*": {
                "subject": "Внедрение и поддержка компьютерных систем",
                "type": "Лекция",
                "teacher": "Ушакова М.А.",
                "room": "Актовый зал",
            },

            "**": {
                "subject": "Компьютерное 3D-моделирование",
                "type": "Лабораторная",
                "teacher": "Леонтьев Д.А.",
                "room": "1-02",
            },
        },

        3: {
            "subject": "Системное программирование",
            "type": "Лекция",
            "teacher": "Токаев Т.И.",
            "room": "Актовый зал",
        },

        4: None,
        5: None,
    },

    "Пятница": {
        1: None,
        2: None,
        3: None,
        4: None,
        5: None,
    },

    "Суббота": {
        1: {
            "subject": "Инструментальные средства разработки программного обеспечения",
            "type": "Лабораторная",
            "teacher": "Леонтьев Д.А.",
            "room": "3-03",
        },

        2: {
            "subject": "Технология разработки программного обеспечения",
            "type": "Лабораторная",
            "teacher": "Катунов Д.А.",
            "room": "3-09",
        },

        3: None,
        4: None,
        5: None,
    },
}


# ============================================================
# ПОЛУЧЕНИЕ РАСПИСАНИЯ ГРУППЫ
# ============================================================

def get_schedule(group_name):
    if group_name == "ИСП-241":
        return SCHEDULE_ISP_241

    return None


# ============================================================
# ПОЛУЧЕНИЕ КОНКРЕТНОЙ ПАРЫ
# ============================================================

def get_lesson(lesson_data, star):

    if lesson_data is None:
        return None

    # Постоянная пара
    if "subject" in lesson_data:
        return lesson_data

    # Пара зависит от звезды
    return lesson_data.get(star)


# ============================================================
# КОМПАКТНЫЙ ВЫВОД ОДНОЙ ПАРЫ
# ============================================================

def format_lesson(target_date, number, lesson):

    if lesson is None:
        return None

    lesson_time = get_lesson_time(target_date, number)

    text = (
        f"{number}. {lesson_time} — "
        f"{lesson['subject']}"
    )

    if lesson["type"]:
        text += f" ({lesson['type']})"

    text += f"\n   {lesson['teacher']} · {lesson['room']}"

    return text


# ============================================================
# РАСПИСАНИЕ НА ОДИН ДЕНЬ
# ============================================================

def get_day_schedule(target_date, group_name):

    schedule = get_schedule(group_name)

    if schedule is None:
        return "❌ Для этой группы расписание пока не добавлено."

    weekday = WEEKDAYS[target_date.weekday()]
    star = get_star(target_date)

    day_schedule = schedule.get(weekday, {})

    lessons = []

    for number in range(1, 6):

        lesson_data = day_schedule.get(number)

        lesson = get_lesson(
            lesson_data,
            star
        )

        formatted = format_lesson(
            target_date,
            number,
            lesson
        )

        if formatted:
            lessons.append(formatted)

    if not lessons:
        return (
            f"📅 {weekday}\n"
            f"⭐ Неделя: {star}\n\n"
            "Пар нет 🎉"
        )

    text = (
        f"📅 {weekday} · {target_date.strftime('%d.%m')}\n"
        f"⭐ Неделя: {star}\n\n"
    )

    text += "\n\n".join(lessons)

    return text


# ============================================================
# ПРОВЕРКА ПРОФИЛЯ
# ============================================================

async def require_profile(message: Message):

    user = get_user(message.from_user.id)

    if user is not None:
        return user

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⚙️ Выбрать группу",
                    callback_data="register"
                )
            ]
        ]
    )

    await send_new_message(
        message,
        "❗ Сначала нужно выбрать свой курс, факультет и группу."
    )

    # Отправляем кнопку отдельно
    user_id = message.from_user.id

    try:
        await last_bot_message[user_id].delete()
    except Exception:
        pass

    new_message = await message.answer(
        "👇 Нажми кнопку ниже:",
        reply_markup=keyboard
    )

    last_bot_message[user_id] = new_message

    return None


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

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="ИСП",
                    callback_data=f"faculty_{course}_ИСП"
                ),
                InlineKeyboardButton(
                    text="ЗСП",
                    callback_data=f"faculty_{course}_ЗСП"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="ЭСП",
                    callback_data=f"faculty_{course}_ЭСП"
                ),
                InlineKeyboardButton(
                    text="ЮСП",
                    callback_data=f"faculty_{course}_ЮСП"
                ),
            ],
        ]
    )


# ============================================================
# КЛАВИАТУРА ГРУПП
# ============================================================

def group_keyboard(course, faculty):

    buttons = []

    # Пока для теста существует только ИСП-241
    if course == 3 and faculty == "ИСП":

        buttons.append([
            InlineKeyboardButton(
                text="ИСП-241",
                callback_data="group_ИСП-241"
            )
        ])

    if not buttons:
        buttons.append([
            InlineKeyboardButton(
                text="Пока нет групп",
                callback_data="nothing"
            )
        ])

    return InlineKeyboardMarkup(
        inline_keyboard=buttons
    )


# ============================================================
# /START
# ============================================================
@dp.message(Command("broadcast"))
async def broadcast_handler(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ У вас нет доступа к этой команде.")
        return

    text = message.text.replace("/broadcast", "", 1).strip()

    if not text:
        await message.answer(
            "Использование:\n\n"
            "/broadcast Текст сообщения"
        )
        return

    status_message = await message.answer(
        "📤 Начинаю рассылку..."
    )

    success, failed = await broadcast_message(text)

    await status_message.edit_text(
        f"✅ Рассылка завершена!\n\n"
        f"📨 Отправлено: {success}\n"
        f"❌ Не удалось отправить: {failed}"
    )
@dp.message(Command("start"))
async def start_command(message: Message):

    user = get_user(message.from_user.id)

    if user is not None:

        course, faculty, group_name = user

        await send_new_message(
            message,
            f"👋 С возвращением!\n\n"
            f"🎓 {course} курс · {faculty}\n"
            f"👥 Группа: {group_name}\n\n"
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
        "Для начала выбери свой курс:"
    )

    user_id = message.from_user.id

    try:
        await last_bot_message[user_id].delete()
    except Exception:
        pass

    new_message = await message.answer(
        "🎓 Выбери курс:",
        reply_markup=course_keyboard()
    )

    last_bot_message[user_id] = new_message


# ============================================================
# ВЫБОР КУРСА
# ============================================================

@dp.callback_query(F.data.startswith("course_"))
async def course_selected(callback: CallbackQuery):

    course = int(callback.data.split("_")[1])

    await callback.answer()

    await send_new_callback_message(
        callback,
        f"🎓 Выбран {course} курс.\n\n"
        "Теперь выбери факультет:"
    )

    user_id = callback.from_user.id

    try:
        await last_bot_message[user_id].delete()
    except Exception:
        pass

    new_message = await callback.message.answer(
        "🏫 Выбери факультет:",
        reply_markup=faculty_keyboard(course)
    )

    last_bot_message[user_id] = new_message


# ============================================================
# ВЫБОР ФАКУЛЬТЕТА
# ============================================================

@dp.callback_query(F.data.startswith("faculty_"))
async def faculty_selected(callback: CallbackQuery):

    parts = callback.data.split("_")

    course = int(parts[1])
    faculty = parts[2]

    await callback.answer()

    user_id = callback.from_user.id

    try:
        await last_bot_message[user_id].delete()
    except Exception:
        pass

    new_message = await callback.message.answer(
        f"🏫 Факультет: {faculty}\n\n"
        "Теперь выбери группу:",
        reply_markup=group_keyboard(course, faculty)
    )

    last_bot_message[user_id] = new_message


# ============================================================
# ВЫБОР ГРУППЫ
# ============================================================

@dp.callback_query(F.data.startswith("group_"))
async def group_selected(callback: CallbackQuery):

    group_name = callback.data.replace("group_", "")

    await callback.answer()

    # Для теста определяем данные группы
    if group_name == "ИСП-241":
        course = 3
        faculty = "ИСП"
    else:
        await callback.message.answer(
            "❌ Эта группа пока не добавлена."
        )
        return

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
        f"🏫 Факультет: {faculty}\n"
        f"👥 Группа: {group_name}\n\n"
        f"Теперь расписание будет показываться автоматически.\n\n"
        f"/today — сегодня\n"
        f"/tomorrow — завтра\n"
        f"/week — неделя\n"
        f"/profile — мой профиль\n"
        f"/settings — изменить группу"
    )


# ============================================================
# /TODAY
# ============================================================

@dp.message(Command("today"))
async def today_command(message: Message):

    user = await require_profile(message)

    if user is None:
        return

    _, _, group_name = user

    today = date.today()

    await send_new_message(
        message,
        get_day_schedule(
            today,
            group_name
        )
    )


# ============================================================
# /TOMORROW
# ============================================================

@dp.message(Command("tomorrow"))
async def tomorrow_command(message: Message):

    user = await require_profile(message)

    if user is None:
        return

    _, _, group_name = user

    tomorrow = date.today() + timedelta(days=1)

    await send_new_message(
        message,
        get_day_schedule(
            tomorrow,
            group_name
        )
    )


# ============================================================
# /WEEK
# ============================================================

@dp.message(Command("week"))
async def week_command(message: Message):

    user = await require_profile(message)

    if user is None:
        return

    _, _, group_name = user

    today = date.today()

    monday = today - timedelta(
        days=today.weekday()
    )

    text = (
        f"📚 Неделя · {group_name}\n\n"
    )

    for i in range(6):

        target_date = monday + timedelta(days=i)

        day_text = get_day_schedule(
            target_date,
            group_name
        )

        text += day_text
        text += "\n\n"

        if i != 5:
            text += "────────────\n\n"

    await send_new_message(
        message,
        text
    )


# ============================================================
# /WHATSTAR
# ============================================================

@dp.message(Command("whatstar"))
async def whatstar_command(message: Message):

    user = await require_profile(message)

    if user is None:
        return

    today = date.today()

    star = get_star(today)

    await send_new_message(
        message,
        f"⭐ Сейчас учебная неделя {star}"
    )


# ============================================================
# /PROFILE
# ============================================================

@dp.message(Command("profile"))
async def profile_command(message: Message):

    user = get_user(message.from_user.id)

    if user is None:
        await require_profile(message)
        return

    course, faculty, group_name = user

    await send_new_message(
        message,
        f"👤 Твой профиль\n\n"
        f"🎓 Курс: {course}\n"
        f"🏫 Факультет: {faculty}\n"
        f"👥 Группа: {group_name}\n\n"
        f"Чтобы изменить данные:\n"
        f"/settings"
    )


# ============================================================
# /SETTINGS
# ============================================================

@dp.message(Command("settings"))
async def settings_command(message: Message):

    await send_new_message(
        message,
        "⚙️ Настройки\n\n"
        "Здесь можно изменить свой курс, факультет или группу."
    )

    user_id = message.from_user.id

    try:
        await last_bot_message[user_id].delete()
    except Exception:
        pass

    new_message = await message.answer(
        "🎓 Выбери новый курс:",
        reply_markup=course_keyboard()
    )

    last_bot_message[user_id] = new_message


# ============================================================
# /HELP
# ============================================================

@dp.message(Command("help"))
async def help_command(message: Message):

    await send_new_message(
        message,
        "📚 Доступные команды:\n\n"
        "/today — расписание на сегодня\n"
        "/tomorrow — расписание на завтра\n"
        "/week — расписание на неделю\n"
        "/whatstar — текущая звезда\n"
        "/profile — мой профиль\n"
        "/settings — изменить группу\n"
        "/help — помощь"
    )


# ============================================================
# ЗАПУСК
# ============================================================

async def main():

    init_db()

    print("Бот запущен!")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())