import hashlib
import random
from bot.config import settings


def generate_inv_id() -> int:
    return random.randint(100000, 9999999)


def generate_payment_url(user_id: int, amount: int, inv_id: int) -> str:
    login = settings.ROBOKASSA_LOGIN
    pwd1 = settings.ROBOKASSA_PASSWORD1
    sig = hashlib.md5(f"{login}:{amount}:{inv_id}:{pwd1}".encode()).hexdigest()
    base = "https://auth.robokassa.ru/Merchant/Index.aspx"
    is_test = 1 if settings.ROBOKASSA_TEST_MODE else 0
    return (
        f"{base}?MerchantLogin={login}&OutSum={amount}"
        f"&InvId={inv_id}&SignatureValue={sig}"
        f"&IsTest={is_test}&Shp_user={user_id}"
    )


def verify_result_signature(out_sum: str, inv_id: str, signature: str) -> bool:
    pwd2 = settings.ROBOKASSA_PASSWORD2
    expected = hashlib.md5(f"{out_sum}:{inv_id}:{pwd2}".encode()).hexdigest()
    return expected.lower() == signature.lower()
