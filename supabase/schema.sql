-- companion-cube — Supabase schema. Paste into your project's SQL Editor and run.
-- Auth is Google OAuth (Authentication > Providers > Google). Every table is row-level-secured, so a
-- signed-in user only ever reads or writes their own rows — the client talks to Postgres directly and
-- RLS is the guard.

-- progress: one row per user per game — the set of completed beat ids
create table if not exists progress (
  user_id    uuid not null references auth.users (id) on delete cascade,
  game       text not null,
  beats      jsonb not null default '[]'::jsonb,
  updated_at timestamptz not null default now(),
  primary key (user_id, game)
);
alter table progress enable row level security;
create policy "own progress" on progress
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- collectibles: one row per user per game — the set of checked completion-checklist item ids
-- (mask shards, tools, charms, ...). Purely for the player's own tracking; unlike `progress`, this
-- never gates retrieval. See web/lib/checklistData.js for the item taxonomy.
create table if not exists collectibles (
  user_id    uuid not null references auth.users (id) on delete cascade,
  game       text not null,
  items      jsonb not null default '[]'::jsonb,
  updated_at timestamptz not null default now(),
  primary key (user_id, game)
);
alter table collectibles enable row level security;
create policy "own collectibles" on collectibles
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- conversations: a chat thread, per user per game
create table if not exists conversations (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null references auth.users (id) on delete cascade,
  game       text not null,
  title      text,
  created_at timestamptz not null default now()
);
alter table conversations enable row level security;
create policy "own conversations" on conversations
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- messages: the turns of a conversation
create table if not exists messages (
  id              bigint generated always as identity primary key,
  conversation_id uuid not null references conversations (id) on delete cascade,
  role            text not null check (role in ('user', 'guide')),
  content         text not null,
  citations       jsonb not null default '[]'::jsonb,
  created_at      timestamptz not null default now()
);
create index if not exists idx_messages_conversation on messages (conversation_id, id);
alter table messages enable row level security;
create policy "own messages" on messages
  for all
  using (exists (select 1 from conversations c where c.id = conversation_id and c.user_id = auth.uid()))
  with check (exists (select 1 from conversations c where c.id = conversation_id and c.user_id = auth.uid()));
