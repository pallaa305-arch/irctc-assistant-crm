import io
import random
from PIL import Image, ImageDraw, ImageFont

def generate_mock_captcha_image(text: str) -> bytes:
    """
    Generates a realistic visual CAPTCHA image with distortions for testing.
    """
    width, height = 220, 70
    image = Image.new('RGB', (width, height), color=(245, 247, 250))
    draw = ImageDraw.Draw(image)

    # Draw background noise lines
    for _ in range(8):
        x1 = random.randint(0, width)
        y1 = random.randint(0, height)
        x2 = random.randint(0, width)
        y2 = random.randint(0, height)
        draw.line(((x1, y1), (x2, y2)), fill=(random.randint(180, 220), random.randint(180, 220), random.randint(180, 220)), width=2)

    # Draw noise dots
    for _ in range(120):
        xy = (random.randint(0, width), random.randint(0, height))
        draw.point(xy, fill=(random.randint(100, 200), random.randint(100, 200), random.randint(100, 200)))

    # Draw letters
    char_x = 25
    for char in text:
        y_offset = random.randint(15, 25)
        # Using default font
        draw.text((char_x, y_offset), char, fill=(random.randint(20, 90), random.randint(30, 110), random.randint(30, 120)))
        char_x += 35

    # Border
    draw.rectangle([0, 0, width - 1, height - 1], outline=(180, 190, 205), width=1)

    buf = io.BytesIO()
    image.save(buf, format='PNG')
    return buf.getvalue()

def get_mock_upi_url(amount: float, ref: str) -> str:
    return f"upi://pay?pa=irctc.pay@hdfcbank&pn=IRCTC%20Official&am={amount:.2f}&cu=INR&tr={ref}&tn=IRCTC%20Tatkal%20Ticket"

def generate_mock_upi_qr_image(amount: float, ref: str) -> bytes:
    """
    Generates a genuine, scannable UPI Payment QR image.
    """
    upi_url = get_mock_upi_url(amount, ref)
    try:
        import qrcode
        qr = qrcode.QRCode(box_size=8, border=3)
        qr.add_data(upi_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        return buf.getvalue()
    except Exception:
        width, height = 280, 280
        image = Image.new('RGB', (width, height), color=(255, 255, 255))
        draw = ImageDraw.Draw(image)
        draw.text((20, 20), f"UPI Pay: Rs {amount:.2f}", fill=(0, 0, 0))
        buf = io.BytesIO()
        image.save(buf, format='PNG')
        return buf.getvalue()
