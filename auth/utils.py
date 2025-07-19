from typing import Any

def generate_password_hash(bcrypt, password: str) -> str:
    """Generate a bcrypt password hash"""
    return bcrypt.generate_password_hash(password).decode("utf-8")


def check_password(bcrypt, hashed_password: str, password: str) -> bool:
    """Check a password against a bcrypt hash"""
    return bcrypt.check_password_hash(hashed_password, password)


def create_test_user(user_manager, bcrypt, email: str, password: str) -> Any:
    """Create a test user for development/testing purposes"""
    existing_user = user_manager.get_user_by_email(email)
    if not existing_user:
        password_hash = generate_password_hash(bcrypt, password)
        user = user_manager.create_user(email, password_hash)
        return user
    return existing_user
