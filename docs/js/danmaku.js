/**
 * MisakaNet Danmaku Feedback Wall (#513)
 * Opt-out friction sensor — users post where they got stuck.
 * Desktop: default ON, max 8-12 visible
 * Mobile: default OFF, max 3-5 visible
 * Data stored in localStorage (no backend required)
 */
(function () {
  'use strict';

  var STORAGE_KEY = 'misakanet_danmaku';
  var TOGGLE_KEY = 'misakanet_danmaku_enabled';
  var MAX_VISIBLE_DESKTOP = 10;
  var MAX_VISIBLE_MOBILE = 4;
  var SCROLL_SPEED = 0.4;
  var MAX_TEXT_LENGTH = 200;

  var BLOCK_PATTERNS = [
    /https?:\/\/\S+/i,
    /(?:sk-|ghp_|token|password|secret|api[_-]?key)/i,
    /(?:^|\s)(?:fuck|shit|bitch|asshole)(?:\s|$|!)/i,
    /(.)\1{10,}/
  ];

  function isMobile() { return window.innerWidth < 768; }

  function shouldFilter(text) {
    for (var i = 0; i < BLOCK_PATTERNS.length; i++) {
      if (BLOCK_PATTERNS[i].test(text)) return true;
    }
    return false;
  }

  function loadMessages() {
    try {
      var raw = localStorage.getItem(STORAGE_KEY);
      return raw ? JSON.parse(raw) : [];
    } catch (e) { return []; }
  }

  function saveMessages(msgs) {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(msgs)); }
    catch (e) { /* quota exceeded */ }
  }

  function addMessage(text) {
    var trimmed = text.trim().slice(0, MAX_TEXT_LENGTH);
    if (!trimmed || shouldFilter(trimmed)) return null;
    var msg = {
      id: 'dm_' + Date.now() + '_' + Math.random().toString(36).slice(2, 6),
      text: trimmed,
      lang: /[\u4e00-\u9fff]/.test(trimmed) ? 'zh' : 'en',
      status: 'visible',
      source: 'web',
      created_at: new Date().toISOString()
    };
    var msgs = loadMessages();
    msgs.push(msg);
    if (msgs.length > 100) msgs = msgs.slice(-100);
    saveMessages(msgs);
    return msg;
  }

  function isEnabled() {
    var stored = localStorage.getItem(TOGGLE_KEY);
    if (stored !== null) return stored === 'true';
    return !isMobile();
  }

  function setEnabled(val) { localStorage.setItem(TOGGLE_KEY, String(val)); }

  function createStyles() {
    var css = [
      '.dm-wall{position:fixed;inset:0;pointer-events:none;z-index:9998;overflow:hidden}',
      '.dm-wall *{pointer-events:auto}',
      '.dm-toggle{position:fixed;top:12px;right:12px;z-index:10001;background:rgba(10,16,30,.85);border:1px solid rgba(0,229,255,.3);border-radius:8px;padding:6px 14px;cursor:pointer;color:#e2e8f0;font-size:13px;font-family:Inter,sans-serif;backdrop-filter:blur(8px);transition:all .2s}',
      '.dm-toggle:hover{border-color:rgba(0,229,255,.6);background:rgba(0,229,255,.1)}',
      '.dm-input-wrap{position:fixed;bottom:16px;right:16px;z-index:10000;display:flex;gap:8px;align-items:center}',
      '.dm-input{background:rgba(10,16,30,.9);border:1px solid rgba(0,229,255,.25);border-radius:10px;padding:10px 14px;color:#e2e8f0;font-size:13px;width:240px;outline:none;font-family:Inter,sans-serif;backdrop-filter:blur(8px)}',
      '.dm-input::placeholder{color:rgba(255,255,255,.4)}',
      '.dm-input:focus{border-color:rgba(0,229,255,.5)}',
      '.dm-send{background:rgba(0,229,255,.15);border:1px solid rgba(0,229,255,.3);border-radius:8px;padding:8px 14px;color:#00e5ff;cursor:pointer;font-size:13px;font-family:Inter,sans-serif;white-space:nowrap}',
      '.dm-send:hover{background:rgba(0,229,255,.25)}',
      '.dm-bubble{position:absolute;white-space:nowrap;padding:4px 12px;background:rgba(10,16,30,.75);border:1px solid rgba(0,229,255,.15);border-radius:16px;color:rgba(255,255,255,.82);font-size:13px;font-family:Inter,sans-serif;backdrop-filter:blur(4px);will-change:transform;pointer-events:none}',
      '.dm-hint{position:fixed;bottom:56px;right:16px;z-index:9999;color:rgba(255,255,255,.4);font-size:11px;font-family:Inter,sans-serif;max-width:260px;text-align:right}',
      '.dm-hidden{display:none!important}'
    ].join('\n');
    var style = document.createElement('style');
    style.textContent = css;
    document.head.appendChild(style);
  }

  function spawnBubble(wall, msg) {
    var maxV = isMobile() ? MAX_VISIBLE_MOBILE : MAX_VISIBLE_DESKTOP;
    var existing = wall.querySelectorAll('.dm-bubble');
    if (existing.length >= maxV) existing[0].remove();

    var bubble = document.createElement('div');
    bubble.className = 'dm-bubble';
    bubble.textContent = msg.text;
    bubble.style.top = (Math.random() * 70 + 10) + '%';
    bubble.style.right = '-400px';
    wall.appendChild(bubble);

    var pos = window.innerWidth + 20;
    var w = bubble.offsetWidth || 200;
    function animate() {
      pos -= SCROLL_SPEED;
      bubble.style.transform = 'translateX(' + (pos - window.innerWidth) + 'px)';
      if (pos < -w - 50) { bubble.remove(); return; }
      requestAnimationFrame(animate);
    }
    requestAnimationFrame(animate);
  }

  function createUI(onToggle, onSend) {
    var toggle = document.createElement('button');
    toggle.className = 'dm-toggle';
    toggle.id = 'dm-toggle';
    toggle.textContent = isEnabled() ? '\uD83D\uDCAC Danmaku ON' : '\uD83D\uDCAC Danmaku OFF';
    toggle.addEventListener('click', function () {
      var next = !isEnabled();
      setEnabled(next);
      toggle.textContent = next ? '\uD83D\uDCAC Danmaku ON' : '\uD83D\uDCAC Danmaku OFF';
      onToggle(next);
    });
    document.body.appendChild(toggle);

    var wall = document.createElement('div');
    wall.className = 'dm-wall';
    wall.id = 'dm-wall';
    if (!isEnabled()) wall.classList.add('dm-hidden');
    document.body.appendChild(wall);

    var hint = document.createElement('div');
    hint.className = 'dm-hint';
    hint.id = 'dm-hint';
    hint.textContent = 'Vent, ask, or send an emoji. No secrets or personal info.';
    if (!isEnabled()) hint.classList.add('dm-hidden');
    document.body.appendChild(hint);

    var wrap = document.createElement('div');
    wrap.className = 'dm-input-wrap';
    wrap.id = 'dm-input-wrap';
    if (!isEnabled()) wrap.classList.add('dm-hidden');

    var input = document.createElement('input');
    input.className = 'dm-input';
    input.type = 'text';
    input.placeholder = 'Say where you got stuck...';
    input.maxLength = MAX_TEXT_LENGTH;

    var send = document.createElement('button');
    send.className = 'dm-send';
    send.textContent = 'Send';

    function doSend() {
      var msg = onSend(input.value);
      if (msg) { input.value = ''; spawnBubble(wall, msg); }
    }
    send.addEventListener('click', doSend);
    input.addEventListener('keydown', function (e) { if (e.key === 'Enter') doSend(); });

    wrap.appendChild(input);
    wrap.appendChild(send);
    document.body.appendChild(wrap);

    return { wall: wall, hint: hint, wrap: wrap };
  }

  function init() {
    if (window.self !== window.top) return;
    createStyles();
    var ui = createUI(
      function (enabled) {
        var wall = document.getElementById('dm-wall');
        var hint = document.getElementById('dm-hint');
        var wrap = document.getElementById('dm-input-wrap');
        if (enabled) {
          wall.classList.remove('dm-hidden');
          hint.classList.remove('dm-hidden');
          wrap.classList.remove('dm-hidden');
          loadMessages().slice(-20).forEach(function (m) { spawnBubble(wall, m); });
        } else {
          wall.classList.add('dm-hidden');
          hint.classList.add('dm-hidden');
          wrap.classList.add('dm-hidden');
          wall.innerHTML = '';
        }
      },
      function (text) { return addMessage(text); }
    );
    if (isEnabled()) {
      loadMessages().slice(-15).forEach(function (m) {
        setTimeout(function () { spawnBubble(ui.wall, m); }, Math.random() * 3000);
      });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else { init(); }

  window.MisakaNetDanmaku = { addMessage: addMessage, isEnabled: isEnabled, setEnabled: setEnabled };
})();
