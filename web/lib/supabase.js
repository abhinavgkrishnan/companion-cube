import { createClient } from "@supabase/supabase-js";

// Null when the env isn't set — the app then runs in local mode (no login, localStorage progress).
const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

export const supabase = url && key ? createClient(url, key) : null;
export const authEnabled = !!supabase;
