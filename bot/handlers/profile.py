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
from bot.keyboards.inline import main_menu, persona_keyboard

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


_PERSONA_NAMES = {
    "young_moon": "🌙 Молодая Луна",
    "full_moon": "🌕 Полная Луна",
    "dark_moon": "🌑 Тёмная Луна",
}


def _profile_keyboard(has_name: bool, is_pro: bool = False) -> object:
    builder = InlineKeyboardBuilder()
    if not has_name:
        builder.row(InlineKeyboardButton(text="📝 Настроить профиль", callback_data="setup_profile"))
    if is_pro:
        builder.row(InlineKeyboardButton(text="🌙 Сменить Луну", callback_data="change_persona"))
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

    pro_active = is_pro_active(user)
    persona = _PERSONA_NAMES.get(user.luna_persona or "young_moon", "🌙 Молодая Луна")
    ref_link = _referral_link(message.from_user.id)
    text = (
        f"👤 *Профиль*\n\n"
        f"Имя: {name}\n"
        f"Знак: {zodiac}\n"
        f"Луна: {persona}\n"
        f"Статус: {status}\n\n"
        f"🌙 *Реферальная ссылка:*\n"
        f"`{ref_link}`\n"
        f"_Пригласи подругу — оба получите 7 дней Pro_"
    )
    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=_profile_keyboard(has_name=bool(user.name), is_pro=pro_active)
    )


@router.callback_query(F.data == "change_persona")
async def change_persona(callback: CallbackQuery) -> None:
    async with async_session_factory() as session:
        user = await crud.get_or_create_user(session, callback.from_user.id)

    await callback.message.edit_text(
        "🌙 Выбери свою Луну.\n\n"
        "Каждый архетип — разный голос, разный взгляд на карты.",
        reply_markup=persona_keyboard(is_pro=is_pro_active(user))
    )


@router.callback_query(F.data.startswith("persona:"))
async def set_persona(callback: CallbackQuery) -> None:
    persona = callback.data.split(":", 1)[1]
    async with async_session_factory() as session:
        user = await crud.get_or_create_user(session, callback.from_user.id)
        if persona in ("full_moon", "dark_moon") and not is_pro_active(user):
            await callback.answer(
                "Этот архетип доступен только в Pro-подписке.", show_alert=True
            )
            return
        await crud.update_user(session, callback.from_user.id, luna_persona=persona)

    names = {"young_moon": "Молодая Луна", "full_moon": "Полная Луна", "dark_moon": "Тёмная Луна"}
    await callback.message.edit_text(
        f"🌙 Теперь ты разговариваешь с *{names.get(persona, 'Луной')}*.",
        parse_mode="Markdown",
        reply_markup=main_menu()
    )


@router.callback_query(F.data == "persona_locked")
async def persona_locked(callback: CallbackQuery) -> None:
    await callback.answer(
        "Этот архетип доступен только в Pro-подписке.", show_alert=True
    )
