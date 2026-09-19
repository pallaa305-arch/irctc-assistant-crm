"""
IRCTC Web Selectors & Challenge Signatures
"""

URLS = {
    "HOME": "https://www.irctc.co.in/nget/train-search",
    "LOGIN": "https://www.irctc.co.in/nget/profile/user-login",
    "BOOKING_REVIEW": "https://www.irctc.co.in/nget/booking/review-booking",
    "PAYMENT": "https://www.irctc.co.in/nget/payment"
}

CHALLENGE_SELECTORS = {
    # CAPTCHA elements on IRCTC
    "CAPTCHA_IMAGE": "app-captcha img, #captchaImg, img[alt='Captcha']",
    "CAPTCHA_INPUT": "#nlpAnswer, #captcha, input[placeholder*='Captcha']",
    
    # OTP modal or input elements
    "OTP_CONTAINER": "div:has-text('OTP'), div:has-text('One Time Password'), input[placeholder*='OTP'], #otp",
    
    # 2FA / Security challenge
    "SECURITY_CHALLENGE": "div:has-text('Security Question'), div:has-text('Verification Code')",
    
    # Payment Stage indicator
    "PAYMENT_CONTAINER": "app-payment, div:has-text('Payment Option'), div:has-text('Payment Method'), #bank-type"
}

NAVIGATION_SELECTORS = {
    "FROM_STATION": "p-autocomplete[formcontrolname='origin'] input, #origin input",
    "TO_STATION": "p-autocomplete[formcontrolname='destination'] input, #destination input",
    "JOURNEY_DATE": "p-calendar[formcontrolname='journeyDate'] input, #jDate input",
    "CLASS_DROPDOWN": "p-dropdown[formcontrolname='journeyQuota'], #journeyClass",
    "SEARCH_BUTTON": "button[type='submit']:has-text('Search'), button:has-text('SEARCH')",
    
    # Passenger form elements
    "PASSENGER_NAME": "input[placeholder='Passenger Name'], p-autocomplete[formcontrolname='passengerName'] input",
    "PASSENGER_AGE": "input[placeholder='Age'], input[formcontrolname='passengerAge']",
    "PASSENGER_GENDER": "select[formcontrolname='passengerGender'], p-dropdown[formcontrolname='passengerGender']",
    "PASSENGER_BERTH": "select[formcontrolname='passengerBerthChoice'], p-dropdown[formcontrolname='passengerBerthChoice']",
    "ADD_PASSENGER_BTN": "a:has-text('+ Add Passenger'), button:has-text('Add Passenger')",
    
    # Contact
    "CONTACT_MOBILE": "input[formcontrolname='mobileNumber'], input[placeholder='Mobile Number']",
    
    # Continue / Review
    "CONTINUE_BOOKING": "button:has-text('Continue'), button[type='submit']:has-text('Continue')",
    
    # Confirmation details
    "PNR_CONTAINER": "span:has-text('PNR No.'), div.ticket-pnr, div:has-text('PNR :')",
    "CONFIRMATION_TITLE": "div:has-text('Booking Confirmation'), span:has-text('Transaction ID')"
}
