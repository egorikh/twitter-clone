from fastapi import HTTPException, Header
from sqlalchemy.future import select

from core.database import async_session
from models import User


async def get_current_user(api_key: str = Header(..., alias="api-key")) -> User:
    async with async_session() as db:
        user = await db.execute(select(User).where(User.api_key == api_key))
        user = user.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=401, detail="Invalid API key")
        return user
