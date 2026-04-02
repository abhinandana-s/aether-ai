# ✦ Aether AI v2 — Full-Stack AI Chatbot

A production-grade AI chatbot with persistent memory, file analysis, math/code tools, and a beautiful dark UI.

---

## 📁 Folder Structure

```
aether-v2/
├── backend/
│   ├── main.py            # FastAPI — all API endpoints
│   ├── database.py        # SQLite persistence via aiosqlite
│   ├── tools.py           # Intent detection + tool system
│   ├── requirements.txt
│   └── chat_history.db    # Auto-created on first run
├── frontend/
│   └── index.html         # Single-file UI (no build step)
└── README.md
```

---

## 🚀 Quick Start

### 1. Set your OpenAI API Key

```bash
# macOS/Linux
export OPENAI_API_KEY=sk-your-key-here

# Windows (PowerShell)
$env:OPENAI_API_KEY="sk-your-key-here"
```

### 2. Install & run backend

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Backend runs at: http://localhost:8000  
API docs: http://localhost:8000/docs

### 3. Open frontend

```bash
open frontend/index.html
# or serve with:
cd frontend && python -m http.server 3000
```

---

## ✨ Features

### 🧠 Memory (SQLite)
- All messages saved with `role`, `content`, `timestamp`
- Full conversation history sent to AI on each message
- Session list in sidebar — click to reload any past chat
- "Clear Chat" button wipes the current session

### 📎 File Upload
- Upload **PDF** or **text files** (py, js, ts, md, csv, json, html…)
- Text extracted automatically (pdfplumber for PDFs)
- File content sent as context with your question
- Max 10 MB, truncated to 12,000 chars for context limits

### 🧮 Math Tool (sympy)
- Detects math expressions automatically
- Pre-computes with sympy before sending to AI
- Shows calculator result card in chat
- Handles algebra, calculus, trig, symbolic math

### ⌨ Code Tools
- Intent detection for code questions
- Auto-formats Python with `black`
- **Explain Code** / **Fix Bugs** / **Optimize Code** buttons
- Syntax-highlighted code blocks with copy button

### 📋 Summarizer
- Detects summarization intent
- Switches to structured summary mode

### 🎨 UI
- Dark mode with gradient accents
- Animated typing indicator (3 colored dots)
- Intent badge in topbar (Math / Code / Summary / General)
- Tool result cards (calculator, formatter)
- Copy message button on every bubble
- File chip showing name + size

---

## 🔌 API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/chat` | Send message, get AI reply |
| POST | `/upload` | Upload file, get extracted text |
| GET | `/history/{session_id}` | Full message history |
| GET | `/sessions` | List recent sessions |
| POST | `/clear` | Clear a session |
| GET | `/health` | Health check |

### POST /chat body
```json
{
  "session_id": "sess_abc123",
  "message": "What does this code do?",
  "file_context": "optional extracted file text..."
}
```

---

## ⚙️ Customization

| What | Where |
|------|-------|
| AI model | `model=` in `main.py` |
| System prompt | `BASE_SYSTEM` in `tools.py` |
| Max file size | `max_size` in `main.py` |
| Context limit | `12000` char truncation in `tools.py` |
| Colors / fonts | CSS `:root` vars in `index.html` |
| API URL | `const API =` in `index.html` |

---

## 📦 Dependencies

| Package | Purpose |
|---------|---------|
| fastapi | API framework |
| uvicorn | ASGI server |
| openai | GPT API |
| aiosqlite | Async SQLite |
| pdfplumber | PDF text extraction |
| black | Python code formatting |
| sympy | Symbolic math / calculator |
| python-multipart | File uploads |
