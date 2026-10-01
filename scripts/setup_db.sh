#!/usr/bin/env bash
# Fixed project identifiers; only the password is a SQL variable.
set -euo pipefail
cd "$(dirname "$0")/.."
test -s secrets/db_password.txt
jev_db_password=$(cat secrets/db_password.txt)
# Secret travels over stdin, not shell tracing, output, or SQL interpolation.
{ printf '\\set job_password %s\n' "'${jev_db_password//\'/\'\'}'"; cat <<'SQL'
SELECT format('CREATE ROLE jev LOGIN PASSWORD %L', :'job_password')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'jev') \gexec
SELECT format('ALTER ROLE jev PASSWORD %L', :'job_password') \gexec
SELECT 'CREATE DATABASE jev OWNER jev' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname='jev') \gexec
SQL
} | docker exec -i postgres psql -v ON_ERROR_STOP=1 -U postgres -d postgres
docker exec -i postgres psql -v ON_ERROR_STOP=1 -U postgres -d jev <<'SQL'
CREATE EXTENSION IF NOT EXISTS vector;
CREATE SCHEMA IF NOT EXISTS jev AUTHORIZATION jev;
ALTER ROLE jev IN DATABASE jev SET search_path TO jev, public;
GRANT ALL ON SCHEMA jev TO jev;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
REVOKE CREATE ON SCHEMA public FROM jev;
GRANT USAGE ON SCHEMA public TO jev;
SQL
docker compose run --rm --entrypoint alembic jev-backend upgrade head
docker exec postgres psql -v ON_ERROR_STOP=1 -U postgres -d jev -c "DO \$\$ BEGIN IF EXISTS (SELECT FROM pg_tables WHERE schemaname='public' AND tableowner='jev') THEN RAISE EXCEPTION 'Application table outside jev schema'; END IF; END \$\$;"
