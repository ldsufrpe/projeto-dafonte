from fastapi import Request
from sqladmin import Admin
from sqladmin.authentication import AuthenticationBackend
from sqlalchemy import select

from app.core.config import settings
from app.core.database import engine
from app.core.security import create_access_token, decode_token, verify_password
from app.models.user import User, UserRole


class AdminAuth(AuthenticationBackend):
    async def authenticate(self, request: Request) -> bool:
        token = request.session.get("admin_token")
        if not token:
            return False
        try:
            payload = decode_token(token)
            return payload.get("role") == UserRole.admin.value
        except Exception:
            return False

    async def login(self, request: Request) -> bool:
        form = await request.form()
        username = form.get("username", "")
        password = form.get("password", "")

        # Import here to avoid circular import issues at module load time
        from app.core.database import AsyncSessionLocal

        async with AsyncSessionLocal() as db:
            result = await db.execute(select(User).where(User.username == username))
            user = result.scalar_one_or_none()

        if not user or not user.is_active or user.role != UserRole.admin:
            return False
        if not user.hashed_password or not verify_password(password, user.hashed_password):
            return False

        token = create_access_token(subject=str(user.id), role=user.role.value)
        request.session["admin_token"] = token
        return True

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True


def create_admin(app) -> Admin:
    authentication_backend = AdminAuth(secret_key=settings.SECRET_KEY)
    admin = Admin(app, engine=engine, authentication_backend=authentication_backend)
    return admin
