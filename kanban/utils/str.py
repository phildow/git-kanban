
import re

def kebab_case(s: str) -> str:
    """Convert free-form title text into a kebab-case filename slug."""
    # strip leading and trailing whitespace
    s = s.strip()
    # remove any characters that are not alphanumeric, spaces, underscores, or hyphens
    s = re.sub(r"[^a-zA-Z0-9\s_\-]", "", s)
    # replace spaces, underscores, and hyphens with a single space
    s = re.sub(r"[\s_\-]+", " ", s)
    # replace spaces with a single hyphen
    s = s.replace(" ", "-")
    # remove any characters that are not alphanumeric or hyphens
    # s = re.sub(r"[^a-zA-Z0-9\-]", "", s)
    # convert to lowercase and strip leading/trailing hyphens
    s = s.lower().strip("-")
    
    if not s:
        raise ValueError("Title must contain at least one alphanumeric character")
    return s