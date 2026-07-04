"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";

// Dust density + vignette were canvas-editor props in the source design; fixed here.
const DUST_DENSITY = 110;
const VIGNETTE = 0.85;

// ─── Mock API data (shapes match the real GET /api/beats + POST /api/query) ───
const DATA = {
  hollow_knight: {
    abilities: [
      { id: "mothwing_cloak", title: "Mothwing Cloak" }, { id: "mantis_claw", title: "Mantis Claw" },
      { id: "crystal_heart", title: "Crystal Heart" }, { id: "desolate_dive", title: "Desolate Dive" },
      { id: "dream_nail", title: "Dream Nail" }, { id: "ismas_tear", title: "Isma's Tear" },
      { id: "monarch_wings", title: "Monarch Wings" }, { id: "shade_cloak", title: "Shade Cloak" },
      { id: "kings_brand", title: "King's Brand" },
    ],
    areas: [
      { id: "crossroads", title: "Forgotten Crossroads" }, { id: "greenpath", title: "Greenpath" },
      { id: "fungal", title: "Fungal Wastes" }, { id: "fog_canyon", title: "Fog Canyon" },
      { id: "city", title: "City of Tears" }, { id: "crystal_peak", title: "Crystal Peak" },
      { id: "waterways", title: "Royal Waterways" }, { id: "deepnest", title: "Deepnest" },
      { id: "basin", title: "Ancient Basin" }, { id: "kingdoms_edge", title: "Kingdom's Edge" },
      { id: "queens_gardens", title: "Queen's Gardens" }, { id: "white_palace", title: "White Palace" },
    ],
    bosses: [
      { id: "false_knight", title: "False Knight" }, { id: "hornet_1", title: "Hornet (Greenpath)" },
      { id: "mantis_lords", title: "Mantis Lords" }, { id: "soul_master", title: "Soul Master" },
      { id: "dung_defender", title: "Dung Defender" }, { id: "broken_vessel", title: "Broken Vessel" },
      { id: "watcher_knights", title: "Watcher Knights" }, { id: "uumuu", title: "Uumuu" },
      { id: "traitor_lord", title: "Traitor Lord" }, { id: "hornet_2", title: "Hornet (Kingdom's Edge)" },
      { id: "hollow_knight", title: "The Hollow Knight" }, { id: "radiance", title: "The Radiance" },
    ],
  },
  silksong: {
    abilities: [
      { id: "swift_step", title: "Swift Step" }, { id: "drifters_cloak", title: "Drifter's Cloak" },
      { id: "cling_grip", title: "Cling Grip" }, { id: "needolin", title: "Needolin" },
      { id: "clawline", title: "Clawline" }, { id: "silk_soar", title: "Silk Soar" },
    ],
    areas: [
      { id: "moss_grotto", title: "Moss Grotto" }, { id: "bone_bottom", title: "Bone Bottom" },
      { id: "the_marrow", title: "The Marrow" }, { id: "deep_docks", title: "Deep Docks" },
      { id: "far_fields", title: "Far Fields" }, { id: "greymoor", title: "Greymoor" },
      { id: "shellwood", title: "Shellwood" }, { id: "bellhart", title: "Bellhart" },
      { id: "blasted_steps", title: "Blasted Steps" }, { id: "citadel", title: "The Citadel" },
    ],
    bosses: [
      { id: "moss_mother", title: "Moss Mother" }, { id: "bell_beast", title: "Bell Beast" },
      { id: "lace_1", title: "Lace (Deep Docks)" }, { id: "fourth_chorus", title: "Fourth Chorus" },
      { id: "widow", title: "Widow" }, { id: "last_judge", title: "Last Judge" },
      { id: "cogwork_dancers", title: "Cogwork Dancers" }, { id: "trobbio", title: "Trobbio" },
      { id: "lace_2", title: "Lace (The Cradle)" }, { id: "grand_mother_silk", title: "Grand Mother Silk" },
    ],
  },
};

const PRESETS = {
  hk: {
    just: ["crossroads", "false_knight"],
    mid: ["crossroads", "false_knight", "greenpath", "hornet_1", "mothwing_cloak", "fungal", "mantis_lords", "mantis_claw", "city", "soul_master", "desolate_dive", "fog_canyon"],
    end: ["crossroads", "false_knight", "greenpath", "hornet_1", "mothwing_cloak", "fungal", "mantis_lords", "mantis_claw", "city", "soul_master", "desolate_dive", "fog_canyon", "crystal_peak", "crystal_heart", "waterways", "dung_defender", "ismas_tear", "deepnest", "basin", "broken_vessel", "monarch_wings", "watcher_knights", "uumuu", "dream_nail", "kingdoms_edge", "hornet_2", "kings_brand", "shade_cloak", "queens_gardens", "traitor_lord"],
  },
  ss: {
    just: ["moss_grotto", "moss_mother"],
    mid: ["moss_grotto", "moss_mother", "bone_bottom", "the_marrow", "bell_beast", "deep_docks", "lace_1", "swift_step", "far_fields", "fourth_chorus", "greymoor", "drifters_cloak"],
    end: ["moss_grotto", "moss_mother", "bone_bottom", "the_marrow", "bell_beast", "deep_docks", "lace_1", "swift_step", "far_fields", "fourth_chorus", "greymoor", "drifters_cloak", "shellwood", "cling_grip", "bellhart", "widow", "blasted_steps", "last_judge", "needolin", "citadel", "cogwork_dancers", "trobbio", "clawline"],
  },
};

const WIKI = { hk: "https://hollowknight.wiki/w/", ss: "https://hollowknight.wiki/w/" };

const ANSWERS = {
  hk: [
    { keys: /mantis/i, gate: "fungal", gateTitle: "Fungal Wastes",
      full: "The **Mantis Lords** await at the base of the Mantis Village, in the southwest of the **Fungal Wastes**.\n\n### The duel\n- **Phase one** is a single Lord. Learn her three moves: a low dash (jump), a downward dive (step aside), and a wall-cling boomerang (stand in the gap).\n- **Phase two** brings the remaining two sisters at once — the same moves, interleaved. Stay near the centre and commit to short nail exchanges.\n- Every attack has a long, honest wind-up. This fight teaches patience; don't greed for extra hits.\n\nWin with honour and the village will *bow to you* — the Mantis tribe becomes docile.",
      hint: "Their duel is a dance of three moves, each announced plainly before it lands. Watch one full round without swinging your nail — the answer is in the wind-ups. And remember: this tribe respects patience, in more ways than one.",
      cites: [{ title: "Mantis Lords", section: "Behaviour and Tactics", slug: "Mantis_Lords" }, { title: "Mantis Village", section: "Overview", slug: "Mantis_Village" }] },
    { keys: /dash|cloak|mothwing/i, gate: "greenpath", gateTitle: "Greenpath",
      full: "The dash is granted by the **Mothwing Cloak**, found in **Greenpath** — the verdant region west of the Forgotten Crossroads.\n\n- Push west and down through Greenpath until a certain *needle-wielding stranger* bars your way.\n- Beyond that duel lies a broken vessel and, beside it, the cloak.\n- Once taken: dash with it to cross gaps and slip through closing traps.",
      hint: "Follow the green. West of the Crossroads the air turns soft and mossy — keep descending, and the way will make itself known after a sharp encounter.",
      cites: [{ title: "Mothwing Cloak", section: "Location", slug: "Mothwing_Cloak" }, { title: "Greenpath", section: "How to reach", slug: "Greenpath" }] },
    { keys: /hornet/i, gate: "greenpath", gateTitle: "Greenpath",
      full: "**Hornet** duels you deep in **Greenpath**.\n\n- She has three tells: a lunging needle throw (jump over the string), a leaping slash (dash beneath), and a spinning silk burst (keep your distance).\n- Between attacks she pauses to taunt — *that* is your window.\n- Two or three nail hits per opening, no more. Greed is what kills vessels here.",
      hint: "She announces everything — listen for the cry before each lunge. Fight her like a conversation: speak only when she pauses.",
      cites: [{ title: "Hornet", section: "Boss Fight (Greenpath)", slug: "Hornet" }] },
    { keys: /radiance|true ending|dream/i, gate: "dream_nail", gateTitle: "the Dream Nail",
      full: "You seek the light behind it all. With the **Dream Nail** in hand:\n\n- Gather **Essence** from Whispering Roots and Warrior Dreams — you'll want 1,800 for the Awoken Dream Nail.\n- Seek the **Birthplace** in the Abyss to unite the fractured halves of a certain charm.\n- Then, at the final battle, strike the fallen vessel with the Dream Nail when the chance appears… and face **The Radiance** herself.",
      hint: "Some dreams are doors. The old nail you were given can open more than memories — strengthen it, look to where vessels are born, and the true ending will show its seam.",
      cites: [{ title: "The Radiance", section: "How to unlock", slug: "The_Radiance" }, { title: "Godmaster", section: "Endings", slug: "Endings" }] },
  ],
  ss: [
    { keys: /lace/i, gate: "deep_docks", gateTitle: "Deep Docks",
      full: "**Lace** crosses blades with you in the **Deep Docks**, amid the forge-light.\n\n- Her pin work is fast but rhythmic: parry-bait lunges, a rising flourish, and a mid-air pirouette strike.\n- Stay grounded; most of her strings whiff if you hold your ground and strike after her flourish.\n- Use **Swift Step** to slip behind her recovery — two needle hits, then reset.",
      hint: "She fights like a duellist expecting applause. Let her finish each flourish — the bow at the end of it is where your needle belongs.",
      cites: [{ title: "Lace", section: "Boss Fight (Deep Docks)", slug: "Lace" }] },
    { keys: /bell ?beast|bell/i, gate: "bone_bottom", gateTitle: "Bone Bottom",
      full: "The **Bell Beast** dwells past **Bone Bottom**, in the bell-way tunnels of the Marrow.\n\n- It charges wall to wall — cling and hop over each pass.\n- When it burrows, watch the dust; it erupts where the motes gather.\n- Spare your silk for healing between charge cycles.\n\nCalm it, and the old courier becomes your **fast travel** through Pharloom.",
      hint: "What rings the bells of Pharloom is not an enemy, exactly. Follow the tolling east of Bone Bottom, and be ready to prove you're worth carrying.",
      cites: [{ title: "Bell Beast", section: "Encounter", slug: "Bell_Beast" }, { title: "Bone Bottom", section: "Connections", slug: "Bone_Bottom" }] },
    { keys: /grand mother|final|silk.*end|ending/i, gate: "citadel", gateTitle: "the Citadel",
      full: "The thread of Pharloom winds upward to **Grand Mother Silk**.\n\n- Ascend the **Citadel** and settle its choir — the Cogwork Dancers and Trobbio bar the melodies you need.\n- Learn **Silk Soar** to reach the Cradle above.\n- There, an old duel is repaid in full before the Mother of it all unspools.",
      hint: "Everything in Pharloom is stitched toward one high place. Keep climbing; when songs start answering your Needolin, you are close.",
      cites: [{ title: "Grand Mother Silk", section: "How to reach", slug: "Grand_Mother_Silk" }] },
  ],
};

const NEXT = {
  hk: [
    [0, "You stand at the beginning, little ghost. Descend the well into the **Forgotten Crossroads** — map its corners, find the bench, and seek the **False Knight** beneath the old arena. Cornifer's humming will lead you to a map."],
    [5, "With the Crossroads behind you, the kingdom opens two ways: **Greenpath** to the west holds the gift of the dash, and the **Fungal Wastes** below test your claws. Greenpath first is the gentler thread."],
    [12, "You've walked far. The **City of Tears** is the kingdom's heart — the **Soul Master** waits in its sanctum, and roads fan out to **Crystal Peak** and the **Royal Waterways** from there."],
    [99, "Little remains unmapped. The **Ancient Basin** and what sleeps beneath it call to vessels who have come this far. You know, by now, what you approach."],
  ],
  ss: [
    [0, "Your climb begins in the **Moss Grotto**. Find your needle, quiet the **Moss Mother**, and follow the pilgrims' path up to **Bone Bottom** — the town will give you your first tasks and your first tools."],
    [4, "Pharloom widens. The **Deep Docks** burn to the east — a duellist in white waits there — while the **Far Fields** teach your needle new reach. Take the Bell Beast's roads between them."],
    [9, "The **Citadel's** spires are no longer rumour. Push through **Bellhart** and the **Blasted Steps**; the songs of the upper kingdom are calling you to the climb."],
    [99, "The last threads gather at the top of the world. The Cradle waits above the Citadel — finish what the pilgrimage started."],
  ],
};

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

// ─── Mock query (swap for `fetch('/api/query', …)` against the Python backend) ───
function apiQuery(body) {
  const g = body.game === "silksong" ? "ss" : "hk";
  const done = body.completed_beats;
  const nudge = body.mode === "gently_nudge";
  const hit = ANSWERS[g].find((a) => a.keys.test(body.question));
  const mk = (c) => ({ id: c.slug, title: c.title, section: c.section, url: WIKI[g] + c.slug });
  if (hit) {
    const gated = hit.gate && !done.includes(hit.gate);
    if (gated && body.tolerance === "none") {
      const md = g === "hk"
        ? "*The seals upon this knowledge hold fast, little ghost.*\n\nYou ask of things beyond where your map is marked, and your ward forbids me to speak of them plainly. Some truths are sweeter found than told.\n\n- Mark more of your journey in **Where are you?** — perhaps you've been further than you've said\n- Or loosen your spoiler ward to **Adventurous**, and I shall answer in careful riddles"
        : "*That thread is not yet yours to pull, weaver.*\n\nThe answer lies past where your climb is marked, and your ward binds my needle. I will not unravel what Pharloom means you to discover.\n\n- Mark more of your ascent in **Where are you?**\n- Or loosen your spoiler ward to **Adventurous**, and I'll hum the shape of it";
      return Promise.resolve({ answer: md, citations: [], gated: true });
    }
    let md = nudge ? hit.hint : hit.full;
    if (gated) {
      md = (g === "hk" ? "*⟡ A veil thins — this lies beyond " : "*⟡ Careful, weaver — this lies past ") + hit.gateTitle + ", further than you've marked. Faint spoilers follow.*\n\n" + md;
    }
    return Promise.resolve({ answer: md, citations: nudge ? hit.cites.slice(0, 1).map(mk) : hit.cites.map(mk) });
  }
  if (/where|next|should i go|what now|stuck/i.test(body.question)) {
    const tier = NEXT[g].find((t) => done.length <= t[0]) || NEXT[g][NEXT[g].length - 1];
    return Promise.resolve({ answer: tier[1], citations: [] });
  }
  const md = g === "hk"
    ? "Hm. That question drifts beyond the paths I know well, little ghost. I keep counsel on **bosses**, **abilities**, and **where to wander next**.\n\nTry asking of a foe by name — *\"How do I beat the Mantis Lords?\"* — or simply, *\"Where should I go?\"*"
    : "That thread frays beyond my weave, I'm afraid. Ask me of **foes**, **tools**, or **where the climb leads next**.\n\nTry a name — *\"How do I beat Lace?\"* — or simply, *\"Where should I go?\"*";
  return Promise.resolve({ answer: md, citations: [] });
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
  const [collapsed, setCollapsed] = useState(false);
  const [search, setSearch] = useState("");
  const [mode, setMode] = useState("hold_my_hand");
  const [tolerance, setTolerance] = useState("none");
  const [checked, setChecked] = useState({ hk: ["crossroads", "false_knight"], ss: ["moss_grotto"] });
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

  const stream = useCallback((msgId, res) => {
    const words = res.answer.split(/(\s+)/);
    const start = Date.now();
    const tick = () => {
      const i = Math.min(words.length, Math.max(2, Math.round(((Date.now() - start) / 1000) * 90)));
      const partial = words.slice(0, i).join("");
      const complete = i >= words.length;
      setMessages((s) => s.map((m) => (m.id === msgId ? { ...m, pending: false, md: partial, citations: complete ? res.citations : [], gated: res.gated } : m)));
      if (!complete) streamTRef.current = setTimeout(tick, 34);
    };
    tick();
  }, []);

  const ask = useCallback((q) => {
    if (!q.trim()) return;
    const gameKey = game === "ss" ? "silksong" : "hollow_knight";
    const id = Date.now();
    setInput("");
    setMessages((s) => [...s, { id, role: "user", md: q }, { id: id + 1, role: "guide", md: "", pending: true, citations: [] }]);
    const el = sendBtnRef.current;
    if (el) { el.style.animation = "none"; requestAnimationFrame(() => { if (sendBtnRef.current) sendBtnRef.current.style.animation = "sendGlow .9s ease-out"; }); }
    apiQuery({ question: q, game: gameKey, mode, tolerance, completed_beats: checked[game] })
      .then((res) => setTimeout(() => stream(id + 1, res), 700 + Math.random() * 500));
  }, [game, mode, tolerance, checked, stream]);

  // ─── derived view values ───
  const t = THEMES[game];
  const gk = game === "ss" ? "silksong" : "hollow_knight";
  const data = DATA[gk];
  const done = checked[game];
  const all = [...data.abilities, ...data.areas, ...data.bosses];
  const q = search.trim().toLowerCase();
  const hkOn = game === "hk", ssOn = game === "ss";

  const toggleItem = (id) => setChecked((st) => ({ ...st, [game]: done.includes(id) ? st[game].filter((x) => x !== id) : [...st[game], id] }));
  const setPreset = (tier) => setChecked((st) => ({ ...st, [game]: [...PRESETS[game][tier]] }));

  const groups = [["Abilities", "abilities"], ["Areas", "areas"], ["Bosses", "bosses"]].map(([name, key]) => {
    const items = data[key].filter((it) => !q || it.title.toLowerCase().includes(q));
    const doneN = data[key].filter((it) => done.includes(it.id)).length;
    return { name, key, items, count: doneN + "/" + data[key].length };
  }).filter((g) => g.items.length > 0);

  const checkedCount = done.filter((id) => all.some((a) => a.id === id)).length;
  const progressPct = Math.round((100 * checkedCount) / all.length) + "%";

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
      bd: user ? t.userBd : (m.gated ? t.glowDim : t.border),
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
        {/* Hallownest */}
        <div style={{ position: "absolute", inset: 0, opacity: hkOn ? 1 : 0, transition: "opacity 1600ms ease", background: "radial-gradient(120% 90% at 50% -10%, #10263f 0%, #081527 34%, #04090f 68%, #02050a 100%)" }}>
          <div style={{ position: "absolute", left: "50%", top: "-12%", width: "26vw", height: "130%", transform: "translateX(-50%)", transformOrigin: "top center", background: "linear-gradient(to bottom, rgba(110,180,250,.22), rgba(110,180,250,.05) 55%, transparent 80%)", filter: "blur(28px)", animation: "beamSway1 11s ease-in-out infinite", animationPlayState: reduceMotion ? "paused" : "running" }} />
          <div style={{ position: "absolute", left: "50%", top: "-12%", width: "12vw", height: "130%", transform: "translateX(-50%)", transformOrigin: "top center", background: "linear-gradient(to bottom, rgba(160,215,255,.30), rgba(160,215,255,.06) 60%, transparent 82%)", filter: "blur(18px)", animation: "beamSway2 9s ease-in-out infinite", animationPlayState: reduceMotion ? "paused" : "running" }} />
          <div style={{ position: "absolute", left: "50%", top: "-12%", width: "40vw", height: "120%", transform: "translateX(-50%)", transformOrigin: "top center", background: "linear-gradient(to bottom, rgba(80,150,230,.12), transparent 70%)", filter: "blur(46px)", animation: "beamSway3 14s ease-in-out infinite", animationPlayState: reduceMotion ? "paused" : "running" }} />
        </div>
        {/* Pharloom */}
        <div style={{ position: "absolute", inset: 0, opacity: ssOn ? 1 : 0, transition: "opacity 1600ms ease", background: "radial-gradient(120% 90% at 62% -6%, #3a1710 0%, #24100b 36%, #120705 66%, #0a0403 100%)" }}>
          <div style={{ position: "absolute", left: "62%", top: "-12%", width: "24vw", height: "130%", transform: "translateX(-50%)", transformOrigin: "top center", background: "linear-gradient(to bottom, rgba(232,180,106,.20), rgba(232,180,106,.04) 55%, transparent 80%)", filter: "blur(26px)", animation: "beamSway2 12s ease-in-out infinite", animationPlayState: reduceMotion ? "paused" : "running" }} />
          <div style={{ position: "absolute", left: "62%", top: "-12%", width: "11vw", height: "130%", transform: "translateX(-50%)", transformOrigin: "top center", background: "linear-gradient(to bottom, rgba(245,205,140,.26), rgba(245,205,140,.05) 60%, transparent 82%)", filter: "blur(16px)", animation: "beamSway1 10s ease-in-out infinite", animationPlayState: reduceMotion ? "paused" : "running" }} />
          <div style={{ position: "absolute", inset: 0, opacity: 0.5, background: "repeating-linear-gradient(112deg, transparent 0px, transparent 190px, rgba(240,205,150,.05) 191px, transparent 193px), repeating-linear-gradient(68deg, transparent 0px, transparent 260px, rgba(200,90,60,.06) 261px, transparent 263px)" }} />
        </div>
        <canvas ref={canvasRef} style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }} />
      </div>
      {/* vignette */}
      <div style={{ position: "absolute", inset: 0, pointerEvents: "none", background: `radial-gradient(ellipse 105% 90% at 50% 45%, transparent 42%, rgba(0,0,0,${VIGNETTE}) 100%)` }} />

      {/* ── app ── */}
      <div style={{ position: "relative", height: "100%", display: "flex", flexDirection: "column" }}>

        {/* top bar */}
        <header style={{ display: "flex", alignItems: "center", gap: 20, padding: "14px 26px", borderBottom: `1px solid ${t.border}`, transition: "border-color 1200ms ease", backdropFilter: "blur(4px)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12, minWidth: 280 }}>
            <span style={{ fontSize: 15, color: t.glow, transition: "color 1200ms ease" }}>❖</span>
            <span style={{ fontFamily: cin, fontWeight: 600, fontSize: 17, letterSpacing: ".32em", textTransform: "uppercase", animation: "titleGlow 6s ease-in-out infinite" }}>CompanionCube</span>
          </div>

          {/* game switch */}
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

        {/* body */}
        <div style={{ flex: 1, display: "flex", minHeight: 0 }}>

          {/* progress panel */}
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

          {/* collapse handle */}
          <button className="cc-settings" onClick={() => setCollapsed((v) => !v)} title="Toggle progress panel"
            style={{ width: 20, border: "none", background: "transparent", color: t.textDim, cursor: "pointer", fontSize: 11, flexShrink: 0, transition: "color 300ms" }}>{collapsed ? "❯" : "❮"}</button>

          {/* chat */}
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

            {/* composer */}
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
