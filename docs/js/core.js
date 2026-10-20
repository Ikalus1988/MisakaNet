/**
 * MisakaNet Frontend Core — 类型安全 + 错误边界 + XSS 净化
 * 提供 ESM / CommonJS / 浏览器全局变量三种加载方式
 */

/**
 * @typedef {Object} Lesson
 * @property {string} id
 * @property {string} domain
 * @property {string} title
 * @property {string} [summary]
 * @property {string[]} [tags]
 * @property {string} [url]
 */

/**
 * 安全异步加载并校验 Lessons 数据
 * @param {string} url
 * @param {Function} [errorUI]
 * @returns {Promise<Array>}
 */
export async function safeFetchLessons(url, errorUI) {
  try {
    const response = await fetch(url);
    if (!response.ok) throw new Error('HTTP ' + response.status);
    const data = await response.json();
    if (!Array.isArray(data)) throw new TypeError('lessons.json root must be an Array');
    return data.filter(function(l) {
      return l && typeof l.title === 'string' && typeof l.domain === 'string';
    });
  } catch (err) {
    console.error('MisakaNet Frontend Shield: Lessons load blocked \u2014', err.message);
    if (typeof errorUI === 'function') errorUI(err.message);
    return [];
  }
}

// The alert mark, drawn rather than typed. The emoji was a colour bitmap chosen by the
// platform, and the rest of the site's icons are SVG (scripts/site_icons.py, #3541 batch Y) — one
// icon system means one way to be wrong, and one place to be right.
const ALERT_ICON = '<svg class="ico" viewBox="0 0 24 24" aria-hidden="true"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/><path d="M12 9v4"/><path d="M12 17h.01"/></svg>';

/**
 * 构建降级 UI HTML
 * @param {string} message
 * @returns {string}
 */
export function buildErrorHTML(message) {
  var safeMsg = encodeURIComponent(String(message));
  return '<div style="border:1px solid #ff4d4f;padding:12px;margin:8px;background:rgba(255,77,79,0.08);border-radius:8px;">' +
    '<div style="color:#ff4d4f;font-weight:600;font-size:13px;">' + ALERT_ICON + ' Frontend Shield: Data Parse Blocked</div>' +
    '<div style="color:#8b949e;font-size:11px;margin-top:4px;">The intelligence feed contains anomalies or failed to load.</div>' +
    '<code style="color:#ff4d4f;font-size:10px;">' + safeMsg + '</code></div>';
}

/**
 * 验证 Lesson 对象
 * @param {*} obj
 * @returns {boolean}
 */
export function isValidLesson(obj) {
  return obj && typeof obj.title === 'string' && typeof obj.domain === 'string';
}

// ── 浏览器全局挂载 & CommonJS 兼容 ──
(function() {
  'use strict';

  // Expose globally (browser: window, Node: globalThis)
  var root = typeof window !== 'undefined' ? window : globalThis;
  root.MisakaCore = {
    safeFetchLessons,
    buildErrorHTML,
    isValidLesson
  };

  // CommonJS export (for vitest with node environment)
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = { safeFetchLessons, buildErrorHTML, isValidLesson };
  }
})();
