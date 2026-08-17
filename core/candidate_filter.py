def deduplicate_lessons(items):
    seen = set()
    unique = []
    for item in items:
        key = (item.get('title'), item.get('source_url'))
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique