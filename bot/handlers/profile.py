from datetime import datetime, timezone, timedelta
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from bot.config import settings
from bot.db.session import async_session_factory
from bot.db import crud
from bot.services.limit_service import is_pro_active, remaining_tarot
from bot.keyboards.inline import main_menu

router = Router()

HELP_TEXT = (
    "🌙 *Луна* — медитативные расклады и астрологический анализ\n\n"
    "*Что я умею:*\n"
    "🃏 /start — главное меню\n"
    "👤 /profile — твой профиль и статус\n"
    "❌ /cancel — отменить текущее действие\n\n"
    "*Бесплатно каждый день:*\n"
    "— 3 медитативных расклада\n"
    "— 1 астрологический прогноз\n"
    "— Карта дня\n\n"
    "*Pro-подписка:*\n"
    "— Безлимитные расклады\n"
    "— Расклад на отношения (5 карт)\n"
    "— Расклад на год (12 карт)\n"
    "— 199 ₽/мес · 990 ₽/год"
)


def _profile_keyboard(has_name: bool) -> object:
    builder = InlineKeyboardBuilder()
    if not has_name:
        builder.row(InlineKeyboardButton(text="📝 Настроить профиль", callback_data="setup_profile"))
    builder.row(InlineKeyboardButton(text="◀️ В главное меню", callback_data="main_menu"))
    return builder.as_markup()


def _referral_link(user_id: int) -> str:
    if settings.BOT_USERNAME:
        return f"https://t.me/{settings.BOT_USERNAME}?start=ref_{user_id}"
    return f"/start ref_{user_id}"


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(HELP_TEXT, parse_mode="Markdown", reply_markup=main_menu())


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    current = await state.get_state()
    await state.clear()
    if current:
        await message.answer("🌙 Действие отменено.", reply_markup=main_menu())
    else:
        await message.answer("🌙 Нечего отменять.", reply_markup=main_menu())


@router.message(Command("profile"))
async def cmd_profile(message: Message) -> None:
    async with async_session_factory() as session:
        user = await crud.get_or_create_user(session, message.from_user.id, message.from_user.username)
        remaining = await remaining_tarot(session, user)

    name = user.name or message.from_user.first_name or "—"
    zodiac = user.zodiac_sign or "не указан"

    if is_pro_active(user):
        msk = timezone(timedelta(hours=3))
        expires = user.pro_until.astimezone(msk).strftime("%d.%m.%Y")
        status = f"✨ *Pro* до {expires}"
    elif user.extra_spreads > 0:
        status = f"🎯 Пакет: {user.extra_spreads} раскладов"
    else:
        status = f"🆓 Бесплатно ({remaining} раскл. сегодня)"

    ref_link = _referral_link(message.from_user.id)
    text = (
        f"👤 *Профиль*\n\n"
        f"Имя: {name}\n"
        f"Знак: {zodiac}\n"
        f"Статус: {status}\n\n"
        f"🌙 *Реферальная ссылка:*\n"
        f"`{ref_link}`\n"
        f"_Пригласи подругу — оба получите 7 дней Pro_"
    )
    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=_profile_keyboard(has_name=bool(user.name))
    )
