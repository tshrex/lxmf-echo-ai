import struct
from .utils import logger

def decode(data):
    if not isinstance(data, dict):
        return data
    if 2 in data and isinstance(data[2], list):
        decoded = []
        for item in data[2]:
            if isinstance(item, bytes) and len(item) == 4:
                try:
                    decoded.append(struct.unpack(">i", item)[0] / 1_000_000)
                except struct.error:
                    logger.warning(f"Bad 4-byte location: {item!r}")
                    decoded.append(item)
            else:
                decoded.append(item)
        data[2] = decoded
    return data
