from datetime import datetime

from sqlalchemy import Integer, Column, String, ForeignKey, DATETIME, Table
from sqlalchemy.orm import relationship

from core.database import Base


# Ассоциативная таблица для связи многие-ко-многим между твитами и медиа
tweet_media_association = Table(
    "tweet_media",
    Base.metadata,
    Column("tweet_id", Integer, ForeignKey("tweets.id")),
    Column("media_id", Integer, ForeignKey("media.id")),
)


class User(Base):
    """Модель пользователя микросервиса.

    Attributes:
        id (int): Уникальный идентификатор пользователя (первичный ключ).
        name (str): Имя пользователя (максимум 50 символов).
        api_key (str): Уникальный API-ключ для аутентификации.
        tweets (relationship): Связь один-ко-многим с твитами пользователя.
        likes (relationship): Связь один-ко-многим с лайками пользователя.
        followers (relationship): Подписчики пользователя (связь через Follow.following_id).
        following (relationship): Подписки пользователя (связь через Follow.follower_id).
    """

    __table__name = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False)
    api_key = Column(String, unique=True, nullable=False)
    tweets = relationship("Tweet", back_populates="author")
    likes = relationship("Like", back_populates="user")
    followers = relationship(
        "Follow", foreign_keys="Follow.following_id", back_populates="following"
    )
    following = relationship(
        "Follow", foreign_keys="Follow.follower_id", back_populates="follower"
    )


class Tweet(Base):
    """Модель твита (микропоста).

    Attributes:
        id (int): Уникальный идентификатор твита.
        content (str): Текст твита (максимум 280 символов).
        user_id (int): ID автора твита (внешний ключ к User).
        created_at (datetime): Дата и время создания (автоматически заполняется).
        author (relationship): Связь с автором твита.
        likes (relationship): Связь с лайками твита.
        media (relationship): Связь многие-ко-многим с медиафайлами через tweet_media_association.
    """

    __tablename__ = "tweets"
    id = Column(Integer, primary_key=True)
    content = Column(String(280), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DATETIME, default=datetime.now())
    author = relationship("User", back_populates="tweets")
    likes = relationship("Like", back_populates="tweet")
    media = relationship(
        "Media", secondary=tweet_media_association, back_populates="tweets"
    )


class Like(Base):
    """Модель лайка (отметки "нравится") для твитов.

    Attributes:
        id (int): Уникальный идентификатор лайка.
        user_id (int): ID пользователя, поставившего лайк.
        tweet_id (int): ID твита, который лайкнули.
        user (relationship): Связь с пользователем.
        tweet (relationship): Связь с твитом.
    """

    __tablename__ = "likes"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    tweet_id = Column(Integer, ForeignKey("tweets.id"))
    user = relationship("User", back_populates="likes")
    tweet = relationship("Tweet", back_populates="likes")


class Follow(Base):
    """Модель подписки пользователей друг на друга.

    Attributes:
        id (int): Уникальный идентификатор подписки.
        follower_id (int): ID пользователя, который подписывается.
        following_id (int): ID пользователя, на которого подписываются.
        follower (relationship): Связь с подписчиком (User).
        following (relationship): Связь с автором, на которого подписались (User).
    """

    __tablename__ = "follows"
    id = Column(Integer, primary_key=True)
    follower_id = Column(Integer, ForeignKey("users.id"))
    following_id = Column(Integer, ForeignKey("users.id"))
    follower = relationship(
        "User", foreign_keys=[follower_id], back_populates="following"
    )
    following = relationship(
        "User", foreign_keys=[following_id], back_populates="follower"
    )


class Media(Base):
    """Модель медиафайла (изображения), прикрепленного к твиту.

    Attributes:
        id (int): Уникальный идентификатор медиафайла.
        file_path (str): Путь к файлу в файловой системе/S3.
        user (int): ID пользователя, загрузившего файл.
        tweets (relationship): Связь многие-ко-многим с твитами через tweet_media_association.
    """

    __tablename__ = "media"
    id = Column(Integer, primary_key=True)
    file_path = Column(String(255), nullable=False)
    user = Column(Integer, ForeignKey("users.id"))
    tweets = relationship(
        "Tweet", secondary=tweet_media_association, back_populates="media"
    )
