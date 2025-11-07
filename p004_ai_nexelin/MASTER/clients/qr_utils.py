from typing import Optional
from io import BytesIO
import base64
import hmac
import hashlib
import urllib.parse
from PIL import Image, ImageOps
import qrcode
from django.core.files.base import ContentFile
from django.conf import settings


def build_start2_prefill(branch: str, spec: str, client_token: str, table_number: str) -> str:
    """Створює START2 prefill текст для WhatsApp QR-коду"""
    secret = getattr(settings, 'WHATSAPP_QR_SECRET', 'default-secret-key')
    ref_raw = f"{branch}~{spec}~{client_token}"
    ref_b64 = base64.urlsafe_b64encode(ref_raw.encode()).decode().rstrip("=")
    payload = f"{ref_raw}|{table_number}"
    sig = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()[:16]
    return f"START2 ref={ref_b64} tbl={table_number} sig={sig}"


def build_wa_me_link(prefill_text: str, *, client=None) -> str:
    """Створює WhatsApp wa.me посилання з prefill текстом

    Пріоритет: client.meta_phone_number -> settings.META_PHONE_NUMBER -> fallback (error)
    """
    number = None
    if client is not None:
        num = getattr(client, 'meta_phone_number', '')
        if num:
            number = num
    if not number:
        number = getattr(settings, 'META_PHONE_NUMBER', '')
    if not number:
        # Fallback для сумісності, але краще налаштувати meta_phone_number
        number = getattr(settings, 'TWILIO_WHATSAPP_NUMBER', '')
    if not number:
        raise ValueError('Meta phone number is not configured')
    if number.startswith('whatsapp:'):
        number = number.replace('whatsapp:', '')
    if number.startswith('+'):
        number = number[1:]
    return f"https://wa.me/{number}?text={urllib.parse.quote(prefill_text, safe='')}"


def make_qr_image(link: str, box_size: int = 10, border: int = 4) -> Image.Image:
    """Створює QR-код зображення з високою корекцією помилок"""
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=box_size,
        border=border
    )
    qr.add_data(link)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGBA")
    return img


def paste_center_logo(qr_img: Image.Image, logo_img: Image.Image, scale: float = 0.22, with_ring: bool = True) -> Image.Image:
    """Вставляє логотип по центру QR-коду з білим кільцем для контрасту"""
    qr = qr_img.copy()
    w, h = qr.size
    target = int(min(w, h) * scale)

    # Підготовка логотипу: квадрат, прозорий фон, антиаліас
    logo = logo_img.convert("RGBA")
    # Вписати у квадрат
    max_side = max(logo.size)
    square = Image.new("RGBA", (max_side, max_side), (255, 255, 255, 0))
    off = ((max_side - logo.size[0]) // 2, (max_side - logo.size[1]) // 2)
    square.alpha_composite(logo, off)
    logo = square.resize((target, target), Image.LANCZOS)

    if with_ring:
        # Біле кільце під логотипом для контрасту
        ring_pad = int(target * 0.16)
        ring_size = target + ring_pad * 2
        ring = Image.new("RGBA", (ring_size, ring_size), (255, 255, 255, 0))
        
        # Створюємо біле коло
        bg = Image.new("RGBA", ring.size, (255, 255, 255, 230))
        ring_x = (w - ring.size[0]) // 2
        ring_y = (h - ring.size[1]) // 2
        qr.alpha_composite(bg, (ring_x, ring_y))

    # Вставка логотипу по центру
    x = (w - target) // 2
    y = (h - target) // 2
    qr.alpha_composite(logo, (x, y))
    return qr


def render_qr_with_logo(link: str, logo_path: Optional[str]) -> bytes:
    """Рендерить QR-код з логотипом (якщо є) та повертає PNG bytes"""
    qr = make_qr_image(link)
    if logo_path:
        try:
            with Image.open(logo_path) as li:
                qr = paste_center_logo(qr, li)
        except Exception:
            # Якщо з логотипом щось не так – зробимо звичайний QR
            pass
    out = BytesIO()
    qr.save(out, format="PNG")
    return out.getvalue()


def save_qr_png_to_field(model_instance, field_name: str, png_bytes: bytes, filename: str):
    """Зберігає PNG bytes у ImageField моделі"""
    getattr(model_instance, field_name).save(filename, ContentFile(png_bytes), save=False)


def generate_whatsapp_qr_for_table(table, branch_slug: str, specialization_slug: str, client_token: str) -> bytes:
    """Генерує QR-код для столика з логотипом ресторану"""
    # Створюємо prefill текст
    prefill_text = build_start2_prefill(branch_slug, specialization_slug, client_token, table.table_number)
    
    # Створюємо WhatsApp посилання
    whatsapp_link = build_wa_me_link(prefill_text)
    
    # Отримуємо шлях до логотипу ресторану
    logo_path = None
    if table.restaurant and table.restaurant.logo:
        logo_path = table.restaurant.logo.path
    
    # Генеруємо QR-код з логотипом
    return render_qr_with_logo(whatsapp_link, logo_path)


def generate_whatsapp_qr_for_client_qr(qr_code, branch_slug: str, specialization_slug: str, client_token: str) -> bytes:
    """Генерує QR-код для ClientQRCode з логотипом клієнта"""
    # Створюємо prefill текст (використовуємо qr_token замість table_number)
    prefill_text = build_start2_prefill(branch_slug, specialization_slug, client_token, qr_code.qr_token)
    
    # Створюємо WhatsApp посилання
    whatsapp_link = build_wa_me_link(prefill_text, client=qr_code.client)
    
    # Отримуємо шлях до логотипу клієнта
    logo_path = None
    if qr_code.client and qr_code.client.logo:
        logo_path = qr_code.client.logo.path
    
    # Генеруємо QR-код з логотипом
    return render_qr_with_logo(whatsapp_link, logo_path)
