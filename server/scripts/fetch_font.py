"""Fetch a verified redistributable Korean font during the cloud build."""
import hashlib
from pathlib import Path
from urllib.request import urlopen

dest = Path(__file__).resolve().parents[1] / "fonts"
dest.mkdir(exist_ok=True)
url = "https://raw.githubusercontent.com/google/fonts/main/ofl/nanumgothic/"
for name in ("NanumGothic-Regular.ttf", "OFL.txt"):
    with urlopen(url + name, timeout=30) as response:
        data = response.read(3 * 1024 * 1024)
    if name.endswith(".ttf") and hashlib.sha256(data).hexdigest() != "76f45ef4a6bcff344c837c95a7dcc26e017e38b5846d5ae0cdcb5b86be2e2d31":
        raise RuntimeError("Font digest mismatch; refusing unverified asset.")
    (dest / name).write_bytes(data)
print("Verified Korean font installed.")
