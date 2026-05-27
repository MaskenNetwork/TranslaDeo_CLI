import csv
import logging
import os
from typing import List


def load_video_ids(path: str) -> List[str]:
    if not os.path.exists(path):
        logging.error("Video IDs file not found: %s", path)
        return []

    ids: List[str] = []
    with open(path, "r", encoding="utf-8") as csv_file:
        reader = csv.reader(csv_file)
        next(reader, None)
        for row in reader:
            if row and row[0].strip():
                ids.append(row[0].strip())

    logging.info("Found %s video IDs to process.", len(ids))
    return ids
