import logging
from aiohttp.web import Request, Response
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from bot.config import settings
from bot.db.session import async_session_factory
from bot.db import crud
from bot.services.payment_service import create_payment_link, fetch_payment, PaymentError
from bot.keyboards.inline import paywall_menu

logger = logging.getLogger(__name__)
router = Router()

_PLAN_NAMES = {"month": "месяц", "year": "год", "pack": "пакет +10 раскладов"}
_PLAN_DESC = {
    "month": "Luna Pro — подписка на месяц",
    "year": "Luna Pro — подписка на год",
    "pack": "Luna — пакет +10 раскладов",
}


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
    user_id = callback.from_user.id

    async with async_session_factory() as session:
        payment = await crud.create_payment(session, user_id, amount, plan)

    try:
        url, provider_id = await create_payment_link(
            amount, _PLAN_DESC[plan], payment.id
        )
    except PaymentError as e:
        logger.error(f"YooKassa create failed for user={user_id} plan={plan}: {e}")
        await callback.answer()
        await callback.message.edit_text(
            "🌙 Не удалось создать платёж. Попробуй ещё раз чуть позже.",
            reply_markup=paywall_menu(),
        )
        return

    async with async_session_factory() as session:
        await crud.set_payment_provider_id(session, payment.id, provider_id)

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text=f"💳 Оплатить {amount} ₽", url=url))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="paywall"))

    await callback.message.edit_text(
        f"🌙 Оплата Pro на *{_PLAN_NAMES[plan]}*\n\n"
        f"Сумма: *{amount} ₽*\n\n"
        "После оплаты подписка активируется автоматически.\n\n"
        "_Нажимая «Оплатить», ты принимаешь "
        "[условия использования](https://telegra.ph/Luna-Usloviya-ispolzovaniya) "
        "и [политику конфиденциальности](https://telegra.ph/Luna-Politika-konfidencialnosti) "
        "и подтверждаешь: цифровой контент предоставляется в момент оплаты, "
        "возврат не предусмотрен._",
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


_PRO_CONFIRM = (
    "✨ Оплата прошла — добро пожаловать в Pro!\n\n"
    "Теперь тебе доступны безлимитные расклады, гороскоп каждый день, "
    "расклад на год и карта дня по утрам.\n\n"
    "Я рядом. 🌙"
)
_PACK_CONFIRM = (
    "✨ Оплата прошла — пакет из 10 раскладов зачислен.\n\n"
    "Спрашивай — я слушаю. 🌙"
)


async def yookassa_webhook_handler(request: Request) -> Response:
    """Webhook endpoint for YooKassa notifications (POST JSON).

    YooKassa has no signatures, so we trust nothing in the body except the
    payment id: we re-fetch the payment from the API and act only on the
    server's own status/amount. Idempotent — only the first pending→paid
    transition grants the purchase; duplicates are acked with 200.
    """
    try:
        body = await request.json()
    except Exception:
        return Response(status=400, text="bad json")

    event = body.get("event")
    obj = body.get("object") or {}
    provider_id = obj.get("id")
    if not provider_id:
        return Response(status=400, text="no id")

    # We only act on success. Ack everything else with 200 so YooKassa stops retrying.
    if event != "payment.succeeded":
        return Response(text="ignored")

    # Verify against the source of truth, not the (forgeable) webhook body
    try:
        real = await fetch_payment(provider_id)
    except PaymentError as e:
        logger.warning(f"YooKassa: could not verify payment {provider_id}: {e}")
        return Response(status=502, text="verify failed")  # 5xx → YooKassa retries

    if real.get("status") != "succeeded":
        return Response(text="not succeeded")

    async with async_session_factory() as session:
        payment = await crud.get_payment_by_provider_id(session, provider_id)
        if payment is None:
            logger.warning(f"YooKassa: unknown payment id={provider_id}")
            return Response(text="unknown")  # 200 — nothing we can do, don't retry

        # Defense in depth: paid amount must match what we billed
        paid_value = (real.get("amount") or {}).get("value", "0")
        try:
            if int(float(paid_value)) != payment.amount:
                logger.warning(
                    f"YooKassa: amount mismatch id={provider_id}: "
                    f"paid={paid_value}, expected={payment.amount}"
                )
                return Response(text="amount mismatch")
        except (ValueError, TypeError):
            return Response(text="bad amount")

        claimed = await crud.mark_payment_paid(session, provider_id)
        if claimed is None:
            return Response(text="OK")  # duplicate/replay — already granted

        if claimed.plan in ("month", "year"):
            await crud.set_pro(session, claimed.user_id, claimed.plan)
        elif claimed.plan == "pack":
            await crud.add_extra_spreads(session, claimed.user_id, 10)
        logger.info(
            f"Payment processed: id={provider_id} user={claimed.user_id} plan={claimed.plan}"
        )

    # Notify the user (bot instance stashed on the aiohttp app)
    bot = request.app.get("bot")
    if bot is not None:
        text = _PACK_CONFIRM if claimed.plan == "pack" else _PRO_CONFIRM
        try:
            await bot.send_message(claimed.user_id, text)
        except Exception as e:
            logger.warning(f"YooKassa: could not notify user {claimed.user_id}: {e}")

    return Response(text="OK")
