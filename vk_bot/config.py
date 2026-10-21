"""
Конфигурация VK-бота.

Все секреты берутся из переменных окружения / файла .env.
НИКОГДА не вставляйте реальный токен в код, который попадает в Git!

Файл .env (в папке vk_bot/, рядом с этим файлом):
    VK_TOKEN=ваш_ключ_серверных_API
    VK_GROUP_ID=идентификатор_сообщества
    VK_ADMIN_ID=ваш_VK_ID_администратора
"""

import os

try:  # python-dotenv устанавливается через requirements.txt
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # если dotenv не установлен — работаем просто из окружения
    pass


def _get_int(name: str) -> int | None:
    """Читает целое из переменной окружения; возвращает None, если не задано."""
    raw = os.getenv(name, "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


# --- Обязательные настройки (заполняете в .env) ---------------------------
VK_TOKEN: str | None = os.getenv("VK_TOKEN") or None          # ключ серверных API сообщества
VK_GROUP_ID: int | None = _get_int("VK_GROUP_ID")             # id сообщества (число, без минуса)
VK_ADMIN_ID: int | None = _get_int("VK_ADMIN_ID")             # VK ID администратора (НЕ telegram id!)

# Telegram ID администратора 1746985964 — это НЕ VK ID. Для VK укажите свой номер профиля.

# --- API --------------------------------------------------------------------
API_VERSION = "5.199"   # актуальная версия VK API на момент разработки

# --- База данных -------------------------------------------------------------
# Отдельный файл, чтобы не повредить базу Telegram-бота (bot.db).
DB_FILE = os.path.join(os.path.dirname(__file__), "vk_bot.db")

# Расписание — та же структура JSON, что и у Telegram-бота.
SCHEDULE_FILE = os.path.join(os.path.dirname(__file__), "data", "schedule.json")


def check_config() -> list[str]:
    """Возвращает список ошибок конфигурации (пустой список = всё ок)."""
    errors = []
    if not VK_TOKEN:
        errors.append("VK_TOKEN не задан. Укажите его в файле .env")
    if VK_GROUP_ID is None:
        errors.append("VK_GROUP_ID не задан. Укажите его в файле .env")
    if VK_ADMIN_ID is None:
        errors.append("VK_ADMIN_ID не задан (нужен для команды рассылки). Укажите его в .env")
    return errors
