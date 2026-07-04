"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";

// Dust density + vignette were canvas-editor props in the source design; fixed here.
const DUST_DENSITY = 110;
const VIGNETTE = 0.85;

const THEMES = {
  hk: {
    text: "#e6eff8", textDim: "rgba(196,216,234,.55)", accent: "#d7ecff", glow: "#a8d8ff",
    glowDim: "rgba(168,216,255,.45)", glowSoft: "rgba(140,195,255,.22)",
    border: "rgba(160,200,240,.16)", panelBg: "rgba(8,16,30,.45)", popBg: "rgba(10,20,36,.92)",
    inputBg: "rgba(10,22,40,.55)", chipBg: "rgba(120,180,255,.07)", rowHover: "rgba(140,190,255,.07)",
    trackBg: "rgba(140,190,255,.12)", userBg: "rgba(70,125,190,.16)", userBd: "rgba(130,180,240,.25)",
    guideBg: "rgba(12,24,44,.55)", sendBg: "rgba(60,110,175,.22)", glowDimGrad: "rgba(168,216,255,.25)",
  },
  ss: {
    text: "#f4e9da", textDim: "rgba(232,206,172,.55)", accent: "#f5dcab", glow: "#e8b46a",
    glowDim: "rgba(232,180,106,.45)", glowSoft: "rgba(232,180,106,.2)",
    border: "rgba(226,170,96,.18)", panelBg: "rgba(28,12,8,.45)", popBg: "rgba(32,14,10,.92)",
    inputBg: "rgba(36,16,10,.55)", chipBg: "rgba(232,180,106,.08)", rowHover: "rgba(232,180,106,.08)",
    trackBg: "rgba(232,180,106,.14)", userBg: "rgba(170,70,45,.18)", userBd: "rgba(220,130,90,.28)",
    guideBg: "rgba(38,18,12,.55)", sendBg: "rgba(150,80,40,.24)", glowDimGrad: "rgba(232,180,106,.25)",
  },
};

const EMPTY_BEATS = { abilities: [], areas: [], bosses: [] };

// ─── Real API (proxied to the FastAPI backend via next.config rewrites) ───
async function fetchBeats(gameKey) {
  try {
    const r = await fetch(`/api/beats?game=${gameKey}`);
    if (!r.ok) throw new Error();
    return await r.json();
  } catch {
    return EMPTY_BEATS;
  }
}
async function postQuery(body) {
  const r = await fetch("/api/query", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error("query failed");
  return await r.json();
}

// ─── Markdown → React ───
function mdInline(text, key) {
  const parts = text.split(/(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`|\[[^\]]+\]\([^)]+\))/g);
  return parts.map((p, i) => {
    if (!p) return null;
    if (p.startsWith("**")) return React.createElement("strong", { key: key + "-" + i, style: { fontWeight: 600, color: "inherit" } }, p.slice(2, -2));
    if (p.startsWith("*")) return React.createElement("em", { key: key + "-" + i, style: { opacity: 0.85 } }, p.slice(1, -1));
    if (p.startsWith("`")) return React.createElement("code", { key: key + "-" + i, style: { fontFamily: "monospace", fontSize: ".85em", padding: "1px 5px", borderRadius: 4, background: "rgba(255,255,255,.08)" } }, p.slice(1, -1));
    if (p.startsWith("[")) {
      const m = p.match(/\[([^\]]+)\]\(([^)]+)\)/);
      if (m) return React.createElement("a", { key: key + "-" + i, href: m[2], target: "_blank", rel: "noopener", style: { color: "inherit", textDecorationColor: "rgba(255,255,255,.35)" } }, m[1]);
    }
    return p;
  });
}
function mdRender(md) {
  const blocks = []; let list = null; let k = 0;
  const flush = () => { if (list) { blocks.push(React.createElement("ul", { key: "ul" + k++, style: { margin: "8px 0", paddingLeft: 22 } }, list)); list = null; } };
  md.split("\n").forEach((line) => {
    const t = line.trim();
    if (!t) { flush(); return; }
    if (t.startsWith("### ")) { flush(); blocks.push(React.createElement("div", { key: "h" + k++, style: { fontFamily: "Cinzel, serif", fontSize: 13, fontWeight: 600, letterSpacing: ".2em", textTransform: "uppercase", margin: "14px 0 6px", opacity: 0.8 } }, mdInline(t.slice(4), "h" + k))); return; }
    if (t.startsWith("- ")) { list = list || []; list.push(React.createElement("li", { key: "li" + k++, style: { margin: "4px 0" } }, mdInline(t.slice(2), "li" + k))); return; }
    flush(); blocks.push(React.createElement("p", { key: "p" + k++, style: { margin: "6px 0" } }, mdInline(t, "p" + k)));
  });
  flush(); return blocks;
}

export default function CompanionCube() {
  const [game, setGame] = useState("hk");
  const [beats, setBeats] = useState(EMPTY_BEATS);
  const [collapsed, setCollapsed] = useState(false);
  const [search, setSearch] = useState("");
  const [mode, setMode] = useState("hold_my_hand");
  const [tolerance, setTolerance] = useState("none");
  const [checked, setChecked] = useState({ hk: [], ss: [] });
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [reduceMotion, setReduceMotion] = useState(false);

  const canvasRef = useRef(null);
  const bgWrapRef = useRef(null);
  const transcriptRef = useRef(null);
  const sendBtnRef = useRef(null);
  const partsRef = useRef([]);
  const mixRef = useRef(0);
  const mouseRef = useRef({ x: 0, y: 0 });
  const rafRef = useRef(null);
  const streamTRef = useRef(null);
  const reduceMotionRef = useRef(reduceMotion);
  const gameRef = useRef(game);
  reduceMotionRef.current = reduceMotion;
  gameRef.current = game;

  // Load the checklist for the current game from the backend.
  useEffect(() => {
    let alive = true;
    const gk = game === "ss" ? "silksong" : "hollow_knight";
    fetchBeats(gk).then((b) => { if (alive) setBeats(b || EMPTY_BEATS); });
    return () => { alive = false; };
  }, [game]);

  // Canvas dust background + mouse parallax
  useEffect(() => {
    partsRef.current = Array.from({ length: DUST_DENSITY }, () => ({
      x: Math.random(), y: Math.random(), z: 0.25 + Math.random() * 0.75,
      r: 0.6 + Math.random() * 1.9, tw: Math.random() * Math.PI * 2,
      vx: (Math.random() - 0.5) * 0.00006, vy: -(0.00003 + Math.random() * 0.00009),
    }));
    const sizeCanvas = () => { const cv = canvasRef.current; if (cv) { cv.width = cv.offsetWidth; cv.height = cv.offsetHeight; } };
    sizeCanvas();
    const draw = () => {
      const cv = canvasRef.current; if (!cv) return;
      if (cv.width !== cv.offsetWidth || cv.height !== cv.offsetHeight) sizeCanvas();
      const ctx = cv.getContext("2d"); const W = cv.width, H = cv.height;
      const target = gameRef.current === "ss" ? 1 : 0;
      mixRef.current += (target - mixRef.current) * 0.025;
      const m = mixRef.current;
      const cr = Math.round(160 + (236 - 160) * m), cg = Math.round(208 + (188 - 208) * m), cb = Math.round(255 + (118 - 255) * m);
      ctx.clearRect(0, 0, W, H);
      const time = performance.now() / 1000;
      for (const p of partsRef.current) {
        p.x += p.vx * (1 + p.z); p.y += p.vy * (1 + p.z * 1.6);
        if (p.y < -0.02) { p.y = 1.02; p.x = Math.random(); }
        if (p.x < -0.02) p.x = 1.02; if (p.x > 1.02) p.x = -0.02;
        const tw = 0.35 + 0.65 * (0.5 + 0.5 * Math.sin(time * (0.5 + p.z) + p.tw));
        const px = p.x * W + mouseRef.current.x * p.z * 22, py = p.y * H + mouseRef.current.y * p.z * 14;
        const a = tw * p.z * 0.55;
        ctx.beginPath();
        ctx.fillStyle = `rgba(${cr},${cg},${cb},${a.toFixed(3)})`;
        ctx.shadowColor = `rgba(${cr},${cg},${cb},.8)`;
        ctx.shadowBlur = p.r * 4;
        ctx.arc(px, py, p.r * p.z, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.shadowBlur = 0;
    };
    const loop = () => { rafRef.current = requestAnimationFrame(loop); if (reduceMotionRef.current) return; draw(); };
    loop();
    const onMove = (e) => {
      mouseRef.current = { x: (e.clientX / window.innerWidth - 0.5) * 2, y: (e.clientY / window.innerHeight - 0.5) * 2 };
      if (bgWrapRef.current) bgWrapRef.current.style.transform = `translate(${mouseRef.current.x * -10}px, ${mouseRef.current.y * -7}px)`;
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("resize", sizeCanvas);
    return () => { cancelAnimationFrame(rafRef.current); window.removeEventListener("mousemove", onMove); window.removeEventListener("resize", sizeCanvas); };
  }, []);

  useEffect(() => { if (transcriptRef.current) transcriptRef.current.scrollTop = transcriptRef.current.scrollHeight; }, [messages]);

  // Word-by-word reveal of the answer the backend returns (light, purely cosmetic).
  const stream = useCallback((msgId, res) => {
    const words = res.answer.split(/(\s+)/);
    const start = Date.now();
    const tick = () => {
      const i = Math.min(words.length, Math.max(2, Math.round(((Date.now() - start) / 1000) * 90)));
      const partial = words.slice(0, i).join("");
      const complete = i >= words.length;
      setMessages((s) => s.map((m) => (m.id === msgId ? { ...m, pending: false, md: partial, citations: complete ? res.citations : [] } : m)));
      if (!complete) streamTRef.current = setTimeout(tick, 34);
    };
    tick();
  }, []);

  const ask = useCallback((qtext) => {
    if (!qtext.trim()) return;
    const gameKey = game === "ss" ? "silksong" : "hollow_knight";
    const id = Date.now();
    setInput("");
    setMessages((s) => [...s, { id, role: "user", md: qtext }, { id: id + 1, role: "guide", md: "", pending: true, citations: [] }]);
    const el = sendBtnRef.current;
    if (el) { el.style.animation = "none"; requestAnimationFrame(() => { if (sendBtnRef.current) sendBtnRef.current.style.animation = "sendGlow .9s ease-out"; }); }
    postQuery({ question: qtext, game: gameKey, mode, tolerance, completed_beats: checked[game] })
      .then((res) => stream(id + 1, res))
      .catch(() => stream(id + 1, { answer: "*The link to the archives is broken.*\n\nIs the backend running? Start it with `python -m uvicorn api.main:app --port 8000` from the repo root.", citations: [] }));
  }, [game, mode, tolerance, checked, stream]);

  // ─── derived view values ───
  const t = THEMES[game];
  const done = checked[game];
  const all = [...beats.abilities, ...beats.areas, ...beats.bosses];
  const q = search.trim().toLowerCase();
  const hkOn = game === "hk", ssOn = game === "ss";

  const toggleItem = (id) => setChecked((st) => ({ ...st, [game]: done.includes(id) ? st[game].filter((x) => x !== id) : [...st[game], id] }));
  const allIds = all.map((a) => a.id);
  const setPreset = (tier) => {
    const ids = tier === "just" ? [] : tier === "end" ? allIds : allIds.slice(0, Math.ceil(allIds.length / 2));
    setChecked((st) => ({ ...st, [game]: ids }));
  };

  const groups = [["Abilities", "abilities"], ["Areas", "areas"], ["Bosses", "bosses"]].map(([name, key]) => {
    const list = beats[key] || [];
    const items = list.filter((it) => !q || it.title.toLowerCase().includes(q));
    const doneN = list.filter((it) => done.includes(it.id)).length;
    return { name, key, items, count: doneN + "/" + list.length };
  }).filter((g) => g.items.length > 0);

  const checkedCount = done.filter((id) => all.some((a) => a.id === id)).length;
  const progressPct = (all.length ? Math.round((100 * checkedCount) / all.length) : 0) + "%";

  const seg = (opts, cur, set) => opts.map(([val, label, tip]) => ({
    label, tip: tip || "", val,
    bg: cur === val ? t.chipBg : "transparent",
    fg: cur === val ? t.accent : t.textDim,
    pick: () => set(val),
  }));
  const modeOpts = seg([["hold_my_hand", "Hold my hand", "Full walkthrough"], ["gently_nudge", "Gently nudge", "A hint, nothing more"]], mode, setMode);
  const tolOpts = seg([["none", "Strict", "Nothing past your marked progress"], ["light", "Adventurous", "Careful riddles about what lies ahead"]], tolerance, setTolerance);

  const starters = (game === "hk"
    ? ["How do I beat the Mantis Lords?", "How do I get the dash?", "Where should I go next?"]
    : ["How do I beat Lace?", "Where is the Bell Beast?", "Where should I go next?"]);

  const viewMessages = messages.map((m) => {
    const user = m.role === "user";
    return {
      ...m,
      who: user ? "You" : (game === "hk" ? "The Guide" : "The Weaver"),
      justify: user ? "flex-end" : "flex-start",
      align: user ? "flex-end" : "flex-start",
      radius: user ? "14px 14px 4px 14px" : "14px 14px 14px 4px",
      bg: user ? t.userBg : t.guideBg,
      bd: user ? t.userBd : t.border,
      body: user ? m.md : mdRender(m.md || ""),
      hasCites: !user && (m.citations || []).length > 0,
      citations: m.citations || [],
    };
  });

  const rootVars = { "--glow": t.glow, "--glow-soft": t.glowSoft, "--accent": t.accent, "--row-hover": t.rowHover };
  const cin = "Cinzel, serif";
  const gar = "'EB Garamond', serif";
  const icon = game === "hk" ? "/assets/icon-hk.png" : "/assets/icon-ss.png";

  return (
    <div style={{ position: "fixed", inset: 0, overflow: "hidden", fontFamily: gar, color: t.text, transition: "color 1200ms ease", ...rootVars }}>

      {/* ── animated background ── */}
      <div ref={bgWrapRef} style={{ position: "absolute", inset: -40, pointerEvents: "none", willChange: "transform" }}>
        <div style={{ position: "absolute", inset: 0, opacity: hkOn ? 1 : 0, transition: "opacity 1600ms ease", background: "radial-gradient(120% 90% at 50% -10%, #10263f 0%, #081527 34%, #04090f 68%, #02050a 100%)" }}>
          <div style={{ position: "absolute", left: "50%", top: "-12%", width: "26vw", height: "130%", transform: "translateX(-50%)", transformOrigin: "top center", background: "linear-gradient(to bottom, rgba(110,180,250,.22), rgba(110,180,250,.05) 55%, transparent 80%)", filter: "blur(28px)", animation: "beamSway1 11s ease-in-out infinite", animationPlayState: reduceMotion ? "paused" : "running" }} />
          <div style={{ position: "absolute", left: "50%", top: "-12%", width: "12vw", height: "130%", transform: "translateX(-50%)", transformOrigin: "top center", background: "linear-gradient(to bottom, rgba(160,215,255,.30), rgba(160,215,255,.06) 60%, transparent 82%)", filter: "blur(18px)", animation: "beamSway2 9s ease-in-out infinite", animationPlayState: reduceMotion ? "paused" : "running" }} />
          <div style={{ position: "absolute", left: "50%", top: "-12%", width: "40vw", height: "120%", transform: "translateX(-50%)", transformOrigin: "top center", background: "linear-gradient(to bottom, rgba(80,150,230,.12), transparent 70%)", filter: "blur(46px)", animation: "beamSway3 14s ease-in-out infinite", animationPlayState: reduceMotion ? "paused" : "running" }} />
        </div>
        <div style={{ position: "absolute", inset: 0, opacity: ssOn ? 1 : 0, transition: "opacity 1600ms ease", background: "radial-gradient(120% 90% at 62% -6%, #3a1710 0%, #24100b 36%, #120705 66%, #0a0403 100%)" }}>
          <div style={{ position: "absolute", left: "62%", top: "-12%", width: "24vw", height: "130%", transform: "translateX(-50%)", transformOrigin: "top center", background: "linear-gradient(to bottom, rgba(232,180,106,.20), rgba(232,180,106,.04) 55%, transparent 80%)", filter: "blur(26px)", animation: "beamSway2 12s ease-in-out infinite", animationPlayState: reduceMotion ? "paused" : "running" }} />
          <div style={{ position: "absolute", left: "62%", top: "-12%", width: "11vw", height: "130%", transform: "translateX(-50%)", transformOrigin: "top center", background: "linear-gradient(to bottom, rgba(245,205,140,.26), rgba(245,205,140,.05) 60%, transparent 82%)", filter: "blur(16px)", animation: "beamSway1 10s ease-in-out infinite", animationPlayState: reduceMotion ? "paused" : "running" }} />
          <div style={{ position: "absolute", inset: 0, opacity: 0.5, background: "repeating-linear-gradient(112deg, transparent 0px, transparent 190px, rgba(240,205,150,.05) 191px, transparent 193px), repeating-linear-gradient(68deg, transparent 0px, transparent 260px, rgba(200,90,60,.06) 261px, transparent 263px)" }} />
        </div>
        <canvas ref={canvasRef} style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }} />
      </div>
      <div style={{ position: "absolute", inset: 0, pointerEvents: "none", background: `radial-gradient(ellipse 105% 90% at 50% 45%, transparent 42%, rgba(0,0,0,${VIGNETTE}) 100%)` }} />

      {/* ── app ── */}
      <div style={{ position: "relative", height: "100%", display: "flex", flexDirection: "column" }}>

        <header style={{ display: "flex", alignItems: "center", gap: 20, padding: "14px 26px", borderBottom: `1px solid ${t.border}`, transition: "border-color 1200ms ease", backdropFilter: "blur(4px)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12, minWidth: 280 }}>
            <span style={{ fontSize: 15, color: t.glow, transition: "color 1200ms ease" }}>❖</span>
            <span style={{ fontFamily: cin, fontWeight: 600, fontSize: 17, letterSpacing: ".32em", textTransform: "uppercase", animation: "titleGlow 6s ease-in-out infinite" }}>CompanionCube</span>
          </div>

          <div style={{ flex: 1, display: "flex", justifyContent: "center" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 4, border: `1px solid ${t.border}`, borderRadius: 999, padding: 4, background: t.panelBg, transition: "border-color 1200ms ease, background 1200ms ease" }}>
              {[["hk", "Hollow Knight", "/assets/icon-hk.png", hkOn, "rgba(168,216,255,.45)"], ["ss", "Silksong", "/assets/icon-ss.png", ssOn, "rgba(232,180,106,.5)"]].map(([g, label, ic, on, iconGlow]) => (
                <button key={g} onClick={() => { setGame(g); setSettingsOpen(false); }} title={label}
                  style={{ display: "flex", alignItems: "center", gap: 9, whiteSpace: "nowrap", fontFamily: cin, fontSize: 12, fontWeight: 600, letterSpacing: ".16em", textTransform: "uppercase", padding: "6px 16px 6px 10px", borderRadius: 999, cursor: "pointer", border: `1px solid ${on ? t.glowDim : "transparent"}`, background: on ? t.chipBg : "transparent", color: on ? t.accent : t.textDim, textShadow: on ? `0 0 10px ${t.glowSoft}` : "none", transition: "all 700ms ease" }}>
                  <img src={ic} alt="" width={24} height={24} style={{ display: "block", flexShrink: 0, opacity: on ? 1 : 0.5, filter: `drop-shadow(0 0 5px ${on ? iconGlow : "transparent"})`, transition: "all 700ms ease" }} onError={(e) => { e.currentTarget.style.display = "none"; }} />
                  <span>{label}</span>
                </button>
              ))}
            </div>
          </div>

          <div style={{ minWidth: 280, display: "flex", justifyContent: "flex-end", position: "relative" }}>
            <button className="cc-settings" onClick={() => setSettingsOpen((v) => !v)} title="Settings"
              style={{ width: 38, height: 38, borderRadius: "50%", border: `1px solid ${t.border}`, background: "transparent", color: t.textDim, fontSize: 16, cursor: "pointer", transition: "all 500ms ease" }}>✦</button>
            {settingsOpen && (
              <div style={{ position: "absolute", top: 46, right: 0, zIndex: 40, width: 230, padding: "16px 18px", border: `1px solid ${t.border}`, borderRadius: 10, background: t.popBg, backdropFilter: "blur(14px)", boxShadow: "0 12px 40px rgba(0,0,0,.55)", animation: "fadeUp .3s ease both" }}>
                <div style={{ fontFamily: cin, fontSize: 11, letterSpacing: ".22em", textTransform: "uppercase", color: t.textDim, marginBottom: 12 }}>Settings</div>
                <label style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10, fontSize: 15, cursor: "pointer" }}>
                  <span>Reduce motion</span>
                  <button onClick={() => setReduceMotion((v) => !v)} style={{ width: 40, height: 22, borderRadius: 999, border: `1px solid ${t.border}`, background: reduceMotion ? t.chipBg : "transparent", position: "relative", cursor: "pointer", transition: "background 400ms ease" }}>
                    <span style={{ position: "absolute", top: 2, left: reduceMotion ? 20 : 2, width: 16, height: 16, borderRadius: "50%", background: t.accent, transition: "left 300ms ease" }} />
                  </button>
                </label>
              </div>
            )}
          </div>
        </header>

        <div style={{ flex: 1, display: "flex", minHeight: 0 }}>

          <aside style={{ width: collapsed ? 0 : 312, minWidth: 0, transition: "width 500ms cubic-bezier(.4,0,.2,1)", overflow: "hidden", borderRight: `1px solid ${t.border}`, background: t.panelBg, backdropFilter: "blur(6px)", display: "flex", flexDirection: "column", flexShrink: 0 }}>
            <div style={{ width: 312, display: "flex", flexDirection: "column", height: "100%", minHeight: 0 }}>
              <div style={{ padding: "18px 20px 12px" }}>
                <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between" }}>
                  <div style={{ fontFamily: cin, fontSize: 14, fontWeight: 600, letterSpacing: ".2em", textTransform: "uppercase", color: t.accent, transition: "color 1200ms ease" }}>Where are you?</div>
                  <div style={{ fontSize: 13, color: t.textDim }}>{checkedCount} / {all.length}</div>
                </div>
                <div style={{ marginTop: 12, height: 4, borderRadius: 2, background: t.trackBg, overflow: "hidden" }}>
                  <div style={{ height: "100%", width: progressPct, borderRadius: 2, background: `linear-gradient(90deg, ${t.glowDimGrad}, ${t.glow})`, boxShadow: `0 0 8px ${t.glowSoft}`, transition: "width 600ms cubic-bezier(.4,0,.2,1), background 1200ms ease" }} />
                </div>
                <div style={{ display: "flex", gap: 6, marginTop: 14 }}>
                  {[["Just Started", "just"], ["Mid-game", "mid"], ["Endgame", "end"]].map(([label, tier]) => (
                    <button key={tier} className="cc-hover" onClick={() => setPreset(tier)}
                      style={{ flex: 1, fontFamily: cin, fontSize: 10, letterSpacing: ".08em", textTransform: "uppercase", padding: "7px 4px", borderRadius: 6, cursor: "pointer", border: `1px solid ${t.border}`, background: "transparent", color: t.textDim }}>{label}</button>
                  ))}
                </div>
                <input className="cc-focus" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Find a boss, area, ability…"
                  style={{ marginTop: 12, width: "100%", padding: "9px 12px", fontFamily: gar, fontSize: 15, borderRadius: 8, border: `1px solid ${t.border}`, background: t.inputBg, color: t.text, outline: "none", transition: "border-color 400ms ease" }} />
              </div>

              <div style={{ flex: 1, overflowY: "auto", padding: "0 12px 20px", minHeight: 0 }}>
                {all.length === 0 && (
                  <div style={{ padding: "20px 8px", fontSize: 14, color: t.textDim, fontStyle: "italic", lineHeight: 1.5 }}>
                    {game === "ss" ? "Pharloom is still being charted…" : "Loading the map of Hallownest…"}
                  </div>
                )}
                {groups.map((g) => (
                  <div key={g.key} style={{ marginTop: 14 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "0 8px 6px" }}>
                      <span style={{ fontFamily: cin, fontSize: 11, fontWeight: 600, letterSpacing: ".24em", textTransform: "uppercase", color: t.textDim }}>{g.name}</span>
                      <span style={{ flex: 1, height: 1, background: t.border }} />
                      <span style={{ fontSize: 12, color: t.textDim }}>{g.count}</span>
                    </div>
                    {g.items.map((it) => {
                      const on = done.includes(it.id);
                      return (
                        <button key={it.id} className="cc-row" onClick={() => toggleItem(it.id)}
                          style={{ display: "flex", alignItems: "center", gap: 10, width: "100%", textAlign: "left", padding: "6px 8px", border: "none", borderRadius: 6, background: "transparent", cursor: "pointer", fontFamily: gar, fontSize: 15.5, color: on ? t.text : t.textDim, transition: "color 300ms ease, background 300ms ease" }}>
                          <span style={{ width: 16, textAlign: "center", fontSize: 12, color: on ? t.glow : t.textDim, textShadow: on ? `0 0 8px ${t.glowSoft}` : "none", transition: "all 300ms ease" }}>{on ? "◆" : "◇"}</span>
                          <span>{it.title}</span>
                        </button>
                      );
                    })}
                  </div>
                ))}
              </div>
            </div>
          </aside>

          <button className="cc-settings" onClick={() => setCollapsed((v) => !v)} title="Toggle progress panel"
            style={{ width: 20, border: "none", background: "transparent", color: t.textDim, cursor: "pointer", fontSize: 11, flexShrink: 0, transition: "color 300ms" }}>{collapsed ? "❯" : "❮"}</button>

          <main style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0, minHeight: 0 }}>
            <div ref={transcriptRef} style={{ flex: 1, overflowY: "auto", padding: "28px 8% 16px", minHeight: 0 }}>

              {messages.length === 0 && (
                <div style={{ height: "100%", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 18, textAlign: "center", animation: "fadeIn 1.2s ease both" }}>
                  <img src={icon} alt="" width={64} height={64} style={{ display: "block", width: 64, height: 64, filter: `drop-shadow(0 0 16px ${t.glowSoft})`, animation: "fadeIn 1.2s ease both" }} onError={(e) => { e.currentTarget.style.display = "none"; }} />
                  <div style={{ fontFamily: cin, fontSize: 22, fontWeight: 500, letterSpacing: ".14em", textTransform: "uppercase" }}>{game === "hk" ? "Ask, little ghost" : "Ask, little weaver"}</div>
                  <div style={{ maxWidth: 440, fontSize: 17, lineHeight: 1.6, color: t.textDim, fontStyle: "italic" }}>
                    {game === "hk"
                      ? "I know every corner of Hallownest — but I will only speak of paths you have already walked. Mark your journey, and ask freely."
                      : "Every thread of Pharloom passes through my hands — but I will not unspool what lies ahead of your climb. Mark your ascent, and ask freely."}
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: 14, color: t.textDim, fontSize: 13, marginTop: -4 }}>
                    <span style={{ width: 60, height: 1, background: t.border }} />
                    <span style={{ color: t.glow }}>✦</span>
                    <span style={{ width: 60, height: 1, background: t.border }} />
                  </div>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 10, justifyContent: "center", maxWidth: 560 }}>
                    {starters.map((s) => (
                      <button key={s} className="cc-chip" onClick={() => ask(s)}
                        style={{ fontFamily: gar, fontSize: 15, padding: "9px 18px", borderRadius: 999, cursor: "pointer", border: `1px solid ${t.border}`, background: t.chipBg, color: t.text, transition: "all 400ms ease" }}>{s}</button>
                    ))}
                  </div>
                </div>
              )}

              {viewMessages.map((m) => (
                <div key={m.id} style={{ display: "flex", justifyContent: m.justify, marginBottom: 20, animation: "fadeUp .5s ease both" }}>
                  <div style={{ maxWidth: "68%", display: "flex", flexDirection: "column", gap: 8, alignItems: m.align }}>
                    <div style={{ fontFamily: cin, fontSize: 10, letterSpacing: ".24em", textTransform: "uppercase", color: t.textDim, padding: "0 4px" }}>{m.who}</div>
                    <div style={{ padding: "14px 18px", borderRadius: m.radius, border: `1px solid ${m.bd}`, background: m.bg, fontSize: 16.5, lineHeight: 1.62, transition: "border-color 1200ms ease, background 1200ms ease" }}>
                      {m.pending && (
                        <span style={{ display: "inline-flex", gap: 5, padding: "4px 2px" }}>
                          <span style={{ width: 6, height: 6, borderRadius: "50%", background: t.glow, animation: "dotPulse 1.2s infinite" }} />
                          <span style={{ width: 6, height: 6, borderRadius: "50%", background: t.glow, animation: "dotPulse 1.2s .2s infinite" }} />
                          <span style={{ width: 6, height: 6, borderRadius: "50%", background: t.glow, animation: "dotPulse 1.2s .4s infinite" }} />
                        </span>
                      )}
                      {m.body}
                    </div>
                    {m.hasCites && (
                      <div style={{ display: "flex", flexWrap: "wrap", gap: 8, padding: "0 2px" }}>
                        {m.citations.map((c) => (
                          <a key={c.id} className="cc-chip" href={c.url} target="_blank" rel="noopener"
                            style={{ display: "inline-flex", alignItems: "center", gap: 7, textDecoration: "none", fontSize: 13, padding: "5px 12px", borderRadius: 999, border: `1px solid ${t.border}`, background: t.chipBg, color: t.textDim, transition: "all 400ms ease" }}>
                            <span style={{ color: t.glow, fontSize: 10 }}>◆</span>
                            <span style={{ color: t.text }}>{c.title}</span>
                            <span style={{ opacity: 0.65 }}>· {c.section}</span>
                          </a>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>

            <div style={{ padding: "0 8% 22px", flexShrink: 0 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 10, flexWrap: "wrap" }}>
                {[["Guidance", modeOpts], ["Spoiler ward", tolOpts]].map(([label, opts]) => (
                  <div key={label} style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span style={{ fontFamily: cin, fontSize: 10, letterSpacing: ".18em", textTransform: "uppercase", color: t.textDim }}>{label}</span>
                    <div style={{ display: "flex", border: `1px solid ${t.border}`, borderRadius: 999, padding: 2, background: t.panelBg }}>
                      {opts.map((o) => (
                        <button key={o.val} onClick={o.pick} title={o.tip}
                          style={{ fontFamily: gar, fontSize: 13.5, padding: "5px 14px", borderRadius: 999, cursor: "pointer", border: "none", background: o.bg, color: o.fg, transition: "all 500ms ease" }}>{o.label}</button>
                      ))}
                    </div>
                  </div>
                ))}
              </div>

              <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
                <input className="cc-focus" value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") ask(input); }}
                  placeholder={game === "hk" ? "Ask the Guide of Hallownest…" : "Ask the Weaver of Pharloom…"}
                  style={{ flex: 1, padding: "15px 20px", fontFamily: gar, fontSize: 17, borderRadius: 14, border: `1px solid ${t.border}`, background: t.inputBg, color: t.text, outline: "none", backdropFilter: "blur(6px)", transition: "border-color 500ms ease, background 1200ms ease" }} />
                <button ref={sendBtnRef} className="cc-send" onClick={() => ask(input)} title="Send"
                  style={{ width: 52, height: 52, borderRadius: "50%", cursor: "pointer", border: `1px solid ${t.glowDim}`, background: t.sendBg, color: t.accent, fontSize: 18, display: "flex", alignItems: "center", justifyContent: "center", transition: "all 500ms ease", flexShrink: 0 }}>➤</button>
              </div>
            </div>
          </main>
        </div>
      </div>
    </div>
  );
}
