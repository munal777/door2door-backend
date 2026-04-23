import secrets

def generate_otp():
    otp = ''.join(str(secrets.randbelow(10)) for _ in range(6))

    return otp