from aiohttp.web import Request, Response
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery
from bot.config import settings
from bot.db.session import async_session_factory
from bot.db import crud
from bot.services.payment_service import generate_inv_id, generate_payment_url, verify_result_signature
from bot.keyboards.inline import paywall_menu, back_to_menu

router = Router()


@router.callback_query(F.data == "paywall")
async def show_paywall(callback: CallbackQuery) -> None:
    text = (
        "💎 *Pro-подписка Луны*\n\n"
        "— Безлимитные расклады\n"
        "— Гороскоп каждый день\n"
        "— Расклад на год (12 карт)\n"
        "— Карта дня утром\n\n"
        "Выбери подходящий вариант:"
    )
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=paywall_menu())


async def _create_payment_link(callback: CallbackQuery, plan: str) -> None:
    amount_map = {
        "month": settings.SUBSCRIPTION_PRICE_MONTH,
        "year": settings.SUBSCRIPTION_PRICE_YEAR,
        "pack": 99,
    }
    amount = amount_map[plan]
    inv_id = generate_inv_id()
    user_id = callback.from_user.id

    async with async_session_factory() as session:
        await crud.create_payment(session, user_id, amount, plan, inv_id)

    url = generate_payment_url(user_id, amount, inv_id)
    plan_names = {"month": "месяц", "year": "год", "pack": "пакет +10 раскладов"}

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text=f"💳 Оплатить {amount} ₽", url=url))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="paywall"))

    await callback.message.edit_text(
        f"🌙 Оплата Pro на *{plan_names[plan]}*\n\n"
        f"Сумма: *{amount} ₽*\n\n"
        "После оплаты подписка активируется автоматически.",
        parse_mode="Markdown",
        reply_markup=builder.as_markup()
    )


@router.callback_query(F.data == "pay_month")
async def pay_month(callback: CallbackQuery) -> None:
    await _create_payment_link(callback, "month")


@router.callback_query(F.data == "pay_year")
async def pay_year(callback: CallbackQuery) -> None:
    await _create_payment_link(callback, "year")


@router.callback_query(F.data == "pay_pack")
async def pay_pack(callback: CallbackQuery) -> None:
    await _create_payment_link(callback, "pack")


async def robokassa_result_handler(request: Request) -> Response:
    """Webhook endpoint for Robokassa ResultURL."""
    data = await request.post()
    out_sum = data.get("OutSum", "")
    inv_id = data.get("InvId", "")
    signature = data.get("SignatureValue", "")

    if not verify_result_signature(out_sum, inv_id, signature):
        return Response(text="bad sign", status=400)

    async with async_session_factory() as session:
        payment = await crud.set_payment_status(session, int(inv_id), "paid")
        if payment and payment.plan in ("month", "year"):
            await crud.set_pro(session, payment.user_id, payment.plan)

    return Response(text=f"OK{inv_id}")
