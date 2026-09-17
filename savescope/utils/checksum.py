import zlib
import hashlib
from typing import Union

def compute_crc32(data: bytes) -> int:
    return zlib.crc32(data) & 0xFFFFFFFF

def compute_adler32(data: bytes) -> int:
    return zlib.adler32(data) & 0xFFFFFFFF

def compute_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def compute_md5(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()
