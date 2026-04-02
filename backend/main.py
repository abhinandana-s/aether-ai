from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from contextlib import asynccontextmanager
from typing import Optional
import os

from groq import Groq
from database import init_db, save_message, get_history, clear_session, list_sessions
from tools import (
    detect_intent, run_calculator, extract_code_blocks,
    format_python_code, extract_text_from_file, build_system_prompt
)

# ── Startup ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield

app = FastAPI(title="Aether AI API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

# ── Models ────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    session_id: str
    message: str
    file_context: Optional[str] = None

class ClearRequest(BaseModel):
    session_id: str

# ── Chat Endpoint ─────────────────────────────────────────────────────────────

@app.post("/chat")
async def chat(req: ChatRequest):
    session_id = req.session_id
    user_message = req.message.strip()
    if not user_message:
        raise HTTPException(400, "Message cannot be empty")

    # Detect intent and pick tools
    intent = detect_intent(user_message)
    tool_result = None

    # Pre-process: run calculator if math
    if intent["tool"] == "math":
        tool_result = run_calculator(user_message)

    # Pre-process: format code blocks if code
    if intent["tool"] == "code":
        blocks = extract_code_blocks(user_message)
        if blocks:
            for block in blocks:
                if block["lang"] in ("python", "py", ""):
                    fmt = format_python_code(block["code"])
                    if fmt["success"] and fmt["formatted"] != block["code"]:
                        tool_result = {"formatted_code": fmt["formatted"], "lang": block["lang"]}
                        break

    # Build system prompt based on intent + optional file context
    system_prompt = build_system_prompt(intent, req.file_context)

    # If calculator got a clean result, prepend it to help the AI
    enriched_message = user_message
    if tool_result and "numeric" in tool_result and tool_result["numeric"] is not None:
        enriched_message = (
            f"{user_message}\n\n[Calculator pre-computed: {tool_result['expression']} = "
            f"{tool_result['numeric']} (exact: {tool_result['symbolic']})]"
        )
    elif tool_result and "formatted_code" in tool_result:
        enriched_message = (
            f"{user_message}\n\n[Auto-formatted code:\n```{tool_result['lang']}\n"
            f"{tool_result['formatted_code']}\n```]"
        )

    # Save user message
    await save_message(session_id, "user", user_message)

    # Load history for context
    history = await get_history(session_id)
    messages_for_api = [
        {"role": m["role"], "content": m["content"]}
        for m in history[:-1]  # exclude last (just saved) — we'll use enriched version
    ]
    messages_for_api.append({"role": "user", "content": enriched_message})

    # Call OpenAI
    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "system", "content": system_prompt}, *messages_for_api],
            max_tokens=2048,
            temperature=0.65,
        )
        reply = response.choices[0].message.content
    except Exception as e:
    	raise HTTPException(500, f"Groq error: {e}")

    # Save assistant reply
    await save_message(session_id, "assistant", reply)

    # Reload full history
    full_history = await get_history(session_id)

    return {
        "session_id": session_id,
        "reply": reply,
        "intent": intent,
        "tool_result": tool_result,
        "history": full_history,
    }


# ── File Upload ───────────────────────────────────────────────────────────────

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(400, "No file provided")

    max_size = 10 * 1024 * 1024  # 10 MB
    content = await file.read()
    if len(content) > max_size:
        raise HTTPException(413, "File too large (max 10 MB)")

    result = extract_text_from_file(file.filename, content)
    if not result["success"]:
        raise HTTPException(422, result["error"])

    return {
        "filename": file.filename,
        "text": result["text"],
        "pages": result.get("pages"),
        "char_count": len(result["text"]),
    }


# ── History / Sessions ────────────────────────────────────────────────────────

@app.get("/history/{session_id}")
async def get_chat_history(session_id: str):
    history = await get_history(session_id)
    return {"session_id": session_id, "history": history}

@app.get("/sessions")
async def get_sessions():
    sessions = await list_sessions()
    return {"sessions": sessions}

@app.post("/clear")
async def clear_chat(req: ClearRequest):
    await clear_session(req.session_id)
    return {"status": "cleared", "session_id": req.session_id}

@app.get("/health")
async def health():
    return {"status": "ok", "version": "2.0"}
