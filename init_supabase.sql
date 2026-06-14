-- init_supabase.sql
-- 在 Supabase → SQL Editor 貼上執行（只需一次）
-- 若已執行過，再跑也安全（全部 IF NOT EXISTS）

-- ── 主表 ───────────────────────────────────────────────────────────────────────
create table if not exists contacts (
  id               text primary key,
  company          text not null default '',
  company_en       text not null default '',
  name_zh          text not null default '',
  name_en          text not null default '',
  title            text not null default '',
  department       text not null default '',
  mobile           text not null default '',
  phone            text not null default '',
  fax              text not null default '',
  email            text not null default '',
  address          text not null default '',
  website          text not null default '',
  tags             text not null default '',
  notes            text not null default '',
  front_image_path text not null default '',
  back_image_path  text not null default '',
  drive_file_id    text not null default '',
  ocr_raw_text     text not null default '',
  created_at       text not null default '',
  updated_at       text not null default ''
);

-- ── 索引 ───────────────────────────────────────────────────────────────────────
create index if not exists idx_contacts_email    on contacts (email);
create index if not exists idx_contacts_mobile   on contacts (mobile);
create index if not exists idx_contacts_name_zh  on contacts (name_zh);
create index if not exists idx_contacts_company  on contacts (company);
create index if not exists idx_contacts_updated  on contacts (updated_at desc);

-- ── exec_sql RPC（讓 Python init_db() 可自動建表）────────────────────────────
-- 若不需要 Python 自動建表，可略過這段
create or replace function exec_sql(sql text)
returns void
language plpgsql
security definer
as $$
begin
  execute sql;
end;
$$;

-- ── 完成 ───────────────────────────────────────────────────────────────────────
-- 驗證：
select count(*) from contacts;
