import re
with open("misakanet/search/engine.py") as f:
    t = f.read()
m = re.search(r"(# ── 分层缓存.*?)(?=__all__)", t, re.DOTALL)
cache = m.group(1)
t = t.replace(cache, "")
# Find first function after CachedDoc class
func_start = t.find("def _parse_json_frontmatter")
t = t[:func_start] + "\n" + cache + "\n" + t[func_start:]
open("misakanet/search/engine.py", "w").write(t)
print("fixed")
