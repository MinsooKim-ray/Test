/* 인프라 OJT 가이드 — 정적 SPA (빌드 도구 없이 동작) */
(function () {
  "use strict";

  var STORE_KEY = "ojtGuide.v1";
  var D = null;
  var app = document.getElementById("app");

  /* ───────── storage (실패해도 동작) ───────── */
  function loadState() {
    try { return JSON.parse(localStorage.getItem(STORE_KEY)) || {}; } catch (e) { return {}; }
  }
  var state = loadState();
  state.checks = state.checks || {};
  state.memos = state.memos || {};
  function saveState() {
    try { localStorage.setItem(STORE_KEY, JSON.stringify(state)); } catch (e) { /* private mode 등 */ }
  }

  /* ───────── helpers ───────── */
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function list(items) {
    return "<ul>" + items.map(function (i) { return "<li>" + esc(i) + "</li>"; }).join("") + "</ul>";
  }
  function badgeFor(text) {
    var cls = /높음|장애|전환 중/.test(text) ? "danger" : /중간|POC|예정|진행/.test(text) ? "warn" : /운영 중|도입|기회/.test(text) ? "ok" : "accent";
    return '<span class="badge ' + cls + '">' + esc(text) + "</span>";
  }
  function header(title, lead) {
    return "<h1>" + esc(title) + "</h1>" + (lead ? '<p class="lead">' + esc(lead) + "</p>" : "");
  }

  /* ───────── views ───────── */
  var views = {};

  views.home = function () {
    var total = 0, done = 0;
    D.learning.forEach(function (p, pi) {
      p.items.forEach(function (_, ii) { total++; if (state.checks["learn-" + pi + "-" + ii]) done++; });
    });
    var pct = total ? Math.round(done / total * 100) : 0;
    var tiles = [
      ["principles", "🧭 핵심 원칙", "금융 IT에서 일하는 방식 6가지"],
      ["infra", "🏢 인프라 구조", "센터·망·핵심 수치"],
      ["flows", "🔀 업무 흐름", "주문·뱅킹·시세·DR 흐름"],
      ["glossary", "📖 용어·시스템 사전", D.glossary.length + "개 항목 검색"],
      ["nextit", "🚀 넥스트 IT", D.nextit.tasks.length + "대 과제와 로드맵"],
      ["cloud", "☁️ 클라우드", "도입 절차·현황·운영 업무"],
      ["process", "📋 운영 프로세스", D.processes.length + "개 정기·상시 절차"],
      ["rnr", "🤝 협업 R&R", "누구에게 무엇을 요청하나"],
      ["issues", "🧩 진행 과제·대안", D.issues.length + "개 과제 × 대안 3가지"],
      ["verify", "⚠️ 확인 필요", "수치·용어 검증 목록"]
    ];
    return header(D.meta.title, D.meta.subtitle) +
      '<div class="callout warn small"><b>보안 유의</b> — 이 가이드에는 사내 인프라 구성 정보가 포함되어 있습니다. 공개 호스팅 시 암호화 빌드(README 참고) 또는 접근 제한 호스팅을 사용하세요. 인명은 역할명으로 치환했습니다.</div>' +
      '<div class="card"><h3>학습 로드맵 진도</h3><div class="progress"><i style="width:' + pct + '%"></i></div>' +
      '<div class="small muted">' + done + " / " + total + " 완료 (" + pct + '%) · <a href="#learn">로드맵 보기</a></div></div>' +
      "<h2>바로가기</h2><div class=\"grid\">" +
      tiles.map(function (t) {
        return '<a class="card" href="#' + t[0] + '"><h3>' + esc(t[1]) + '</h3><div class="small muted">' + esc(t[2]) + "</div></a>";
      }).join("") + "</div>" +
      "<h2>오늘 기억할 한 줄</h2><div class=\"card\">" + esc(D.tips[new Date().getDate() % D.tips.length]) + "</div>" +
      '<h2>출처</h2><div class="card small muted">' + list(D.meta.sources) + '<p class="small">정리 기준일: ' + esc(D.meta.updated) + "</p></div>";
  };

  views.principles = function () {
    return header("핵심 원칙", "OJT 전반에 반복된 ‘금융 IT 인프라 관리자’의 일하는 방식") +
      '<div class="grid wide">' + D.principles.map(function (p, i) {
        return '<div class="card"><span class="badge accent">원칙 ' + (i + 1) + "</span><h3>" + esc(p.title) + "</h3><p>" + esc(p.body) + "</p>" + list(p.points) + "</div>";
      }).join("") + "</div>";
  };

  views.infra = function () {
    return header("인프라 구조", "센터 구성, 망 구분, 꼭 알아야 할 수치") +
      "<h2>핵심 수치</h2><div class=\"grid\">" + D.keyNumbers.map(function (k) {
        return '<div class="card stat"><div class="lbl">' + esc(k.label) + (k.verify ? ' <span class="badge warn">확인 필요</span>' : "") +
          '</div><div class="val">' + esc(k.value) + '</div><div class="small muted">' + esc(k.note) + "</div></div>";
      }).join("") + "</div>" +
      "<h2>센터</h2><div class=\"grid wide\">" + D.centers.map(function (c) {
        return '<div class="card"><h3>' + esc(c.name) + "</h3>" + badgeFor(c.role) + '<span class="badge">' + esc(c.type) + "</span><p>" + esc(c.desc) + "</p>" +
          c.tags.map(function (t) { return '<span class="badge">#' + esc(t) + "</span>"; }).join("") + "</div>";
      }).join("") + "</div>" +
      "<h2>망(Zone) 구분</h2><div class=\"table-wrap\"><table><thead><tr><th>구역</th><th>설명</th></tr></thead><tbody>" +
      D.networkZones.map(function (z) { return "<tr><td><b>" + esc(z.name) + "</b></td><td>" + esc(z.desc) + "</td></tr>"; }).join("") +
      "</tbody></table></div>" +
      "<h2>여의도 주요 서버팜</h2><div class=\"grid\">" + D.serverFarms.map(function (s) {
        return '<div class="card"><h3>' + esc(s.name) + '</h3><div class="small">' + esc(s.desc) + "</div></div>";
      }).join("") + "</div>" +
      '<div class="callout small">이중화 방식은 업무마다 다릅니다: 접속(MCA)은 센터간 액티브-액티브, 계정계 처리·DB는 액티브-스탠바이, 일부(콜센터·아너스넷·시세)는 액티브-액티브, 인증은 일부 기능만 액티브.</div>';
  };

  views.flows = function () {
    return header("업무 흐름", "장애 영향도를 판단하려면 데이터가 어디를 지나가는지 알아야 합니다.") +
      '<div class="chips">' + D.flows.map(function (f) { return '<a class="chip" href="#flows/' + f.id + '">' + esc(f.title) + "</a>"; }).join("") + "</div>" +
      D.flows.map(function (f) {
        return '<section class="card" id="flow-' + f.id + '" style="margin-bottom:16px"><h3>' + esc(f.title) + '</h3><div class="small muted">' + esc(f.summary) + '</div><div class="flow">' +
          f.steps.map(function (s) { return '<div class="node"><b>' + esc(s.node) + "</b><span>" + esc(s.detail) + "</span></div>"; }).join("") +
          "</div>" + (f.notes.length ? '<div class="small">' + list(f.notes) + "</div>" : "") + "</section>";
      }).join("");
  };

  views.glossary = function (sub) {
    var cats = ["전체"].concat(D.glossary.map(function (g) { return g.cat; }).filter(function (c, i, a) { return a.indexOf(c) === i; }));
    var cur = sub ? decodeURIComponent(sub) : "전체";
    var items = D.glossary.filter(function (g) { return cur === "전체" || g.cat === cur; });
    return header("용어·시스템 사전", "녹취 속 약어와 제품명을 정리했습니다. 상단 검색창으로도 찾을 수 있어요.") +
      '<div class="chips">' + cats.map(function (c) {
        return '<a class="chip' + (c === cur ? " on" : "") + '" href="#glossary/' + encodeURIComponent(c) + '">' + esc(c) + "</a>";
      }).join("") + "</div>" +
      '<div class="table-wrap"><table><thead><tr><th>용어</th><th>분류</th><th>설명</th></tr></thead><tbody>' +
      items.map(function (g) {
        return "<tr><td><b>" + esc(g.term) + '</b></td><td><span class="badge">' + esc(g.cat) + "</span></td><td>" + esc(g.desc) + "</td></tr>";
      }).join("") + "</tbody></table></div>";
  };

  views.nextit = function () {
    var n = D.nextit;
    return header("넥스트 IT 구조 전환", "ISP 컨설팅 → 사전준비 → 1단계(14개월) → 2단계") +
      '<div class="grid"><div class="card"><h3>추진 배경</h3>' + list(n.background) + "</div>" +
      '<div class="card"><h3>아키텍처 원칙</h3><ul>' + n.architecturePrinciples.map(function (a) {
        return "<li><b>" + esc(a.name) + "</b> — " + esc(a.desc) + "</li>";
      }).join("") + "</ul></div></div>" +
      "<h2>일정</h2><div class=\"flow\">" + n.timeline.map(function (t) {
        return '<div class="node"><b>' + esc(t.when) + "</b><span>" + esc(t.what) + "</span></div>";
      }).join("") + "</div>" +
      "<h2>이행 과제</h2><div class=\"table-wrap\"><table><thead><tr><th>#</th><th>과제</th><th>내용</th><th>인프라 관점</th></tr></thead><tbody>" +
      n.tasks.map(function (t) {
        return "<tr><td>" + t.no + "</td><td><b>" + esc(t.title) + "</b></td><td>" + esc(t.desc) + "</td><td>" + esc(t.infra) + "</td></tr>";
      }).join("") + "</tbody></table></div>" +
      '<div class="callout small">' + esc(n.note) + "</div>";
  };

  views.cloud = function () {
    var c = D.cloud;
    return header("클라우드", "도입 절차, 현황, 운영 업무") +
      "<h2>도입 절차 (금융분야 클라우드 이용 가이드 기반)</h2><div class=\"flow\">" + c.procedure.map(function (p, i) {
        return '<div class="node"><b>' + (i + 1) + ". " + esc(p.step) + "</b><span>" + esc(p.desc) + "</span></div>";
      }).join("") + "</div>" +
      '<div class="callout">💡 ' + esc(c.procedureTip) + "</div>" +
      "<h2>현황</h2><div class=\"table-wrap\"><table><thead><tr><th>서비스</th><th>위치</th><th>상태</th><th>비고</th></tr></thead><tbody>" +
      c.inventory.map(function (i) {
        return "<tr><td><b>" + esc(i.name) + "</b></td><td>" + esc(i.where) + "</td><td>" + badgeFor(i.status) + "</td><td>" + esc(i.note) + "</td></tr>";
      }).join("") + "</tbody></table></div>" +
      '<h2>운영 업무</h2><div class="card">' + list(c.ops) + "</div>";
  };

  views.process = function () {
    return header("운영 프로세스", "정기·상시 업무와 남겨야 할 증적. 모든 절차는 ‘우리가 만들고, ITO가 실행’합니다.") +
      '<div class="grid wide">' + D.processes.map(function (p) {
        return '<div class="card"><h3>' + esc(p.name) + '</h3><span class="badge accent">' + esc(p.cycle) + '</span><span class="badge">' + esc(p.owner) + "</span>" +
          "<ol>" + p.steps.map(function (s) { return "<li>" + esc(s) + "</li>"; }).join("") + "</ol>" +
          '<div class="small muted" style="margin-top:6px">📎 증적: ' + esc(p.evidence) + "</div></div>";
      }).join("") + "</div>";
  };

  views.rnr = function () {
    return header("협업 R&R", "누가 무엇을 하는지, 어떻게 요청하면 좋은지") +
      '<div class="table-wrap"><table><thead><tr><th>조직</th><th>담당 범위</th><th>협업 팁</th></tr></thead><tbody>' +
      D.rnr.map(function (r) {
        return "<tr><td><b>" + esc(r.org) + "</b></td><td>" + esc(r.scope) + '</td><td class="small">' + esc(r.tip) + "</td></tr>";
      }).join("") + "</tbody></table></div>";
  };

  views.issues = function () {
    return header("진행 과제·대안", "과제마다 대안 2~3가지와 추천안을 정리했습니다. 메모는 이 브라우저에만 저장됩니다.") +
      D.issues.map(function (it) {
        return '<section class="card" style="margin-bottom:16px"><h3>' + esc(it.title) + " " + badgeFor(it.priority) + '</h3><p class="small">' + esc(it.context) + '</p><div class="alts">' +
          it.alternatives.map(function (a) {
            return '<div class="alt"><h4>' + esc(a.name) + "</h4><p>" + esc(a.desc) + '</p><div class="pc"><span class="p">장점</span> ' + esc(a.pros) +
              '</div><div class="pc"><span class="c">단점</span> ' + esc(a.cons) + "</div></div>";
          }).join("") + '</div><div class="callout small"><b>추천</b> ' + esc(it.recommendation) + "</div>" +
          '<textarea class="memo" data-memo="' + esc(it.id) + '" placeholder="내 메모 (결정 사항, 담당자, 다음 액션 등)">' + esc(state.memos[it.id] || "") + "</textarea></section>";
      }).join("");
  };

  views.tips = function () {
    return header("실무 팁", "OJT에서 선배들이 강조한 교훈") +
      '<div class="grid wide">' + D.tips.map(function (t, i) { return '<div class="card"><span class="badge accent">TIP ' + (i + 1) + "</span><p>" + esc(t) + "</p></div>"; }).join("") + "</div>";
  };

  views.verify = function () {
    return header("확인 필요", "녹취 간 수치가 다르거나 STT 오류 가능성이 있는 항목. 검증 후 data.js를 갱신하세요.") +
      '<div class="table-wrap"><table><thead><tr><th>완료</th><th>항목</th><th>내용</th><th>확인 방법</th></tr></thead><tbody>' +
      D.verify.map(function (v, i) {
        var k = "verify-" + i;
        return '<tr><td><input type="checkbox" data-check="' + k + '"' + (state.checks[k] ? " checked" : "") + ' aria-label="확인 완료"></td><td><b>' + esc(v.item) + "</b></td><td>" + esc(v.detail) + "</td><td>" + esc(v.how) + "</td></tr>";
      }).join("") + "</tbody></table></div>";
  };

  views.learn = function () {
    return header("학습 로드맵 (30·60·90일)", "체크하면 이 브라우저에 진도가 저장됩니다.") +
      '<div class="grid wide">' + D.learning.map(function (p, pi) {
        var done = p.items.filter(function (_, ii) { return state.checks["learn-" + pi + "-" + ii]; }).length;
        var pct = Math.round(done / p.items.length * 100);
        return '<div class="card"><h3>' + esc(p.phase) + '</h3><div class="progress"><i style="width:' + pct + '%"></i></div><div class="small muted">' + done + " / " + p.items.length + "</div>" +
          p.items.map(function (it, ii) {
            var k = "learn-" + pi + "-" + ii;
            return '<label class="check' + (state.checks[k] ? " done" : "") + '"><input type="checkbox" data-check="' + k + '"' + (state.checks[k] ? " checked" : "") + "><span>" + esc(it) + "</span></label>";
          }).join("") + "</div>";
      }).join("") + "</div>";
  };

  views.quiz = function () {
    return header("셀프 퀴즈", "답을 먼저 떠올린 뒤 펼쳐 보세요.") +
      '<p><button class="btn ghost" id="openAll">모두 펼치기</button></p>' +
      D.quiz.map(function (q, i) {
        return '<details class="q"><summary>Q' + (i + 1) + ". " + esc(q.q) + "</summary><p>" + esc(q.a) + "</p></details>";
      }).join("");
  };

  /* ───────── search ───────── */
  var index = [];
  function buildIndex() {
    function add(title, text, route) { index.push({ title: title, text: text, route: route }); }
    D.principles.forEach(function (p) { add(p.title, p.body + " " + p.points.join(" "), "principles"); });
    D.centers.forEach(function (c) { add(c.name, c.role + " " + c.desc + " " + c.tags.join(" "), "infra"); });
    D.keyNumbers.forEach(function (k) { add(k.label, k.value + " " + k.note, "infra"); });
    D.networkZones.forEach(function (z) { add(z.name, z.desc, "infra"); });
    D.flows.forEach(function (f) { add(f.title, f.summary + " " + f.steps.map(function (s) { return s.node + " " + s.detail; }).join(" ") + " " + f.notes.join(" "), "flows"); });
    D.glossary.forEach(function (g) { add(g.term, g.desc, "glossary"); });
    D.nextit.tasks.forEach(function (t) { add("넥스트 IT " + t.no + ". " + t.title, t.desc + " " + t.infra, "nextit"); });
    D.cloud.procedure.forEach(function (p) { add("클라우드 절차: " + p.step, p.desc, "cloud"); });
    D.cloud.inventory.forEach(function (i) { add("클라우드: " + i.name, i.where + " " + i.status + " " + i.note, "cloud"); });
    D.processes.forEach(function (p) { add(p.name, p.cycle + " " + p.owner + " " + p.steps.join(" ") + " " + p.evidence, "process"); });
    D.rnr.forEach(function (r) { add(r.org, r.scope + " " + r.tip, "rnr"); });
    D.issues.forEach(function (it) { add(it.title, it.context + " " + it.alternatives.map(function (a) { return a.name + " " + a.desc; }).join(" ") + " " + it.recommendation, "issues"); });
    D.tips.forEach(function (t) { add("실무 팁", t, "tips"); });
    D.quiz.forEach(function (q) { add("퀴즈: " + q.q, q.a, "quiz"); });
  }
  function highlight(text, q) {
    var safe = esc(text);
    var re = new RegExp("(" + q.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + ")", "gi");
    return safe.replace(re, "<mark>$1</mark>");
  }
  function snippet(text, q) {
    var i = text.toLowerCase().indexOf(q.toLowerCase());
    if (i < 0) return text.slice(0, 140);
    var s = Math.max(0, i - 50);
    return (s > 0 ? "…" : "") + text.slice(s, i + q.length + 90) + "…";
  }
  function renderSearch(q) {
    var ql = q.toLowerCase();
    var hits = index.filter(function (e) { return (e.title + " " + e.text).toLowerCase().indexOf(ql) >= 0; });
    app.innerHTML = header("검색: " + q, hits.length + "건") +
      (hits.length ? hits.map(function (h) {
        return '<div class="result"><a href="#' + h.route + '">' + highlight(h.title, q) + '</a> <span class="badge">' + esc(h.route) + '</span><div class="small">' + highlight(snippet(h.text, q), q) + "</div></div>";
      }).join("") : '<p class="muted">결과가 없습니다. 다른 키워드로 찾아보세요.</p>');
  }

  /* ───────── router ───────── */
  function route() {
    if (!D) return;
    var hash = (location.hash || "#home").slice(1);
    var parts = hash.split("/");
    var name = views[parts[0]] ? parts[0] : "home";
    var sub = parts[1];
    if (name === "flows" && sub) {
      app.innerHTML = views.flows();
      var el = document.getElementById("flow-" + sub);
      if (el) el.scrollIntoView({ block: "start" });
    } else {
      app.innerHTML = views[name](sub);
      window.scrollTo(0, 0);
    }
    document.querySelectorAll(".sidebar a").forEach(function (a) {
      a.classList.toggle("active", a.getAttribute("data-route") === name);
    });
    document.getElementById("search").value = "";
    closeMenu();
  }

  /* ───────── events ───────── */
  app.addEventListener("change", function (e) {
    var k = e.target.getAttribute && e.target.getAttribute("data-check");
    if (k) {
      state.checks[k] = e.target.checked;
      saveState();
      var lab = e.target.closest(".check");
      if (lab) lab.classList.toggle("done", e.target.checked);
      if (k.indexOf("learn-") === 0) route();
    }
  });
  var memoTimer;
  app.addEventListener("input", function (e) {
    var id = e.target.getAttribute && e.target.getAttribute("data-memo");
    if (!id) return;
    state.memos[id] = e.target.value;
    clearTimeout(memoTimer);
    memoTimer = setTimeout(saveState, 300);
  });
  app.addEventListener("click", function (e) {
    if (e.target.id === "openAll") {
      app.querySelectorAll("details.q").forEach(function (d) { d.open = true; });
    }
  });

  var searchTimer;
  document.getElementById("search").addEventListener("input", function (e) {
    var q = e.target.value.trim();
    clearTimeout(searchTimer);
    searchTimer = setTimeout(function () {
      if (!D) return;
      if (q.length >= 1) renderSearch(q); else route();
    }, 150);
  });

  var sidebar = document.getElementById("sidebar"), scrim = document.getElementById("scrim"), menuBtn = document.getElementById("menuBtn");
  function closeMenu() { sidebar.classList.remove("open"); scrim.classList.remove("show"); menuBtn.setAttribute("aria-expanded", "false"); }
  menuBtn.addEventListener("click", function () {
    var open = !sidebar.classList.contains("open");
    sidebar.classList.toggle("open", open); scrim.classList.toggle("show", open); menuBtn.setAttribute("aria-expanded", String(open));
  });
  scrim.addEventListener("click", closeMenu);

  function applyTheme() { if (state.theme) document.documentElement.setAttribute("data-theme", state.theme); }
  document.getElementById("themeBtn").addEventListener("click", function () {
    var dark = state.theme ? state.theme === "dark" : window.matchMedia("(prefers-color-scheme: dark)").matches;
    state.theme = dark ? "light" : "dark";
    applyTheme(); saveState();
  });
  applyTheme();

  document.getElementById("exportBtn").addEventListener("click", function () {
    var blob = new Blob([JSON.stringify({ checks: state.checks, memos: state.memos }, null, 2)], { type: "application/json" });
    var a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "ojt-guide-progress.json";
    a.click();
    setTimeout(function () { URL.revokeObjectURL(a.href); }, 1000);
  });
  document.getElementById("importInput").addEventListener("change", function (e) {
    var f = e.target.files && e.target.files[0];
    if (!f) return;
    f.text().then(function (t) {
      var o = JSON.parse(t);
      state.checks = Object.assign(state.checks, o.checks || {});
      state.memos = Object.assign(state.memos, o.memos || {});
      saveState(); route();
    }).catch(function () { alert("파일 형식을 확인해 주세요."); });
  });

  window.addEventListener("hashchange", route);

  /* ───────── 암호화 빌드 지원 ───────── */
  function b64(s) { return Uint8Array.from(atob(s), function (c) { return c.charCodeAt(0); }); }
  function decrypt(pkg, password) {
    var enc = new TextEncoder();
    return crypto.subtle.importKey("raw", enc.encode(password), "PBKDF2", false, ["deriveKey"])
      .then(function (base) {
        return crypto.subtle.deriveKey({ name: "PBKDF2", salt: b64(pkg.salt), iterations: pkg.iter, hash: "SHA-256" },
          base, { name: "AES-GCM", length: 256 }, false, ["decrypt"]);
      })
      .then(function (key) { return crypto.subtle.decrypt({ name: "AES-GCM", iv: b64(pkg.iv) }, key, b64(pkg.data)); })
      .then(function (buf) { return JSON.parse(new TextDecoder().decode(buf)); });
  }
  function start(data) { D = data; buildIndex(); route(); }
  function lockScreen(pkg) {
    app.innerHTML = '<div class="lock card"><h1>🔒 인프라 OJT 가이드</h1><p class="muted small">팀에서 공유받은 암호를 입력하세요.</p>' +
      '<form id="unlock"><input id="pw" type="password" autocomplete="current-password" placeholder="암호" required>' +
      '<div class="err" id="err"></div><button class="btn" type="submit">열기</button></form></div>';
    document.getElementById("unlock").addEventListener("submit", function (e) {
      e.preventDefault();
      var pw = document.getElementById("pw").value;
      decrypt(pkg, pw).then(function (data) {
        try { sessionStorage.setItem("ojtGuide.pw", pw); } catch (er) { /* ignore */ }
        start(data);
      }).catch(function () { document.getElementById("err").textContent = "암호가 올바르지 않습니다."; });
    });
    document.getElementById("pw").focus();
  }

  if (window.OJT_DATA) {
    start(window.OJT_DATA);
  } else if (window.OJT_ENC) {
    // 단일 HTML 암호화 파일: 데이터가 파일 안에 포함됨
    var savedPw = null;
    try { savedPw = sessionStorage.getItem("ojtGuide.pw"); } catch (e) { /* ignore */ }
    if (savedPw) decrypt(window.OJT_ENC, savedPw).then(start).catch(function () { lockScreen(window.OJT_ENC); });
    else lockScreen(window.OJT_ENC);
  } else {
    fetch("data.enc.json", { cache: "no-cache" }).then(function (r) {
      if (!r.ok) throw new Error("no data");
      return r.json();
    }).then(function (pkg) {
      var saved = null;
      try { saved = sessionStorage.getItem("ojtGuide.pw"); } catch (e) { /* ignore */ }
      if (saved) decrypt(pkg, saved).then(start).catch(function () { lockScreen(pkg); });
      else lockScreen(pkg);
    }).catch(function () {
      app.innerHTML = '<p class="muted">데이터를 불러오지 못했습니다. js/data.js 또는 data.enc.json 이 있는지 확인하세요.</p>';
    });
  }

  /* ───────── PWA ───────── */
  if ("serviceWorker" in navigator && location.protocol !== "file:") {
    window.addEventListener("load", function () { navigator.serviceWorker.register("sw.js").catch(function () {}); });
  }
})();
