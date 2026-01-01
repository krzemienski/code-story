-- Code Story Database Initialization Script
-- This script runs when PostgreSQL container first starts

-- Initialize extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Create enum types (idempotent with DO blocks)
DO $$ BEGIN
    CREATE TYPE story_status AS ENUM ('pending', 'analyzing', 'generating', 'synthesizing', 'completed', 'failed');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE narrative_style AS ENUM ('fiction', 'documentary', 'tutorial', 'podcast', 'technical');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE user_plan AS ENUM ('free', 'pro', 'enterprise');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE admin_role AS ENUM ('super_admin', 'admin', 'support');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Grant permissions (use current database)
DO $$
DECLARE
    db_name TEXT;
    db_user TEXT;
BEGIN
    SELECT current_database() INTO db_name;
    SELECT current_user INTO db_user;
    EXECUTE format('GRANT ALL PRIVILEGES ON DATABASE %I TO %I', db_name, db_user);
END $$;

-- Create schema for analytics if needed
CREATE SCHEMA IF NOT EXISTS analytics;

-- Output completion message
DO $$ BEGIN
    RAISE NOTICE 'Code Story database initialization complete.';
END $$;
