#!/bin/sh
set -eu
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  --set=gateway_user="$FINANCE_GATEWAY_DB_USER" --set=gateway_password="$FINANCE_GATEWAY_DB_PASSWORD" --set=gateway_db="$FINANCE_GATEWAY_DB" <<'SQL'
CREATE USER :"gateway_user" WITH PASSWORD :'gateway_password';
CREATE DATABASE :"gateway_db" OWNER :"gateway_user";
REVOKE ALL ON DATABASE :"gateway_db" FROM PUBLIC;
SQL
PGPASSWORD="$FINANCE_GATEWAY_DB_PASSWORD" psql -v ON_ERROR_STOP=1 \
  --username "$FINANCE_GATEWAY_DB_USER" --dbname "$FINANCE_GATEWAY_DB" -f /opt/finance/gateway-schema.sql
