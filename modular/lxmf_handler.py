import RNS, LXMF, RNS.vendor.umsgpack as msgpack
from .db import save, load_history
from .telemetry import decode
from .ai_handler import get_reply
from .utils import logger


def handle_incoming(message, local_destination, message_router):
    source = RNS.hexrep(message.source_hash, delimit=False)
    logger.info(f"Message from {source[:5]}")
    try:
        text = message.content.decode("utf-8").strip()
    except Exception:
        logger.error("Could not decode message content.")
        return

    # Decode and save telemetry
    if LXMF.FIELD_TELEMETRY in message.fields:
        try:
            raw = msgpack.unpackb(message.fields[LXMF.FIELD_TELEMETRY], strict_map_key=False)
            decoded = decode(raw)
            save(source, decoded)
        except Exception as e:
            logger.error(f"Telemetry unpack error: {e}")

    # Load history and respond via AI
    history = load_history(source)
    if text:
        reply = get_reply(text, history)
        send_message(source, reply, local_destination, message_router)

def send_message(destination_hash, message_content, local_destination, message_router):
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
