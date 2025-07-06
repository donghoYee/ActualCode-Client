import pickle
import os
import time
import logging


def load_messages(file_path: str) -> list:
    startTime = time.time()
    if not os.path.exists(file_path): return []
    with open(file_path, "rb") as f:
        messages = pickle.load(f)
        logging.warning(f"loading messages took {time.time() - startTime}")
        return messages


def save_messages(file_path: str, messages: list) -> None:
    startTime = time.time()
    with open(file_path, "wb") as f:
        pickle.dump(messages, f)
        logging.warning(f"saving messages to disk took {time.time() - startTime}")
        return 