// Persistence for progress + conversations. Uses Supabase (per-user, cross-device) when signed in;
// falls back to localStorage so the app still works with no account / no Supabase configured.

import { supabase } from "./supabase";

const lsKey = (game) => `cc-progress-${game}`;
const checklistLsKey = (game) => `cc-checklist-${game}`;

export async function loadProgress(user, game, fallback) {
  if (supabase && user) {
    const { data } = await supabase.from("progress").select("beats").eq("game", game).maybeSingle();
    return data?.beats ?? fallback;
  }
  if (typeof window !== "undefined") {
    const raw = localStorage.getItem(lsKey(game));
    if (raw) return JSON.parse(raw);
  }
  return fallback;
}

export async function saveProgress(user, game, beats) {
  if (supabase && user) {
    await supabase.from("progress").upsert(
      { user_id: user.id, game, beats, updated_at: new Date().toISOString() },
      { onConflict: "user_id,game" },
    );
  } else if (typeof window !== "undefined") {
    localStorage.setItem(lsKey(game), JSON.stringify(beats));
  }
}

// The completion checklist (mask shards, tools, charms, ...) — a separate, purely-informational
// tracker. It never feeds the spoiler gate; see web/lib/checklistData.js.
export async function loadChecklist(user, game, fallback = []) {
  if (supabase && user) {
    const { data } = await supabase.from("collectibles").select("items").eq("game", game).maybeSingle();
    return data?.items ?? fallback;
  }
  if (typeof window !== "undefined") {
    const raw = localStorage.getItem(checklistLsKey(game));
    if (raw) return JSON.parse(raw);
  }
  return fallback;
}

export async function saveChecklist(user, game, items) {
  if (supabase && user) {
    await supabase.from("collectibles").upsert(
      { user_id: user.id, game, items, updated_at: new Date().toISOString() },
      { onConflict: "user_id,game" },
    );
  } else if (typeof window !== "undefined") {
    localStorage.setItem(checklistLsKey(game), JSON.stringify(items));
  }
}

// One conversation per (user, game) — the running thread for that game.
export async function loadConversation(user, game) {
  if (!supabase || !user) return { id: null, messages: [] };
  let { data: convo } = await supabase
    .from("conversations").select("id").eq("game", game)
    .order("created_at", { ascending: false }).limit(1).maybeSingle();
  if (!convo) {
    const res = await supabase.from("conversations").insert({ user_id: user.id, game }).select("id").single();
    convo = res.data;
  }
  const { data: msgs } = await supabase
    .from("messages").select("id, role, content, citations").eq("conversation_id", convo.id).order("id");
  return {
    id: convo.id,
    messages: (msgs || []).map((m) => ({ id: `db-${m.id}`, role: m.role, md: m.content, citations: m.citations || [] })),
  };
}

export async function saveMessage(conversationId, role, content, citations = []) {
  if (!supabase || !conversationId) return;
  await supabase.from("messages").insert({ conversation_id: conversationId, role, content, citations });
}
