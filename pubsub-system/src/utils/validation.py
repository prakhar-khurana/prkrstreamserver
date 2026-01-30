import re


def validate_topic_name(name: str) -> bool:
    if not name or len(name) > 255:
        return False
    if not re.match(r'^[a-zA-Z0-9_\-\.]+$', name):
        return False
    return True
