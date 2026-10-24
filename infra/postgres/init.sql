-- infra/postgres/init.sql
-- Runs ONCE, the first time the Postgres container starts with an empty volume.
-- LOCAL DEVELOPMENT ONLY: these passwords are never used in production.

-- One database user per service
CREATE USER identity_user WITH PASSWORD 'identity_dev_pw';
CREATE USER ride_user     WITH PASSWORD 'ride_dev_pw';
CREATE USER booking_user  WITH PASSWORD 'booking_dev_pw';
CREATE USER agent_user    WITH PASSWORD 'agent_dev_pw';
CREATE USER realtime_user WITH PASSWORD 'realtime_dev_pw';

-- One database per service, owned by that service's user
CREATE DATABASE identity_db OWNER identity_user;
CREATE DATABASE ride_db     OWNER ride_user;
CREATE DATABASE booking_db  OWNER booking_user;
CREATE DATABASE agent_db    OWNER agent_user;
CREATE DATABASE realtime_db OWNER realtime_user;
CREATE DATABASE identity_test_db OWNER identity_user;

-- Boundary enforcement: other users cannot even connect to a service's database
REVOKE CONNECT ON DATABASE identity_db FROM PUBLIC;
REVOKE CONNECT ON DATABASE ride_db     FROM PUBLIC;
REVOKE CONNECT ON DATABASE booking_db  FROM PUBLIC;
REVOKE CONNECT ON DATABASE agent_db    FROM PUBLIC;
REVOKE CONNECT ON DATABASE realtime_db FROM PUBLIC;

-- Only ride_db needs PostGIS. Enabling it requires a superuser, so we do it here.
\connect ride_db
CREATE EXTENSION IF NOT EXISTS postgis;