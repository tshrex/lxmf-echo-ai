import os
from dotenv import load_dotenv
import time
import json
import logging
import sqlite3
import RNS
import LXMF
import RNS.vendor.umsgpack as msgpack
import google.generativeai as ai
import base64
import struct

# ------------------ CONFIGURATION ------------------ #
# V1.2.0 - Updated to support telemetry history
CONFIG_DIR = os.path.expanduser("~/.nomadmb")
STORAGE_PATH = os.path.join(CONFIG_DIR, "storage")
IDENTITY_PATH = os.path.join(STORAGE_PATH, "echoidentity")
ANNOUNCE_PATH = os.path.join(STORAGE_PATH, "echoannounce")
TELEMETRY_DB_PATH = os.path.join(STORAGE_PATH, "telemetry.db")
DISPLAY_NAME = "Echo/AI"
ANNOUNCE_INTERVAL = 1800  # seconds

# API Key from environment variable or fallback
load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    raise RuntimeError("Missing GEMINI_API_KEY environment variable.")
ai.configure(api_key=API_KEY)

# Ensure directories exist
os.makedirs(STORAGE_PATH, exist_ok=True)

# ------------------ LOGGING ------------------ #
logging.basicConfig(level=RNS.LOG_VERBOSE, # Changed to LOG_VERBOSE for better debugging of SQLite operations
                    format="%(asctime)s [%(levelname)s] %(message)s",
                    handlers=[logging.StreamHandler()])
logger = logging.getLogger("echo-ai")

# The global DB_CONN is removed to fix threading issues.
# Each database operation will now create its own connection.

# ------------------ JSON SERIALIZATION HELPERS ------------------ #
def safe_json(obj):
    """Serializes objects, handling bytes by encoding them to hex or utf-8."""
    if isinstance(obj, bytes):
        try:
            # Try decoding as UTF-8 first (since many RNS fields are text)
            return obj.decode("utf-8")
        except UnicodeDecodeError:
            # Fallback to Hex encoding for binary data like hashes/IDs
            return obj.hex()
    # For any other unsupported types, raise an error as usual
    raise TypeError(f"Type {obj.__class__.__name__} not serializable")

def serialize_telemetry(telemetry_data):
    """
    Centralized serialization function to ensure all bytes are handled 
    before saving to the database.
    """
    # Use the 'default=safe_json' parameter to catch any remaining bytes objects 
    # that haven't been handled by decode_telemetry_data
    return json.dumps(telemetry_data, default=safe_json)

# ------------------ DATABASE HANDLER ------------------ #

def get_db_connection():
    """Establishes and returns a new thread-local SQLite connection."""
    # This function is called within the thread that needs the connection.
    return sqlite3.connect(TELEMETRY_DB_PATH)

def init_db():
    """Initializes the SQLite database connection and creates the telemetry table."""
    try:
        # Use a temporary connection for initial setup
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # NOTE: Database schema updated to support history (AUTOINCREMENT ID)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS telemetry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_hash_hex TEXT NOT NULL,
                telemetry_json TEXT NOT NULL,
                updated_at REAL
            )
        """)
        conn.commit()
        conn.close()
        logger.info(f"Telemetry database initialized at {TELEMETRY_DB_PATH}")
    except sqlite3.Error as e:
        logger.error(f"SQLite database error during initialization: {e}")

def load_telemetry_history(source_hash_hex, limit=5):
    """
    Retrieves the latest N telemetry entries (including the timestamp) for a user.
    Returns a list of dictionaries [{'updated_at': time, 'data': {decoded_json}}, ...]
    """
    conn = None
    history = []
    try:
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row 
        cursor = conn.cursor()
        
        # Select the latest N entries for this user, ordered by timestamp
        cursor.execute("""
            SELECT telemetry_json, updated_at 
            FROM telemetry 
            WHERE source_hash_hex = ? 
            ORDER BY updated_at DESC 
            LIMIT ?
        """, (source_hash_hex, limit))
        
        rows = cursor.fetchall()
        
        for row in rows:
            try:
                # Deserialize the JSON string back into a Python dictionary/list
                telemetry_data = json.loads(row['telemetry_json'])
                history.append({
                    "updated_at": row['updated_at'],
                    "data": telemetry_data
                })
            except json.JSONDecodeError as e:
                # Log an error if a historical record fails to decode
                logger.error(f"JSON decode error when loading historic telemetry for {source_hash_hex}: {e}")
        
    except sqlite3.Error as e:
        logger.error(f"SQLite load history error for {source_hash_hex}: {e}")
    finally:
        if conn:
            conn.close()
    
    # Log the number of records found
    logger.info(f"Loaded {len(history)} historic telemetry entries for {source_hash_hex}.")
            
    return history

def save_telemetry(source_hash_hex, telemetry_data):
    """
    Saves the decoded telemetry data for a given source hash by appending a new record.
    Opens and closes a connection within the calling thread.
    """
    conn = None
    try:
        # 1. Serialize using the helper that handles remaining bytes
        telemetry_json = serialize_telemetry(telemetry_data)
        
        # 2. Open thread-local connection
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Use simple INSERT to add a new historical record
        cursor.execute("""
            INSERT INTO telemetry (source_hash_hex, telemetry_json, updated_at)
            VALUES (?, ?, ?)
        """, (source_hash_hex, telemetry_json, time.time()))
        
        conn.commit()
        # Logging success and size to help diagnose if data is being saved
        logger.info(f"Telemetry saved for {source_hash_hex}. Size: {len(telemetry_json)} bytes.")
        
    except sqlite3.Error as e:
        logger.error(f"SQLite save error for {source_hash_hex}: {e}")
    except Exception as e:
        # This will now catch the serialization error properly
        logger.error(f"General error during telemetry serialization/save for {source_hash_hex}: {e}")
    finally:
        if conn:
            conn.close()

# ------------------ AI HANDLER ------------------ #

def decode_telemetry_data(data):
    """
    Decodes specific binary blobs within the telemetry data structure,
    specifically the location data (key 2), using a Scaled Integer format.
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
                    # If unpack fails, keep the original bytes representation, 
                    # which will be handled by serialize_telemetry/safe_json later.
                    decoded_location.append(item)
                    logger.warning(f"Could not unpack 4-byte location blob: {item!r}")
            else:
                # Keep non-byte items (like the final timestamp/integer) as is
                decoded_location.append(item)
        data[2] = decoded_location
        
    return data

def ai_chatbot_reply(message_content, historic_telemetry_list):
    """
    Prepares and sends the user query and (potentially updated) telemetry data to the Gemini API.
    
    historic_telemetry_list: List of the last N telemetry points, newest first.
    """
    model = ai.GenerativeModel("gemini-2.5-flash")
    chat = model.start_chat()
    
    preprompt = ""
    
    if historic_telemetry_list:
        # Format the historical data into a readable string for the AI
        historic_data_str = ""
        current_data = historic_telemetry_list[0]
        
        # Iterate over all points, up to the limit
        for i, entry in enumerate(historic_telemetry_list):
            timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(entry['updated_at']))
            telemetry_json_str = serialize_telemetry(entry['data'])
            
            # The newest data is at index 0
            if i == 0:
                historic_data_str += f"--- NEWEST DATA ({timestamp}) ---\n"
                historic_data_str += f"{telemetry_json_str}\n"
            else:
                historic_data_str += f"--- PREVIOUS DATA POINT {i} ({timestamp}) ---\n"
                historic_data_str += f"{telemetry_json_str}\n"
                
        preprompt = f"""
        You are the Echo/AI Assistant, running on the Reticulum mesh network.
        The user's current sensor data and a history of the last few readings are provided below.
        look at the difference between the NEWEST DATA and PREVIOUS DATA POINT 1..2..etc to immediately spot trends.
        Analyze this data to answer the user's query, looking for trends or sudden changes in metrics like battery, light, or location.
        
        {historic_data_str}
        
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
        
        Always be concise, helpful, acknowledge the source of information if it comes from sensor data, and mention if a trend was observed.
        """
    else:
        # Fallback if no telemetry is ever loaded/saved
        preprompt = "You are the Echo/AI Assistant. No sensor data history is available for this user."

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
    
    new_telemetry_data = None
    source_hash_hex = RNS.hexrep(message.source_hash, delimit=False)
    username = source_hash_hex[:5]
    logger.info(f"Message from user {username}")
    
    # We no longer load *stored* telemetry initially, we fetch *history* later
    
    try:
        content = message.content.decode("utf-8").strip()
        logger.info(f"Received message: {content}")
    except Exception as e:
        logger.error(f"Failed to decode message: {e}")
        return

    # 2. Extract and Decode NEW Telemetry (if present)
    if LXMF.FIELD_TELEMETRY in message.fields:
        try:
            # Unpack the binary blob
            unpacked_data = msgpack.unpackb(message.fields[LXMF.FIELD_TELEMETRY], strict_map_key=False)
            RNS.log(f"Received Telemetry from {username}")
            
            # Decode the binary fields (like location)
            new_telemetry_data = decode_telemetry_data(unpacked_data)
            
            # FIX: Use serialize_telemetry to log the hex-encoded data instead of the raw Python dict
            logged_json_data = serialize_telemetry(new_telemetry_data)
            RNS.log(f"Decoded fields data: {logged_json_data}", RNS.LOG_INFO)

            # 3. SAVE the newly decoded data to the database
            # This call now establishes its own thread-safe connection and INSERTS a new record
            save_telemetry(source_hash_hex, new_telemetry_data)
            
        except Exception as e:
            logger.error(f"Error unpacking or decoding telemetry: {e}")
            
    # 4. Load the history (which will include the newest saved data if present)
    # The history list is what we pass to the AI now
    # This always loads the latest data from the DB, regardless of whether a new one just arrived.
    historic_telemetry_list = load_telemetry_history(source_hash_hex, limit=5)
            
    # 5. Reply using the history list
    if content:
        reply = ai_chatbot_reply(
            message_content=content, 
            historic_telemetry_list=historic_telemetry_list
        )
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
# 1. Initialize DB before starting Reticulum
init_db()

logger.info("Starting Reticulum...")
# RNS.Reticulum takes over the main thread's execution flow here
reticulum = RNS.Reticulum(loglevel=RNS.LOG_INFO)

current_identity = setup_identity()
message_router = LXMF.LXMRouter(identity=current_identity, storagepath=CONFIG_DIR)
local_destination = message_router.register_delivery_identity(current_identity, display_name=DISPLAY_NAME)

# LXMF callbacks (like handle_incoming) are executed in separate threads
message_router.register_delivery_callback(handle_incoming)
logger.info(f"LXMF Router ready on: {RNS.prettyhexrep(local_destination.hash)}")

while True:
    announce_check()
    time.sleep(10)