import re

def normalize_sa_phone(phone: str) -> str | None:
    if not phone:
        return None

    # remove spaces and non-digits except +
    phone = re.sub(r"[^\d+]", "", phone)

    # Convert 0XXXXXXXXX → +27XXXXXXXXX
    if phone.startswith("0") and len(phone) == 10:
        return "+27" + phone[1:]

    # Accept already normalized numbers
    if phone.startswith("+27") and len(phone) == 12:
        return phone

    # Accept numbers like 2782xxxxxxx
    if phone.startswith("27") and len(phone) == 11:
        return "+" + phone

    return None
