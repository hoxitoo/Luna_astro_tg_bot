from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def main_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🃏 Расклад Таро", callback_data="tarot_menu"))
    builder.row(InlineKeyboardButton(text="⭐ Гороскоп на сегодня", callback_data="horoscope"))
    builder.row(InlineKeyboardButton(text="🌙 Карта дня", callback_data="card_of_day"))
    builder.row(InlineKeyboardButton(text="💎 Pro-подписка", callback_data="paywall"))
    return builder.as_markup()


def tarot_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔮 Расклад на 3 карты", callback_data="tarot_3"))
    builder.row(InlineKeyboardButton(text="💞 Расклад на отношения", callback_data="tarot_relations"))
    builder.row(InlineKeyboardButton(text="📅 Расклад на год (Pro)", callback_data="tarot_year"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu"))
    return builder.as_markup()


def paywall_menu(price_month: int = 199, price_year: int = 990) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text=f"💳 Подписка на месяц — {price_month} ₽",
        callback_data="pay_month"
    ))
    builder.row(InlineKeyboardButton(
        text=f"🌟 Подписка на год — {price_year} ₽ (скидка 58%)",
        callback_data="pay_year"
    ))
    builder.row(InlineKeyboardButton(
        text="🎯 Пакет +10 раскладов — 99 ₽",
        callback_data="pay_pack"
    ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu"))
    return builder.as_markup()


def cancel_button() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"))
    return builder.as_markup()


def zodiac_keyboard() -> InlineKeyboardMarkup:
    signs = [
        ("♈ Овен", "zodiac_Овен"), ("♉ Телец", "zodiac_Телец"),
        ("♊ Близнецы", "zodiac_Близнецы"), ("♋ Рак", "zodiac_Рак"),
        ("♌ Лев", "zodiac_Лев"), ("♍ Дева", "zodiac_Дева"),
        ("♎ Весы", "zodiac_Весы"), ("♏ Скорпион", "zodiac_Скорпион"),
        ("♐ Стрелец", "zodiac_Стрелец"), ("♑ Козерог", "zodiac_Козерог"),
        ("♒ Водолей", "zodiac_Водолей"), ("♓ Рыбы", "zodiac_Рыбы"),
    ]
    builder = InlineKeyboardBuilder()
    for i in range(0, len(signs), 2):
        row = [InlineKeyboardButton(text=signs[i][0], callback_data=signs[i][1])]
        if i + 1 < len(signs):
            row.append(InlineKeyboardButton(text=signs[i + 1][0], callback_data=signs[i + 1][1]))
        builder.row(*row)
    return builder.as_markup()


def back_to_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="◀️ В главное меню", callback_data="main_menu"))
    return builder.as_markup()
