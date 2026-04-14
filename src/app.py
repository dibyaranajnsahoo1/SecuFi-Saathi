from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

try:
    from agent import get_agent
except ImportError:
    from src.agent import get_agent

BASE_DIR = Path(__file__).resolve().parents[1]
UI_FILE = BASE_DIR / "ui" / "index.html"

app = FastAPI(title="SecuFi Saathi")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

agent = None


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    session_id: str | None = None


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    tool_events: list[str]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/")
def ui() -> FileResponse:
    return FileResponse(UI_FILE)


@app.post("/api/chat", response_model=ChatResponse)
def chat(payload: ChatRequest) -> ChatResponse:
    global agent
    if agent is None:
        try:
            agent = get_agent()
        except Exception as error:
            raise HTTPException(status_code=500, detail=str(error)) from error

    try:
        response = agent.chat(payload.message, payload.session_id)
    except RuntimeError as error:
        raise HTTPException(status_code=429, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail="Chat request failed due to an upstream model error. Please try again.",
        ) from error
    return ChatResponse(
        session_id=response.session_id,
        reply=response.text,
        tool_events=response.tool_events,
    )
