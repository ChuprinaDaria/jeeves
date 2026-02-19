import hashlib
import hmac
import requests

SECRET = "jnqUHdov1VnHoBaY5VI4KA5k4Cd4ue3QV3XinrCLksSEUiIDj3eWBeSvoi1224"
BASE_URL = "http://localhost:8008"
USER = "bot"
PASSWORD = "SuperSecretPassword123"

def get_token():
    for version in ["v3", "r0"]:
        url = f"{BASE_URL}/_matrix/client/{version}/admin/register"
        try:
            r = requests.get(url)
            if r.status_code == 200:
                nonce = r.json().get("nonce")
                
                # Формуємо HMAC підпис за протоколом Matrix
                msg = f"{nonce}\x00{USER}\x00{PASSWORD}\x00admin"
                mac = hmac.new(SECRET.encode(), msg.encode(), hashlib.sha1).hexdigest()

                payload = {
                    "nonce": nonce,
                    "username": USER,
                    "password": PASSWORD,
                    "mac": mac,
                    "admin": True
                }
                
                reg = requests.post(url, json=payload)
                return reg.json()
        except Exception as e:
            continue
    return {"error": "All API endpoints failed"}

if __name__ == "__main__":
    print(get_token())

