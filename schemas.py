from typing import List

from pydantic import BaseModel, Field


class TweetCreate(BaseModel):
    tweet_data: str = Field(...)
    tweet_media_ids: list[int] = []


class UserResponse(BaseModel):
    id: int
    name: str

class TweetResponse(BaseModel):
    result: bool
    tweet_id: int

class TweetsResponse(BaseModel):
    result: bool = True
    tweets: List[TweetResponse]


class UserProfile(BaseModel):
    id: int
    name: str
    followers: List[UserResponse]
    following: List[UserResponse]


class UserMeResponse(BaseModel):
    result: bool
    user: UserProfile
