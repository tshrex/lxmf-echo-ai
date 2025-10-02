import os
import time
import json
import logging
import RNS
import LXMF
import RNS.vendor.umsgpack as msgpack
import google.generativeai as ai
import base64
import struct

# ------------------ CONFIGURATION ------------------ #
CONFIG_DIR = os.path.expanduser("~/.nomadmb")
STORAGE_PATH = os.path.join(CONFIG_DIR, "storage")
IDENTITY_PATH = os.path.join(STORAGE_PATH, "echoidentity")
ANNOUNCE_PATH = os.path.join(STORAGE_PATH, "echoannounce")
DISPLAY_NAME = "Echo/AI"
# V1
ANNOUNCE_INTERVAL = 1800  # seconds

# API Key from environment variable or fallback
API_KEY = '' # os.getenv("GEMINI_API_KEY")
if not API_KEY:
    raise RuntimeError("Missing GEMINI_API_KEY environment variable.")
ai.configure(api_key=API_KEY)

# Ensure directories exist
os.makedirs(STORAGE_PATH, exist_ok=True)

# ------------------ LOGGING ------------------ #
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s",
                    handlers=[logging.StreamHandler()])
logger = logging.getLogger("echo-ai")

# ------------------ AI HANDLER ------------------ #

def safe_json(obj):
    """Safely serializes objects, handling bytes by encoding them to Base64."""
    if isinstance(obj, bytes):
        try:
            return obj.decode("utf-8")
        except UnicodeDecodeError:
            # Fallback to Base64 if UTF-8 fails
            return base64.b64encode(obj).decode("ascii")
    raise TypeError(f"Type {obj.__class__.__name__} not serializable")

def decode_telemetry_data(data):
    """
    Decodes specific binary blobs within the telemetry data structure,
    specifically the location data (key 2), using a Scaled Integer format.
    
    The format specification is: Signed 32-bit Integer (4-byte), scaled by 10^6.
    We assume Big-Endian byte order (>).
    """
    if not isinstance(data, dict):
        return data

    # Key 2 holds the location data array
    if 2 in data and isinstance(data[2], list):
        decoded_location = []
        for item in data[2]:
            if isinstance(item, bytes) and len(item) == 4:
                try:
                    # Unpack 4 bytes as a signed 32-bit integer (Big-Endian: >i)
                    scaled_int = struct.unpack(">i", item)[0]
                    
                    # Convert scaled integer to float coordinate (division by 1,000,000)
                    coordinate = scaled_int / 1000000.0
                    decoded_location.append(coordinate)
                except struct.error:
                    # If unpack fails, keep the original bytes representation
                    decoded_location.append(item)
                    logger.warning(f"Could not unpack 4-byte location blob: {item!r}")
            else:
                # Keep non-byte items (like the final timestamp/integer) as is
                decoded_location.append(item)
        data[2] = decoded_location
        
    return data

def ai_chatbot_reply(message_content, telemetry_data):
    # Prepares and sends the user query and decoded telemetry data to the Gemini API.
    model = ai.GenerativeModel("gemini-2.5-flash")
    chat = model.start_chat()
    
    # --- DECODE TELEMETRY BEFORE PROMPTING ---
    decoded_telemetry = decode_telemetry_data(telemetry_data.copy()) if telemetry_data else None
    
    preprompt =""
    
    if decoded_telemetry:
        try:
            # The telemetry string is now built from the *decoded* data
            telemetry_str = json.dumps(decoded_telemetry, indent=2, default=safe_json)
        except Exception:
            telemetry_str = str(decoded_telemetry)
            
        # Update the preprompt to reflect the already decoded location data
        preprompt = f"""
        You are the Echo/AI Assistant, running on the Reticulum mesh network.
        The user sent the following telemetry data. Note that all numerical sensor values (including GPS location)
        have already been decoded from their binary format into standard numbers (floats/integers): 
        {telemetry_str}. Use this information to inform your response.
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
        25 rns_transport (network transport stats & interfaces, keep as structured JSON object)
        Always be concise, helpful, and acknowledge the source of information if it comes from sensor data.
        """
    try:
        response = chat.send_message(preprompt + message_content)
        return response.text
    except Exception as e:
        logger.error(f"AI request failed: {e}")
        return "AI service unavailable right now."

# ------------------ LXMF HANDLER ------------------ #
def setup_identity():
    if os.path.isfile(IDENTITY_PATH):
        identity = RNS.Identity.from_file(IDENTITY_PATH)
        logger.info("Loaded identity from file")
    else:
        logger.info("No identity found, creating new one...")
        identity = RNS.Identity()
        identity.to_file(IDENTITY_PATH)
    return identity


def handle_incoming(message):
    telemetry_data = None
    source_hash_hex = RNS.hexrep(message.source_hash, delimit=False)
    username = source_hash_hex[:5]
    logger.info(f"Message from user {username}")
    try:
        content = message.content.decode("utf-8").strip()
        logger.info(f"Received message: {content}")
    except Exception as e:
        logger.error(f"Failed to decode message: {e}")
        return

    if LXMF.FIELD_TELEMETRY in message.fields:
        try:
            telemetry_data = msgpack.unpackb(message.fields[LXMF.FIELD_TELEMETRY], strict_map_key=False)
            RNS.log(f"Received Telemetry from {username}")
            RNS.log(f"Received fields data: {telemetry_data}", RNS.LOG_INFO)
        except Exception as e:
            logger.error(f"Error unpacking telemetry: {e}")

    if content:
        reply = ai_chatbot_reply(content, telemetry_data)
        send_message(source_hash_hex, reply)


def announce_now(dest):
    dest.announce()
    logger.info("Node announced.")


def send_message(destination_hash, message_content):
    try:
        destination_hash = bytes.fromhex(destination_hash)
    except Exception:
        logger.error("Invalid destination hash")
        return

    if len(destination_hash) != RNS.Reticulum.TRUNCATED_HASHLENGTH // 8:
        logger.error("Invalid destination hash length")
        return

    destination_identity = RNS.Identity.recall(destination_hash)
    if not destination_identity:
        logger.warning("Unknown identity, requesting path...")
        RNS.Transport.request_path(destination_hash)
        return

    lxmf_dest = RNS.Destination(destination_identity, RNS.Destination.OUT,
                                 RNS.Destination.SINGLE, "lxmf", "delivery")
    lxm = LXMF.LXMessage(lxmf_dest, local_destination, message_content,
                          title="Reply", desired_method=LXMF.LXMessage.DIRECT)
    lxm.try_propagation_on_fail = True

    try:
        message_router.handle_outbound(lxm)
        logger.info(f"Message sent to {destination_hash.hex()}")
    except Exception as e:
        logger.error(f"Send failed: {e}")


def announce_check():
    next_announce = int(time.time())
    if os.path.isfile(ANNOUNCE_PATH):
        try:
            with open(ANNOUNCE_PATH, "r") as f:
                next_announce = int(f.readline())
        except Exception:
            logger.warning("Failed to read announce file")

    if time.time() >= next_announce:
        with open(ANNOUNCE_PATH, "w") as f:
            f.write(str(int(time.time()) + ANNOUNCE_INTERVAL))
        announce_now(local_destination)

# ------------------ MAIN ------------------ #
logger.info("Starting Reticulum...")
reticulum = RNS.Reticulum(loglevel=RNS.LOG_INFO)

current_identity = setup_identity()
message_router = LXMF.LXMRouter(identity=current_identity, storagepath=CONFIG_DIR)
local_destination = message_router.register_delivery_identity(current_identity, display_name=DISPLAY_NAME)

message_router.register_delivery_callback(handle_incoming)
logger.info(f"LXMF Router ready on: {RNS.prettyhexrep(local_destination.hash)}")

while True:
    announce_check()
    time.sleep(10)
