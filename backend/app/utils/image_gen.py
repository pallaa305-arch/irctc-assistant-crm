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

def generate_mock_upi_qr_image(amount: float, ref: str) -> bytes:
    """
    Generates a mock UPI Payment QR display image.
    """
    width, height = 280, 320
    image = Image.new('RGB', (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(image)

    # Top Header
    draw.rectangle([0, 0, width, 55], fill=(30, 90, 50))
    draw.text((20, 15), "BHARAT UPI / IRCTC PAY", fill=(255, 255, 255))
    draw.text((20, 32), f"Amount: Rs. {amount:.2f}", fill=(200, 240, 210))

    # Mock QR pattern box
    qr_box = [40, 75, 240, 275]
    draw.rectangle(qr_box, outline=(0, 0, 0), width=3)

    # Draw pseudo-QR grid pattern
    random.seed(hash(ref))
    grid_size = 10
    for r in range(45, 235, grid_size):
        for c in range(80, 270, grid_size):
            if random.random() > 0.45:
                draw.rectangle([r, c, r + grid_size - 1, c + grid_size - 1], fill=(0, 0, 0))

    # Corner anchors
    draw.rectangle([45, 80, 85, 120], fill=(0, 0, 0))
    draw.rectangle([55, 90, 75, 110], fill=(255, 255, 255))
    draw.rectangle([195, 80, 235, 120], fill=(0, 0, 0))
    draw.rectangle([205, 90, 225, 110], fill=(255, 255, 255))
    draw.rectangle([45, 230, 85, 270], fill=(0, 0, 0))
    draw.rectangle([55, 240, 75, 260], fill=(255, 255, 255))

    # Footer note
    draw.text((40, 290), f"Ref: {ref}", fill=(100, 100, 100))

    buf = io.BytesIO()
    image.save(buf, format='PNG')
    return buf.getvalue()
