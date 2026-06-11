"""Lunar Diary — spread history with pagination."""
import math
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.db.session import async_session_factory
from bot.db import crud
from bot.utils.text_utils import truncate

router = Router()

_PER_PAGE = 8

_SPREAD_TYPE_EMOJI = {
    "tarot_3": "🔮",
    "relations_5": "💞",
    "year_12": "📅",
    "past": "🌑",
    "birthday": "🎂",
}

_SPREAD_TYPE_NAME = {
    "tarot_3": "Расклад 3 карты",
    "relations_5": "Расклад на отношения",
    "year_12": "Расклад на год",
    "past": "Расклад на прошлое",
    "birthday": "Солнечный возврат",
}

_MONTH_RU = {
    1: "янв", 2: "фев", 3: "мар", 4: "апр",
    5: "май", 6: "июн", 7: "июл", 8: "авг",
    9: "сен", 10: "окт", 11: "ноя", 12: "дек",
}


def _spread_button_text(spread) -> str:
    dt = spread.created_at
    day = dt.day
    mon = _MONTH_RU.get(dt.month, "?")
    emoji = _SPREAD_TYPE_EMOJI.get(spread.spread_type, "🃏")
    label = _SPREAD_TYPE_NAME.get(spread.spread_type, spread.spread_type)
    return f"{day} {mon} — {label} {emoji}"


def _diary_keyboard(spreads, page: int, total: int) -> object:
    total_pages = max(1, math.ceil(total / _PER_PAGE))
    builder = InlineKeyboardBuilder()

    for spread in spreads:
        builder.row(InlineKeyboardButton(
            text=_spread_button_text(spread),
            callback_data=f"spread_view:{spread.id}"
        ))

    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"history_page:{page - 1}"))
    nav.append(InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="noop"))
    if page < total_pages:
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"history_page:{page + 1}"))
    if nav:
        builder.row(*nav)

    builder.row(InlineKeyboardButton(text="◀️ В главное меню", callback_data="main_menu"))
    return builder.as_markup()


async def _show_diary(target, user_id: int, page: int) -> None:
    async with async_session_factory() as session:
        spreads, total = await crud.get_spreads_page(session, user_id, page, _PER_PAGE)

    if total == 0:
        text = (
            "📖 *Лунный дневник*\n\n"
            "Здесь будут храниться все твои расклады.\n"
            "Сделай первый расклад — и он появится здесь."
        )
        from bot.keyboards.inline import main_menu
        kb = main_menu()
    else:
        text = f"📖 *Лунный дневник* — {total} раскладов"
        kb = _diary_keyboard(spreads, page, total)

    if isinstance(target, Message):
        await target.answer(text, parse_mode="Markdown", reply_markup=kb)
    else:
        await target.message.edit_text(text, parse_mode="Markdown", reply_markup=kb)


@router.message(Command("history"))
async def cmd_history(message: Message) -> None:
    await _show_diary(message, message.from_user.id, page=1)


@router.callback_query(F.data.startswith("history_page:"))
async def history_page(callback: CallbackQuery) -> None:
    page = int(callback.data.split(":", 1)[1])
    await _show_diary(callback, callback.from_user.id, page=page)


@router.callback_query(F.data.startswith("spread_view:"))
async def spread_view(callback: CallbackQuery) -> None:
    spread_id = int(callback.data.split(":", 1)[1])
    async with async_session_factory() as session:
        spread = await crud.get_spread_by_id(session, spread_id, callback.from_user.id)

    if not spread:
        await callback.answer("Расклад не найден.", show_alert=True)
        return

    dt = spread.created_at
    date_str = f"{dt.day} {_MONTH_RU.get(dt.month, '?')} {dt.year}"
    type_name = _SPREAD_TYPE_NAME.get(spread.spread_type, spread.spread_type)

    header = f"🃏 *{type_name}* · {date_str}\n"
    if spread.question:
        header += f"_{spread.question}_\n"
    header += "\n"

    full_text = header + spread.interpretation
    builder = InlineKeyboardBuilder()
    # Back to diary — remember which page is tricky without storing it, go to page 1
    builder.row(InlineKeyboardButton(text="◀️ Дневник", callback_data="history_page:1"))
    builder.row(InlineKeyboardButton(text="◀️ Главное меню", callback_data="main_menu"))

    await callback.message.edit_text(
        truncate(full_text, max_len=4096),
        parse_mode="Markdown",
        reply_markup=builder.as_markup()
    )


@router.callback_query(F.data == "noop")
async def noop(callback: CallbackQuery) -> None:
    await callback.answer()
