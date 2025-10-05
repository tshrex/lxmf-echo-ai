from functools import partial
from .lxmf_handler import handle_incoming
from .utils import logger
import RNS, LXMF, time, os
from .config import CONFIG_DIR, IDENTITY_PATH, ANNOUNCE_INTERVAL
from .db import init_db

def setup_identity():
    if os.path.isfile(IDENTITY_PATH):
        return RNS.Identity.from_file(IDENTITY_PATH)
    identity = RNS.Identity()
    identity.to_file(IDENTITY_PATH)
    return identity

def main():
    init_db()
    logger.info("Starting Reticulum...")
    reticulum = RNS.Reticulum(loglevel=RNS.LOG_INFO)
    identity = setup_identity()
    router = LXMF.LXMRouter(identity=identity, storagepath=CONFIG_DIR)
    dest = router.register_delivery_identity(identity, display_name="Echo/AI")

    # Bind the two extra arguments here
    router.register_delivery_callback(
        partial(handle_incoming, local_destination=dest, message_router=router)
    )

    logger.info(f"LXMF Router ready on: {RNS.prettyhexrep(dest.hash)}")

    next_announce = 0
    while True:
        if time.time() >= next_announce:
            dest.announce()
            next_announce = time.time() + ANNOUNCE_INTERVAL
        time.sleep(10)

if __name__ == "__main__":
    main()
