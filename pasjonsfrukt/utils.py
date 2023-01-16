import re
from datetime import datetime


def date_of_episode(episode):
    date_iso_str = re.sub(r'\.\d*', "", episode['dateAdded'])
    try:
        return datetime.fromisoformat(date_iso_str)
    except ValueError:
        print("[ERROR] Invalid ISO date string")
        try:
            # Try again with just the date part
            return datetime.fromisoformat(episode['dateAdded'][:10])
        except ValueError:
            return datetime.now()
