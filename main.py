from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from core.database import Base, engine, session


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Управление жизненным циклом приложения.

    - Создает таблицы в БД при старте.
    - Закрывает соединения при завершении.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    await session.close()
    await engine.dispose()


app = FastAPI(
    title="Сервис микроблогов",
    description="API корпоративного сервиса микроблогов, похожего на Twitter",
    lifespan=lifespan,
)
app.router.lifespan_context = lifespan


@app.get("/")
def test_root():
    """Тестовый роут"""
    return {"message": "OK!"}
