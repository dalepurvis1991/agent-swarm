import hashlib
import struct

DIM = 384  # Smaller, more reasonable size


def embed(text: str) -> list[float]:
    """Simple hash-based embedding for testing purposes.
    
    Creates a deterministic embedding without requiring external APIs.
    Uses multiple hash rounds for better distribution.
    """
    embeddings = []
    for i in range(DIM // 8):
        # Use text + index to get different hashes for each segment
        h = hashlib.sha256(f"{text}:{i}".encode()).digest()
        for j in range(8):
            val = struct.unpack(">I", h[j*4:(j+1)*4])[0]
            # Normalize to [-1,1] range
            embeddings.append((val / 2**32) * 2 - 1)
    return embeddings 