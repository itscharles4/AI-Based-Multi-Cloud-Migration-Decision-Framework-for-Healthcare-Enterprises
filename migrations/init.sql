-- migrations/init.sql
-- =====================================================================
-- Runs automatically on first PostgreSQL container start
-- Creates the MLflow database and enables TimescaleDB extension
-- =====================================================================

-- Create MLflow database
SELECT 'CREATE DATABASE mlflow' WHERE NOT EXISTS (
    SELECT FROM pg_database WHERE datname = 'mlflow'
)\gexec

-- Enable TimescaleDB extension on main DB
\c telemedicine
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
