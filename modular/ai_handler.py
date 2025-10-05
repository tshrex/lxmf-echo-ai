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
        preprompt =f"""
        Keys are as follows:
        1 time.utc (UNIX timestamp, int32)
        2 location data (DECODED GPS coordinates: [latitude, longitude, altitude, ...])
        3 unused / null
        4 battery → [charge_percent (float), charging (bool), temperature (nullable float)]
        6 acceleration → [x, y, z] (float)
        7 unused
        8 unused
        9 magnetic_field → [x, y, z] (float)
        10 ambient_light.lux (float)
        11 gravity → [x, y, z] (float)
        12 angular_velocity → [x, y, z] (float)
        14 proximity (bool)
        15 information.contents (string)
        25 rns_transport (network transport stats & interfaces, keep as structured JSON object 
        (Reticulum distinguishes between two types of network nodes. 
        All nodes on a Reticulum network are Reticulum Instances, and some are also Transport Nodes)
        """
    return (
        "You are the Echo/AI Assistant on the Reticulum mesh.\n"
        "Analyze trends in the sensor telemetry below.\n\n" + "\n".join(lines).join(preprompt)
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
