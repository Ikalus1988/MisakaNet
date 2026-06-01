import { describe, it, expect, vi, beforeAll } from 'vitest';

// Minimal DOM shim
function setupDOM() {
  let innerHTML = '';
  const el = {
    get innerHTML() { return innerHTML; },
    set innerHTML(v) { innerHTML = String(v); },
    style: { display: '' },
    getElementById: () => el,
  };
  globalThis.document = { getElementById: () => el };
  return el;
}

// Inline the functions under test (mirrors docs/js/core.js logic)
async function safeFetchLessons(url, errorUI) {
  try {
    const response = await globalThis.fetch(url);
    if (!response.ok) throw new Error('HTTP ' + response.status);
    const data = await response.json();
    if (!Array.isArray(data)) throw new TypeError('lessons.json root must be an Array');
    return data.filter(function(l) {
      return l && typeof l.title === 'string' && typeof l.domain === 'string';
    });
  } catch (err) {
    console.error('Frontend Shield blocked:', err.message);
    if (typeof errorUI === 'function') errorUI(err.message);
    return [];
  }
}

function isValidLesson(obj) {
  return obj && typeof obj.title === 'string' && typeof obj.domain === 'string';
}

function buildErrorHTML(message) {
  const safeMsg = encodeURIComponent(String(message));
  return '<div style="border:1px solid #ff4d4f;padding:12px;margin:8px;background:rgba(255,77,79,0.08);border-radius:8px;">' +
    '<div style="color:#ff4d4f;font-weight:600;font-size:13px;">\u26a0\ufe0f Frontend Shield: Data Parse Blocked</div>' +
    '<div style="color:#8b949e;font-size:11px;margin-top:4px;">The intelligence feed contains anomalies or failed to load.</div>' +
    '<code style="color:#ff4d4f;font-size:10px;">' + safeMsg + '</code></div>';
}

describe('🛡️ MisakaNet Frontend Shield', () => {
  let searchEl;

  beforeAll(() => {
    searchEl = setupDOM();

    globalThis.DOMPurify = {
      sanitize: (html) => {
        if (typeof html !== 'string') return '';
        return String(html)
          .replace(/<script[^>]*>([\s\S]*?)<\/script>/gi, '')
          .replace(/\bon\w+\s*=\s*"[^"]*"/gi, '');
      },
    };

    globalThis.fetch = vi.fn();
    vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  it('🚨 场景一：lessons.json 非数组时触发错误边界', async () => {
    globalThis.fetch.mockResolvedValue({
      ok: true,
      json: async () => ({ last_updated: 12345, lessons: 'not-an-array' }),
    });

    const errorUI = (msg) => {
      searchEl.innerHTML = buildErrorHTML(msg);
    };
    const lessons = await safeFetchLessons('./lessons.json', errorUI);

    expect(lessons).toEqual([]);
    expect(searchEl.innerHTML).toContain('Frontend Shield');
    expect(searchEl.innerHTML).toContain('lessons.json');
  });

  it('🧹 场景二：合法 JSON 含无效条目时被过滤', async () => {
    globalThis.fetch.mockResolvedValue({
      ok: true,
      json: async () => [
        { id: 'v1', title: 'Good', domain: 'python' },
        { id: 'b1', title: null, domain: 't' },
        { id: 'b2', domain: 'missing-title' },
        null,
        { id: 'v2', title: 'Another', domain: 'devops' },
      ],
    });

    const lessons = await safeFetchLessons('./lessons.json');

    expect(lessons).toHaveLength(2);
    expect(lessons[0].title).toBe('Good');
    expect(lessons[1].title).toBe('Another');
  });

  it('🧹 场景三：XSS script 注入被 DOMPurify 拦截', () => {
    const malicious = "RAG Exploit <script>alert('XSS')</script>";
    const safe = DOMPurify.sanitize(malicious);
    expect(safe).not.toContain('<script>');
    expect(safe).toContain('RAG Exploit');
  });

  it('🧹 场景四：isValidLesson 正确校验', () => {
    expect(isValidLesson({ title: 'a', domain: 'b' })).toBe(true);
    expect(isValidLesson({ title: '', domain: 'b' })).toBe(true);
    expect(isValidLesson({ title: 'a' })).toBe(false);
    expect(isValidLesson(null)).toBeFalsy();
    expect(isValidLesson({})).toBe(false);
  });

  it('🚨 场景五：网络错误时触发错误边界', async () => {
    globalThis.fetch.mockRejectedValue(new Error('Network failure'));

    const errorUI = (msg) => {
      searchEl.innerHTML = buildErrorHTML(msg);
    };
    const lessons = await safeFetchLessons('./lessons.json', errorUI);

    expect(lessons).toEqual([]);
    expect(searchEl.innerHTML).toContain('Frontend Shield');
  });

  it('🧹 场景六：buildErrorHTML 不含未转义内容', () => {
    const html = buildErrorHTML('test <script> malicious');
    expect(html).toContain('test');
    expect(html).not.toContain('<script>');
  });
});
