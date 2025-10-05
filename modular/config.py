import os
from dotenv import load_dotenv

load_dotenv()

CONFIG_DIR = os.path.expanduser("~/.nomadmb")
STORAGE_PATH = os.path.join(CONFIG_DIR, "storage")
IDENTITY_PATH = os.path.join(STORAGE_PATH, "echoidentity")
ANNOUNCE_PATH = os.path.join(STORAGE_PATH, "echoannounce")
TELEMETRY_DB_PATH = os.path.join(STORAGE_PATH, "telemetry.db")
DISPLAY_NAME = "Echo/AI"
ANNOUNCE_INTERVAL = 1800  # seconds

os.makedirs(STORAGE_PATH, exist_ok=True)

API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    raise RuntimeError("Missing GEMINI_API_KEY environment variable.")