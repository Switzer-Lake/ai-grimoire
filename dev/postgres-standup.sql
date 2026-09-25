-- Create the ai-grimoire role and databases on an existing Postgres server.
-- Run as a superuser (or any role with CREATEROLE + CREATEDB):
--
--   psql -h localhost -U postgres -v pw=localdev -f dev/postgres-standup.sql
--
-- Idempotent: re-running only resets the role's password. Omit -v pw=... to use
-- "localdev".
--
--   grimoire       real data (point AI_GRIMOIRE_DSN at it)
--   grimoire_test  contract tests - they DELETE every row, so never share it
--
-- Tables are created by the plugin on first use; nothing to migrate here.

\set ON_ERROR_STOP on
\if :{?pw}
\else
  \set pw localdev
\endif

SELECT CASE WHEN EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'grimoire')
            THEN format('ALTER ROLE grimoire WITH LOGIN PASSWORD %L', :'pw')
            ELSE format('CREATE ROLE grimoire WITH LOGIN PASSWORD %L', :'pw')
       END
\gexec

-- CREATE DATABASE can't run inside a DO block, so generate it only for the
-- databases that don't exist yet.
SELECT format('CREATE DATABASE %I OWNER grimoire ENCODING ''UTF8''', d)
  FROM unnest(ARRAY['grimoire', 'grimoire_test']) AS d
 WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = d)
\gexec

\echo
\echo 'Done. Connection strings (substitute your password):'
\echo '  export AI_GRIMOIRE_DSN=postgresql://grimoire:<pw>@localhost:5432/grimoire'
\echo '  export AI_GRIMOIRE_TEST_PG_DSN=postgresql://grimoire:<pw>@localhost:5432/grimoire_test'
