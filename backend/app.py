from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy.orm import Session
from dotenv import load_dotenv
import os

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))
from backend.database import SessionLocal, engine, get_db, Base
from backend import models
from backend.schemas import Chat as ChatSchema, ChatCreate, MessageCreate, UserLogin, UserCreate, Token
from backend.crud import *
from backend.auth import *
from backend.ai_service import get_ai_response, get_ai_response_stream
import asyncio

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Agnix AI Chatbot")

# CORS — restrict to known frontend origins (override with ALLOWED_ORIGINS env var, comma-separated)
_default_origins = "https://agnix.onrender.com,http://127.0.0.1:8000,http://localhost:8000"
allowed_origins = os.getenv("ALLOWED_ORIGINS", _default_origins).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files
app.mount("/static", StaticFiles(directory="frontend/static"), name="static")

# -------------------------------
# Create Demo User
# -------------------------------
def create_demo_user():
    db = SessionLocal()
    user = get_user_by_username(db, "demo")
    if not user:
        create_user(db, UserCreate(username="demo", email="demo@example.com", password="demo123"))
    db.close()

create_demo_user()

# -------------------------------
# Auth Routes
# -------------------------------
@app.post("/register", response_model=Token)
def register(user: UserCreate, db: Session = Depends(get_db)):
    db_user = get_user_by_username(db, username=user.username)
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")

    db_email = get_user_by_email(db, email=user.email)
    if db_email:
        raise HTTPException(status_code=400, detail="Email already registered")

    new_user = create_user(db=db, user=user)
    access_token = create_access_token(data={"sub": new_user.username})
    
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/login", response_model=Token)
def login(user: UserLogin, db: Session = Depends(get_db)):
    db_user = get_user_by_username(db, username=user.username)

    if not db_user:
        raise HTTPException(status_code=400, detail="User not found")

    if not verify_password(user.password, db_user.hashed_password):
        raise HTTPException(status_code=400, detail="Invalid password")

    access_token = create_access_token(data={"sub": db_user.username})

    return {
        "access_token": access_token,
        "token_type": "bearer"
    }


# -------------------------------
# Chat Routes
# -------------------------------
@app.post("/chats/", response_model=ChatSchema) 
def create_chat_route(chat: ChatCreate, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return create_chat(db, chat, current_user.id)


@app.get("/chats/", response_model=list[ChatSchema])  
def read_chats(skip: int = 0, limit: int = 100, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    chats = get_chats(db, current_user.id, skip=skip, limit=limit)
    
    for chat in chats:
        chat.messages = get_chat_messages(db, chat.id)
    
    return chats

# -------------------------------
# WebSocket Chat (Streaming AI)
# -------------------------------
@app.websocket("/ws/{chat_id}")
async def websocket_endpoint(websocket: WebSocket, chat_id: int, token: str = Query(None)):
    # Verify JWT token BEFORE accepting the connection
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    db = SessionLocal()
    user = get_user_from_token(token, db)

    if user is None:
        db.close()
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # Verify this chat actually belongs to the connecting user
    chat = get_chat(db, chat_id)
    if chat is None or chat.user_id != user.id:
        db.close()
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    print(f"✅ WebSocket connected for chat_id={chat_id}, user={user.username}")
    
    try:
        while True:
            # Receive message from frontend
            data = await websocket.receive_text()

            # Save user message
            user_msg = MessageCreate(role="user", content=data)
            create_message(db, user_msg, chat_id)

            # Get all messages for this chat
            messages = [
                {"role": m.role, "content": m.content}
                for m in get_chat_messages(db, chat_id)
            ]

            try:
                # Stream AI response chunk-by-chunk (real token streaming)
                full_response = ""
                loop = asyncio.get_event_loop()
                queue: asyncio.Queue = asyncio.Queue()

                def producer():
                    try:
                        for chunk in get_ai_response_stream(messages):
                            loop.call_soon_threadsafe(queue.put_nowait, chunk)
                    finally:
                        loop.call_soon_threadsafe(queue.put_nowait, None)

                executor_future = loop.run_in_executor(None, producer)

                while True:
                    chunk = await queue.get()
                    if chunk is None:
                        break
                    full_response += chunk
                    await websocket.send_json({
                        "type": "chunk",
                        "role": "assistant",
                        "content": chunk
                    })

                await executor_future

                # Let frontend know streaming is complete
                await websocket.send_json({"type": "done", "role": "assistant"})

                # Save full AI response once streaming is done
                create_message(db, MessageCreate(role="assistant", content=full_response), chat_id)

            except Exception as e:
                print("🔥 AI ERROR:", repr(e))
                await websocket.send_json({
                    "type": "done",
                    "role": "assistant",
                    "content": "⚠️ Error getting response from AI"
                })

    except WebSocketDisconnect:
        print("Client disconnected")
    finally:
        # Close the database session when connection ends
        db.close()
# -------------------------------
# Frontend Route
# -------------------------------
@app.get("/", response_class=HTMLResponse)
async def read_index():
    return FileResponse("frontend/templates/index.html")