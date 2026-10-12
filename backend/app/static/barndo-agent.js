/*!
 * Barndo Build Assistant widget for barndobible.com
 * Embed:  <script src="https://API_HOST/widget/barndo-agent.js" defer></script>
 * Options (data- attributes on the script tag):
 *   data-api="https://API_HOST"   backend URL (defaults to where this script is served from)
 *   data-tab="estimate"           open on the estimator tab
 *   data-inline="#element-id"     render inside that element instead of as a floating button
 */
(function () {
  "use strict";
  if (window.__barndoAgentLoaded) return;
  window.__barndoAgentLoaded = true;

  var script = document.currentScript || document.querySelector('script[src*="barndo-agent.js"]');
  var API = ((script && script.getAttribute("data-api")) || (script ? new URL(script.src).origin : "")).replace(/\/$/, "");
  var START_TAB = (script && script.getAttribute("data-tab")) === "estimate" ? "estimate" : "ask";
  var INLINE = script && script.getAttribute("data-inline");
  var STORE_KEY = "barndo-agent-chat-v1";

  // Brand images, served from barndobible.com's own media library.
  var IMG = {
    avatar: "https://barndobible.com/wp-content/uploads/2026/09/BarndoBible.com-Avatar-Round.png",
    welcome: "https://barndobible.com/wp-content/uploads/2026/09/Barndominium-with-shop.jpg"
  };

  var STARTERS = [
    "What does a 40x60 barndominium cost to build?",
    "When does spray foam go in relative to electrical rough-in?",
    "What should I check before buying land for a barndo?"
  ];

  var CSS = [
    ":host{all:initial;font-family:inherit;color:#16283F;--navy:#16283F;--teal:#1FA79B;--teal-ink:#0E7A70;--mist:#F4FBFA;--rule:#D3E5E2;--white:#fff}",
    "*{box-sizing:border-box;font-family:inherit}",
    "button,input,select,textarea{font:inherit;color:inherit}",
    ":focus-visible{outline:3px solid var(--teal);outline-offset:2px}",
    ".launch{position:fixed;right:20px;bottom:20px;z-index:2147483000;display:flex;align-items:center;gap:10px;padding:8px 18px 8px 8px;border:0;border-radius:999px;background:var(--navy);color:var(--white);font-size:15px;font-weight:600;cursor:pointer;box-shadow:0 6px 20px rgba(22,40,63,.28)}",
    ".launch:hover{background:#1d3452}",
    ".launch svg{flex:none}",
    ".panel{position:fixed;right:20px;bottom:84px;z-index:2147483000;width:392px;height:min(640px,calc(100vh - 110px));display:flex;flex-direction:column;background:var(--mist);border:1px solid var(--rule);border-radius:10px;overflow:hidden;box-shadow:0 18px 48px rgba(22,40,63,.25)}",
    ".panel[hidden]{display:none}",
    ".inline .panel{position:static;width:100%;height:640px;box-shadow:none}",
    "@media (max-width:520px){.panel{right:0;left:0;bottom:0;top:0;width:auto;height:auto;border-radius:0;border:0}.launch{right:14px;bottom:14px}}",
    "header{background:var(--navy);color:var(--white);padding:14px 16px 0}",
    ".top{display:flex;align-items:center;justify-content:space-between;gap:8px}",
    ".title{font-size:16px;font-weight:700;margin:0}",
    ".who{display:flex;align-items:center;gap:10px}",
    ".avatar{width:38px;height:38px;border-radius:50%;flex:none;background:var(--teal) center/cover no-repeat;border:2px solid rgba(255,255,255,.85)}",
    ".launch .avatar{width:30px;height:30px;border-width:1.5px}",
    ".hero{position:relative;margin:-16px -16px 14px;height:150px;background:var(--navy) center 60%/cover no-repeat}",
    ".hero::after{content:'';position:absolute;inset:0;background:linear-gradient(180deg,rgba(22,40,63,0) 35%,rgba(22,40,63,.85) 100%)}",
    ".hero span{position:absolute;left:16px;right:16px;bottom:12px;z-index:1;color:#fff;font-weight:700;font-size:17px;line-height:1.25}",
    ".sub{font-size:12.5px;opacity:.8;margin:2px 0 0}",
    ".close{border:0;background:transparent;color:var(--white);width:34px;height:34px;border-radius:6px;cursor:pointer;font-size:22px;line-height:1}",
    ".close:hover{background:rgba(255,255,255,.12)}",
    ".tabs{display:flex;gap:4px;margin-top:12px}",
    ".tab{border:0;background:transparent;color:rgba(255,255,255,.78);padding:9px 12px 11px;font-size:14px;font-weight:600;cursor:pointer;border-bottom:3px solid transparent}",
    ".tab[aria-selected=true]{color:var(--white);border-bottom-color:var(--teal)}",
    ".view{flex:1;min-height:0;display:flex;flex-direction:column}",
    ".view[hidden]{display:none}",
    ".log{flex:1;overflow-y:auto;padding:16px;display:flex;flex-direction:column;gap:14px;font-size:14.5px;line-height:1.55}",
    ".msg p{margin:0 0 8px}.msg p:last-child{margin-bottom:0}.msg ul{margin:4px 0 8px;padding-left:20px}.msg li{margin:2px 0}",
    ".msg a{color:var(--teal-ink);font-weight:600}",
    ".msg.user{align-self:flex-end;max-width:85%;background:var(--navy);color:var(--white);padding:9px 13px;border-radius:12px 12px 2px 12px;white-space:pre-wrap}",
    ".msg.bot{align-self:stretch;padding-left:12px;border-left:3px solid var(--teal)}",
    ".msg.err{border-left-color:#B4432F;color:#7a2a1c}",
    ".srcs{margin-top:8px;font-size:12.5px;color:#4a5b6e}.srcs a{color:var(--teal-ink)}",
    ".empty{padding:4px 0}",
    ".empty h3{font-size:15px;margin:0 0 6px}.empty .hero+p{margin-top:0}.empty p{margin:0 0 12px;color:#3d4f63}",
    ".starter{display:block;width:100%;text-align:left;margin:0 0 8px;padding:10px 12px;background:var(--white);border:1px solid var(--rule);border-radius:8px;cursor:pointer;font-size:14px;color:var(--navy)}",
    ".starter:hover{border-color:var(--teal)}",
    ".typing{color:#4a5b6e;font-size:13.5px;padding-left:15px}",
    "@media (prefers-reduced-motion:no-preference){.typing::after{content:'';display:inline-block;width:1.2em;text-align:left;animation:dots 1.2s steps(4) infinite}@keyframes dots{0%{content:''}25%{content:'.'}50%{content:'..'}75%{content:'...'}}}",
    "form.composer{display:flex;gap:8px;padding:12px;border-top:1px solid var(--rule);background:var(--white)}",
    "textarea{flex:1;resize:none;min-height:44px;max-height:120px;padding:10px 12px;border:1px solid var(--rule);border-radius:8px;font-size:14.5px;line-height:1.4;background:var(--white)}",
    ".btn{border:0;background:var(--teal);color:var(--white);font-weight:700;padding:0 16px;border-radius:6px;cursor:pointer;font-size:14.5px;min-height:44px}",
    ".btn:hover{background:#17897f}.btn:disabled{opacity:.55;cursor:default}",
    ".fine{font-size:11.5px;color:#56677a;padding:0 12px 10px;background:var(--white);margin:0}",
    ".est{flex:1;overflow-y:auto;padding:16px;font-size:14px}",
    ".grid{display:grid;grid-template-columns:1fr 1fr;gap:10px 12px}",
    "label{display:flex;flex-direction:column;gap:4px;font-size:13px;font-weight:600}",
    "label small{font-weight:400;color:#56677a}",
    "input,select{padding:9px 10px;border:1px solid var(--rule);border-radius:6px;background:var(--white);font-size:14.5px;min-height:40px}",
    ".full{grid-column:1/-1}",
    ".est .btn{width:100%;margin-top:14px}",
    ".res{margin-top:18px}",
    ".elev{margin:0 0 14px;background:var(--white);border:1px solid var(--rule);border-radius:8px;padding:10px 10px 6px}",
    ".elev figcaption{font-size:12px;color:#56677a;margin-top:4px}",
    ".kpis{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:16px}",
    ".kpi{background:var(--white);border:1px solid var(--rule);border-radius:8px;padding:8px 10px}",
    ".kpi b{display:block;font-size:18px;color:var(--navy)}.kpi span{font-size:11.5px;color:#56677a}",
    ".sec h4{font-size:14px;margin:16px 0 6px;color:var(--navy)}",
    ".row{display:grid;grid-template-columns:1fr auto;gap:2px 10px;padding:7px 0;border-bottom:1px solid var(--rule)}",
    ".row .q{font-weight:700;text-align:right;white-space:nowrap}",
    ".row .n{grid-column:1/-1;font-size:12px;color:#56677a}",
    "details{margin-top:16px;background:var(--white);border:1px solid var(--rule);border-radius:8px;padding:10px 12px}",
    "summary{cursor:pointer;font-weight:600}",
    "details ul{margin:8px 0 0;padding-left:18px;font-size:13px;color:#3d4f63}",
    ".ask-link{margin-top:14px;font-size:13.5px}.ask-link button{border:0;background:none;color:var(--teal-ink);font-weight:700;cursor:pointer;padding:0;text-decoration:underline}"
  ].join("\n");

  // ------------------------------------------------------------ helpers
  function el(tag, attrs, kids) {
    var n = document.createElement(tag);
    if (attrs) for (var k in attrs) {
      if (k === "text") n.textContent = attrs[k];
      else if (k === "html") n.innerHTML = attrs[k];
      else if (k.slice(0, 2) === "on") n.addEventListener(k.slice(2), attrs[k]);
      else n.setAttribute(k, attrs[k]);
    }
    (kids || []).forEach(function (c) { if (c) n.appendChild(typeof c === "string" ? document.createTextNode(c) : c); });
    return n;
  }
  function esc(s) { return String(s).replace(/[&<>"']/g, function (c) { return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]; }); }
  function inline(s) {
    s = esc(s);
    s = s.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, function (_, t, u) {
      return '<a href="' + u + '" target="_blank" rel="noopener">' + t + "</a>";
    });
    s = s.replace(/(^|[\s(])(https?:\/\/[^\s<)]+)/g, function (_, pre, u) {
      return pre + '<a href="' + u + '" target="_blank" rel="noopener">' + u.replace(/^https?:\/\/(www\.)?/, "").replace(/\/$/, "") + "</a>";
    });
    return s.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  }
  // Minimal, safe markdown: paragraphs, "- " lists, **bold**, links. Everything else is escaped.
  function md(text) {
    var out = [], list = null;
    text.split(/\n/).forEach(function (line) {
      var m = line.match(/^\s*(?:[-*•]|\d+\.)\s+(.*)$/);
      if (m) { if (!list) { list = []; } list.push("<li>" + inline(m[1]) + "</li>"); return; }
      if (list) { out.push("<ul>" + list.join("") + "</ul>"); list = null; }
      if (line.trim()) out.push("<p>" + inline(line.replace(/^#+\s*/, "")) + "</p>");
    });
    if (list) out.push("<ul>" + list.join("") + "</ul>");
    return out.join("");
  }
  function load() { try { return JSON.parse(sessionStorage.getItem(STORE_KEY)) || []; } catch (e) { return []; } }
  function save(h) { try { sessionStorage.setItem(STORE_KEY, JSON.stringify(h.slice(-30))); } catch (e) {} }
  function fmt(n) { return Number(n).toLocaleString("en-US"); }

  function post(path, body) {
    return fetch(API + path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) })
      .then(function (r) {
        return r.json().catch(function () { return {}; }).then(function (j) {
          if (!r.ok) {
            var d = j && j.detail;
            throw new Error(typeof d === "string" ? d : "Something went wrong (" + r.status + "). Please try again.");
          }
          return j;
        });
      }, function () { throw new Error("Can't reach the assistant. Check your connection and try again."); });
  }

  // ------------------------------------------------------------ elevation drawing
  function elevation(w, h, pitch) {
    var rise = (w / 2) * pitch / 12, W = 300, H = 120, pad = 12;
    var scale = Math.min((W - pad * 2) / w, (H - pad * 2) / (h + rise));
    var bw = w * scale, bh = h * scale, br = rise * scale;
    var x0 = (W - bw) / 2, ground = H - pad;
    var pts = [[x0, ground], [x0, ground - bh], [x0 + bw / 2, ground - bh - br], [x0 + bw, ground - bh], [x0 + bw, ground]]
      .map(function (p) { return p[0].toFixed(1) + "," + p[1].toFixed(1); }).join(" ");
    var svg = '<svg viewBox="0 0 ' + W + " " + H + '" width="100%" role="img" aria-label="Gable end elevation, ' + w + " ft wide, " + h + " ft eave, " + pitch + '/12 pitch">' +
      '<line x1="0" y1="' + ground + '" x2="' + W + '" y2="' + ground + '" stroke="#D3E5E2" stroke-width="2"/>' +
      '<polygon points="' + pts + '" fill="#F4FBFA" stroke="#16283F" stroke-width="2" stroke-linejoin="round"/>' +
      '<line x1="' + x0 + '" y1="' + (ground - bh) + '" x2="' + (x0 + bw) + '" y2="' + (ground - bh) + '" stroke="#1FA79B" stroke-width="1.5" stroke-dasharray="4 4"/>' +
      '<text x="' + (x0 + bw / 2) + '" y="' + (ground - 6) + '" text-anchor="middle" font-size="11" fill="#16283F">' + w + " ft</text>" +
      '<text x="' + (x0 + bw + 6) + '" y="' + (ground - bh / 2) + '" font-size="11" fill="#16283F">' + h + " ft</text>" +
      '<text x="' + (x0 + bw / 2) + '" y="' + (ground - bh - br - 4) + '" text-anchor="middle" font-size="11" fill="#0E7A70">' + pitch + "/12</text></svg>";
    return el("figure", { class: "elev", html: svg + "<figcaption>Gable end, drawn to scale. The dashed line is the eave.</figcaption>" });
  }

  // ------------------------------------------------------------ build UI
  var host = el("div", { id: "barndo-agent" });
  var root = host.attachShadow({ mode: "open" });
  root.appendChild(el("style", { text: CSS }));
  var wrap = el("div", { class: INLINE ? "inline" : "" });
  root.appendChild(wrap);

  var roof = '<svg width="22" height="22" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"><path d="M3 11 12 4l9 7"/><path d="M5 10v10h14V10"/><path d="M10 20v-5h4v5"/></svg>';
  var launch = el("button", { class: "launch", type: "button", "aria-expanded": "false", "aria-controls": "ba-panel", html: '<span class="avatar" aria-hidden="true"></span><span>Ask BarndoBible</span>' });
  // Show the BarndoBible avatar; if it can't load, fall back to the roofline icon.
  (function () {
    var test = new Image();
    test.onload = function () { root.querySelectorAll(".avatar").forEach(function (a) { a.style.backgroundImage = "url(" + IMG.avatar + ")"; }); };
    test.onerror = function () { var a = launch.querySelector(".avatar"); if (a) a.outerHTML = roof; };
    test.src = IMG.avatar;
  })();

  var panel = el("section", { class: "panel", id: "ba-panel", role: "dialog", "aria-label": "Barndo Build Assistant" });
  if (!INLINE) panel.hidden = true;

  var closeBtn = el("button", { class: "close", type: "button", "aria-label": "Close assistant", text: "×" });
  var tabAsk = el("button", { class: "tab", type: "button", role: "tab", "aria-selected": "true", text: "Ask a question" });
  var tabEst = el("button", { class: "tab", type: "button", role: "tab", "aria-selected": "false", text: "Estimate materials" });
  var header = el("header", null, [
    el("div", { class: "top" }, [
      el("div", { class: "who" }, [el("span", { class: "avatar", "aria-hidden": "true" }),
        el("div", null, [el("p", { class: "title", text: "Barndo Build Assistant" }), el("p", { class: "sub", text: "Answers from the BarndoBible guides" })])]),
      INLINE ? null : closeBtn
    ]),
    el("div", { class: "tabs", role: "tablist" }, [tabAsk, tabEst])
  ]);

  // Ask view
  var log = el("div", { class: "log", "aria-live": "polite" });
  var input = el("textarea", { rows: "1", placeholder: "Ask about costs, plans, rough-in…", "aria-label": "Your question", maxlength: "2000" });
  var send = el("button", { class: "btn", type: "submit", text: "Send" });
  var composer = el("form", { class: "composer" }, [input, send]);
  var viewAsk = el("div", { class: "view", role: "tabpanel" }, [log, composer,
    el("p", { class: "fine", text: "AI answers can be wrong. Check with your county and a licensed pro before you build. Please don't share personal details." })]);

  // Estimate view
  function field(label, name, val, extra, hint) {
    var i = el("input", Object.assign({ name: name, type: "number", inputmode: "decimal", value: val, required: "" }, extra || {}));
    return el("label", null, [label + " ", hint ? el("small", { text: hint }) : null, i]);
  }
  function choice(label, name, opts) {
    var s = el("select", { name: name });
    opts.forEach(function (o) { s.appendChild(el("option", { value: o[0], text: o[1] })); });
    return el("label", null, [label, s]);
  }
  var estForm = el("form", { novalidate: "" }, [
    el("div", { class: "grid" }, [
      field("Width", "width_ft", "40", { min: "10", max: "200", step: "1" }, "ft, gable end"),
      field("Length", "length_ft", "60", { min: "10", max: "400", step: "1" }, "ft, sidewall"),
      field("Eave height", "eave_height_ft", "14", { min: "8", max: "30", step: "0.5" }, "ft"),
      field("Roof pitch", "roof_pitch", "3", { min: "0.5", max: "12", step: "0.5" }, "rise per 12"),
      el("label", { class: "full" }, ["Living area ", el("small", { text: "sq ft; leave blank if the whole building is living space" }),
        el("input", { name: "living_sqft", type: "number", inputmode: "numeric", min: "100", step: "50", placeholder: "e.g. 1800" })]),
      choice("Spray foam", "insulation", [["closed_cell", "Closed cell"], ["open_cell", "Open cell"]]),
      choice("Interior studs", "framing", [["wood", "Wood 2x4"], ["steel", "Steel"]])
    ]),
    el("button", { class: "btn", type: "submit", text: "Calculate materials" })
  ]);
  var estOut = el("div", { class: "res", "aria-live": "polite" });
  var viewEst = el("div", { class: "view", role: "tabpanel", hidden: "" }, [el("div", { class: "est" }, [
    el("p", { style: "margin:0 0 12px;color:#3d4f63", text: "Quantities for a rectangular, gable-roof metal building. Take them to your supplier to price." }),
    estForm, estOut])]);

  panel.appendChild(header); panel.appendChild(viewAsk); panel.appendChild(viewEst);
  if (!INLINE) wrap.appendChild(launch);
  wrap.appendChild(panel);

  // ------------------------------------------------------------ behaviour
  var history = load(), busy = false;

  function setTab(t) {
    var ask = t === "ask";
    tabAsk.setAttribute("aria-selected", ask); tabEst.setAttribute("aria-selected", !ask);
    viewAsk.hidden = !ask; viewEst.hidden = ask;
    (ask ? input : estForm.querySelector("input")).focus({ preventScroll: true });
  }
  tabAsk.addEventListener("click", function () { setTab("ask"); });
  tabEst.addEventListener("click", function () { setTab("estimate"); });

  function open(v) {
    panel.hidden = !v; launch.setAttribute("aria-expanded", v);
    if (v) setTab(viewEst.hidden ? "ask" : "estimate"); else launch.focus();
  }
  launch.addEventListener("click", function () { open(panel.hidden); });
  closeBtn.addEventListener("click", function () { open(false); });
  panel.addEventListener("keydown", function (e) { if (e.key === "Escape" && !INLINE) open(false); });

  function addMsg(role, text, sources, isErr) {
    var m = el("div", { class: "msg " + (role === "user" ? "user" : "bot") + (isErr ? " err" : "") });
    if (role === "user") m.textContent = text; else m.innerHTML = md(text);
    if (sources && sources.length) {
      var s = el("div", { class: "srcs" }, ["From: "]);
      sources.forEach(function (src, i) {
        if (i) s.appendChild(document.createTextNode(", "));
        s.appendChild(el("a", { href: src.url, target: "_blank", rel: "noopener", text: src.title }));
      });
      m.appendChild(s);
    }
    log.appendChild(m); log.scrollTop = log.scrollHeight;
  }
  function renderEmpty() {
    log.innerHTML = "";
    var hero = el("div", { class: "hero", role: "img", "aria-label": "Finished barndominium with an attached shop at dusk" }, [el("span", { text: "Planning a barndo or a home build?" })]);
    hero.style.backgroundImage = "url(" + IMG.welcome + ")";
    var box = el("div", { class: "empty" }, [
      hero,
      el("p", { text: "Ask anything about costs, floor plans, kits, land, rough-in or finish-out. Answers draw on BarndoBible's guides." })
    ]);
    STARTERS.forEach(function (q) { box.appendChild(el("button", { class: "starter", type: "button", text: q, onclick: function () { ask(q); } })); });
    log.appendChild(box);
  }
  function renderHistory() {
    if (!history.length) return renderEmpty();
    log.innerHTML = "";
    history.forEach(function (m) { addMsg(m.role, m.content, m.sources); });
  }

  function ask(q) {
    q = (q || "").trim();
    if (!q || busy) return;
    if (!history.length) log.innerHTML = "";
    busy = true; send.disabled = true; input.value = "";
    history.push({ role: "user", content: q });
    addMsg("user", q);
    var typing = el("div", { class: "typing", text: "Looking through the guides" });
    log.appendChild(typing); log.scrollTop = log.scrollHeight;
    var payload = history.map(function (m) { return { role: m.role, content: m.content }; });
    post("/public/chat", { messages: payload }).then(function (r) {
      typing.remove();
      history.push({ role: "assistant", content: r.reply, sources: r.sources });
      addMsg("assistant", r.reply, r.sources);
      save(history);
    }).catch(function (e) {
      typing.remove();
      history.pop(); // let them resend the same question
      addMsg("assistant", e.message, null, true);
      input.value = q;
    }).then(function () { busy = false; send.disabled = false; input.focus({ preventScroll: true }); });
  }
  composer.addEventListener("submit", function (e) { e.preventDefault(); ask(input.value); });
  input.addEventListener("keydown", function (e) { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); ask(input.value); } });
  input.addEventListener("input", function () { input.style.height = "auto"; input.style.height = Math.min(input.scrollHeight, 120) + "px"; });

  estForm.addEventListener("submit", function (e) {
    e.preventDefault();
    if (!estForm.checkValidity()) { estForm.reportValidity(); return; }
    var fd = new FormData(estForm), body = {};
    fd.forEach(function (v, k) { if (v !== "") body[k] = isNaN(v) ? v : Number(v); });
    var btn = estForm.querySelector(".btn"); btn.disabled = true; btn.textContent = "Calculating…";
    post("/public/estimate", body).then(function (r) { showEstimate(body, r); })
      .catch(function (err) { estOut.innerHTML = ""; estOut.appendChild(el("p", { class: "msg bot err", text: err.message })); })
      .then(function () { btn.disabled = false; btn.textContent = "Calculate materials"; });
  });

  function showEstimate(inp, r) {
    estOut.innerHTML = "";
    var s = r.summary;
    estOut.appendChild(elevation(inp.width_ft, inp.eave_height_ft, inp.roof_pitch));
    estOut.appendChild(el("div", { class: "kpis" }, [
      el("div", { class: "kpi", html: "<b>" + fmt(s.concrete_cy) + "</b><span>cu yd concrete</span>" }),
      el("div", { class: "kpi", html: "<b>" + fmt(s.metal_panel_area_sqft) + "</b><span>sq ft metal</span>" }),
      el("div", { class: "kpi", html: "<b>" + fmt(s.drywall_sheets) + "</b><span>drywall sheets</span>" })
    ]));
    Object.keys(r.sections).forEach(function (name) {
      var sec = el("div", { class: "sec" }, [el("h4", { text: name })]);
      r.sections[name].forEach(function (l) {
        sec.appendChild(el("div", { class: "row" }, [
          el("span", { text: l.item }), el("span", { class: "q", text: fmt(l.qty) + " " + l.unit }),
          l.note ? el("span", { class: "n", text: l.note }) : null
        ]));
      });
      estOut.appendChild(sec);
    });
    var d = el("details", null, [el("summary", { text: "How these were calculated" })]);
    var ul = el("ul"); r.assumptions.forEach(function (a) { ul.appendChild(el("li", { text: a })); });
    d.appendChild(ul); estOut.appendChild(d);
    estOut.scrollIntoView({ block: "start", behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
    estOut.appendChild(el("p", { class: "ask-link" }, [
      el("button", { type: "button", text: "Ask the assistant about this estimate", onclick: function () {
        setTab("ask");
        ask("I ran the material estimator for a " + inp.width_ft + "x" + inp.length_ft + " barndo with " + inp.eave_height_ft +
          " ft eaves at " + inp.roof_pitch + "/12" + (inp.living_sqft ? ", " + inp.living_sqft + " sq ft living" : "") +
          ". What should I watch out for when ordering these materials?");
      } })
    ]));
  }

  renderHistory();
  if (START_TAB === "estimate") { viewAsk.hidden = true; viewEst.hidden = false; tabAsk.setAttribute("aria-selected", "false"); tabEst.setAttribute("aria-selected", "true"); }

  function mount() {
    var target = INLINE ? document.querySelector(INLINE) : document.body;
    (target || document.body).appendChild(host);
  }
  if (document.body) mount(); else document.addEventListener("DOMContentLoaded", mount);
})();
