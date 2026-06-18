import json, re
from pathlib import Path
for f in sorted(Path(__file__).resolve().parent.parent.joinpath('lessons').glob('**/*.md')):
    if any(x in str(f) for x in ['_archive','locales','TEMPLATE','README','index']): continue
    c = f.read_text()
    if not c.startswith('---'): continue
    end = c.index('---', 3)
    try: fm = json.loads(c[3:end].strip())
    except: continue
    eng = fm.get('title', '')
    if not eng: continue
    lines = c.split('\n')
    for i, line in enumerate(lines):
        if line.startswith('# ') and line[2:].strip() != eng.strip():
            lines[i] = '# ' + eng
            break
    f.write_text('\n'.join(lines), encoding='utf-8')
print('done')
