/* ─────────────────────────────────────────
   writeup_detail.js
   Place at:  yourapp/static/js/writeup_detail.js
   Depends on: highlight.js loaded before this script
───────────────────────────────────────── */

(function () {
  'use strict';

  /**
   * For every <pre><code> block inside .md-render:
   * 1. Detect the language from the class name (e.g. "language-python")
   * 2. Inject a .code-header bar above the <pre> with the lang label + copy button
   * 3. Run highlight.js on the code block
   */
  function initCodeBlocks() {
    const article = document.getElementById('md-content');
    if (!article) return;

    article.querySelectorAll('pre').forEach(function (pre) {
      const code = pre.querySelector('code');
      if (!code) return;

      // ── Detect language ──
      const cls   = code.className || '';
      const match = cls.match(/language-(\w+)/);
      const lang  = match ? match[1] : 'text';

      // ── Build header ──
      const header = document.createElement('div');
      header.className = 'code-header';

      const langLabel = document.createElement('span');
      langLabel.className = 'code-lang';
      langLabel.textContent = lang;

      const copyBtn = document.createElement('button');
      copyBtn.className  = 'code-copy';
      copyBtn.textContent = 'copy';
      copyBtn.setAttribute('aria-label', 'Copy code to clipboard');

      copyBtn.addEventListener('click', function () {
        const text = code.innerText;
        if (!navigator.clipboard) {
          fallbackCopy(text);
          flashCopied(copyBtn);
          return;
        }
        navigator.clipboard.writeText(text).then(function () {
          flashCopied(copyBtn);
        }).catch(function () {
          fallbackCopy(text);
          flashCopied(copyBtn);
        });
      });

      header.appendChild(langLabel);
      header.appendChild(copyBtn);

      // ── Wrap <pre> so the header sits outside it ──
      const wrapper = document.createElement('div');
      wrapper.className = 'code-block-wrapper';
      pre.parentNode.insertBefore(wrapper, pre);
      wrapper.appendChild(header);
      wrapper.appendChild(pre);

      // ── Syntax highlight ──
      if (typeof hljs !== 'undefined') {
        hljs.highlightElement(code);
      }
    });
  }

  /** Briefly change button label to "copied!" then revert */
  function flashCopied(btn) {
    btn.textContent = 'copied!';
    btn.classList.add('copied');
    setTimeout(function () {
      btn.textContent = 'copy';
      btn.classList.remove('copied');
    }, 1800);
  }

  /** Fallback for browsers without clipboard API */
  function fallbackCopy(text) {
    var ta = document.createElement('textarea');
    ta.value = text;
    ta.style.cssText = 'position:fixed;opacity:0;top:0;left:0';
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    try { document.execCommand('copy'); } catch (e) {}
    document.body.removeChild(ta);
  }

  // Run after DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initCodeBlocks);
  } else {
    initCodeBlocks();
  }
})();