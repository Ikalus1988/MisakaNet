
import re
with open("misakanet/search/engine.py") as f:
    t = f.read()
# Extract cache section
m = re.search(r"(# ── 分层缓存.*?)(?=__all__)", t, re.DOTALL)
cache = m.group(1)
t = t.replace(cache, "")  # remove from current pos
# Find CachedDoc class end and insert after it
class_end = t.find("@dataclass")
class_end = t.find("

", class_end) + 1
t = t[:class_end] + "
" + cache + t[class_end:]
open("misakanet/search/engine.py", "w").write(t)
print("fixed")
