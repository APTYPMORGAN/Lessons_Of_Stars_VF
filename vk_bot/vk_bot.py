"""
VK-бот с расписанием ВФ ВолГУ (аналог Telegram-бота).

Транспорт: Bots Long Poll API (vk_api, VkBotLongPoll) — актуальный способ
получения событий сообщества без внешнего сервера и без HTTPS-webhook.

Требуемые настройки в сообществе ВК (Управление -> Сообщения):
  1. "Тип системы управления сообщениями" -> "Статические адреса".
  2. Включить бота (Long Poll), скопировать "Ключ серверных API".
  3. Разрешения токена: messages, photos (для домена сообщений), notify.
  4. Во вкладке "Доступные события" включить "Личные сообщения".

Запуск:  python vk_bot.py     (из папки vk_bot/, при активном venv)
Остановка: Ctrl+C.
"""

import json
import logging
import sys
from datetime import date, timedelta

import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.exceptions import VkApiError  # в vk_api класс пишется как VkApiError

import config
import db
import keyboards as kb
from groups import find_group, get_courses, get_faculties, get_groups
from schedule_core import get_star, render_schedule_title, render_week

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger("vk_bot")

# ---------- тексты ----------

WELCOME_TEXT = (
    "👋 Привет! Это бот расписания ВФ ВолГУ.\n\n"
    "Здесь можно смотреть расписание на сегодня, завтра и всю неделю.\n"
    "Для начала выбери курс, направление и группу — профиль сохранится,\n"
    "и больше выбирать не придётся."
)

HELP_TEXT = (
    "ℹ️ Команды (можно писать текстом или нажимать кнопки):\n\n"
    "/start — начать / настроить профиль\n"
    "/today — расписание на сегодня\n"
    "/tomorrow — расписание на завтра\n"
    "/week — расписание на учебную неделю\n"
    "/whatstar — какая сейчас звёздная неделя\n"
    "/profile — твой профиль\n"
    "/settings — сменить группу\n"
    "/help — эта справка\n\n"
    "⭐ Звёздные недели чередуются: * и ** каждую неделю,\n"
    "отсчёт — с понедельника 31.08.2026."
)


def send(session: vk_api.VkApi, peer_id: int, text: str, keyboard: str | None = None) -> int | None:
    """
    Отправляет сообщение. Возвращает id отправленного сообщения (или None).
    Ошибку ловим ЛЮБУЮ (сеть, запрет ЛС у пользователя и т.п.) — чтобы
    один сбойный получатель не рвал обработку и рассылку.
    """
    if len(text) > 4000:
        text = text[:4000] + "\n…"
    try:
        res = session.vk.messages.send(
            peer_id=peer_id,
            message=text,
            random_id=_random_id(),
            keyboard=keyboard or "",
            edit_reset=True,
        )
        return int(res) if res else None
    except Exception as e:  # noqa: BLE001
        # в т.ч. ошибки 902/914 — пользователь запретил сообщения сообщества
        log.warning("Не удалось отправить %s: %s", peer_id, e)
        return None


def _random_id() -> int:
    import time
    return int(time.time() * 1000) % (2**31)


def delete_previous(session: vk_api.VkApi, peer_id: int) -> None:
    """Аналог удаления предыдущего ответа бота из TG. Удаление доступно <=24ч."""
    last_id = db.get_last_message_id(peer_id)
    if not last_id:
        return
    try:
        session.vk.messages.delete(message_id=last_id, delete_all=True)
    except VkApiError:
        pass  # старше 24 часов или уже удалено — просто оставляем как есть
    db.set_last_message_id(peer_id, None)


def reply(session: vk_api.VkApi, peer_id: int, text: str, keyboard: str | None = None) -> None:
    """Удаляет предыдущий ответ бота (если можно) и отправляет новый."""
    delete_previous(session, peer_id)
    mid = send(session, peer_id, text, keyboard)
    if mid:
        db.set_last_message_id(peer_id, mid)


# ---------- разбор текста/payload в команду ----------

TEXT_COMMANDS = {
    "/start": "start", "/help": "help", "/помощь": "help",
    "/today": "today", "/сегодня": "today",
    "/tomorrow": "tomorrow", "/завтра": "tomorrow",
    "/week": "week", "/неделя": "week",
    "/whatstar": "whatstar", "/звезда": "whatstar",
    "/profile": "profile", "/профиль": "profile",
    "/settings": "settings", "/настройки": "settings",
    "/broadcast": "broadcast",
    "start": "start", "меню": "menu",
    # текстовые кнопки reply-клавиатуры (без payload приходят как текст)
    "📅 сегодня": "today", "📅 завтра": "tomorrow", "📚 неделя": "week",
    "⭐ какая неделя?": "whatstar", "👤 мой профиль": "profile",
    "⚙️ настройки": "settings", "ℹ️ помощь": "help",
}


def parse_event(event_obj: dict) -> tuple[str, dict]:
    """Возвращает (cmd, data) из тела события message_new."""
    msg = event_obj["object"]["message"]
    text = (msg.get("text") or "").strip()

    # 1) payload от инлайн/reply-кнопок
    raw_payload = msg.get("payload")
    if raw_payload:
        try:
            payload = json.loads(raw_payload) if isinstance(raw_payload, str) else raw_payload
            cmd = payload.get("cmd", "")
            return cmd, {"text": text}
        except (json.JSONDecodeError, AttributeError):
            pass

    low = text.lower()
    # 2) команда вида /xxx [аргументы]
    if low.startswith("/"):
        parts = low.split(maxsplit=1)
        name = parts[0]
        args = parts[1] if len(parts) > 1 else ""
        mapped = TEXT_COMMANDS.get(name)
        if mapped == "broadcast":
            return "broadcast", {"args": args}
        if mapped:
            return mapped, {}
        return "unknown_cmd", {"text": text}
    # 3) точное совпадение с кнопками/словами
    if low in TEXT_COMMANDS:
        return TEXT_COMMANDS[low], {}
    # 4) название группы текстом ("ИСП-251")
    norm = text.upper().replace(" ", "")
    for key, names in GROUPS_FOR_LOOKUP.items():
        if norm in names:
            course, faculty = key
            return f"group:{course}:{faculty}:{norm}", {}
    return "chat", {"text": text}


# быстрый индекс групп по названию (для ручного ввода текстом)
GROUPS_FOR_LOOKUP: dict[tuple[int, str], set[str]] = {
    (c, f): {g.upper() for g in gs} for (c, f), gs in __import__("groups").GROUPS.items()
}


# ---------- логика ответов ----------

def handle(cmd: str, data: dict, session: vk_api.VkApi, peer_id: int) -> None:
    profile = db.get_profile(peer_id)

    def need_profile(feature: str) -> None:
        reply(
            session, peer_id,
            f"👤 Профиль ещё не настроен, а без него {feature} недоступно.\n\n"
            "Выбери курс:",
            kb.need_profile_kb(),
        )

    base = cmd.split(":")[0]

    if base == "start" or cmd == "start":
        if profile:
            reply(session, peer_id,
                  f"👋 С возвращением! Твоя группа: {profile['group_name']}\n"
                  "Меню ниже 👇", kb.main_menu_kb())
        else:
            reply(session, peer_id, WELCOME_TEXT + "\n\nВыбери курс:", kb.courses_kb())
        return

    if base == "menu":
        if profile:
            reply(session, peer_id,
                  f"🏠 Главное меню\n🎓 Группа: {profile['group_name']}", kb.main_menu_kb())
        else:
            reply(session, peer_id, WELCOME_TEXT + "\n\nВыбери курс:", kb.courses_kb())
        return

    if base == "help":
        reply(session, peer_id, HELP_TEXT, kb.back_home_kb())
        return

    if base == "whatstar":
        star = get_star(date.today())
        reply(session, peer_id,
              f"⭐ Сейчас звёздная неделя: {star}\n"
              "(чередование каждую неделю, отсчёт с пн 31.08.2026)",
              kb.back_home_kb())
        return

    if base == "profile":
        if not profile:
            need_profile("просмотр профиля")
            return
        reply(session, peer_id,
              f"👤 Твой профиль:\n"
              f"📚 Курс: {profile['course']}\n"
              f"🏛 Направление: {profile['faculty']}\n"
              f"🎓 Группа: {profile['group_name']}\n\n"
              "Изменить — кнопка «Настройки».",
              kb.settings_kb())
        return

    if base == "settings":
        txt = "⚙️ Настройки"
        if profile:
            txt += f"\nТекущая группа: {profile['group_name']}"
        txt += "\n\nХочешь сменить группу?"
        reply(session, peer_id, txt, kb.settings_kb())
        return

    if base in ("today", "tomorrow", "week"):
        if not profile:
            need_profile({"today": "расписание на сегодня",
                          "tomorrow": "расписание на завтра",
                          "week": "расписание на неделю"}[base])
            return
        group = profile["group_name"]
        today = date.today()
        if base == "today":
            text = render_schedule_title(group, today)
        elif base == "tomorrow":
            text = render_schedule_title(group, today + timedelta(days=1))
        else:
            text = render_week(group, today)
        reply(session, peer_id, text, kb.main_menu_kb())
        return

    # --- мастер выбора профиля ---
    if base == "courses":
        reply(session, peer_id, "📚 Выбери курс:", kb.courses_kb())
        return

    if base == "course":  # course:<n>
        course = int(cmd.split(":")[1])
        reply(session, peer_id, f"🏛 Курс {course}. Выбери направление:",
              kb.faculties_kb(course))
        return

    if base == "faculties":  # faculties:<n>
        course = int(cmd.split(":")[1])
        reply(session, peer_id, f"🏛 Курс {course}. Выбери направление:",
              kb.faculties_kb(course))
        return

    if base == "faculty":  # faculty:<n>:<fac>
        _, c, fac = cmd.split(":", 2)
        course = int(c)
        groups = get_groups(course, fac)
        if not groups:
            reply(session, peer_id, "Для этого направления групп пока нет 🤔",
                  kb.courses_kb())
            return
        reply(session, peer_id, f"🎓 {fac}, {course} курс. Выбери группу:",
              kb.groups_kb(course, fac))
        return

    if base == "group":  # group:<n>:<fac>:<name>
        _, c, fac, name = cmd.split(":", 3)
        course = int(c)
        loc = find_group(name)
        if loc is None:
            reply(session, peer_id, "Такой группы нет в справочнике 😕\nПопробуй снова:",
                  kb.courses_kb())
            return
        db.save_profile(peer_id, course, fac, name)
        reply(session, peer_id,
              f"✅ Готово! Сохранена группа {name} ({course} курс, {fac}).\n"
              "Теперь просто нажимай кнопки расписания 👇",
              kb.main_menu_kb())
        return

    if base == "broadcast":
        do_broadcast(session, peer_id, data.get("args", ""))
        return

    if base == "unknown_cmd":
        reply(session, peer_id,
              "🤔 Не знаю такую команду. Напиши /help или используй кнопки.",
              kb.back_home_kb())
        return

    # base == "chat" — обычное сообщение: подсказка
    reply(session, peer_id,
          "Я показываю расписание ВФ ВолГУ 🙂 Нажми кнопку или напиши /help.",
          kb.main_menu_kb() if profile else kb.reply_menu_kb())


def do_broadcast(session: vk_api.VkApi, peer_id: int, args: str) -> None:
    """Рассылка только для администратора (VK_ADMIN_ID из .env)."""
    if peer_id != config.VK_ADMIN_ID:
        reply(session, peer_id, "⛔ Рассылка доступна только администратору.")
        return
    if not args.strip():
        reply(session, peer_id, "Использование: /broadcast <текст рассылки>")
        return
    ids = db.all_vk_ids()
    sent, failed = 0, 0
    for uid in ids:
        if uid == peer_id:
            continue  # не отправляем рассылку самому администратору
        # ошибки одного получателя не должны рвать всю рассылку;
        # тем, кто запретил ЛС, отправка просто не удаётся (см. send)
        try:
            ok = send(session, uid, f"📢 Сообщение от бота:\n{args}") is not None
        except Exception:  # noqa: BLE001 — сеть/токен упали у одного — идём дальше
            ok = False
        if ok:
            sent += 1
        else:
            failed += 1
    reply(session, peer_id, f"📢 Рассылка завершена: доставлено {sent}, ошибок {failed}.")


# ---------- главный цикл ----------

def main() -> None:
    errors = config.check_config()
    # ADMIN_ID не обязателен для работы бота — предупреждаем, но не останавливаем
    hard_errors = [e for e in errors if "ADMIN" not in e]
    warns = [e for e in errors if "ADMIN" in e]
    if hard_errors:
        print("Настройте .env перед запуском:")
        for e in hard_errors:
            print(" -", e)
        sys.exit(1)
    for w in warns:
        log.warning(w)

    db.init_db()

    vk_session = vk_api.VkApi(token=config.VK_TOKEN)
    vk = vk_session.vk
    longpoll = VkBotLongPoll(vk_session, config.VK_GROUP_ID)

    log.info("VK-бот запущен. Сообщество: -%s. Ожидание событий...", config.VK_GROUP_ID)

    for event in longpoll.listen():
        try:
            if event.type == VkBotEventType.MESSAGE_NEW:
                msg = event.obj["object"]["message"]
                peer_id = msg["peer_id"]
                # игнорируем собственные сообщения сообщества
                if msg.get("from_user_id") == config.VK_GROUP_ID or msg.get("out"):
                    continue
                cmd, data = parse_event(event.obj)
                log.info("peer=%s cmd=%s", peer_id, cmd)
                handle(cmd, data, vk_session, peer_id)
            elif event.type == VkBotEventType.MESSAGE_EVENT:
                # нажатие инлайн-кнопки: обрабатываем payload и «гасим» кнопку
                peer_id = event.obj["peer_id"]
                payload_raw = event.obj.get("object", {}).get("payload", "{}")
                payload = json.loads(payload_raw) if isinstance(payload_raw, str) else payload_raw
                cmd = payload.get("cmd", "")
                if cmd:
                    handle(cmd, {}, vk_session, peer_id)
                try:
                    vk.messages.sendMessageEvent(
                        peer_id=peer_id,
                        event_id=event.obj["event_id"],
                        user_id=event.obj["user_id"],
                        type="show_snackbar",
                        text="OK",
                    )
                except VkApiError:
                    pass
        except Exception:  # noqa: BLE001 — бот не должен падать на одном событии
            log.exception("Ошибка обработки события")


if __name__ == "__main__":
    main()
