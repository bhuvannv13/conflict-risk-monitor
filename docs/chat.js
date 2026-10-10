/* Small, dependency-free chat assistant that runs entirely in the browser.
   No API keys, no server, no cost. Answers come from a local knowledge base. */
(function (global) {
  "use strict";

  const STOP = new Set("a an the is are was were be been of to in on for and or with what which who how does do did can could tell me about show give list your my you i it its this that there please any some".split(" "));

  function normalise(text) {
    return String(text || "").toLowerCase().normalize("NFKD").replace(/[̀-ͯ]/g, "");
  }

  function tokens(text) {
    return normalise(text).split(/[^\p{L}\p{N}]+/u).filter(t => t && !STOP.has(t));
  }

  /* TF-IDF index over {id, text} documents; search returns [{doc, score}] sorted by cosine score. */
  class Index {
    constructor(docs) {
      this.docs = docs;
      const df = new Map();
      this.vectors = docs.map(doc => {
        const tf = new Map();
        for (const t of tokens(doc.text)) tf.set(t, (tf.get(t) || 0) + 1);
        for (const t of tf.keys()) df.set(t, (df.get(t) || 0) + 1);
        return tf;
      });
      const n = docs.length;
      this.idf = new Map([...df].map(([t, c]) => [t, Math.log(1 + n / c)]));
      this.norms = this.vectors.map(tf => Math.sqrt([...tf].reduce((s, [t, c]) => s + (c * this.idf.get(t)) ** 2, 0)) || 1);
    }
    search(query, limit = 5) {
      const q = new Map();
      for (const t of tokens(query)) q.set(t, (q.get(t) || 0) + 1);
      const scored = this.vectors.map((tf, i) => {
        let dot = 0;
        for (const [t, c] of q) {
          const idf = this.idf.get(t);
          if (idf && tf.has(t)) dot += c * idf * tf.get(t) * idf;
        }
        return { doc: this.docs[i], score: dot / this.norms[i] };
      });
      return scored.filter(s => s.score > 0).sort((a, b) => b.score - a.score).slice(0, limit);
    }
  }

  function escapeHtml(text) {
    return String(text).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  /* options: {title, subtitle, avatar (svg markup), greeting, suggestions, answer(text) -> {html, suggestions}} */
  function createChat(options) {
    const root = document.createElement("div");
    root.className = "chat-root";
    root.innerHTML = `
      <button class="chat-launcher" type="button" aria-expanded="false" aria-controls="chat-panel">
        <span class="chat-launcher-avatar" aria-hidden="true">${options.avatar || ""}</span>
        <span class="chat-launcher-label">${escapeHtml(options.launcherLabel || "Ask me")}</span>
      </button>
      <section class="chat-panel" id="chat-panel" role="dialog" aria-label="${escapeHtml(options.title)}" hidden>
        <header class="chat-header">
          <span class="chat-header-avatar" aria-hidden="true">${options.avatar || ""}</span>
          <div><strong>${escapeHtml(options.title)}</strong><small>${escapeHtml(options.subtitle || "")}</small></div>
          <button class="chat-close" type="button" aria-label="Close chat">&times;</button>
        </header>
        <div class="chat-log" aria-live="polite"></div>
        <div class="chat-chips"></div>
        <form class="chat-form">
          <label class="chat-sr" for="chat-input">Your question</label>
          <input id="chat-input" class="chat-input" autocomplete="off" placeholder="${escapeHtml(options.placeholder || "Type a question…")}">
          <button class="chat-send" type="submit">Send</button>
        </form>
      </section>`;
    document.body.appendChild(root);

    const launcher = root.querySelector(".chat-launcher");
    const panel = root.querySelector(".chat-panel");
    const log = root.querySelector(".chat-log");
    const chips = root.querySelector(".chat-chips");
    const form = root.querySelector(".chat-form");
    const input = root.querySelector(".chat-input");
    let started = false;

    function add(html, who) {
      const bubble = document.createElement("div");
      bubble.className = "chat-msg chat-" + who;
      bubble.innerHTML = html;
      log.appendChild(bubble);
      log.scrollTop = log.scrollHeight;
    }

    function setChips(list) {
      chips.innerHTML = "";
      (list || []).slice(0, 5).forEach(label => {
        const chip = document.createElement("button");
        chip.type = "button";
        chip.className = "chat-chip";
        chip.textContent = label;
        chip.addEventListener("click", () => ask(label));
        chips.appendChild(chip);
      });
    }

    async function ask(text) {
      text = String(text || "").trim();
      if (!text) return;
      add(escapeHtml(text), "user");
      input.value = "";
      let reply;
      try { reply = await options.answer(text); }
      catch (error) { reply = { html: "Sorry, something went wrong while answering that." }; console.error(error); }
      add(reply.html, "bot");
      setChips(reply.suggestions || options.suggestions);
    }

    function open(show) {
      panel.hidden = !show;
      launcher.setAttribute("aria-expanded", String(show));
      root.classList.toggle("chat-open", show);
      if (show && !started) {
        started = true;
        add(options.greeting, "bot");
        setChips(options.suggestions);
      }
      if (show) input.focus();
    }

    launcher.addEventListener("click", () => open(panel.hidden));
    root.querySelector(".chat-close").addEventListener("click", () => open(false));
    form.addEventListener("submit", event => { event.preventDefault(); ask(input.value); });
    document.addEventListener("keydown", event => { if (event.key === "Escape" && !panel.hidden) open(false); });

    return { open: () => open(true), ask: text => { open(true); ask(text); } };
  }

  global.LocalChat = { Index, tokens, normalise, escapeHtml, createChat };
})(window);
