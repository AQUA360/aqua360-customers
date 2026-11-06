import re
import uuid
from datetime import datetime

BATCH_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
MAX_BATCH_ITEMS = 1000


def generate_batch_id(batch_type_token: str) -> str:
    """
    Identificador únic compatible:
    1-64 caràcters [A-Za-z0-9._-].
    """
    raw = re.sub(r"[^A-Za-z0-9]", "", batch_type_token or "")[:3].upper() or "SB"
    stamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    suffix = uuid.uuid4().hex[:8]
    batch_id = f"{raw}-{stamp}-{suffix}"
    if not BATCH_ID_RE.match(batch_id):
        raise ValueError(f"batch_id invàlid generat: {batch_id}")
    return batch_id


def chunked(sequence, size=MAX_BATCH_ITEMS):
    seq = list(sequence)
    for i in range(0, len(seq), size):
        yield seq[i : i + size]
