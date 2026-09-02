/**
 * Search handler — lesson search, fetch, and BM25 scoring.
 * Extracted from register-proxy-sw.js for maintainability.
 */

const GITHUB_API = "https://api.github.com";
const REPO = "Ikalus1988/MisakaNet";
const PUBLIC_DATA_BASE = "https://raw.githubusercontent.com/Ikalus1988/MisakaNet/main/data";

// ── BM25 Search ──

const BM25_K1 = 1.2;
const BM25_B = 0.75;

function tokenize(text) {
  return String(text || "")
    .toLowerCase()
    .replace(/[^a-z0-9一-鿿]+/g, " ")
    .split(/\s+/)
    .filter(Boolean);
}

function searchLessons(lessons, query, domain, top = 5) {
  if (!Array.isArray(lessons) || !query) return [];
  const queryTokens = tokenize(query);
  if (!queryTokens.length) return [];

  const filtered = domain
    ? lessons.filter((l) => (l.domain || "").toLowerCase() === domain.toLowerCase())
    : lessons;

  const docTokens = filtered.map((l) =>
    tokenize(`${l.title || ""} ${l.description || ""} ${l.domain || ""} ${(l.tags || []).join(" ")}`)
  );

  const avgDl = docTokens.reduce((sum, t) => sum + t.length, 0) / Math.max(docTokens.length, 1) || 1;
  const df = {};
  for (const term of queryTokens) {
    df[term] = docTokens.filter((dt) => dt.includes(term)).length;
  }
  const N = docTokens.length || 1;

  const scored = filtered.map((lesson, i) => {
    const dt = docTokens[i];
    const dl = dt.length;
    let score = 0;
    for (const term of queryTokens) {
      const tf = dt.filter((t) => t === term).length;
      if (!tf) continue;
      const idf = Math.log((N - (df[term] || 0) + 0.5) / ((df[term] || 0) + 0.5) + 1);
      score += (idf * tf * (BM25_K1 + 1)) / (tf + BM25_K1 * (1 - BM25_B + BM25_B * (dl / avgDl)));
    }
    return { lesson, score };
  });

  scored.sort((a, b) => b.score - a.score);
  return scored.slice(0, top).map(({ lesson, score }) => ({
    id: lesson.id || lesson.name || "",
    title: lesson.title || lesson.name || "",
    domain: lesson.domain || "",
    status: lesson.status || "",
    description: (lesson.description || "").slice(0, 200),
    path: lesson.path || "",
    score,
  }));
}

// ── Fetch lesson content from GitHub ──

async function fetchLessonContent(env, lessonPath, lessonId) {
  const token = env.REGISTER_TOKEN;
  if (!token) throw new Error("REGISTER_TOKEN not configured");
  let filePath = lessonPath;
  if (!filePath && lessonId) {
    const paths = [`lessons/core/${lessonId}.md`, `lessons/contrib/${lessonId}.md`, `lessons/_archive/${lessonId}.md`];
    const branches = ["main", "data"];
    for (const branch of branches) {
      for (const c of paths) {
        try {
          const url = `${GITHUB_API}/repos/${REPO}/contents/${c}?ref=${branch}`;
          const resp = await fetch(url, {
            headers: { Authorization: `Bearer ${token}`, "User-Agent": "MisakaNet-Worker", Accept: "application/vnd.github.v3+json" },
          });
          if (resp.ok) {
            const data = await resp.json();
            if (data.content && data.encoding === "base64") return { path: c, content: atob(data.content).slice(0, 5000) };
          }
        } catch {}
      }
    }
    throw new Error(`Lesson not found: ${lessonId}`);
  }
  if (!filePath) throw new Error("Missing path or id");
  for (const branch of ["main", "data"]) {
    const url = `${GITHUB_API}/repos/${REPO}/contents/${filePath}?ref=${branch}`;
    const resp = await fetch(url, {
      headers: { Authorization: `Bearer ${token}`, "User-Agent": "MisakaNet-Worker", Accept: "application/vnd.github.v3+json" },
    });
    if (resp.ok) {
      const data = await resp.json();
      if (data.content && data.encoding === "base64") return { path: filePath, content: atob(data.content).slice(0, 5000) };
    }
  }
  throw new Error(`Lesson not found: ${filePath}`);
}

// ── GitHub fetch helpers ──

async function fetchFromGitHub(token, path, ref = "data") {
  const url = `${PUBLIC_DATA_BASE}/${path}`;
  const headers = { "User-Agent": "MisakaNet-Worker" };
  if (token) headers.Authorization = `Bearer ${token}`;
  const resp = await fetch(url, { headers });
  if (!resp.ok) throw new Error(`GitHub fetch failed: ${resp.status} ${path}`);
  return resp.json();
}

const _cache = new Map();
async function getWithCache(env, cacheKey, fetchFn) {
  const ttl = 30_000;
  const cached = _cache.get(cacheKey);
  if (cached && Date.now() - cached.ts < ttl) return cached.data;
  const data = await fetchFn();
  _cache.set(cacheKey, { data, ts: Date.now() });
  if (_cache.size > 50) {
    const oldest = [..._cache.entries()].sort((a, b) => a[1].ts - b[1].ts)[0];
    if (oldest) _cache.delete(oldest[0]);
  }
  return data;
}

async function fetchPublicJson(path) {
  const url = `${PUBLIC_DATA_BASE}/${path}`;
  const resp = await fetch(url, { headers: { "User-Agent": "MisakaNet-Worker" } });
  if (!resp.ok) throw new Error(`Fetch failed: ${resp.status} ${path}`);
  return resp.json();
}

export {
  fetchFromGitHub,
  getWithCache,
  fetchPublicJson,
  GITHUB_API,
  REPO,
  PUBLIC_DATA_BASE,
};
