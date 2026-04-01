import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    bot_token: str
    db_path: str
    reminder_interval_minutes: int


def get_config() -> Config:
    load_dotenv()

    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token:
        raise ValueError("BOT_TOKEN не найден. Добавьте его в .env файл.")

    db_path = os.getenv("DB_PATH", "tasks.db")
    interval_raw = os.getenv("REMINDER_INTERVAL_MINUTES", "60")

    try:
        interval = int(interval_raw)
    except ValueError as error:
        raise ValueError("REMINDER_INTERVAL_MINUTES должен быть целым числом.") from error

    if interval < 1:
        raise ValueError("REMINDER_INTERVAL_MINUTES должен быть >= 1.")

    return Config(
        bot_token=bot_token,
        db_path=db_path,
        reminder_interval_minutes=interval,
    )
