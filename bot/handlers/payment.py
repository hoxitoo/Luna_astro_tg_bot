import logging
from aiohttp.web import Request, Response
from aiogram import Router, F, Bot
from aiogram.types import (
    CallbackQuery, InlineKeyboardButton, LabeledPrice, Message, PreCheckoutQuery,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from bot.config import settings
from bot.db.session import async_session_factory
from bot.db import crud
from bot.services.payment_service import generate_payment_url, verify_result_signature
from bot.keyboards.inline import paywall_menu

logger = logging.getLogger(__name__)
router = Router()

_PLAN_NAMES = {"month": "месяц", "year": "год", "pack": "пакет +10 раскладов"}
_STARS_PRICES = {"month": settings.STARS_PRICE_MONTH, "year": settings.STARS_PRICE_YEAR}

_PRO_CONFIRM = (
    "✨ Оплата прошла — добро пожаловать в Pro!\n\n"
    "Теперь тебе доступны безлимитные расклады, гороскоп каждый день, "
    "расклад на год и карта дня по утрам.\n\n"
    "Я рядом. 🌙"
)


@router.callback_query(F.data == "paywall")
async def show_paywall(callback: CallbackQuery) -> None:
    text = (
        "💎 *Pro-подписка Луны*\n\n"
        "— Безлимитные расклады\n"
        "— Гороскоп каждый день\n"
        "— Расклад на год (12 карт)\n"
        "— Карта дня утром\n\n"
        "Оплати звёздами Telegram (мгновенно) или картой:"
    )
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=paywall_menu(
            price_month=settings.SUBSCRIPTION_PRICE_MONTH,
            price_year=settings.SUBSCRIPTION_PRICE_YEAR,
            stars_month=settings.STARS_PRICE_MONTH,
            stars_year=settings.STARS_PRICE_YEAR,
        ),
    )


# ─────────────────────────── Telegram Stars ───────────────────────────

async def _send_stars_invoice(callback: CallbackQuery, bot: Bot, plan: str) -> None:
    stars = _STARS_PRICES[plan]
    await callback.answer()
    await bot.send_invoice(
        chat_id=callback.from_user.id,
        title=f"🌙 Луна Pro — {_PLAN_NAMES[plan]}",
        description=(
            "Безлимитные расклады, гороскоп каждый день, "
            "расклад на год и карта дня по утрам."
        ),
        # Stars require an EMPTY provider_token and currency XTR.
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label=f"Luna Pro — {_PLAN_NAMES[plan]}", amount=stars)],
        payload=f"stars:{plan}",  # parsed back in on_successful_payment
    )


@router.callback_query(F.data == "pay_stars_month")
async def pay_stars_month(callback: CallbackQuery, bot: Bot) -> None:
    await _send_stars_invoice(callback, bot, "month")


@router.callback_query(F.data == "pay_stars_year")
async def pay_stars_year(callback: CallbackQuery, bot: Bot) -> None:
    await _send_stars_invoice(callback, bot, "year")


@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery) -> None:
    # Always approve — we have no reason to reject a Stars charge.
    await query.answer(ok=True)


@router.message(F.successful_payment)
async def on_successful_payment(message: Message) -> None:
    sp = message.successful_payment
    payload = sp.invoice_payload or ""
    if not payload.startswith("stars:"):
        return
    plan = payload.split(":", 1)[1]
    if plan not in ("month", "year"):
        logger.warning(f"Stars: unknown plan in payload '{payload}'")
        return

    user_id = message.from_user.id
    charge_id = sp.telegram_payment_charge_id  # needed for refundStarPayment
    async with async_session_factory() as session:
        recorded = await crud.record_stars_payment(
            session, user_id, sp.total_amount, plan, charge_id
        )
        if recorded is None:
            return  # duplicate delivery — already granted
        await crud.set_pro(session, user_id, plan)
    logger.info(f"Stars payment: user={user_id} plan={plan} charge={charge_id}")
    await message.answer(_PRO_CONFIRM)


# ─────────────────────────── Robokassa (cards) ───────────────────────────

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

    url = generate_payment_url(amount, payment.robokassa_inv_id)

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


async def robokassa_result_handler(request: Request) -> Response:
    """Webhook endpoint for Robokassa ResultURL (POST).

    Idempotent: only the first pending→paid transition grants the purchase.
    Robokassa retries this callback if it doesn't get OK{inv_id} — duplicates
    (and replay attempts) are acknowledged but grant nothing.
    """
    data = await request.post()
    out_sum = data.get("OutSum", "")
    inv_id_raw = data.get("InvId", "")
    signature = data.get("SignatureValue", "")

    try:
        inv_id = int(inv_id_raw)
    except (ValueError, TypeError):
        return Response(text="bad invid", status=400)

    if not verify_result_signature(out_sum, inv_id_raw, signature):
        logger.warning(f"Robokassa: bad signature for InvId={inv_id} from {request.remote}")
        return Response(text="bad sign", status=400)

    async with async_session_factory() as session:
        payment = await crud.get_payment_by_inv_id(session, inv_id)
        if payment is None:
            logger.warning(f"Robokassa: unknown InvId={inv_id}")
            return Response(text="unknown invid", status=400)

        # Defense in depth: the paid amount must match what we billed
        try:
            paid_amount = float(out_sum)
        except ValueError:
            return Response(text="bad outsum", status=400)
        if int(paid_amount) != payment.amount:
            logger.warning(
                f"Robokassa: amount mismatch InvId={inv_id}: paid={out_sum}, expected={payment.amount}"
            )
            return Response(text="bad amount", status=400)

        claimed = await crud.mark_payment_paid(session, inv_id)
        if claimed is None:
            # Already processed (duplicate/replay) — ack so Robokassa stops retrying
            return Response(text=f"OK{inv_id}")

        if claimed.plan in ("month", "year"):
            await crud.set_pro(session, claimed.user_id, claimed.plan)
        elif claimed.plan == "pack":
            await crud.add_extra_spreads(session, claimed.user_id, 10)
        logger.info(f"Payment processed: InvId={inv_id} user={claimed.user_id} plan={claimed.plan}")

    return Response(text=f"OK{inv_id}")
