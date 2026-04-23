from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException
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
from backend.ai_service import get_ai_response

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Agnix AI Chatbot")

# CORS (for development)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # restrict in production
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
async def websocket_endpoint(websocket: WebSocket, chat_id: int):
    await websocket.accept()
    
    # Create a new database session for this WebSocket connection
    db = SessionLocal()
    
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
                # Get AI response
                response = get_ai_response(messages)
                print("AI RESPONSE:", response)

                # Send response to frontend
                await websocket.send_json({
                    "role": "assistant",
                    "content": response
                })

                # Save AI response
                create_message(db, MessageCreate(role="assistant", content=response), chat_id)

            except Exception as e:
                print("🔥 AI ERROR:", repr(e))
                await websocket.send_json({
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

print("API KEY:", os.getenv("OPENAI_API_KEY"))

