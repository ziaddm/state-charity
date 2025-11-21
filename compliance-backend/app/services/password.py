import bcrypt

def hash_password(password: str) -> str:
    """Hash a password"""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(entered_password: str, hashed_password: str) -> bool:
    """Check if entered password matches the hash"""
    return bcrypt.checkpw(entered_password.encode(), hashed_password.encode())