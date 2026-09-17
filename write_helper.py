import base64
from pathlib import Path

def write_file(rel_path: str, b64_content: str):
    p = Path(rel_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(base64.b64decode(b64_content.strip()))
    print(f'Wrote {rel_path} ({p.stat().st_size} bytes)')
