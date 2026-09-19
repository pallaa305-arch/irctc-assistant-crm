import re

# Regex patterns for sensitive data
CARD_PATTERN = re.compile(r'\b(?:\d[ -]*?){13,19}\b')
CVV_PATTERN = re.compile(r'\b(?:cvv|cvc|security\s*code)[\s:=]+(\d{3,4})\b', re.IGNORECASE)
OTP_PATTERN = re.compile(r'\b(?:otp|one[\s-]?time[\s-]?password|verification[\s-]?code)[\s:=]+(\d{4,8})\b', re.IGNORECASE)
PASSWORD_PATTERN = re.compile(r'\b(?:password|passwd|pin|secret|auth_token)[\s:=]+([^\s,;]+)', re.IGNORECASE)
UPI_PIN_PATTERN = re.compile(r'\b(?:upi\s*pin|mpin)[\s:=]+(\d{4,6})\b', re.IGNORECASE)

def sanitize_log_message(message: str) -> str:
    """
    Sanitizes log messages by masking sensitive payment, credentials, OTP, and banking data.
    """
    if not message:
        return ""
        
    cleaned = str(message)
    
    # Mask Card Numbers
    cleaned = CARD_PATTERN.sub(lambda m: m.group(0)[:4] + " **** **** " + m.group(0)[-4:] if len(m.group(0).replace(" ", "").replace("-", "")) >= 13 else "[CARD_REDACTED]", cleaned)
    
    # Mask CVV
    cleaned = CVV_PATTERN.sub(lambda m: m.group(0).replace(m.group(1), "[CVV_REDACTED]"), cleaned)
    
    # Mask OTP
    cleaned = OTP_PATTERN.sub(lambda m: m.group(0).replace(m.group(1), "[OTP_REDACTED]"), cleaned)
    
    # Mask UPI PIN
    cleaned = UPI_PIN_PATTERN.sub(lambda m: m.group(0).replace(m.group(1), "[PIN_REDACTED]"), cleaned)
    
    # Mask Passwords
    cleaned = PASSWORD_PATTERN.sub(lambda m: m.group(0).replace(m.group(1), "[SECRET_REDACTED]"), cleaned)
    
    return cleaned
