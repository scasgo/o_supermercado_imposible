-- O supermercado imposible
-- Run this whole file once in Supabase Dashboard > SQL Editor.

create table if not exists public.responses (
    participant_id uuid primary key,
    timestamp_utc timestamptz not null default now(),
    age_band text not null,
    online_purchase_frequency text not null,
    condition text not null check (condition in ('small', 'large', 'algorithm')),

    pref_priority text null check (
        pref_priority is null or pref_priority in ('prezo', 'sabor', 'nutricion', 'sustentabilidade')
    ),
    pref_flavor text null check (
        pref_flavor is null or pref_flavor in ('chocolate', 'froitas', 'mel_froitos_secos', 'neutro_avena')
    ),
    pref_price text null check (
        pref_price is null or pref_price in ('menos_3', 'de_3_a_4', 'mais_4')
    ),

    decision_start timestamptz null,
    decision_end timestamptz null,
    decision_seconds numeric(10, 3) null check (decision_seconds is null or decision_seconds >= 0),

    product_selected text null,
    no_choice boolean not null default false,

    difficulty smallint null check (difficulty is null or difficulty between 1 and 7),
    confidence smallint null check (confidence is null or confidence between 1 and 7),
    satisfaction smallint null check (satisfaction is null or satisfaction between 1 and 7),
    continue_searching boolean null,

    opened_full_catalog boolean not null default false,
    recommendation_ids text[] null,

    status text not null check (status in ('assigned', 'preferences_done', 'decision_made', 'completed')),
    total_start timestamptz null,
    completed_at timestamptz null,
    total_seconds numeric(10, 3) null check (total_seconds is null or total_seconds >= 0),
    is_demo boolean not null default false,

    constraint no_choice_consistency check (
        not (no_choice = true and product_selected is not null)
    )
);

create index if not exists responses_condition_idx
    on public.responses (condition);

create index if not exists responses_status_demo_idx
    on public.responses (status, is_demo);

create index if not exists responses_timestamp_idx
    on public.responses (timestamp_utc);

-- RLS = Row Level Security: rules that restrict which rows a low-privilege client can access.
-- This project does NOT expose a publishable/anon key to participants. Streamlit runs on a server
-- and uses a Supabase Secret key stored only in Streamlit secrets. Secret keys map to service_role
-- and bypass RLS, so we keep RLS enabled with no public policies and revoke public roles.
alter table public.responses enable row level security;

revoke all on table public.responses from anon;
revoke all on table public.responses from authenticated;

grant select, insert, update on table public.responses to service_role;
