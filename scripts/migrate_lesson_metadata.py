"""批量补全 lessons 的 verified_date 和 domain_expert 字段"""
import json, os, re, sys

lessons_dir = sys.argv[1]
files = []
for root, dirs, fnames in os.walk(lessons_dir):
    dirs[:] = [d for d in dirs if d != '_archive']
    for f in fnames:
        if f.endswith('.md') and f not in ('index.md', 'TEMPLATE.md', 'README.md'):
            files.append(os.path.join(root, f))

updated = 0
for fp in sorted(files):
    text = open(fp, encoding='utf-8').read()
    m = re.search(r'^---\s*\n(\{.*?\})\s*\n---', text, re.DOTALL)
    if not m:
        continue
    fm = json.loads(m.group(1))

    dirty = False
    # domain_expert: fallback chain
    if not fm.get('domain_expert'):
        if fm.get('source'):
            fm['domain_expert'] = fm['source']
            dirty = True
        else:
            fm['domain_expert'] = 'unknown'
            dirty = True

    # verified_date: fallback chain
    if not fm.get('verified_date'):
        if fm.get('updated'):
            # 取 updated 日期部分 YYYY-MM-DD
            d = fm['updated'][:10] if fm['updated'] else ''
            if d:
                fm['verified_date'] = d
                dirty = True
        elif fm.get('created'):
            d = fm['created'][:10] if fm['created'] else ''
            if d:
                fm['verified_date'] = d
                dirty = True

    if dirty:
        new_fm = json.dumps(fm, ensure_ascii=False)
        text = text.replace(m.group(1), new_fm)
        open(fp, 'w', encoding='utf-8').write(text)
        updated += 1
        print(f"  ✓ {os.path.relpath(fp, lessons_dir)}")

print(f"\nDone. Updated {updated}/{len(files)} files.")
