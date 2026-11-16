#!/bin/sh
# Starts a throwaway Postgres 16 (port 5433) plus PostgREST (port 3001) that behave like the Supabase API,
# loads source/supabase-setup.sql, so the SQL rules can be tested without Supabase.
# Needs: postgresql-16 (apt), and the PostgREST binary at /tmp/postgrest
#   curl -sSL -o /tmp/p.tar.xz https://github.com/PostgREST/postgrest/releases/download/v12.2.3/postgrest-v12.2.3-linux-static-x64.tar.xz && tar -C /tmp -xf /tmp/p.tar.xz
# Then:  python3 source/test_security_sql.py     (and: node source/test_names.js | compare with the database, see masterfile)
# Stop:  su postgres -c "/usr/lib/postgresql/16/bin/pg_ctl -D /tmp/pg/data stop"; pkill postgrest
set -e
mkdir -p /tmp/pg && chown postgres /tmp/pg
su postgres -c "/usr/lib/postgresql/16/bin/initdb -D /tmp/pg/data -A trust -E UTF8 --locale=C.UTF-8 >/dev/null && /usr/lib/postgresql/16/bin/pg_ctl -D /tmp/pg/data -o '-p 5433 -k /tmp/pg' -l /tmp/pg/log start"
sleep 2
psql -h /tmp/pg -p 5433 -U postgres -q -c "create role anon nologin; create role authenticated nologin; create role authenticator noinherit login; grant anon, authenticated to authenticator;"
psql -h /tmp/pg -p 5433 -U postgres -q -v ON_ERROR_STOP=1 -f "$(dirname "$0")/supabase-setup.sql" >/dev/null
cat > /tmp/pgrst.conf <<CONF
db-uri = "postgres://authenticator@/postgres?host=/tmp/pg&port=5433"
db-schemas = "public"
db-anon-role = "anon"
server-port = 3001
CONF
(nohup /tmp/postgrest /tmp/pgrst.conf > /tmp/pgrst.log 2>&1 &)
sleep 2
echo "Ready: PostgREST on http://127.0.0.1:3001"
