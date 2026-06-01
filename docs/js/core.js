/**
 * MisakaNet Frontend Core — 类型安全 + 错误边界 + XSS 净化
 * 双模加载：vitest 中 import，浏览器中 <script> 加载为全局变量
 */
(function() {
  'use strict';

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
  async function safeFetchLessons(url, errorUI) {
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

  /**
   * 构建降级 UI HTML
   * @param {string} message
   * @returns {string}
   */
  function buildErrorHTML(message) {
    var safeMsg = encodeURIComponent(String(message));
    return '<div style="border:1px solid #ff4d4f;padding:12px;margin:8px;background:rgba(255,77,79,0.08);border-radius:8px;">' +
      '<div style="color:#ff4d4f;font-weight:600;font-size:13px;">\u26a0\ufe0f Frontend Shield: Data Parse Blocked</div>' +
      '<div style="color:#8b949e;font-size:11px;margin-top:4px;">The intelligence feed contains anomalies or failed to load.</div>' +
      '<code style="color:#ff4d4f;font-size:10px;">' + safeMsg + '</code></div>';
  }

  /**
   * 验证 Lesson 对象
   * @param {*} obj
   * @returns {boolean}
   */
  function isValidLesson(obj) {
    return obj && typeof obj.title === 'string' && typeof obj.domain === 'string';
  }

  // Expose globally (browser: window, Node: globalThis)
  var root = typeof window !== 'undefined' ? window : globalThis;
  root.MisakaCore = {
    safeFetchLessons: safeFetchLessons,
    buildErrorHTML: buildErrorHTML,
    isValidLesson: isValidLesson
  };

  // CommonJS / ES module export (for vitest)
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = { safeFetchLessons: safeFetchLessons, buildErrorHTML: buildErrorHTML, isValidLesson: isValidLesson };
  }
})();
