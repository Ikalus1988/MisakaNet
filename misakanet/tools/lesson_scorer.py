import sqlite3
from pathlib import Path

from misakanet.search.engine import _tokenize

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TELEMETRY = REPO_ROOT / ".cache" / "langchain_telemetry.db"
DEFAULT_LESSONS = REPO_ROOT / "lessons" / "contrib"


def _read_queries(telemetry_path: str | Path) -> list[str]:
    path = Path(telemetry_path)
    if not path.exists():
        return []

    conn = None
    try:
        conn = sqlite3.connect(path)
        rows = conn.execute(
            "SELECT query FROM search_telemetry WHERE query IS NOT NULL"
        ).fetchall()
    except sqlite3.Error:
        return []
    finally:
        if conn is not None:
            conn.close()

    return [str(row[0]).strip() for row in rows if str(row[0]).strip()]


def _lesson_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _query_matches_lesson(query: str, lesson_tokens: set[str]) -> bool:
    query_tokens = {token for token in _tokenize(query) if token}
    if not query_tokens:
        return False
    return bool(query_tokens & lesson_tokens)


def score_lessons(
    telemetry_path: str | Path = DEFAULT_TELEMETRY,
    *,
    lessons_dir: str | Path = DEFAULT_LESSONS,
) -> list[dict]:
    queries = _read_queries(telemetry_path)
    lesson_root = Path(lessons_dir)
    lessons = sorted(lesson_root.glob("*.md")) if lesson_root.exists() else []
    total_queries = len(queries)
    scored = []

    for lesson_path in lessons:
        content = _lesson_text(lesson_path)
        lesson_tokens = {
            token for token in _tokenize(f"{lesson_path.stem} {content}") if token
        }
        searches = sum(
            1 for query in queries if _query_matches_lesson(query, lesson_tokens)
        )
        score = searches / total_queries if total_queries else 0.0
        scored.append(
            {
                "lesson": lesson_path.name,
                "score": round(score, 4),
                "searches": searches,
            }
        )

    scored.sort(key=lambda item: (-item["score"], -item["searches"], item["lesson"]))
    return scored


def format_lesson_scores(scores: list[dict], *, limit: int | None = None) -> str:
    rows = scores[:limit] if limit is not None else scores
    if not rows:
        return "No lessons found."

    lesson_width = min(max(len("lesson"), *(len(row["lesson"]) for row in rows)), 64)
    lines = [
        f"{'lesson':<{lesson_width}}  {'score':>7}  {'searches':>8}",
        f"{'-' * lesson_width}  {'-' * 7}  {'-' * 8}",
    ]
    for row in rows:
        lesson = row["lesson"]
        if len(lesson) > lesson_width:
            lesson = lesson[: lesson_width - 3] + "..."
        lines.append(f"{lesson:<{lesson_width}}  {row['score']:>7.2f}  {row['searches']:>8}")
    return "\n".join(lines)
