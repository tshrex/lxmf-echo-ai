import logging
import RNS

logging.basicConfig(
    level=RNS.LOG_VERBOSE,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("echo-ai")

def safe_json(obj):
    if isinstance(obj, bytes):
        try:
            return obj.decode("utf-8")
        except UnicodeDecodeError:
            return obj.hex()
    raise TypeError(f"Type {type(obj)} not serializable")
