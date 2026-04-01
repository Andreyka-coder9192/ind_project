import calendar
import sqlite3
from typing import Dict, Optional, Sequence, Tuple

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)
from utils import split_tasks_for_display

ADD_TASK_BUTTON = "Добавить задачу"
MY_TASKS_BUTTON = "Мои задачи"
CALENDAR_BUTTON = "Календарь"
HELP_BUTTON = "Помощь"
SETTINGS_BUTTON = "Настройки"
BACK_BUTTON = "Назад"
CANCEL_BUTTON = "Отмена"

PRIORITY_IMPORTANT_BUTTON = "🔴 Важно"
PRIORITY_NORMAL_BUTTON = "🟡 Обычное"
PRIORITY_LOW_BUTTON = "🟢 Несрочно"

PRIORITY_BUTTON_TO_VALUE = {
    PRIORITY_IMPORTANT_BUTTON: "important",
    PRIORITY_NORMAL_BUTTON: "normal",
    PRIORITY_LOW_BUTTON: "low",
}

DEADLINE_TODAY_BUTTON = "Сегодня"
DEADLINE_TOMORROW_BUTTON = "Завтра"
DEADLINE_PICK_BUTTON = "Выбрать дату"
DEADLINE_MANUAL_BUTTON = "Ввести вручную"


def _short_task_title(title: str, max_length: int = 23) -> str:
    normalized = " ".join(str(title).split())
    if len(normalized) <= max_length:
        return normalized
    return normalized[: max_length - 3].rstrip() + "..."


def main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=ADD_TASK_BUTTON)],
            [KeyboardButton(text=MY_TASKS_BUTTON), KeyboardButton(text=CALENDAR_BUTTON)],
            [KeyboardButton(text=HELP_BUTTON), KeyboardButton(text=SETTINGS_BUTTON)],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие",
    )


def priority_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=PRIORITY_IMPORTANT_BUTTON)],
            [KeyboardButton(text=PRIORITY_NORMAL_BUTTON)],
            [KeyboardButton(text=PRIORITY_LOW_BUTTON)],
            [KeyboardButton(text=BACK_BUTTON), KeyboardButton(text=CANCEL_BUTTON)],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите приоритет",
    )


def cancel_keyboard(add_back: bool = False) -> ReplyKeyboardMarkup:
    keyboard_rows = []
    if add_back:
        keyboard_rows.append([KeyboardButton(text=BACK_BUTTON)])
    keyboard_rows.append([KeyboardButton(text=CANCEL_BUTTON)])

    return ReplyKeyboardMarkup(
        keyboard=keyboard_rows,
        resize_keyboard=True,
        input_field_placeholder="Можно отменить через кнопку или /cancel",
    )


def deadline_mode_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=DEADLINE_TODAY_BUTTON), KeyboardButton(text=DEADLINE_TOMORROW_BUTTON)],
            [KeyboardButton(text=DEADLINE_PICK_BUTTON)],
            [KeyboardButton(text=DEADLINE_MANUAL_BUTTON)],
            [KeyboardButton(text=BACK_BUTTON), KeyboardButton(text=CANCEL_BUTTON)],
        ],
        resize_keyboard=True,
        input_field_placeholder="Как указать дедлайн?",
    )


def settings_main_inline_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📅 Формат даты", callback_data="settings:date")],
            [InlineKeyboardButton(text="🔔 Напоминания", callback_data="settings:rem")],
            [InlineKeyboardButton(text="✖️ Закрыть", callback_data="settings:close")],
        ]
    )


def settings_date_inline_keyboard(current_format: str) -> InlineKeyboardMarkup:
    dot_text = "✅ dd.mm.yyyy" if current_format == "dd.mm.yyyy" else "dd.mm.yyyy"
    slash_text = "✅ dd/mm/yyyy" if current_format == "dd/mm/yyyy" else "dd/mm/yyyy"
    iso_text = "✅ yyyy-mm-dd" if current_format == "yyyy-mm-dd" else "yyyy-mm-dd"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=dot_text, callback_data="setfmt:dot")],
            [InlineKeyboardButton(text=slash_text, callback_data="setfmt:slash")],
            [InlineKeyboardButton(text=iso_text, callback_data="setfmt:iso")],
            [InlineKeyboardButton(text="⬅️ К настройкам", callback_data="settings:main")],
        ]
    )


def settings_reminder_inline_keyboard(current_reminder_mode: str) -> InlineKeyboardMarkup:
    off_text = "✅ Выкл" if current_reminder_mode == "off" else "Выкл"
    today_text = (
        "✅ В день дедлайна"
        if current_reminder_mode == "due_today"
        else "В день дедлайна"
    )
    before_text = (
        "✅ За 1 день"
        if current_reminder_mode == "day_before"
        else "За 1 день"
    )
    both_text = (
        "✅ За 1 день и в день дедлайна"
        if current_reminder_mode == "both"
        else "За 1 день и в день дедлайна"
    )

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=off_text, callback_data="setrem:off")],
            [InlineKeyboardButton(text=today_text, callback_data="setrem:today")],
            [InlineKeyboardButton(text=before_text, callback_data="setrem:before")],
            [InlineKeyboardButton(text=both_text, callback_data="setrem:both")],
            [InlineKeyboardButton(text="⬅️ К настройкам", callback_data="settings:main")],
        ]
    )


def year_picker_keyboard(year: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="◀️", callback_data="picky:prev"),
                InlineKeyboardButton(text=str(year), callback_data="noop:year"),
                InlineKeyboardButton(text="▶️", callback_data="picky:next"),
            ],
            [
                InlineKeyboardButton(text="Назад", callback_data="pick:back_deadline"),
                InlineKeyboardButton(text="Далее", callback_data="picky:ok"),
            ],
            [InlineKeyboardButton(text="Отмена", callback_data="pick:cancel")],
        ]
    )


def month_picker_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text="01", callback_data="pickm:1"),
            InlineKeyboardButton(text="02", callback_data="pickm:2"),
            InlineKeyboardButton(text="03", callback_data="pickm:3"),
            InlineKeyboardButton(text="04", callback_data="pickm:4"),
        ],
        [
            InlineKeyboardButton(text="05", callback_data="pickm:5"),
            InlineKeyboardButton(text="06", callback_data="pickm:6"),
            InlineKeyboardButton(text="07", callback_data="pickm:7"),
            InlineKeyboardButton(text="08", callback_data="pickm:8"),
        ],
        [
            InlineKeyboardButton(text="09", callback_data="pickm:9"),
            InlineKeyboardButton(text="10", callback_data="pickm:10"),
            InlineKeyboardButton(text="11", callback_data="pickm:11"),
            InlineKeyboardButton(text="12", callback_data="pickm:12"),
        ],
        [
            InlineKeyboardButton(text="Назад", callback_data="pick:back_year"),
            InlineKeyboardButton(text="Отмена", callback_data="pick:cancel"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def day_picker_keyboard(days_in_month: int) -> InlineKeyboardMarkup:
    rows = []
    current_row = []
    for day in range(1, days_in_month + 1):
        current_row.append(
            InlineKeyboardButton(text=str(day), callback_data=f"pickd:{day}")
        )
        if len(current_row) == 7:
            rows.append(current_row)
            current_row = []
    if current_row:
        rows.append(current_row)
    rows.append(
        [
            InlineKeyboardButton(text="Назад", callback_data="pick:back_month"),
            InlineKeyboardButton(text="Отмена", callback_data="pick:cancel"),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _shift_month(year: int, month: int, delta: int) -> Tuple[int, int]:
    month_index = (year * 12 + month - 1) + delta
    return month_index // 12, month_index % 12 + 1


def calendar_month_keyboard(
    year: int,
    month: int,
    day_markers: Dict[int, str],
    today_day: Optional[int] = None,
) -> InlineKeyboardMarkup:
    month_key = f"{year:04d}-{month:02d}"
    prev_year, prev_month = _shift_month(year, month, -1)
    next_year, next_month = _shift_month(year, month, 1)
    prev_key = f"{prev_year:04d}-{prev_month:02d}"
    next_key = f"{next_year:04d}-{next_month:02d}"

    rows = [
        [
            InlineKeyboardButton(text="◀️", callback_data=f"cal:prev:{month_key}"),
            InlineKeyboardButton(text="Сегодня", callback_data="cal:today"),
            InlineKeyboardButton(text="▶️", callback_data=f"cal:next:{month_key}"),
        ],
        [
            InlineKeyboardButton(text="Пн", callback_data="noop:cal"),
            InlineKeyboardButton(text="Вт", callback_data="noop:cal"),
            InlineKeyboardButton(text="Ср", callback_data="noop:cal"),
            InlineKeyboardButton(text="Чт", callback_data="noop:cal"),
            InlineKeyboardButton(text="Пт", callback_data="noop:cal"),
            InlineKeyboardButton(text="Сб", callback_data="noop:cal"),
            InlineKeyboardButton(text="Вс", callback_data="noop:cal"),
        ],
    ]

    for week in calendar.monthcalendar(year, month):
        row = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(text="·", callback_data="noop:cal"))
                continue

            marker = day_markers.get(day, "")
            is_today = today_day == day
            if is_today and marker:
                text = f"📍{marker}{day}"
            elif is_today:
                text = f"📍{day}"
            elif marker:
                text = f"{marker}{day}"
            else:
                text = str(day)
            iso_date = f"{year:04d}-{month:02d}-{day:02d}"
            row.append(InlineKeyboardButton(text=text, callback_data=f"cal:day:{iso_date}"))
        rows.append(row)

    return InlineKeyboardMarkup(inline_keyboard=rows)


def calendar_day_keyboard(month_key: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ К месяцу", callback_data=f"cal:back:{month_key}")]
        ]
    )


def tasks_inline_keyboard(
    tasks: Sequence[sqlite3.Row],
) -> Optional[InlineKeyboardMarkup]:
    if not tasks:
        return None

    active_tasks, done_tasks = split_tasks_for_display(tasks)
    inline_rows = []
    if active_tasks:
        inline_rows.append(
            [InlineKeyboardButton(text="Активные задачи", callback_data="noop:active")]
        )
        for task in active_tasks:
            short_title = _short_task_title(task["title"])
            inline_rows.append(
                [
                    InlineKeyboardButton(
                        text=f"📂 Открыть: {short_title}",
                        callback_data=f"open:{task['id']}",
                    ),
                ]
            )

    if done_tasks:
        inline_rows.append(
            [InlineKeyboardButton(text="Выполненные задачи", callback_data="noop:done")]
        )
        for task in done_tasks:
            short_title = _short_task_title(task["title"])
            inline_rows.append(
                [
                    InlineKeyboardButton(
                        text=f"📂 Открыть: {short_title}",
                        callback_data=f"open:{task['id']}",
                    ),
                ]
            )

    return InlineKeyboardMarkup(inline_keyboard=inline_rows)


def task_card_inline_keyboard(task: sqlite3.Row) -> InlineKeyboardMarkup:
    done_text = "✅ Выполнено" if task["is_done"] else "✅ Выполнить"
    task_id = task["id"]
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=done_text, callback_data=f"done:{task_id}"),
                InlineKeyboardButton(text="🗑 Удалить", callback_data=f"delete:{task_id}"),
            ],
            [InlineKeyboardButton(text="⬅️ Назад к списку", callback_data="back_tasks")],
        ]
    )
