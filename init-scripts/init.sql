---------------------------------------------------------------------
-- INIT SCRIPT FOR POSTGRES DOCKER CONTAINER
-- This file runs ONCE on first initialization of the database.
-- Place inside:  docker-entrypoint-initdb.d/01-init.sql
---------------------------------------------------------------------

---------------------------------------------------------------------
-- 1. Create Application User
-- (Postgres automatically creates POSTGRES_USER from environment
--  but you should explicitly create your app user if needed.)
---------------------------------------------------------------------

CREATE USER werun_user WITH PASSWORD 'password';

---------------------------------------------------------------------
-- 2. Create Application Database
-- (If you already set POSTGRES_DB=werun_db in docker-compose,
--  Postgres will auto-create it.
--  But CREATE DATABASE is harmless if it already exists.)
---------------------------------------------------------------------

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT FROM pg_database WHERE datname = 'werun_db'
    ) THEN
        CREATE DATABASE werun_db OWNER werun_user;
    END IF;
END$$;

---------------------------------------------------------------------
-- 3. Grant Privileges
---------------------------------------------------------------------

GRANT ALL PRIVILEGES ON DATABASE werun_db TO werun_user;

---------------------------------------------------------------------
-- Switch into the new database for the rest of the script
---------------------------------------------------------------------
\connect werun_db;

---------------------------------------------------------------------
-- 4. Create Tables
-- This is the main table that stores multiple entries per phase
---------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS cycle_phase_entries (
    id SERIAL PRIMARY KEY,
    cycle_id INTEGER NOT NULL,
    phase_name VARCHAR(50) NOT NULL CHECK (
        phase_name IN ('Menstrual', 'Follicular', 'Ovulatory', 'Luteal')
    ),
    pace NUMERIC(5,2) NOT NULL,
    motivation_level INTEGER NOT NULL CHECK (motivation_level BETWEEN 1 AND 10),
    entry_timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Useful indexes
CREATE INDEX IF NOT EXISTS idx_cycle_phase ON cycle_phase_entries(cycle_id, phase_name);
CREATE INDEX IF NOT EXISTS idx_phase_timestamp ON cycle_phase_entries(phase_name, entry_timestamp);

---------------------------------------------------------------------
-- 5. Insert Seed Data (3 months worth)
---------------------------------------------------------------------

-- ==========================
-- CYCLE 1 (Jan 1 – Jan 28)
-- ==========================
INSERT INTO cycle_phase_entries (cycle_id, phase_name, pace, motivation_level, created_at) VALUES
(1, 'Menstrual', 6.20, 4, '2025-01-01'),
(1, 'Menstrual', 6.15, 4, '2025-01-02'),
(1, 'Menstrual', 6.05, 5, '2025-01-04'),

(1, 'Follicular', 5.70, 6, '2025-01-06'),
(1, 'Follicular', 5.55, 7, '2025-01-09'),
(1, 'Follicular', 5.48, 7, '2025-01-11'),
(1, 'Follicular', 5.52, 8, '2025-01-13'),

(1, 'Ovulatory', 5.32, 8, '2025-01-14'),
(1, 'Ovulatory', 5.28, 8, '2025-01-15'),
(1, 'Ovulatory', 5.36, 9, '2025-01-16'),

(1, 'Luteal', 5.66, 8, '2025-01-18'),
(1, 'Luteal', 5.60, 9, '2025-01-20'),
(1, 'Luteal', 5.72, 7, '2025-01-23'),
(1, 'Luteal', 5.68, 8, '2025-01-27');

-- ==========================
-- CYCLE 2 (Jan 29 – Feb 25)
-- ==========================
INSERT INTO cycle_phase_entries (cycle_id, phase_name, pace, motivation_level, created_at) VALUES
(2, 'Menstrual', 6.18, 4, '2025-01-29'),
(2, 'Menstrual', 6.10, 5, '2025-01-30'),
(2, 'Menstrual', 6.14, 4, '2025-02-01'),

(2, 'Follicular', 5.63, 6, '2025-02-03'),
(2, 'Follicular', 5.52, 7, '2025-02-05'),
(2, 'Follicular', 5.49, 7, '2025-02-08'),
(2, 'Follicular', 5.46, 8, '2025-02-10'),

(2, 'Ovulatory', 5.31, 8, '2025-02-11'),
(2, 'Ovulatory', 5.29, 9, '2025-02-12'),
(2, 'Ovulatory', 5.34, 8, '2025-02-13'),

(2, 'Luteal', 5.69, 8, '2025-02-15'),
(2, 'Luteal', 5.65, 9, '2025-02-17'),
(2, 'Luteal', 5.70, 7, '2025-02-20'),
(2, 'Luteal', 5.75, 8, '2025-02-24');

-- ==========================
-- CYCLE 3 (Feb 26 – Mar 25)
-- ==========================
INSERT INTO cycle_phase_entries (cycle_id, phase_name, pace, motivation_level, created_at) VALUES
(3, 'Menstrual', 6.22, 4, '2025-02-26'),
(3, 'Menstrual', 6.16, 5, '2025-02-27'),
(3, 'Menstrual', 6.11, 5, '2025-03-01'),

(3, 'Follicular', 5.68, 6, '2025-03-03'),
(3, 'Follicular', 5.50, 7, '2025-03-05'),
(3, 'Follicular', 5.47, 8, '2025-03-08'),
(3, 'Follicular', 5.45, 8, '2025-03-10'),

(3, 'Ovulatory', 5.33, 8, '2025-03-11'),
(3, 'Ovulatory', 5.30, 9, '2025-03-12'),
(3, 'Ovulatory', 5.27, 9, '2025-03-13'),

(3, 'Luteal', 5.71, 8, '2025-03-15'),
(3, 'Luteal', 5.63, 9, '2025-03-18'),
(3, 'Luteal', 5.76, 7, '2025-03-20'),
(3, 'Luteal', 5.69, 8, '2025-03-24');

---------------------------------------------------------------------
-- End of file
---------------------------------------------------------------------
