"""Emit reviewed text source in bounded chunks for the authenticated Vercel connector.

Never include .env, storage, databases, local credentials, tests, or user documents.
The Korean font is fetched and verified during the server build.
"""
import json
import base64
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
files = []
roots = [root / "web/src", root / "server/app"]
selected = [p for base in roots for p in base.rglob("*") if p.is_file() and "__pycache__" not in p.parts]
selected += [root / p for p in ("vercel.json", "web/package.json", "web/package-lock.json", "web/tsconfig.json", "web/next.config.ts", "web/postcss.config.mjs", "server/main.py", "server/requirements.txt", "server/.python-version", "server/scripts/fetch_font.py")]
for p in sorted(set(selected)):
    if p.suffix.lower() not in (".py", ".ps1", ".ts", ".tsx", ".json", ".css", ".mjs") and p.name != ".python-version" and p.name != "requirements.txt":
        continue
    files.append({"file": p.relative_to(root).as_posix(), "data": p.read_text(encoding="utf-8"), "encoding": "utf-8"})
asset = root / "server/app/assets/base.hwpx"
files.append({"file": "server/app/assets/base.hwpx", "data": base64.b64encode(asset.read_bytes()).decode("ascii"), "encoding": "base64"})
files.append({"file": "server/certs/supabase.crt", "data": (root / "server/certs/supabase.crt").read_text(encoding="utf-8"), "encoding": "utf-8"})
encoded = json.dumps(files, ensure_ascii=False)
chunks = [encoded[i:i + 10000] for i in range(0, len(encoded), 10000)]
if len(sys.argv) == 1:
    print(json.dumps({"chunks": len(chunks), "files": len(files)}))
else:
    print(json.dumps(chunks[int(sys.argv[1])], ensure_ascii=False))
