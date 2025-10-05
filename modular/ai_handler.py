import time, google.generativeai as ai
from .config import API_KEY
from .db import serialize
from .utils import logger

ai.configure(api_key=API_KEY)

def build_prompt(history):
    if not history:
        return "You are Echo/AI Assistant. No telemetry available."
    
    lines = []
    for i, entry in enumerate(history):
        ts = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(entry['updated_at']))
        prefix = "NEWEST" if i == 0 else f"PREVIOUS {i}"
        lines.append(f"--- {prefix} ({ts}) ---\n{serialize(entry['data'])}\n")
    return (
        "You are the Echo/AI Assistant on the Reticulum mesh.\n"
        "Analyze trends in the sensor telemetry below.\n\n" + "\n".join(lines)
    )

def get_reply(message, history):
    try:
        model = ai.GenerativeModel("gemini-2.5-flash")
        chat = model.start_chat()
        response = chat.send_message(build_prompt(history) + message)
        return response.text
    except Exception as e:
        logger.error(f"AI request failed: {e}")
        return "AI service unavailable."
