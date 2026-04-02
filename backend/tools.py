"""
Tool system for Aether AI.
Routes user input to the correct tool before/alongside the AI.
"""
import re
import ast
import sympy
from sympy import sympify, SympifyError


# ── Intent Detection ─────────────────────────────────────────────────────────

MATH_PATTERNS = [
    r'\b(calculate|compute|solve|evaluate|what is)\b.{0,60}[\d\+\-\*\/\^=]',
    r'[\d\s]*[\+\-\*\/\^%]{1}[\s\d]',
    r'\b(sqrt|sin|cos|tan|log|exp|integral|derivative|factorial)\b',
    r'=\s*\?',
    r'^\s*[\d\s\+\-\*\/\(\)\.\^]+\s*$',
]

CODE_PATTERNS = [
    r'```[\w]*\n',
    r'\b(def |function |class |import |#include|public static|var |let |const )\b',
    r'\b(explain|fix|optimize|debug|refactor|improve|review)\b.{0,30}\b(code|function|script|program|snippet|bug|error)\b',
    r'\b(error|traceback|exception|syntax error|runtime error)\b',
]

CODE_ACTION_PATTERNS = {
    'explain': r'\b(explain|what does|describe|how does)\b.{0,30}\b(code|function|class|script)\b',
    'fix':     r'\b(fix|debug|repair|correct|there.s a bug|not working)\b',
    'optimize': r'\b(optimize|improve|refactor|make.{0,10}faster|performance)\b',
}

def detect_intent(text: str) -> dict:
    lower = text.lower()

    # Check for coding intent
    for pattern in CODE_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE | re.DOTALL):
            action = 'general'
            for act, pat in CODE_ACTION_PATTERNS.items():
                if re.search(pat, lower):
                    action = act
                    break
            return {"tool": "code", "action": action}

    # Check for math intent
    for pattern in MATH_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return {"tool": "math"}

    # Check for summarize intent
    if re.search(r'\b(summarize|summarise|tldr|brief|summary|overview|key points)\b', lower):
        return {"tool": "summarize"}

    return {"tool": "general"}


# ── Calculator Tool ──────────────────────────────────────────────────────────

def run_calculator(text: str) -> dict | None:
    """Try to evaluate a math expression. Returns result dict or None."""
    # Extract math expression from text
    expr_match = re.search(
        r'([\d\s\+\-\*\/\(\)\.\^%sqrt\w]+(?:\s*[\+\-\*\/\^%=]\s*[\d\s\(\)\.\^%sqrt\w]+)+)',
        text, re.IGNORECASE
    )
    expr = expr_match.group(0).strip() if expr_match else text.strip()

    # Clean up expression
    expr = expr.replace('^', '**').replace('×', '*').replace('÷', '/')
    expr = re.sub(r'=\s*\??\s*$', '', expr).strip()

    try:
        result = sympify(expr)
        simplified = sympy.simplify(result)
        numeric = float(simplified) if simplified.is_number else None
        return {
            "expression": expr,
            "symbolic": str(simplified),
            "numeric": numeric,
        }
    except (SympifyError, Exception):
        return None


# ── Code Formatter Tool ──────────────────────────────────────────────────────

def extract_code_blocks(text: str) -> list[dict]:
    """Extract fenced code blocks from text."""
    blocks = []
    pattern = r'```(\w*)\n?(.*?)```'
    for m in re.finditer(pattern, text, re.DOTALL):
        blocks.append({"lang": m.group(1) or "python", "code": m.group(2).strip()})
    return blocks


def format_python_code(code: str) -> dict:
    """Format Python code using black."""
    try:
        import black
        mode = black.Mode(line_length=88)
        formatted = black.format_str(code, mode=mode)
        return {"success": True, "formatted": formatted}
    except Exception as e:
        return {"success": False, "error": str(e), "formatted": code}


# ── File Text Extractor ──────────────────────────────────────────────────────

def extract_text_from_file(filename: str, content: bytes) -> dict:
    """Extract text from PDF or plain text files."""
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else 'txt'

    if ext == 'pdf':
        try:
            import pdfplumber
            import io
            text_parts = []
            with pdfplumber.open(io.BytesIO(content)) as pdf:
                for i, page in enumerate(pdf.pages):
                    t = page.extract_text()
                    if t:
                        text_parts.append(f"[Page {i+1}]\n{t}")
            if not text_parts:
                return {"success": False, "error": "No text found in PDF (may be scanned/image-based)"}
            full = "\n\n".join(text_parts)
            # Truncate to ~12000 chars to stay within context limits
            truncated = full[:12000] + ("\n\n[...truncated...]" if len(full) > 12000 else "")
            return {"success": True, "text": truncated, "pages": len(text_parts)}
        except Exception as e:
            return {"success": False, "error": f"PDF extraction failed: {e}"}

    elif ext in ('txt', 'md', 'csv', 'json', 'yaml', 'yml', 'html', 'xml', 'py', 'js', 'ts'):
        try:
            text = content.decode('utf-8', errors='replace')
            truncated = text[:12000] + ("\n\n[...truncated...]" if len(text) > 12000 else "")
            return {"success": True, "text": truncated}
        except Exception as e:
            return {"success": False, "error": str(e)}

    return {"success": False, "error": f"Unsupported file type: .{ext}"}


# ── System Prompt Builder ────────────────────────────────────────────────────

BASE_SYSTEM = """You are Aether AI, an advanced AI assistant — intelligent, calm, and slightly warm.

Your rules:
- Be clear, structured, and helpful at all times
- Explain step-by-step when the topic is complex
- Use simple language for complex topics  
- Format answers using **headings** and bullet points where appropriate
- For code questions: give clean, well-commented code with an explanation
- Be polite and slightly conversational — smart but never robotic

Your personality:
- Precise, thoughtful, and direct
- Slightly friendly — not cold, not casual
- Always prioritize accuracy and clarity

Formatting:
- Use markdown headings (##, ###), bullet points, and **bold** for emphasis
- Wrap all code in fenced code blocks with the language specified
- Use numbered lists for step-by-step instructions"""

def build_system_prompt(intent: dict, file_context: str | None = None) -> str:
    parts = [BASE_SYSTEM]

    if intent["tool"] == "math":
        parts.append("\n\n## Math Mode\nThe user has a math question. Show your work step by step. Use LaTeX-style notation when helpful (e.g. `x²`, `√n`). Verify your answer.")

    elif intent["tool"] == "code":
        action = intent.get("action", "general")
        if action == "explain":
            parts.append("\n\n## Code Explanation Mode\nExplain the provided code clearly: what it does, how it works, and any important patterns or gotchas. Use a top-down approach.")
        elif action == "fix":
            parts.append("\n\n## Bug Fix Mode\nIdentify bugs or errors in the code. Explain what's wrong, then provide a corrected version with comments highlighting the changes.")
        elif action == "optimize":
            parts.append("\n\n## Code Optimization Mode\nAnalyze the code for performance, readability, and best practices. Provide an improved version with explanations for each change.")
        else:
            parts.append("\n\n## Code Mode\nWhen writing code, always use proper syntax highlighting, add comments, and explain the key parts after the code block.")

    elif intent["tool"] == "summarize":
        parts.append("\n\n## Summarization Mode\nProvide a concise, well-structured summary. Use: a 1-2 sentence TL;DR, then key points as bullets, then a brief conclusion if needed.")

    if file_context:
        parts.append(f"\n\n## Uploaded File Context\nThe user has uploaded a file. Its contents are below. Answer the user's question based on this content:\n\n---\n{file_context}\n---")

    return "".join(parts)
