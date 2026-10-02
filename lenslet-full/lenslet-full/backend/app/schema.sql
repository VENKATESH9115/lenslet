-- Lenslet schema. Idempotent: safe to run on every start.
CREATE EXTENSION IF NOT EXISTS btree_gist;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS users (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email text NOT NULL,
  name text NOT NULL,
  password_hash text,
  google_sub text UNIQUE,
  avatar_url text,
  phone text,
  role text NOT NULL DEFAULT 'customer' CHECK (role IN ('customer','admin')),
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS users_email_key ON users (lower(email));

CREATE TABLE IF NOT EXISTS categories (
  id serial PRIMARY KEY, slug text UNIQUE NOT NULL, name text NOT NULL, sort int NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS equipment (          -- one row = one physical unit
  id serial PRIMARY KEY,
  slug text UNIQUE NOT NULL,
  category_id int NOT NULL REFERENCES categories(id),
  brand text NOT NULL, name text NOT NULL, short_spec text NOT NULL DEFAULT '',
  description text NOT NULL DEFAULT '',
  price_day int NOT NULL CHECK (price_day > 0),    -- paise
  deposit int NOT NULL DEFAULT 0 CHECK (deposit >= 0),
  serial_no text, condition text NOT NULL DEFAULT 'excellent',
  status text NOT NULL DEFAULT 'available' CHECK (status IN ('available','maintenance','unavailable','archived')),
  rating numeric(2,1) NOT NULL DEFAULT 0, review_count int NOT NULL DEFAULT 0,
  includes text[] NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS kyc (
  user_id uuid PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  full_name text NOT NULL, id_type text NOT NULL CHECK (id_type IN ('aadhaar','passport','driving_licence','voter_id')),
  id_last4 text NOT NULL, status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','approved','rejected')),
  submitted_at timestamptz NOT NULL DEFAULT now(), reviewed_at timestamptz
);

CREATE TABLE IF NOT EXISTS bookings (
  id serial PRIMARY KEY,
  code text UNIQUE,
  user_id uuid NOT NULL REFERENCES users(id),
  status text NOT NULL DEFAULT 'REQUESTED' CHECK (status IN ('REQUESTED','PAYMENT_PENDING','CONFIRMED','READY_FOR_PICKUP','RENTED','RETURN_PENDING','RETURNED','INSPECTION','COMPLETED','CANCELLED')),
  start_at timestamptz NOT NULL, end_at timestamptz NOT NULL CHECK (end_at > start_at),
  fulfilment text NOT NULL CHECK (fulfilment IN ('pickup','home','shoot')),
  address jsonb,
  days int NOT NULL, rental int NOT NULL, discount int NOT NULL DEFAULT 0, delivery_fee int NOT NULL DEFAULT 0,
  tax int NOT NULL DEFAULT 0, deposit int NOT NULL DEFAULT 0, total int NOT NULL,   -- paise
  created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS bookings_user_idx ON bookings(user_id);
CREATE INDEX IF NOT EXISTS bookings_status_idx ON bookings(status);

-- The heart of the system: the database itself refuses overlapping active bookings for one unit.
CREATE TABLE IF NOT EXISTS booking_items (
  id serial PRIMARY KEY,
  booking_id int NOT NULL REFERENCES bookings(id) ON DELETE CASCADE,
  equipment_id int NOT NULL REFERENCES equipment(id),
  price_day int NOT NULL,
  period tstzrange NOT NULL,
  active boolean NOT NULL DEFAULT true,
  CONSTRAINT no_double_booking EXCLUDE USING gist (equipment_id WITH =, period WITH &&) WHERE (active)
);

CREATE TABLE IF NOT EXISTS payments (
  id serial PRIMARY KEY,
  booking_id int NOT NULL REFERENCES bookings(id),
  provider text NOT NULL CHECK (provider IN ('razorpay','manual')),
  provider_order_id text, provider_payment_id text, method text,
  amount int NOT NULL, refunded int NOT NULL DEFAULT 0,
  status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','processing','paid','failed','refunded','partially_refunded')),
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS payments_order_key ON payments(provider_order_id) WHERE provider_order_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS inspections (
  id serial PRIMARY KEY, booking_id int NOT NULL REFERENCES bookings(id),
  condition_before text, condition_after text, damage text, missing_items text,
  late_hours int NOT NULL DEFAULT 0, extra_charges int NOT NULL DEFAULT 0, deposit_deductions int NOT NULL DEFAULT 0,
  deposit_refundable int NOT NULL DEFAULT 0, notes text, inspected_by uuid REFERENCES users(id),
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS notifications (   -- outbox; channels (email/WhatsApp/SMS) plug in at app/notify.py
  id serial PRIMARY KEY, user_id uuid REFERENCES users(id), booking_id int REFERENCES bookings(id),
  kind text NOT NULL, channel text NOT NULL DEFAULT 'email', status text NOT NULL DEFAULT 'queued',
  payload jsonb NOT NULL DEFAULT '{}', created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS audit_logs (
  id bigserial PRIMARY KEY, actor_id uuid, action text NOT NULL, entity text NOT NULL, entity_id text NOT NULL,
  detail jsonb NOT NULL DEFAULT '{}', created_at timestamptz NOT NULL DEFAULT now()
);

-- Seed data (INR, stored in paise)
INSERT INTO categories(slug,name,sort) VALUES
 ('cameras','Cameras',1),('lenses','Lenses',2),('gimbals','Gimbals',3),('tripods','Tripods',4),('lighting','Lighting',5),
 ('microphones','Microphones',6),('monitors','Monitors',7),('drones','Drones',8),('accessories','Accessories',9)
ON CONFLICT DO NOTHING;

INSERT INTO equipment(slug,category_id,brand,name,short_spec,description,price_day,deposit,serial_no,rating,review_count,includes)
SELECT v.slug,c.id,v.brand,v.name,v.spec,v.descr,v.price*100,v.dep*100,v.serial,v.rating,v.rc,v.inc
FROM (VALUES
 ('sony-a7-iv','cameras','Sony','Sony A7 IV','33MP full-frame · 4K 60p','Hybrid full-frame body for weddings and commercial work.',2800,25000,'SN-A7IV-0412',4.9,128,ARRAY['2 batteries','Charger','64GB SD card','Body cap']),
 ('sony-fx3','cameras','Sony','Sony FX3','Cinema line · 4K 120p','Compact cinema camera with active cooling and XLR handle.',4500,40000,'SN-FX3-0117',4.9,86,ARRAY['2 batteries','Charger','XLR handle','CFexpress card']),
 ('canon-r6-ii','cameras','Canon','Canon R6 Mark II','24MP · 6K oversampled','Fast, reliable hybrid body with excellent autofocus.',3000,28000,'SN-R6II-0233',4.8,74,ARRAY['2 batteries','Charger','64GB SD card']),
 ('sony-24-70-gm','lenses','Sony','Sony 24-70mm f/2.8 GM II','Standard zoom · E-mount','The workhorse zoom for events and interviews.',1500,30000,'SN-2470-0098',4.9,102,ARRAY['Hood','Front and rear caps','Pouch']),
 ('sony-70-200-gm','lenses','Sony','Sony 70-200mm f/2.8 GM II','Telephoto zoom · E-mount','Sharp, light telephoto for ceremonies and sports.',1800,35000,'SN-70200-0061',4.9,67,ARRAY['Hood','Tripod collar','Caps']),
 ('dji-rs-4','gimbals','DJI','DJI RS 4','3-axis gimbal · 3 kg payload','Stabiliser for mirrorless cinema rigs.',1200,12000,'SN-RS4-0305',4.8,59,ARRAY['Quick release plate','Grip','Charging cable']),
 ('rode-wireless-pro','microphones','Rode','Rode Wireless PRO','32-bit float · dual transmitter','Clean wireless audio with onboard backup recording.',900,8000,'SN-RWP-0722',4.9,91,ARRAY['2 transmitters','Receiver','Lavalier mics','Charging case']),
 ('godox-sl60','lighting','Godox','Godox SL60','60W LED · Bowens mount','Daylight LED panel for interviews and product shoots.',600,6000,'SN-SL60-0540',4.7,48,ARRAY['Reflector','Power adapter','Stand']),
 ('dji-mini-4-pro','drones','DJI','DJI Mini 4 Pro','Under 249 g · 4K HDR','Pocket drone for travel and real estate.',2200,20000,'SN-M4P-0088',4.8,53,ARRAY['3 batteries','Controller','Charging hub','Case']),
 ('manfrotto-190-tripod','tripods','Manfrotto','Manfrotto 190 Carbon Tripod','Carbon fibre · fluid head','Stable, light tripod with a smooth fluid head.',500,5000,'SN-M190-0419',4.7,44,ARRAY['Fluid head','Carry bag'])
) AS v(slug,cat,brand,name,spec,descr,price,dep,serial,rating,rc,inc)
JOIN categories c ON c.slug=v.cat
ON CONFLICT (slug) DO NOTHING;
