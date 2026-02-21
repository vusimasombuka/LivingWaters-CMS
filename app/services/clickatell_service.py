import requests
from flask import current_app
from app.utils import normalize_sa_phone


CLICKATELL_URL = "https://platform.clickatell.com/v1/message"


def send_sms(phone, message):
    """
    Sends SMS via Clickatell One API
    """

    api_key = current_app.config.get("CLICKATELL_API_KEY")
    if not api_key:
        raise Exception("Clickatell API key not configured")

    # Normalize number to +27 format
    normalized = normalize_sa_phone(phone)

    if not normalized:
        raise ValueError(f"Invalid phone number: {phone}")

    # Clickatell expects NO +
    clickatell_number = normalized.lstrip("+")

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": api_key,
    }

    payload = {
        "messages": [
            {
                "channel": "sms",
                "to": clickatell_number,
                "content": message,
            }
        ]
    }

    response = requests.post(
        CLICKATELL_URL,
        json=payload,
        headers=headers,
        timeout=15,
    )

    result = response.json()

    if response.status_code not in (200, 201, 202):
        raise Exception(
            f"Clickatell error {response.status_code}: {result}"
        )

    return result
