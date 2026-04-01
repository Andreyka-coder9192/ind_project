import calendar
from datetime import date
from html import escape
from typing import Dict, Optional, Tuple

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from database import Database
from keyboards import (
    ADD_TASK_BUTTON,
    BACK_BUTTON,
    CALENDAR_BUTTON,
    CANCEL_BUTTON,
    DEADLINE_MANUAL_BUTTON,
    DEADLINE_PICK_BUTTON,
    DEADLINE_TODAY_BUTTON,
    DEADLINE_TOMORROW_BUTTON,
    HELP_BUTTON,
    MY_TASKS_BUTTON,
    PRIORITY_BUTTON_TO_VALUE,
    SETTINGS_BUTTON,
    calendar_day_keyboard,
    calendar_month_keyboard,
    cancel_keyboard,
    day_picker_keyboard,
    deadline_mode_keyboard,
    main_keyboard,
    month_picker_keyboard,
    priority_keyboard,
    settings_date_inline_keyboard,
    settings_main_inline_keyboard,
    settings_reminder_inline_keyboard,
    task_card_inline_keyboard,
    tasks_inline_keyboard,
    year_picker_keyboard,
)
from utils import (
    DATE_FORMAT_LABELS,
    PRIORITY_LABELS,
    REMINDER_MODE_LABELS,
    STATUS_ACTIVE,
    STATUS_DONE,
    deadline_today_iso,
    deadline_tomorrow_iso,
    format_date_for_user,
    format_task_card,
    format_tasks,
    parse_deadline,
    parse_task_id,
    split_tasks_for_display,
)


HELP_TEXT = (
    "🤖 <b>Мой Дедлайн — помощник по дедлайнам</b>\n\n"
    "Я помогаю хранить учебные задачи и не пропускать сроки.\n\n"
    "<b>Что я умею:</b>\n"
    "• ➕ добавлять задачи с дедлайном\n"
    "• 🔴🟡🟢 задавать важность (приоритет)\n"
    "• 📋 показывать активные и выполненные задачи\n"
    "• 📅 открывать календарь задач по дням\n"
    "• 🔔 напоминать о дедлайнах\n"
    "• ⚙️ менять формат даты и режим напоминаний\n\n"
    "<b>Как пользоваться:</b>\n"
    "• нажмите <b>«Добавить задачу»</b> и пройдите шаги\n"
    "• откройте <b>«Мои задачи»</b>, чтобы увидеть список и карточки\n"
    "• используйте <b>«Календарь»</b>, чтобы смотреть задачи по датам\n"
    "• зайдите в <b>«Настройки»</b>, чтобы настроить даты и напоминания\n\n"
    "<b>Во время добавления задачи:</b>\n"
    "• <b>Назад</b> — вернуться на предыдущий шаг\n"
    "• <b>Отмена</b> — полностью отменить ввод"
)

HELP_TEXT_SHORT = (
    "🤖 <b>Мой Дедлайн</b>\n"
    "Задачи, дедлайны, календарь, напоминания и настройки — через кнопки меню.\n"
    "Во время добавления: <b>Назад</b> и <b>Отмена</b>."
)

MONTH_NAMES_RU = [
    "Январь",
    "Февраль",
    "Март",
    "Апрель",
    "Май",
    "Июнь",
    "Июль",
    "Август",
    "Сентябрь",
    "Октябрь",
    "Ноябрь",
    "Декабрь",
]

FORMAT_CALLBACK_TO_VALUE = {
    "setfmt:dot": "dd.mm.yyyy",
    "setfmt:slash": "dd/mm/yyyy",
    "setfmt:iso": "yyyy-mm-dd",
}
REMINDER_CALLBACK_TO_VALUE = {
    "setrem:off": "off",
    "setrem:today": "due_today",
    "setrem:before": "day_before",
    "setrem:both": "both",
}


class AddTaskState(StatesGroup):
    waiting_title = State()
    waiting_priority = State()
    waiting_deadline_mode = State()
    waiting_manual_deadline = State()
    waiting_picker_year = State()
    waiting_picker_month = State()
    waiting_picker_day = State()


def create_router(db: Database) -> Router:
    router = Router()
    add_states = {
        AddTaskState.waiting_title.state,
        AddTaskState.waiting_priority.state,
        AddTaskState.waiting_deadline_mode.state,
        AddTaskState.waiting_manual_deadline.state,
        AddTaskState.waiting_picker_year.state,
        AddTaskState.waiting_picker_month.state,
        AddTaskState.waiting_picker_day.state,
    }

    async def clear_add_state_if_needed(state: FSMContext) -> bool:
        current_state = await state.get_state()
        if current_state in add_states:
            await state.clear()
            return True
        return False

    async def restore_main_menu_after_add_exit(message: Message) -> None:
        await message.answer(
            "Добавление задачи прервано.",
            reply_markup=main_keyboard(),
        )

    async def show_start(message: Message) -> None:
        await message.answer(
            "Привет! Я помогу не забывать про задания и дедлайны.",
            reply_markup=main_keyboard(),
        )

    async def show_help(message: Message) -> None:
        await message.answer(
            HELP_TEXT,
            reply_markup=main_keyboard(),
            parse_mode="HTML",
        )

    async def render_settings_screen(
        message: Message,
        text: str,
        keyboard,
        edit: bool = False,
    ) -> None:
        if edit:
            try:
                await message.edit_text(
                    text,
                    reply_markup=keyboard,
                    parse_mode="HTML",
                )
                return
            except TelegramBadRequest as error:
                if "message is not modified" in str(error).lower():
                    return
                pass

        await message.answer(
            text,
            reply_markup=keyboard,
            parse_mode="HTML",
        )

    async def show_settings_main(message: Message, user_id: int, edit: bool = False) -> None:
        current_format = db.get_user_date_format(user_id)
        current_reminder_mode = db.get_user_reminder_mode(user_id)
        current_format_label = DATE_FORMAT_LABELS.get(current_format, current_format)
        current_reminder_label = REMINDER_MODE_LABELS.get(
            current_reminder_mode,
            "За 1 день и в день дедлайна",
        )
        text = (
            "<b>⚙️ Настройки</b>\n\n"
            f"Текущий формат даты: <code>{current_format_label}</code>\n"
            f"Текущий режим напоминаний: <b>{current_reminder_label}</b>"
        )
        inline_keyboard = settings_main_inline_keyboard()
        await render_settings_screen(message, text, inline_keyboard, edit=edit)

    async def show_settings_date(message: Message, user_id: int, edit: bool = False) -> None:
        current_format = db.get_user_date_format(user_id)
        current_format_label = DATE_FORMAT_LABELS.get(current_format, current_format)
        text = (
            "<b>📅 Формат даты</b>\n\n"
            f"Текущий формат: <code>{current_format_label}</code>\n\n"
            "Выберите формат отображения:"
        )
        inline_keyboard = settings_date_inline_keyboard(current_format)
        await render_settings_screen(message, text, inline_keyboard, edit=edit)

    async def show_settings_reminders(
        message: Message,
        user_id: int,
        edit: bool = False,
    ) -> None:
        current_reminder_mode = db.get_user_reminder_mode(user_id)
        current_reminder_label = REMINDER_MODE_LABELS.get(
            current_reminder_mode,
            "За 1 день и в день дедлайна",
        )
        text = (
            "<b>🔔 Напоминания</b>\n\n"
            f"Текущий режим: <b>{current_reminder_label}</b>\n\n"
            "Выберите режим напоминаний:"
        )
        inline_keyboard = settings_reminder_inline_keyboard(current_reminder_mode)
        await render_settings_screen(message, text, inline_keyboard, edit=edit)

    async def close_settings(message: Message, edit: bool = False) -> None:
        _ = edit
        try:
            await message.delete()
            return
        except TelegramBadRequest:
            pass

        try:
            await message.edit_reply_markup(reply_markup=None)
        except TelegramBadRequest:
            pass

    async def send_tasks(message: Message, user_id: int, edit: bool = False) -> None:
        tasks = db.get_tasks(user_id)
        user_date_format = db.get_user_date_format(user_id)
        tasks_text = format_tasks(tasks, user_date_format)
        inline_keyboard = tasks_inline_keyboard(tasks)

        if edit:
            try:
                await message.edit_text(
                    tasks_text,
                    reply_markup=inline_keyboard,
                    parse_mode="HTML",
                )
                return
            except TelegramBadRequest as error:
                if "message is not modified" in str(error).lower():
                    return
                pass

        await message.answer(
            tasks_text,
            reply_markup=inline_keyboard,
            parse_mode="HTML",
        )

    async def send_task_card(
        message: Message, user_id: int, task_id: int, edit: bool = False
    ) -> bool:
        task = db.get_task(user_id, task_id)
        if task is None:
            return False

        user_date_format = db.get_user_date_format(user_id)
        card_text = format_task_card(task, user_date_format)
        inline_keyboard = task_card_inline_keyboard(task)
        if edit:
            try:
                await message.edit_text(
                    card_text,
                    reply_markup=inline_keyboard,
                    parse_mode="HTML",
                )
                return True
            except TelegramBadRequest as error:
                if "message is not modified" in str(error).lower():
                    return True
                pass

        await message.answer(
            card_text,
            reply_markup=inline_keyboard,
            parse_mode="HTML",
        )
        return True

    def parse_task_id_from_callback(callback_data: str) -> Optional[int]:
        raw_task_id = callback_data.split(":", 1)[1] if ":" in callback_data else ""
        return parse_task_id(raw_task_id)

    def parse_month_key(month_key: str) -> Optional[Tuple[int, int]]:
        parts = month_key.split("-")
        if len(parts) != 2:
            return None
        try:
            year = int(parts[0])
            month = int(parts[1])
        except ValueError:
            return None
        if month < 1 or month > 12:
            return None
        return year, month

    def shift_month(year: int, month: int, delta: int) -> Tuple[int, int]:
        month_index = (year * 12 + month - 1) + delta
        return month_index // 12, month_index % 12 + 1

    def build_month_markers(
        tasks: list,
        year: int,
        month: int,
    ) -> Dict[int, str]:
        month_prefix = f"{year:04d}-{month:02d}-"
        rank_map = {"important": 0, "normal": 1, "low": 2}
        icon_map = {0: "🔴", 1: "🟡", 2: "🟢"}
        best_rank_by_day: Dict[int, int] = {}

        for task in tasks:
            if task["is_done"]:
                continue
            deadline_iso = str(task["deadline"])
            if not deadline_iso.startswith(month_prefix):
                continue
            parsed_deadline = parse_deadline(deadline_iso)
            if parsed_deadline is None:
                continue
            if parsed_deadline.year != year or parsed_deadline.month != month:
                continue

            day = parsed_deadline.day
            rank = rank_map.get(task["priority"], 1)
            if day not in best_rank_by_day or rank < best_rank_by_day[day]:
                best_rank_by_day[day] = rank

        return {day: icon_map[rank] for day, rank in best_rank_by_day.items()}

    async def send_calendar_month(
        message: Message,
        user_id: int,
        year: int,
        month: int,
        edit: bool = False,
    ) -> None:
        tasks = db.get_tasks(user_id)
        markers = build_month_markers(tasks, year, month)
        month_name = MONTH_NAMES_RU[month - 1]
        today = date.today()
        today_day = today.day if today.year == year and today.month == month else None
        text = (
            "<b>🗓 Календарь задач</b>\n"
            f"<b>{month_name} {year}</b>\n\n"
            "Выберите день:"
        )
        keyboard = calendar_month_keyboard(year, month, markers, today_day=today_day)

        if edit:
            try:
                await message.edit_text(
                    text,
                    reply_markup=keyboard,
                    parse_mode="HTML",
                )
                return
            except TelegramBadRequest as error:
                if "message is not modified" in str(error).lower():
                    return
                pass

        await message.answer(
            text,
            reply_markup=keyboard,
            parse_mode="HTML",
        )

    async def send_calendar_day(
        message: Message,
        user_id: int,
        iso_date: str,
        edit: bool = False,
    ) -> None:
        tasks = db.get_tasks(user_id)
        day_tasks = [task for task in tasks if task["deadline"] == iso_date]
        user_date_format = db.get_user_date_format(user_id)
        date_label = format_date_for_user(iso_date, user_date_format)
        month_key = iso_date[:7]

        lines = [f"<b>📅 Задачи на {date_label}</b>"]
        if not day_tasks:
            lines.append("На эту дату задач нет.")
        else:
            active_tasks, done_tasks = split_tasks_for_display(day_tasks)
            ordered_tasks = active_tasks + done_tasks
            for task in ordered_tasks:
                status = STATUS_DONE if task["is_done"] else STATUS_ACTIVE
                priority_label = PRIORITY_LABELS.get(task["priority"], "🟡 Обычное")
                safe_title = escape(str(task["title"]))
                lines.append(
                    f"#{task['id']} — <b>{safe_title}</b>\n"
                    f"{priority_label} | {status}"
                )

        text = "\n\n".join(lines)
        keyboard = calendar_day_keyboard(month_key)

        if edit:
            try:
                await message.edit_text(
                    text,
                    reply_markup=keyboard,
                    parse_mode="HTML",
                )
                return
            except TelegramBadRequest as error:
                if "message is not modified" in str(error).lower():
                    return
                pass

        await message.answer(
            text,
            reply_markup=keyboard,
            parse_mode="HTML",
        )

    async def show_tasks(message: Message) -> None:
        if message.from_user is None:
            return
        await send_tasks(message, message.from_user.id, edit=False)

    async def start_add_flow(message: Message, state: FSMContext) -> None:
        await state.set_state(AddTaskState.waiting_title)
        await message.answer("Введите название задания:", reply_markup=cancel_keyboard())

    async def ask_deadline_mode(message: Message, state: FSMContext) -> None:
        await state.set_state(AddTaskState.waiting_deadline_mode)
        await message.answer(
            "Как указать дедлайн?",
            reply_markup=deadline_mode_keyboard(),
        )

    async def cancel_add_flow(message: Message, state: FSMContext) -> None:
        await state.clear()
        await message.answer("Добавление задачи отменено.", reply_markup=main_keyboard())

    async def save_task_from_state(
        user_id: int,
        message: Message,
        state: FSMContext,
        deadline_iso: str,
    ) -> bool:
        data = await state.get_data()
        title = data.get("title")
        priority = data.get("priority", "normal")
        if not title:
            await state.clear()
            await message.answer("Ошибка: название задания не найдено. Введите /add снова.")
            return False

        task_id = db.add_task(user_id, title, priority, deadline_iso)
        user_date_format = db.get_user_date_format(user_id)
        deadline_text = format_date_for_user(deadline_iso, user_date_format)
        priority_label = PRIORITY_LABELS.get(priority, "🟡 Обычное")
        safe_title = escape(str(title))
        await state.clear()
        await message.answer(
            "<b>✅ Задание добавлено</b>\n\n"
            f"<b>ID:</b> #{task_id}\n"
            f"<b>Название:</b> {safe_title}\n"
            f"<b>Приоритет:</b> {priority_label}\n"
            f"<b>Дедлайн:</b> <code>{deadline_text}</code>",
            reply_markup=main_keyboard(),
            parse_mode="HTML",
        )
        return True

    async def show_year_picker(message: Message, year: int, edit: bool = False) -> None:
        text = f"Выбор даты: шаг 1/3\nГод: {year}"
        keyboard = year_picker_keyboard(year)
        if edit:
            try:
                await message.edit_text(text, reply_markup=keyboard)
                return
            except TelegramBadRequest as error:
                if "message is not modified" in str(error).lower():
                    return
                pass
        await message.answer(text, reply_markup=keyboard)

    async def show_month_picker(message: Message, year: int, edit: bool = True) -> None:
        text = f"Выбор даты: шаг 2/3\nГод: {year}\nВыберите месяц:"
        keyboard = month_picker_keyboard()
        if edit:
            try:
                await message.edit_text(text, reply_markup=keyboard)
                return
            except TelegramBadRequest as error:
                if "message is not modified" in str(error).lower():
                    return
                pass
        await message.answer(text, reply_markup=keyboard)

    async def show_day_picker(
        message: Message,
        year: int,
        month: int,
        edit: bool = True,
    ) -> None:
        days_in_month = calendar.monthrange(year, month)[1]
        text = f"Выбор даты: шаг 3/3\n{month:02d}.{year}\nВыберите день:"
        keyboard = day_picker_keyboard(days_in_month)
        if edit:
            try:
                await message.edit_text(text, reply_markup=keyboard)
                return
            except TelegramBadRequest as error:
                if "message is not modified" in str(error).lower():
                    return
                pass
        await message.answer(text, reply_markup=keyboard)

    @router.message(Command("start"))
    async def cmd_start(message: Message, state: FSMContext) -> None:
        await clear_add_state_if_needed(state)
        await show_start(message)

    @router.message(Command("help"))
    async def cmd_help(message: Message, state: FSMContext) -> None:
        await clear_add_state_if_needed(state)
        await show_help(message)

    @router.message(Command("calendar"))
    async def cmd_calendar(message: Message, state: FSMContext) -> None:
        was_in_add_flow = await clear_add_state_if_needed(state)
        if was_in_add_flow:
            await restore_main_menu_after_add_exit(message)
        if message.from_user is None:
            return
        today = date.today()
        await send_calendar_month(
            message,
            message.from_user.id,
            today.year,
            today.month,
            edit=False,
        )

    @router.message(Command("settings"))
    async def cmd_settings(message: Message, state: FSMContext) -> None:
        was_in_add_flow = await clear_add_state_if_needed(state)
        if was_in_add_flow:
            await restore_main_menu_after_add_exit(message)
        if message.from_user is None:
            return
        await show_settings_main(message, message.from_user.id)

    @router.message(Command("add"))
    async def cmd_add(message: Message, state: FSMContext) -> None:
        await clear_add_state_if_needed(state)
        await start_add_flow(message, state)

    @router.message(Command("tasks"))
    async def cmd_tasks(message: Message, state: FSMContext) -> None:
        was_in_add_flow = await clear_add_state_if_needed(state)
        if was_in_add_flow:
            await restore_main_menu_after_add_exit(message)
        await show_tasks(message)

    @router.message(Command("done"))
    async def cmd_done(
        message: Message, state: FSMContext, command: CommandObject
    ) -> None:
        await clear_add_state_if_needed(state)
        if message.from_user is None:
            return
        if not command.args:
            await message.answer("Использование: /done <id>")
            return

        task_id = parse_task_id(command.args)
        if task_id is None:
            await message.answer("ID должен быть положительным числом. Пример: /done 3")
            return

        updated = db.mark_task_done(message.from_user.id, task_id)
        if updated:
            await message.answer(
                f"Задание #{task_id} отмечено как выполненное.",
                reply_markup=main_keyboard(),
            )
        else:
            await message.answer(
                "Задание не найдено или уже выполнено.",
                reply_markup=main_keyboard(),
            )

    @router.message(Command("delete"))
    async def cmd_delete(
        message: Message, state: FSMContext, command: CommandObject
    ) -> None:
        await clear_add_state_if_needed(state)
        if message.from_user is None:
            return
        if not command.args:
            await message.answer("Использование: /delete <id>")
            return

        task_id = parse_task_id(command.args)
        if task_id is None:
            await message.answer("ID должен быть положительным числом. Пример: /delete 3")
            return

        deleted = db.delete_task(message.from_user.id, task_id)
        if deleted:
            await message.answer(f"Задание #{task_id} удалено.", reply_markup=main_keyboard())
        else:
            await message.answer(
                "Задание с таким ID не найдено.",
                reply_markup=main_keyboard(),
            )

    @router.message(Command("cancel"))
    async def cmd_cancel(message: Message, state: FSMContext) -> None:
        await cancel_add_flow(message, state)

    @router.callback_query(F.data.startswith("noop:"))
    async def noop_inline(callback: CallbackQuery) -> None:
        await callback.answer()

    @router.callback_query(F.data == "settings:main")
    async def settings_main_inline(callback: CallbackQuery) -> None:
        if callback.from_user is None:
            await callback.answer("Не удалось определить пользователя.", show_alert=True)
            return
        if not isinstance(callback.message, Message):
            await callback.answer()
            return

        await show_settings_main(callback.message, callback.from_user.id, edit=True)
        await callback.answer()

    @router.callback_query(F.data == "settings:date")
    async def settings_date_inline(callback: CallbackQuery) -> None:
        if callback.from_user is None:
            await callback.answer("Не удалось определить пользователя.", show_alert=True)
            return
        if not isinstance(callback.message, Message):
            await callback.answer()
            return

        await show_settings_date(callback.message, callback.from_user.id, edit=True)
        await callback.answer()

    @router.callback_query(F.data == "settings:rem")
    async def settings_reminders_inline(callback: CallbackQuery) -> None:
        if callback.from_user is None:
            await callback.answer("Не удалось определить пользователя.", show_alert=True)
            return
        if not isinstance(callback.message, Message):
            await callback.answer()
            return

        await show_settings_reminders(
            callback.message,
            callback.from_user.id,
            edit=True,
        )
        await callback.answer()

    @router.callback_query(F.data == "settings:close")
    async def settings_close_inline(callback: CallbackQuery) -> None:
        if not isinstance(callback.message, Message):
            await callback.answer()
            return

        await close_settings(callback.message, edit=True)
        await callback.answer()

    @router.callback_query(F.data.startswith("setfmt:"))
    async def set_date_format_inline(callback: CallbackQuery) -> None:
        if callback.from_user is None:
            await callback.answer("Не удалось определить пользователя.", show_alert=True)
            return

        callback_data = callback.data or ""
        selected_format = FORMAT_CALLBACK_TO_VALUE.get(callback_data)
        if selected_format is None:
            await callback.answer("Некорректный формат.", show_alert=True)
            return

        try:
            db.set_user_date_format(callback.from_user.id, selected_format)
        except ValueError:
            await callback.answer("Некорректный формат.", show_alert=True)
            return

        await callback.answer("Формат даты обновлен.")
        if isinstance(callback.message, Message):
            await show_settings_date(callback.message, callback.from_user.id, edit=True)

    @router.callback_query(F.data.startswith("setrem:"))
    async def set_reminder_mode_inline(callback: CallbackQuery) -> None:
        if callback.from_user is None:
            await callback.answer("Не удалось определить пользователя.", show_alert=True)
            return

        callback_data = callback.data or ""
        selected_mode = REMINDER_CALLBACK_TO_VALUE.get(callback_data)
        if selected_mode is None:
            await callback.answer("Некорректный режим.", show_alert=True)
            return

        try:
            db.set_user_reminder_mode(callback.from_user.id, selected_mode)
        except ValueError:
            await callback.answer("Некорректный режим.", show_alert=True)
            return

        await callback.answer("Режим напоминаний обновлен.")
        if isinstance(callback.message, Message):
            await show_settings_reminders(
                callback.message,
                callback.from_user.id,
                edit=True,
            )

    @router.callback_query(F.data == "cal:today")
    async def calendar_today_inline(callback: CallbackQuery) -> None:
        if callback.from_user is None:
            await callback.answer("Не удалось определить пользователя.", show_alert=True)
            return
        if not isinstance(callback.message, Message):
            await callback.answer()
            return

        today = date.today()
        await send_calendar_month(
            callback.message,
            callback.from_user.id,
            today.year,
            today.month,
            edit=True,
        )
        await callback.answer()

    @router.callback_query(F.data.startswith("cal:prev:"))
    async def calendar_prev_inline(callback: CallbackQuery) -> None:
        if callback.from_user is None:
            await callback.answer("Не удалось определить пользователя.", show_alert=True)
            return
        if not isinstance(callback.message, Message):
            await callback.answer()
            return

        parts = (callback.data or "").split(":", 2)
        if len(parts) < 3:
            await callback.answer("Некорректный месяц.", show_alert=True)
            return
        month_key = parts[2]
        parsed = parse_month_key(month_key)
        if parsed is None:
            await callback.answer("Некорректный месяц.", show_alert=True)
            return

        year, month = parsed
        prev_year, prev_month = shift_month(year, month, -1)
        await send_calendar_month(
            callback.message,
            callback.from_user.id,
            prev_year,
            prev_month,
            edit=True,
        )
        await callback.answer()

    @router.callback_query(F.data.startswith("cal:next:"))
    async def calendar_next_inline(callback: CallbackQuery) -> None:
        if callback.from_user is None:
            await callback.answer("Не удалось определить пользователя.", show_alert=True)
            return
        if not isinstance(callback.message, Message):
            await callback.answer()
            return

        parts = (callback.data or "").split(":", 2)
        if len(parts) < 3:
            await callback.answer("Некорректный месяц.", show_alert=True)
            return
        month_key = parts[2]
        parsed = parse_month_key(month_key)
        if parsed is None:
            await callback.answer("Некорректный месяц.", show_alert=True)
            return

        year, month = parsed
        next_year, next_month = shift_month(year, month, 1)
        await send_calendar_month(
            callback.message,
            callback.from_user.id,
            next_year,
            next_month,
            edit=True,
        )
        await callback.answer()

    @router.callback_query(F.data.startswith("cal:day:"))
    async def calendar_day_inline(callback: CallbackQuery) -> None:
        if callback.from_user is None:
            await callback.answer("Не удалось определить пользователя.", show_alert=True)
            return
        if not isinstance(callback.message, Message):
            await callback.answer()
            return

        parts = (callback.data or "").split(":", 2)
        if len(parts) < 3:
            await callback.answer("Некорректная дата.", show_alert=True)
            return
        iso_date = parts[2]
        if parse_deadline(iso_date) is None:
            await callback.answer("Некорректная дата.", show_alert=True)
            return

        await send_calendar_day(
            callback.message,
            callback.from_user.id,
            iso_date,
            edit=True,
        )
        await callback.answer()

    @router.callback_query(F.data.startswith("cal:back:"))
    async def calendar_back_inline(callback: CallbackQuery) -> None:
        if callback.from_user is None:
            await callback.answer("Не удалось определить пользователя.", show_alert=True)
            return
        if not isinstance(callback.message, Message):
            await callback.answer()
            return

        parts = (callback.data or "").split(":", 2)
        if len(parts) < 3:
            await callback.answer("Некорректный месяц.", show_alert=True)
            return
        month_key = parts[2]
        parsed = parse_month_key(month_key)
        if parsed is None:
            await callback.answer("Некорректный месяц.", show_alert=True)
            return

        year, month = parsed
        await send_calendar_month(
            callback.message,
            callback.from_user.id,
            year,
            month,
            edit=True,
        )
        await callback.answer()

    @router.callback_query(F.data.startswith("open:"))
    async def open_task_inline(callback: CallbackQuery) -> None:
        if callback.from_user is None:
            await callback.answer("Не удалось определить пользователя.", show_alert=True)
            return

        callback_data = callback.data or ""
        task_id = parse_task_id_from_callback(callback_data)
        if task_id is None:
            await callback.answer("Некорректный ID задачи.", show_alert=True)
            return

        if not isinstance(callback.message, Message):
            await callback.answer()
            return

        showed = await send_task_card(
            callback.message,
            callback.from_user.id,
            task_id,
            edit=True,
        )
        if not showed:
            await callback.answer("Задача не найдена.", show_alert=True)
            return

        await callback.answer()

    @router.callback_query(F.data == "back_tasks")
    async def back_to_tasks_inline(callback: CallbackQuery) -> None:
        if callback.from_user is None:
            await callback.answer("Не удалось определить пользователя.", show_alert=True)
            return

        if not isinstance(callback.message, Message):
            await callback.answer()
            return

        await send_tasks(callback.message, callback.from_user.id, edit=True)
        await callback.answer()

    @router.callback_query(F.data.startswith("done:"))
    async def done_inline(callback: CallbackQuery) -> None:
        if callback.from_user is None:
            await callback.answer("Не удалось определить пользователя.", show_alert=True)
            return

        callback_data = callback.data or ""
        task_id = parse_task_id_from_callback(callback_data)
        if task_id is None:
            await callback.answer("Некорректный ID задачи.", show_alert=True)
            return

        task = db.get_task(callback.from_user.id, task_id)
        if task is None:
            await callback.answer("Задача не найдена.", show_alert=True)
            return

        if task["is_done"]:
            await callback.answer("Задача уже выполнена.")
        else:
            db.mark_task_done(callback.from_user.id, task_id)
            await callback.answer("Задача отмечена как выполненная.")

        if isinstance(callback.message, Message):
            await send_task_card(
                callback.message,
                callback.from_user.id,
                task_id,
                edit=True,
            )

    @router.callback_query(F.data.startswith("delete:"))
    async def delete_inline(callback: CallbackQuery) -> None:
        if callback.from_user is None:
            await callback.answer("Не удалось определить пользователя.", show_alert=True)
            return

        callback_data = callback.data or ""
        task_id = parse_task_id_from_callback(callback_data)
        if task_id is None:
            await callback.answer("Некорректный ID задачи.", show_alert=True)
            return

        deleted = db.delete_task(callback.from_user.id, task_id)
        if not deleted:
            await callback.answer("Задача с таким ID не найдена.", show_alert=True)
            return

        await callback.answer("Задача удалена.")
        if isinstance(callback.message, Message):
            await send_tasks(callback.message, callback.from_user.id, edit=True)

    @router.callback_query(F.data == "pick:cancel")
    async def pick_cancel_inline(callback: CallbackQuery, state: FSMContext) -> None:
        await state.clear()
        await callback.answer("Добавление отменено.")
        if isinstance(callback.message, Message):
            await callback.message.answer(
                "Добавление задачи отменено.",
                reply_markup=main_keyboard(),
            )

    @router.callback_query(F.data == "pick:back_deadline")
    async def pick_back_to_deadline_mode_inline(
        callback: CallbackQuery,
        state: FSMContext,
    ) -> None:
        current_state = await state.get_state()
        if current_state != AddTaskState.waiting_picker_year.state:
            await callback.answer("Назад сейчас недоступно.", show_alert=True)
            return

        await state.set_state(AddTaskState.waiting_deadline_mode)
        await callback.answer()
        if isinstance(callback.message, Message):
            try:
                await callback.message.edit_reply_markup(reply_markup=None)
            except TelegramBadRequest:
                pass
            await callback.message.answer(
                "Как указать дедлайн?",
                reply_markup=deadline_mode_keyboard(),
            )

    @router.callback_query(F.data == "pick:back_year")
    async def pick_back_to_year_inline(callback: CallbackQuery, state: FSMContext) -> None:
        current_state = await state.get_state()
        if current_state != AddTaskState.waiting_picker_month.state:
            await callback.answer("Назад сейчас недоступно.", show_alert=True)
            return

        if not isinstance(callback.message, Message):
            await callback.answer()
            return

        data = await state.get_data()
        year = int(data.get("picker_year", date.today().year))
        await state.set_state(AddTaskState.waiting_picker_year)
        await show_year_picker(callback.message, year, edit=True)
        await callback.answer()

    @router.callback_query(F.data == "pick:back_month")
    async def pick_back_to_month_inline(callback: CallbackQuery, state: FSMContext) -> None:
        current_state = await state.get_state()
        if current_state != AddTaskState.waiting_picker_day.state:
            await callback.answer("Назад сейчас недоступно.", show_alert=True)
            return

        if not isinstance(callback.message, Message):
            await callback.answer()
            return

        data = await state.get_data()
        year = int(data.get("picker_year", date.today().year))
        await state.set_state(AddTaskState.waiting_picker_month)
        await show_month_picker(callback.message, year, edit=True)
        await callback.answer()

    @router.callback_query(F.data.startswith("picky:"))
    async def pick_year_inline(callback: CallbackQuery, state: FSMContext) -> None:
        current_state = await state.get_state()
        if current_state != AddTaskState.waiting_picker_year.state:
            await callback.answer("Выбор года сейчас недоступен.", show_alert=True)
            return

        if not isinstance(callback.message, Message):
            await callback.answer()
            return

        data = await state.get_data()
        year = int(data.get("picker_year", date.today().year))
        action = (callback.data or "").split(":", 1)[1]

        if action == "prev":
            year -= 1
            await state.update_data(picker_year=year)
            await show_year_picker(callback.message, year, edit=True)
            await callback.answer()
            return

        if action == "next":
            year += 1
            await state.update_data(picker_year=year)
            await show_year_picker(callback.message, year, edit=True)
            await callback.answer()
            return

        if action == "ok":
            await state.set_state(AddTaskState.waiting_picker_month)
            await show_month_picker(callback.message, year)
            await callback.answer()
            return

        await callback.answer("Некорректное действие.", show_alert=True)

    @router.callback_query(F.data.startswith("pickm:"))
    async def pick_month_inline(callback: CallbackQuery, state: FSMContext) -> None:
        current_state = await state.get_state()
        if current_state != AddTaskState.waiting_picker_month.state:
            await callback.answer("Выбор месяца сейчас недоступен.", show_alert=True)
            return

        if not isinstance(callback.message, Message):
            await callback.answer()
            return

        raw_month = (callback.data or "").split(":", 1)[1]
        try:
            month = int(raw_month)
        except ValueError:
            await callback.answer("Некорректный месяц.", show_alert=True)
            return

        if month < 1 or month > 12:
            await callback.answer("Некорректный месяц.", show_alert=True)
            return

        data = await state.get_data()
        year = int(data.get("picker_year", date.today().year))
        await state.update_data(picker_month=month)
        await state.set_state(AddTaskState.waiting_picker_day)
        await show_day_picker(callback.message, year, month)
        await callback.answer()

    @router.callback_query(F.data.startswith("pickd:"))
    async def pick_day_inline(callback: CallbackQuery, state: FSMContext) -> None:
        current_state = await state.get_state()
        if current_state != AddTaskState.waiting_picker_day.state:
            await callback.answer("Выбор дня сейчас недоступен.", show_alert=True)
            return

        if callback.from_user is None:
            await callback.answer("Не удалось определить пользователя.", show_alert=True)
            return

        if not isinstance(callback.message, Message):
            await callback.answer()
            return

        raw_day = (callback.data or "").split(":", 1)[1]
        try:
            day = int(raw_day)
        except ValueError:
            await callback.answer("Некорректный день.", show_alert=True)
            return

        data = await state.get_data()
        year = int(data.get("picker_year", date.today().year))
        month = int(data.get("picker_month", 0))
        if month < 1 or month > 12:
            await callback.answer("Сначала выберите месяц.", show_alert=True)
            return

        days_in_month = calendar.monthrange(year, month)[1]
        if day < 1 or day > days_in_month:
            await callback.answer("Некорректный день.", show_alert=True)
            return

        deadline_iso = date(year, month, day).isoformat()
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except TelegramBadRequest:
            pass
        await callback.answer("Дата выбрана.")
        await save_task_from_state(
            callback.from_user.id,
            callback.message,
            state,
            deadline_iso,
        )

    @router.message(F.text == ADD_TASK_BUTTON)
    async def add_button(message: Message, state: FSMContext) -> None:
        await clear_add_state_if_needed(state)
        await start_add_flow(message, state)

    @router.message(F.text == MY_TASKS_BUTTON)
    async def tasks_button(message: Message, state: FSMContext) -> None:
        was_in_add_flow = await clear_add_state_if_needed(state)
        if was_in_add_flow:
            await restore_main_menu_after_add_exit(message)
        await show_tasks(message)

    @router.message(F.text == CALENDAR_BUTTON)
    async def calendar_button(message: Message, state: FSMContext) -> None:
        was_in_add_flow = await clear_add_state_if_needed(state)
        if was_in_add_flow:
            await restore_main_menu_after_add_exit(message)
        if message.from_user is None:
            return
        today = date.today()
        await send_calendar_month(
            message,
            message.from_user.id,
            today.year,
            today.month,
            edit=False,
        )

    @router.message(F.text == HELP_BUTTON)
    async def help_button(message: Message, state: FSMContext) -> None:
        await clear_add_state_if_needed(state)
        await show_help(message)

    @router.message(F.text == SETTINGS_BUTTON)
    async def settings_button(message: Message, state: FSMContext) -> None:
        was_in_add_flow = await clear_add_state_if_needed(state)
        if was_in_add_flow:
            await restore_main_menu_after_add_exit(message)
        if message.from_user is None:
            return
        await show_settings_main(message, message.from_user.id)

    @router.message(F.text == CANCEL_BUTTON)
    async def cancel_button(message: Message, state: FSMContext) -> None:
        await cancel_add_flow(message, state)

    @router.message(F.text == BACK_BUTTON)
    async def back_button(message: Message, state: FSMContext) -> None:
        current_state = await state.get_state()
        if current_state == AddTaskState.waiting_manual_deadline.state:
            await ask_deadline_mode(message, state)
            return

        if current_state == AddTaskState.waiting_deadline_mode.state:
            await state.set_state(AddTaskState.waiting_priority)
            await message.answer(
                "Выберите приоритет задачи:",
                reply_markup=priority_keyboard(),
            )
            return

        if current_state == AddTaskState.waiting_priority.state:
            await state.set_state(AddTaskState.waiting_title)
            await message.answer(
                "Введите название задания:",
                reply_markup=cancel_keyboard(),
            )
            return

        if current_state == AddTaskState.waiting_picker_year.state:
            await ask_deadline_mode(message, state)
            return

        if current_state == AddTaskState.waiting_picker_month.state:
            data = await state.get_data()
            year = int(data.get("picker_year", date.today().year))
            await state.set_state(AddTaskState.waiting_picker_year)
            await show_year_picker(message, year, edit=False)
            return

        if current_state == AddTaskState.waiting_picker_day.state:
            data = await state.get_data()
            year = int(data.get("picker_year", date.today().year))
            await state.set_state(AddTaskState.waiting_picker_month)
            await show_month_picker(message, year, edit=False)
            return

        await message.answer("Сейчас переход назад недоступен.")

    @router.message(AddTaskState.waiting_title, F.text)
    async def add_task_title(message: Message, state: FSMContext) -> None:
        title = message.text.strip()
        if title == BACK_BUTTON:
            await message.answer("Это первый шаг. Используйте «Отмена» для выхода.")
            return
        if not title:
            await message.answer("Название не может быть пустым. Введите еще раз:")
            return

        await state.update_data(title=title)
        await state.set_state(AddTaskState.waiting_priority)
        await message.answer(
            "Выберите приоритет задачи:",
            reply_markup=priority_keyboard(),
        )

    @router.message(AddTaskState.waiting_priority, F.text)
    async def add_task_priority(message: Message, state: FSMContext) -> None:
        if message.text.strip() == BACK_BUTTON:
            await state.set_state(AddTaskState.waiting_title)
            await message.answer(
                "Введите название задания:",
                reply_markup=cancel_keyboard(),
            )
            return

        selected_priority = PRIORITY_BUTTON_TO_VALUE.get(message.text.strip())
        if selected_priority is None:
            await message.answer(
                "Пожалуйста, выберите приоритет кнопкой ниже.",
                reply_markup=priority_keyboard(),
            )
            return

        await state.update_data(priority=selected_priority)
        await ask_deadline_mode(message, state)

    @router.message(AddTaskState.waiting_deadline_mode, F.text)
    async def add_task_deadline_mode(message: Message, state: FSMContext) -> None:
        if message.from_user is None:
            await state.clear()
            return

        selected_mode = message.text.strip()
        if selected_mode == BACK_BUTTON:
            await state.set_state(AddTaskState.waiting_priority)
            await message.answer(
                "Выберите приоритет задачи:",
                reply_markup=priority_keyboard(),
            )
            return

        if selected_mode == DEADLINE_TODAY_BUTTON:
            await save_task_from_state(
                message.from_user.id,
                message,
                state,
                deadline_today_iso(),
            )
            return

        if selected_mode == DEADLINE_TOMORROW_BUTTON:
            await save_task_from_state(
                message.from_user.id,
                message,
                state,
                deadline_tomorrow_iso(),
            )
            return

        if selected_mode == DEADLINE_MANUAL_BUTTON:
            await state.set_state(AddTaskState.waiting_manual_deadline)
            await message.answer(
                "Введите дедлайн в формате YYYY-MM-DD:",
                reply_markup=cancel_keyboard(add_back=True),
            )
            return

        if selected_mode == DEADLINE_PICK_BUTTON:
            data = await state.get_data()
            picker_year = int(data.get("picker_year", date.today().year))
            picker_month = int(data.get("picker_month", 0))
            await state.update_data(picker_year=picker_year, picker_month=picker_month)
            await state.set_state(AddTaskState.waiting_picker_year)
            await show_year_picker(message, picker_year, edit=False)
            return

        if selected_mode == CANCEL_BUTTON:
            await cancel_add_flow(message, state)
            return

        await message.answer(
            "Пожалуйста, выберите вариант кнопкой ниже.",
            reply_markup=deadline_mode_keyboard(),
        )

    @router.message(AddTaskState.waiting_manual_deadline, F.text)
    async def add_task_deadline_manual(message: Message, state: FSMContext) -> None:
        if message.from_user is None:
            await state.clear()
            return

        if message.text.strip() == BACK_BUTTON:
            await ask_deadline_mode(message, state)
            return

        parsed_deadline = parse_deadline(message.text.strip())
        if parsed_deadline is None:
            await message.answer("Неверный формат даты. Пример: 2026-04-15")
            return

        await save_task_from_state(
            message.from_user.id,
            message,
            state,
            parsed_deadline.isoformat(),
        )

    return router
