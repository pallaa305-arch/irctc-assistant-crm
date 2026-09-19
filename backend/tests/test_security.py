from app.security.sanitizer import sanitize_log_message
from app.security.crypto import encrypt_secret, decrypt_secret

def test_sanitizer_masks_card_numbers():
    raw = "User tried paying with 4111 2222 3333 4444 on gateway"
    sanitized = sanitize_log_message(raw)
    assert "4111 2222 3333 4444" not in sanitized
    assert "****" in sanitized

def test_sanitizer_masks_cvv_and_otp():
    raw = "Payload contained cvv: 987 and OTP: 654321 for authorization"
    sanitized = sanitize_log_message(raw)
    assert "987" not in sanitized
    assert "654321" not in sanitized
    assert "[CVV_REDACTED]" in sanitized
    assert "[OTP_REDACTED]" in sanitized

def test_sanitizer_masks_passwords():
    raw = "Logging request with password: MySuperSecretPassword123"
    sanitized = sanitize_log_message(raw)
    assert "MySuperSecretPassword123" not in sanitized
    assert "[SECRET_REDACTED]" in sanitized

def test_crypto_encryption_and_decryption():
    secret = "MyIrctcPassword@2026"
    encrypted = encrypt_secret(secret)
    assert encrypted != secret
    decrypted = decrypt_secret(encrypted)
    assert decrypted == secret
