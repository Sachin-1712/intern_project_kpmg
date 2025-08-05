# stub_server.py
from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

class ChatRequest(BaseModel):
    uid: str
    message: str

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],    # Open for local testing
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/chat")
async def chat(req: ChatRequest):
    # echo back the incoming message so you can see it in the UI
    return {"reply": f"🦄 Stub says: got your message “{req.message}”"}
