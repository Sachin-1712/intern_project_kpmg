# server.py
from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from master_router import MasterRouter
import os
from dotenv import load_dotenv

load_dotenv()  # so DOTENV in your .env is picked up

class ChatRequest(BaseModel):
    uid: str
    message: str

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],     # restrict in prod!
    allow_methods=["*"],
    allow_headers=["*"],
)

router = MasterRouter(config_path="config.json")

@app.post("/chat")
async def chat(req: ChatRequest):
    # returns just the string reply
    reply = router.process(req.uid, req.message)
    return {"reply": reply}
