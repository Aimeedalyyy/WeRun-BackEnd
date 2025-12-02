-- init-scripts/01-init.sql
-- Optional: This runs automatically when PostgreSQL container first starts
-- Only needed if you want to create additional databases or configurations

-- The main database is already created by POSTGRES_DB environment variable
-- But you can add extra setup here:

-- Create additional databases if needed
-- CREATE DATABASE myapp_test;

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE wereun_db TO werun_user;


-- You could also create custom functions, triggers, etc. here