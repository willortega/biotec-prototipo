-- =====================================================================
--  BASE DE DATOS DEL PROTOTIPO BIOTEC (Supabase / PostgreSQL)
--  Cómo usarlo: Supabase > SQL Editor > New query > pegar todo > Run
-- =====================================================================

-- 1. LOTES: cada lote de larvas que entra a una cama de cría
create table if not exists lotes (
  id               bigint generated always as identity primary key,
  codigo           text unique not null,          -- ej. L-2026-001
  cama             text not null,                 -- ej. cama-01 (debe coincidir con el nodo)
  fecha_siembra    date not null,
  origen_sustrato  text,                          -- proveedor o fuente del residuo
  tipo_sustrato    text,                          -- ej. frutas y verduras, cerdaza, mezcla
  peso_sustrato_kg numeric,                       -- kg de residuo al inicio
  peso_larvas_g    numeric,                       -- g de larvas sembradas
  etapa            text default 'Larva',          -- Larva, Prepupa, Cosechado, Descartado
  fecha_cosecha    date,
  peso_cosecha_kg  numeric,                       -- kg de larva cosechada
  peso_frass_kg    numeric,                       -- kg de abono (frass) obtenido
  responsable      text,
  observaciones    text,
  creado_en        timestamptz default now()
);

-- 2. EVENTOS: todo lo que le pasa a un lote (alimentación, volteo, incidencias...)
create table if not exists eventos_lote (
  id           bigint generated always as identity primary key,
  lote_id      bigint references lotes(id) on delete cascade,
  fecha        timestamptz default now(),
  tipo         text not null,     -- Alimentación, Volteo, Cambio de etapa, Incidencia, Muestreo
  cantidad_kg  numeric,           -- ej. kg de alimento agregado
  descripcion  text,
  responsable  text
);

-- 3. LECTURAS: datos que envía el nodo IoT (físico o virtual)
create table if not exists lecturas (
  id             bigint generated always as identity primary key,
  creado_en      timestamptz default now(),
  nodo           text,
  cama           text,
  temp_aire      numeric,
  hum_aire       numeric,
  temp_sustrato  numeric,
  hum_sustrato   numeric
);

create index if not exists idx_lecturas_cama_fecha on lecturas (cama, creado_en);
create index if not exists idx_eventos_lote on eventos_lote (lote_id, fecha);

-- 4. PERMISOS DEL PROTOTIPO
-- Supabase activa "Row Level Security". Estas políticas permiten que el nodo
-- y la aplicación lean y escriban con la clave pública (anon).
-- LIMITACIÓN A DOCUMENTAR: en producción se usarían usuarios autenticados.
alter table lotes        enable row level security;
alter table eventos_lote enable row level security;
alter table lecturas     enable row level security;

create policy "proto_select_lotes"   on lotes        for select to anon using (true);
create policy "proto_insert_lotes"   on lotes        for insert to anon with check (true);
create policy "proto_update_lotes"   on lotes        for update to anon using (true) with check (true);

create policy "proto_select_eventos" on eventos_lote for select to anon using (true);
create policy "proto_insert_eventos" on eventos_lote for insert to anon with check (true);

create policy "proto_select_lect"    on lecturas     for select to anon using (true);
create policy "proto_insert_lect"    on lecturas     for insert to anon with check (true);

-- 5. PRUEBA RÁPIDA (opcional): inserte una lectura manual y consúltela
-- insert into lecturas (nodo, cama, temp_aire, hum_aire, temp_sustrato, hum_sustrato)
-- values ('prueba', 'cama-01', 30.5, 72, 33.1, 65);
-- select * from lecturas order by creado_en desc limit 5;
