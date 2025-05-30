import os
import uuid
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.params import Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.database import Base, engine, get_db, async_session
from models import User, Tweet, Media, Follow, Like, tweet_media_association
from schemas import TweetResponse, TweetCreate, UserMeResponse
from services import get_current_user


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Управление жизненным циклом приложения.

    - Создает таблицы в БД при старте.
    - Закрывает соединения при завершении.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        async with async_session() as db:
            test_user_1 = await db.execute(select(User).where(User.api_key == "test"))
            test_user_2 = await db.execute(select(User).where(User.api_key == "Bob123"))
            test_user_3 = await db.execute(select(User).where(User.api_key == "Alex123"))
            if not test_user_1.scalar_one_or_none():
                db.add(User(name="test", api_key="test"))
                await db.commit()
            if not test_user_2.scalar_one_or_none():
                db.add(User(name="Bob", api_key="Bob123"))
                await db.commit()
            if not test_user_3.scalar_one_or_none():
                db.add(User(name="Alex", api_key="Alex123"))
                await db.commit()

    yield

    await engine.dispose()


app = FastAPI(
    title="Сервис микроблогов",
    description="API корпоративного сервиса микроблогов, похожего на Twitter",
    lifespan=lifespan,
)
app.router.lifespan_context = lifespan
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/tweets", response_model=TweetResponse)
async def create_tweet(
        tweet: TweetCreate,
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    new_tweet = Tweet(content=tweet.tweet_data, user_id=user.id)
    db.add(new_tweet)
    await db.commit()
    await db.refresh(new_tweet)

    if tweet.tweet_media_ids:
        media = await db.execute(
            select(Media)
            .where(Media.id.in_(tweet.tweet_media_ids))
            .where(Media.user == user.id)
        )
        media_files = media.scalars().all()
        for media in media_files:
            await db.execute(
                tweet_media_association.insert().values(
                    tweet_id=new_tweet.id,
                    media_id=media.id
                )
            )

        await db.commit()

    return {"result": True, "tweet_id": new_tweet.id}


@app.post("/api/medias")
async def upload_media(
        file: UploadFile = File(...),
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    file_ext = os.path.splitext(file.filename)[1] # генерация уникального имени файла
    file_name = f"{uuid.uuid4()}{file_ext}"
    file_path = f"uploads/{file_name}"
    with open(file_path, "wb") as buffer:
        buffer.write(await file.read())

    media = Media(file_path=file_path, user=user.id)
    db.add(media)
    await db.commit()
    await db.refresh(media)

    return {"result": True, "media_id": media.id}


@app.get("/api/tweets")
async def get_tweets(
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
):
    query = (
        select(Tweet, func.count(Like.id).label("likes"))
        .join(Like, Tweet.id == Like.tweet_id, isouter=True)
        .group_by(Tweet.id)
        .options(selectinload(Tweet.media), selectinload(Tweet.author), selectinload(Tweet.likes))
        .order_by(func.count(Like.id).desc(), Tweet.created_at.desc())
    )
    tweets = (await db.execute(query)).scalars().all()

    formatted_tweets = []
    for tweet in tweets:
        formatted_tweets.append({
            "id": tweet.id,
            "content": tweet.content,
            "attachments": [media.file_path for media in tweet.media],
            "author": {
                "id": tweet.author.id,
                "name": tweet.author.name
            },
            "likes": [
                {"user_id": like.user.id, "name": like.user.name}
                for like in tweet.likes
            ]
        })

    return {"result": True, "tweets": formatted_tweets}


@app.delete("/api/tweets/{tweet_id}")
async def delete_tweet(
        tweet_id: int,
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    tweet = await db.execute(select(Tweet).where(Tweet.id==tweet_id))
    tweet = tweet.scalar_one_or_none()

    if not tweet:
        raise HTTPException(status_code=404, detail={
            "result": False,
            "error_type": "NotFound",
            "error_message": "Tweet not found"
        })

    if tweet.user_id != user.id:
        raise HTTPException(status_code=403, detail={
            "result": False,
            "error_type": "Forbidden",
            "error_message": "You can only delete your own tweets"
        })

    await db.delete(tweet)
    await db.commit()

    return {"result": True}


@app.post("/api/tweets/{tweet_id}/likes")
async def like_tweet(
        tweet_id: int,
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    tweet = await db.execute(select(Tweet).where(Tweet.id==tweet_id))
    tweet = tweet.scalar_one_or_none()

    if not tweet:
        raise HTTPException(status_code=404, detail={
            "result": False,
            "error_type": "NotFound",
            "error_message": "Tweet not found"
        })

    existing_like = await db.execute(
        select(Like)
        .where(Like.user_id == user.id)
        .where(Like.tweet_id == tweet_id)
    )
    if existing_like.scalar_one_or_none():
        raise HTTPException(status_code=400, detail={
            "result": False,
            "error_type": "Duplicate",
            "error_message": "You already liked this tweet"
        })

    new_like = Like(user_id=user.id, tweet_id=tweet_id)
    db.add(new_like)
    await db.commit()

    return {"result": True}


@app.delete("/api/tweets/{tweet_id}/likes")
async def delete_like_tweet(
        tweet_id: int,
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    like = await db.execute(
        select(Like)
        .where(Like.user_id == user.id)
        .where(Like.tweet_id == tweet_id)
    )
    like = like.scalar_one_or_none()

    if not like:
        raise HTTPException(status_code=404, detail={
            "result": False,
            "error_type": "NotFound",
            "error_message": "Like not found"
        })

    await db.delete(like)
    await db.commit()

    return {"result": True}


@app.post("/api/users/{user_id}/follow")
async def follow_user(
    user_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if user.id == user_id:
        raise HTTPException(status_code=400, detail={
            "result": False,
            "error_type": "InvalidAction",
            "error_message": "Cannot follow yourself"
        })

    following_user = await db.execute(select(User).where(User.id == user_id))
    following_user = following_user.scalar_one_or_none()
    if not following_user:
        raise HTTPException(status_code=404, detail={
            "result": False,
            "error_type": "NotFound",
            "error_message": "User not found"
        })

    existing_follow = await db.execute(
        select(Follow)
        .where(Follow.follower_id == user.id)
        .where(Follow.following_id == user_id)
    )

    if existing_follow.scalar_one_or_none():
        raise HTTPException(status_code=400, detail={
            "result": False,
            "error_type": "Duplicate",
            "error_message": "Already following this user"
        })

    new_follow = Follow(follower_id=user.id, following_id = user_id)
    db.add(new_follow)
    await db.commit()

    return {"result": True}


@app.delete("/api/users/{user_id}/follow")
async def unfollow_user(
    user_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    follow = await db.execute(
        select(Follow)
        .where(Follow.follower_id == user.id)
        .where(Follow.following_id == user_id)
    )
    follow = follow.scalar_one_or_none()

    if not follow:
        raise HTTPException(status_code=404, detail={
            "result": False,
            "error_type": "NotFound",
            "error_message": "Follow relationship not found"
        })

    await db.delete(follow)
    await db.commit()

    return {"result": True}


@app.get("/api/users/me", response_model=UserMeResponse)
async def get_current_user_profile(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Получение информации о текущем пользователе (профиль)
    Включает список подписчиков и подписок
    """

    result = await db.execute(
        select(User)
        .where(User.id == user.id)
        .options(
            selectinload(User.followers).joinedload(Follow.follower),
            selectinload(User.following).joinedload(Follow.following)
        )
    )
    user = result.scalar_one()

    return {
        "result": True,
        "user": {
            "id": user.id,
            "name": user.name,
            "followers": [
                {"id": follower.follower.id, "name": follower.follower.name}
                for follower in user.followers
            ],
            "following": [
                {"id": following.following.id, "name": following.following.name}
                for following in user.following
            ]
        }
    }


@app.get("/api/users/{user_id}")
async def get_user_profile(
    user_id: int,
    db: AsyncSession = Depends(get_db)
):
    user = await db.execute(
        select(User)
        .where(User.id == user_id)
        .options(
            selectinload(User.followers).joinedload(Follow.follower),
            selectinload(User.following).joinedload(Follow.following)
        )
    )
    user = user.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail={
            "result": False,
            "error_type": "NotFound",
            "error_message": "User not found"
        })

    return {
        "result": True,
        "user": {
            "id": user.id,
            "name": user.name,
            "followers": [
                {"id": follower.follower.id, "name": follower.follower.name}
                for follower in user.followers
            ],
            "following": [
                {"id": following.following.id, "name": following.following.name}
                for following in user.following
            ]
        }
    }


app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
app.mount("/", StaticFiles(directory="dist", html=True), name="frontend")


# отдаём index.html на все не-API пути
@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    try:
        return FileResponse("dist/index.html")
    except:
        raise HTTPException(status_code=404)
