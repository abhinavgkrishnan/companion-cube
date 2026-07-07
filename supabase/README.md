# Supabase setup

Auth (Google) + per-user sync of progress and conversations live in Supabase; the FastAPI backend
stays stateless. One-time setup:

## 1. Project
1. Create a free project at [supabase.com](https://supabase.com).
2. **SQL Editor** → paste and run [`schema.sql`](./schema.sql) (tables + row-level security).
3. **Settings → API** → copy the **Project URL** and the **anon public** key.

## 2. Google login (no OTP, no passwords)
1. [Google Cloud Console](https://console.cloud.google.com) → **APIs & Services → Credentials** →
   **Create OAuth client ID** → *Web application*.
2. **Authorized redirect URI:** `https://<project-ref>.supabase.co/auth/v1/callback`
   (find `<project-ref>` in your Supabase project URL).
3. Copy the client ID + secret into Supabase → **Authentication → Providers → Google** (enable it).
4. **Authentication → URL Configuration** → add your redirect URLs:
   `http://localhost:3000` and your production domain.

## 3. Frontend env
Create `web/.env.local`:

```
NEXT_PUBLIC_SUPABASE_URL=https://<project-ref>.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=<anon public key>
NEXT_PUBLIC_API_BASE=            # blank in dev (Next proxies /api); the FastAPI URL in prod
```

Then `cd web && npm install` (pulls in `@supabase/supabase-js`) and `npm run dev`.

## Notes
- The anon key is safe to ship to the browser — RLS is what protects the data, not the key.
- The backend needs none of these; it only answers gated questions.
