import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

with open(r"C:\Users\EDIKLE~1\AppData\Local\Temp\save_body.html", encoding="utf-8") as f:
    html = f.read()

rows = re.findall(r"<tr.*?</tr>", html, re.S)

current_category = None
for r in rows:
    text = re.sub(r"<[^>]+>", "|", r)
    text = re.sub(r"&nbsp;", "", text)
    parts = [p.strip() for p in text.split("|") if p.strip()]
    if not parts:
        continue
    if parts == ["Rank", "Player", "Member ID", "Points"]:
        continue
    if len(parts) <= 2 and not parts[0].isdigit():
        current_category = parts[0]
        print(f"\n=== {current_category} ===")
        continue
    if parts[0].isdigit():
        print(" | ".join(parts))
