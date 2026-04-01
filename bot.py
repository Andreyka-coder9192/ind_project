import asyncio
import logging
from contextlib import suppress
from datetime import date, timedelta

from aiogram import Bot, Dispatcher

from config import get_config
from database import Database
from handlers import create_router
from utils import format_date_for_user

logger = logging.getLogger(__name__)


async def reminder_worker(bot: Bot, db: Database, interval_minutes: int) -> None:
    while True:
        today = date.today()
        tomorrow = today + timedelta(days=1)
        tasks = db.get_tasks_for_reminders(today.isoformat(), tomorrow.isoformat())
        date_format_cache = {}
        reminder_mode_cache = {}

        for task in tasks:
            user_id = task["user_id"]
            is_due_today = task["deadline"] == today.isoformat()
            day_label = "сегодня" if is_due_today else "завтра"
            if user_id not in date_format_cache:
                date_format_cache[user_id] = db.get_user_date_format(user_id)
            if user_id not in reminder_mode_cache:
                reminder_mode_cache[user_id] = db.get_user_reminder_mode(user_id)
            user_date_format = date_format_cache[user_id]
            reminder_mode = reminder_mode_cache[user_id]

            if reminder_mode == "off":
                continue
            if reminder_mode == "due_today" and not is_due_today:
                continue
            if reminder_mode == "day_before" and is_due_today:
                continue

            deadline_text = format_date_for_user(task["deadline"], user_date_format)
            text = (
                "Напоминание о дедлайне\n"
                f"Задание #{task['id']}: {task['title']}\n"
                f"Дедлайн: {deadline_text} ({day_label})"
            )
            try:
                await bot.send_message(user_id, text)
                db.mark_task_reminded(task["id"], today.isoformat())
            except Exception as error:  # noqa: BLE001
                logger.warning(
                    "Не удалось отправить напоминание по задаче %s: %s",
                    task["id"],
                    error,
                )

        await asyncio.sleep(interval_minutes * 60)


async def main() -> None:
    logging.basicConfig(level=logging.INFO)

    config = get_config()
    db = Database(config.db_path)
    db.init_db()

    bot = Bot(token=config.bot_token)
    dispatcher = Dispatcher()
    dispatcher.include_router(create_router(db))

    reminder_task = asyncio.create_task(
        reminder_worker(bot, db, config.reminder_interval_minutes)
    )

    try:
        await dispatcher.start_polling(bot)
    finally:
        reminder_task.cancel()
        with suppress(asyncio.CancelledError):
            await reminder_task
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
