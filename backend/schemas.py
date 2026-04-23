from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import List, Optional

# -------------------------------
# User Schemas
# -------------------------------
class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=6)


class User(BaseModel):
    id: int
    username: str
    email: EmailStr

    class Config:
        from_attributes = True


# -------------------------------
# Message Schemas
# -------------------------------
class MessageBase(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str = Field(..., min_length=1, max_length=2000)


class MessageCreate(MessageBase):
    pass


class Message(MessageBase):
    id: int
    created_at: datetime
    chat_id: int

    class Config:
        from_attributes = True


# -------------------------------
# Chat Schemas
# -------------------------------
class ChatBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)


class ChatCreate(ChatBase):
    pass


class Chat(ChatBase):
    id: int
    user_id: int
    messages: List[Message] = Field(default_factory=list)  # FIXED

    class Config:
        from_attributes = True


# -------------------------------
# Auth Token
# -------------------------------
class Token(BaseModel):
    access_token: str
    token_type: str

from pydantic import BaseModel

class UserLogin(BaseModel):
    username: str
    password: str  
    
