def filter_candidates(tasks):
    return [t for t in tasks if t.get('attempts', 0) <= 5 and not t.get('saturated')][:10]