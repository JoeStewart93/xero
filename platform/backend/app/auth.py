from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.database import session_scope
from app.models import User
from app.security import hash_password, verify_password

ROLE_ADMIN = "admin"
ROLE_OPERATOR = "operator"


def public_operator(user: User) -> dict:
    return {
        "id": str(user.id),
        "username": user.username,
        "role": user.role,
        "is_enabled": user.is_enabled,
        "created_at": user.created_at,
    }


def get_user_by_username(session: Session, username: str) -> User | None:
    normalized_username = username.strip()
    return session.execute(select(User).where(User.username == normalized_username)).scalar_one_or_none()


def authenticate_operator(session: Session, username: str, password: str) -> User | None:
    user = get_user_by_username(session, username)
    if user is None:
        return None
    if not user.is_enabled:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def update_operator_password(session: Session, user: User, new_password: str, settings: Settings) -> None:
    user.password_hash = hash_password(new_password, rounds=settings.bcrypt_rounds)
    session.add(user)
    session.commit()
    session.refresh(user)


def ensure_seed_user(
    session: Session,
    *,
    username: str,
    password: str,
    role: str,
    settings: Settings,
) -> bool:
    normalized_username = username.strip()
    existing = get_user_by_username(session, normalized_username)
    if existing is not None:
        return False

    session.add(
        User(
            username=normalized_username,
            password_hash=hash_password(password, rounds=settings.bcrypt_rounds),
            role=role,
            is_enabled=True,
        )
    )
    return True


def ensure_seed_users(settings: Settings | None = None) -> list[str]:
    active_settings = settings or Settings()
    created: list[str] = []
    with session_scope(active_settings) as session:
        if ensure_seed_user(
            session,
            username=active_settings.operator_username,
            password=active_settings.operator_password,
            role=ROLE_OPERATOR,
            settings=active_settings,
        ):
            created.append(active_settings.operator_username.strip())
        if ensure_seed_user(
            session,
            username=active_settings.local_admin_username,
            password=active_settings.local_admin_password,
            role=ROLE_ADMIN,
            settings=active_settings,
        ):
            created.append(active_settings.local_admin_username.strip())
    return created


def ensure_seed_operator(settings: Settings | None = None) -> bool:
    return bool(ensure_seed_users(settings))
