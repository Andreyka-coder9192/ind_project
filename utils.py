import sqlite3
from datetime import date, datetime, timedelta
from html import escape
from typing import List, Optional, Sequence, Tuple

PRIORITY_LABELS = {
    "important": "🔴 Важно",
    "normal": "🟡 Обычное",
    "low": "🟢 Несрочно",
}

STATUS_ACTIVE = "⏳ Активно"
STATUS_DONE = "✅ Выполнено"
PRIORITY_ORDER = {
    "important": 0,
    "normal": 1,
    "low": 2,
}
DATE_FORMAT_LABELS = {
    "dd.mm.yyyy": "dd.mm.yyyy",
    "dd/mm/yyyy": "dd/mm/yyyy",
    "yyyy-mm-dd": "yyyy-mm-dd",
}
REMINDER_MODE_LABELS = {
    "off": "Выкл",
    "due_today": "В день дедлайна",
    "day_before": "За 1 день",
    "both": "За 1 день и в день дедлайна",
}


def parse_deadline(raw_value: str) -> Optional[date]:
    try:
        return datetime.strptime(raw_value, "%Y-%m-%d").date()
    except ValueError:
        return None


def parse_task_id(raw_value: str) -> Optional[int]:
    try:
        task_id = int(raw_value.strip())
    except ValueError:
        return None
    return task_id if task_id > 0 else None


def format_date_for_user(iso_date: str, user_format: str) -> str:
    try:
        parsed = datetime.strptime(iso_date, "%Y-%m-%d")
    except ValueError:
        return iso_date

    if user_format == "dd.mm.yyyy":
        return parsed.strftime("%d.%m.%Y")
    if user_format == "dd/mm/yyyy":
        return parsed.strftime("%d/%m/%Y")
    return parsed.strftime("%Y-%m-%d")


def deadline_today_iso() -> str:
    return date.today().isoformat()


def deadline_tomorrow_iso() -> str:
    return (date.today() + timedelta(days=1)).isoformat()


def split_tasks_for_display(
    tasks: Sequence[sqlite3.Row],
) -> Tuple[List[sqlite3.Row], List[sqlite3.Row]]:
    active_tasks = []
    done_tasks = []
    for task in tasks:
        if task["is_done"]:
            done_tasks.append(task)
        else:
            active_tasks.append(task)

    active_tasks.sort(
        key=lambda task: (
            PRIORITY_ORDER.get(task["priority"], 1),
            task["deadline"],
            task["id"],
        )
    )
    done_tasks.sort(key=lambda task: task["id"])
    return active_tasks, done_tasks


def format_tasks(tasks: Sequence[sqlite3.Row], user_date_format: str) -> str:
    if not tasks:
        return (
            "<b>📚 Твои задачи</b>\n\n"
            "Пока задач нет.\n"
            "Добавьте первое задание через кнопку «Добавить задачу»."
        )

    active_tasks, done_tasks = split_tasks_for_display(tasks)

    lines = ["<b>📚 Твои задачи</b>"]
    if active_tasks:
        lines.append("<b>⏳ Активные</b>")
        for task in active_tasks:
            status = STATUS_ACTIVE
            priority_label = PRIORITY_LABELS.get(task["priority"], "🟡 Обычное")
            safe_title = escape(str(task["title"]))
            lines.append(
                f"#{task['id']} — <b>{safe_title}</b>\n"
                f"{priority_label} | {status} | "
                f"<code>{format_date_for_user(task['deadline'], user_date_format)}</code>"
            )

    if done_tasks:
        lines.append("<b>✅ Выполненные</b>")
        for task in done_tasks:
            status = STATUS_DONE
            priority_label = PRIORITY_LABELS.get(task["priority"], "🟡 Обычное")
            safe_title = escape(str(task["title"]))
            lines.append(
                f"#{task['id']} — <b>{safe_title}</b>\n"
                f"{priority_label} | {status} | "
                f"<code>{format_date_for_user(task['deadline'], user_date_format)}</code>"
            )

    return "\n\n".join(lines)


def format_task_card(task: sqlite3.Row, user_date_format: str) -> str:
    priority_label = PRIORITY_LABELS.get(task["priority"], "🟡 Обычное")
    status = STATUS_DONE if task["is_done"] else STATUS_ACTIVE
    safe_title = escape(str(task["title"]))
    return (
        f"<b>📌 Задача #{task['id']}</b>\n\n"
        f"<b>Название:</b> {safe_title}\n"
        f"<b>Статус:</b> {status}\n"
        f"<b>Приоритет:</b> {priority_label}\n"
        f"<b>Дедлайн:</b> "
        f"<code>{format_date_for_user(task['deadline'], user_date_format)}</code>"
    )
