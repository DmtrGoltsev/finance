#!/usr/bin/env bash
set -euo pipefail
export LC_ALL=C

echo 'schema=finance_inventory_v4'

flag() {
  local key="$1"
  shift
  if "$@" >/dev/null 2>&1; then
    printf '%s=yes\n' "$key"
  else
    printf '%s=no\n' "$key"
  fi
}

safe_identity() {
  local name="$1" value="$2"
  if [[ "$value" =~ ^[a-z_][a-z0-9_-]{0,31}$ ]]; then
    printf '%s=%s\n' "$name" "$value"
  elif [[ -z "$value" ]]; then
    printf '%s=default\n' "$name"
  else
    printf '%s=unknown\n' "$name"
  fi
}

http_status() {
  local name="$1" url="$2" status
  status="$(curl -sS --max-time 3 -o /dev/null -w '%{http_code}' "$url" 2>/dev/null || true)"
  if [[ "$status" =~ ^[1-5][0-9][0-9]$ ]]; then
    printf '%s=%s\n' "$name" "$status"
  else
    printf '%s=000\n' "$name"
  fi
}

number_or_unknown() {
  local name="$1" value="$2"
  if [[ "$value" =~ ^[0-9]+$ ]]; then
    printf '%s=%s\n' "$name" "$value"
  else
    printf '%s=unknown\n' "$name"
  fi
}

service_state() {
  local name="$1" service="$2" load state
  load="$(systemctl show "$service" -p LoadState --value 2>/dev/null || true)"
  if [[ "$load" == not-found ]]; then
    printf '%s=not_found\n' "$name"
    return
  fi
  if [[ "$load" != loaded ]]; then
    printf '%s=unknown\n' "$name"
    return
  fi
  state="$(systemctl is-active "$service" 2>/dev/null || true)"
  case "$state" in
    active|inactive|failed|activating|deactivating) printf '%s=%s\n' "$name" "$state" ;;
    *) printf '%s=unknown\n' "$name" ;;
  esac
}

listener_scope() {
  local name="$1" port="$2" sockets="$3" addresses
  addresses="$(awk -v port=":${port}" '$4 ~ (port "$") {print $4}' <<< "$sockets")"
  if [[ -z "$addresses" ]]; then
    printf '%s=none\n' "$name"
  elif grep -Eqv '^(127\.[0-9]+\.[0-9]+\.[0-9]+|\[::1\]|::1):[0-9]+$' <<< "$addresses"; then
    printf '%s=non_loopback\n' "$name"
  else
    printf '%s=loopback\n' "$name"
  fi
}

path_flags() {
  local name="$1" path="$2"
  flag "${name}_exists" test -e "$path"
  flag "${name}_readable" test -r "$path"
  flag "${name}_writable" test -w "$path"
}

link_scope() {
  local name="$1" link="$2" prefix="$3" target
  if ! test -L "$link"; then
    printf '%s=not_symlink\n' "$name"
    return
  fi
  target="$(readlink -f "$link" 2>/dev/null || true)"
  case "$target" in
    "${prefix}/"*) printf '%s=within_releases\n' "$name" ;;
    *) printf '%s=outside_releases\n' "$name" ;;
  esac
}

hostname_value="$(hostname 2>/dev/null || true)"
if [[ -n "$hostname_value" ]] && command -v sha256sum >/dev/null 2>&1; then
  printf 'hostname_sha256=%s\n' "$(printf '%s' "$hostname_value" | sha256sum | cut -d ' ' -f 1)"
else
  echo 'hostname_sha256=unknown'
fi
os_id=unknown
os_version=unknown
if test -r /etc/os-release; then
  os_id="$(awk -F= '$1 == "ID" {gsub(/"/, "", $2); print $2; exit}' /etc/os-release)"
  os_version="$(awk -F= '$1 == "VERSION_ID" {gsub(/"/, "", $2); print $2; exit}' /etc/os-release)"
fi
if [[ "$os_id" =~ ^[a-z][a-z0-9._-]{0,31}$ ]]; then
  printf 'os_id=%s\n' "$os_id"
else
  echo 'os_id=unknown'
fi
if [[ "$os_version" =~ ^[0-9][A-Za-z0-9._-]{0,31}$ ]]; then
  printf 'os_version=%s\n' "$os_version"
else
  echo 'os_version=unknown'
fi
arch="$(uname -m 2>/dev/null || true)"
case "$arch" in
  x86_64|aarch64|armv7l|i686) printf 'os_arch=%s\n' "$arch" ;;
  *) echo 'os_arch=unknown' ;;
esac
package_manager=none
for candidate in apt-get dnf yum apk; do
  if command -v "$candidate" >/dev/null 2>&1; then
    package_manager="$candidate"
    break
  fi
done
printf 'package_manager=%s\n' "$package_manager"
docker_candidate=none
for candidate in /usr/bin/docker /usr/local/bin/docker /snap/bin/docker; do
  if test -x "$candidate"; then
    docker_candidate="$candidate"
    break
  fi
done
case "$docker_candidate" in
  /usr/bin/docker) echo 'docker_candidate=usr_bin' ;;
  /usr/local/bin/docker) echo 'docker_candidate=usr_local_bin' ;;
  /snap/bin/docker) echo 'docker_candidate=snap_bin' ;;
  *) echo 'docker_candidate=none' ;;
esac
number_or_unknown mem_total_kib "$(awk '$1 == "MemTotal:" {print $2; exit}' /proc/meminfo 2>/dev/null || true)"
number_or_unknown mem_available_kib "$(awk '$1 == "MemAvailable:" {print $2; exit}' /proc/meminfo 2>/dev/null || true)"
for target in opt var_lib; do
  case "$target" in
    opt) path=/opt ;;
    var_lib) path=/var/lib ;;
  esac
  number_or_unknown "${target}_free_kib" "$(df -Pk -- "$path" 2>/dev/null | awk 'END {if (NR > 1) print $4}' || true)"
done
ssh_user="$(id -un 2>/dev/null || true)"
if [[ -n "$ssh_user" ]]; then
  safe_identity ssh_user "$ssh_user"
else
  echo 'ssh_user=unknown'
fi
if groups="$(id -nG 2>/dev/null)"; then
  if [[ " $groups " == *' docker '* ]]; then
    echo 'docker_group_member=yes'
  else
    echo 'docker_group_member=no'
  fi
else
  echo 'docker_group_member=unknown'
fi
flag systemctl_available command -v systemctl
flag backend_service_active systemctl is-active --quiet finance-backend.service
backend_load_state="$(systemctl show finance-backend.service -p LoadState --value 2>/dev/null || true)"
if [[ "$backend_load_state" == loaded ]]; then
  safe_identity backend_service_user "$(systemctl show finance-backend.service -p User --value 2>/dev/null || true)"
  safe_identity backend_service_group "$(systemctl show finance-backend.service -p Group --value 2>/dev/null || true)"
  unit_path="$(systemctl show finance-backend.service -p FragmentPath --value 2>/dev/null || true)"
  case "$unit_path" in
    /etc/systemd/system/finance-backend.service|/lib/systemd/system/finance-backend.service|/usr/lib/systemd/system/finance-backend.service)
      printf 'backend_unit_path=%s\n' "$unit_path" ;;
    '') echo 'backend_unit_path=unknown' ;;
    *) echo 'backend_unit_path=other' ;;
  esac
  working_directory="$(systemctl show finance-backend.service -p WorkingDirectory --value 2>/dev/null || true)"
  if [[ "$working_directory" =~ ^/opt/finance(/[A-Za-z0-9._-]+)*$ ]]; then
    printf 'backend_working_directory=%s\n' "$working_directory"
  elif [[ -z "$working_directory" ]]; then
    echo 'backend_working_directory=unset'
  else
    echo 'backend_working_directory=other'
  fi
else
  echo 'backend_service_user=unknown'
  echo 'backend_service_group=unknown'
  echo 'backend_unit_path=unknown'
  echo 'backend_working_directory=unknown'
fi
for service in docker n8n nginx caddy postgresql; do
  service_state "${service}_service_state" "${service}.service"
done
service_state finance_backend_service_state finance-backend.service
for service in finance-delivery finance-n8n finance-gateway; do
  state="$(systemctl show "${service}.service" -p LoadState --value 2>/dev/null || true)"
  if [[ "$state" == loaded ]]; then
    printf '%s_unit_present=yes\n' "${service//-/_}"
  else
    printf '%s_unit_present=no\n' "${service//-/_}"
  fi
done
echo 'backend_service_wiring=unknown'

path_flags backend_releases /opt/finance/releases
path_flags frontend_releases /var/www/finance/releases
path_flags db_backup /opt/finance/backups/postgres
path_flags finance_etc /etc/finance
path_flags n8n_candidate /opt/finance/finance-n8n
path_flags worker_candidate /opt/finance/finance-delivery
flag n8n_stack_root_exists test -d /opt/n8n-stack
flag n8n_stack_current_exists test -e /opt/n8n-stack/current
flag n8n_stack_current_symlink test -L /opt/n8n-stack/current
flag backend_current_exists test -e /opt/finance/current
flag backend_current_symlink test -L /opt/finance/current
link_scope backend_current_scope /opt/finance/current /opt/finance/releases
link_scope frontend_current_scope /var/www/finance/current /var/www/finance/releases
flag backend_env_exists test -f /etc/finance/backend.env
flag backend_env_readable test -r /etc/finance/backend.env
echo 'provider_credential_presence=unknown'
if test -r /etc/finance/backend.env; then
  env_names="$(awk -F= '
    /^[[:space:]]*(export[[:space:]]+)?[A-Za-z_][A-Za-z0-9_]*[[:space:]]*=/ {
      name=$1
      sub(/^[[:space:]]*export[[:space:]]+/, "", name)
      gsub(/[[:space:]]/, "", name)
      print toupper(name)
    }
  ' /etc/finance/backend.env 2>/dev/null || true)"
  if grep -Eq 'DEEPSEEK' <<< "$env_names"; then echo 'backend_env_deepseek_name_present=yes'; else echo 'backend_env_deepseek_name_present=no'; fi
  if grep -Eq 'FCM' <<< "$env_names"; then echo 'backend_env_fcm_name_present=yes'; else echo 'backend_env_fcm_name_present=no'; fi
  if grep -Eq 'DELIVERY.*HMAC|HMAC.*DELIVERY' <<< "$env_names"; then echo 'backend_env_delivery_hmac_name_present=yes'; else echo 'backend_env_delivery_hmac_name_present=no'; fi
else
  echo 'backend_env_deepseek_name_present=unknown'
  echo 'backend_env_fcm_name_present=unknown'
  echo 'backend_env_delivery_hmac_name_present=unknown'
fi
pg_dump_output="$(pg_dump --version 2>/dev/null || true)"
if [[ "$pg_dump_output" =~ ([0-9]+(\.[0-9]+){0,2}) ]]; then
  printf 'pg_dump_version=%s\n' "${BASH_REMATCH[1]}"
else
  echo 'pg_dump_version=unknown'
fi
db_observation=''
if test -x /opt/finance/current/venv/bin/python && test -r /etc/finance/backend.env && command -v timeout >/dev/null 2>&1; then
  db_observation="$(PYTHONDONTWRITEBYTECODE=1 timeout 12s /opt/finance/current/venv/bin/python -B - 2>/dev/null <<'PY' || true
import asyncio
import re

from dotenv import dotenv_values
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

url = dotenv_values('/etc/finance/backend.env').get('FINANCE_BACKEND_DATABASE_URL')
if not isinstance(url, str) or not url.startswith('postgresql+asyncpg://'):
    raise SystemExit(1)

async def probe():
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            await connection.exec_driver_sql('SET TRANSACTION READ ONLY')
            versions = (await connection.exec_driver_sql('SELECT version_num FROM alembic_version')).scalars().all()
            outbox = (await connection.exec_driver_sql("SELECT to_regclass('public.outbox_events') IS NOT NULL")).scalar_one()
            await connection.rollback()
        revision = 'base' if not versions else versions[0] if len(versions) == 1 else None
        if not isinstance(revision, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,127}', revision):
            raise SystemExit(1)
        print(f'{revision} {"yes" if outbox else "no"}')
    finally:
        await engine.dispose()

asyncio.run(asyncio.wait_for(probe(), timeout=8))
PY
)"
fi
if [[ "$db_observation" =~ ^([A-Za-z0-9][A-Za-z0-9._-]{0,127})[[:space:]](yes|no)$ ]]; then
  printf 'alembic_current=%s\n' "${BASH_REMATCH[1]}"
  printf 'outbox_table_present=%s\n' "${BASH_REMATCH[2]}"
else
  echo 'alembic_current=unknown'
  echo 'outbox_table_present=unknown'
fi

flag backend_loopback_health curl -fsS --max-time 3 -o /dev/null http://127.0.0.1:8081/health
flag n8n_loopback_health curl -fsS --max-time 3 -o /dev/null http://127.0.0.1:5680/healthz
http_status backend_8081_http_status http://127.0.0.1:8081/health
http_status n8n_5678_http_status http://127.0.0.1:5678/healthz
if command -v ss >/dev/null 2>&1 && sockets="$(ss -H -ltn 2>/dev/null)"; then
  if grep -Eq '127\.0\.0\.1:8081[[:space:]]' <<< "$sockets"; then
    echo 'backend_8081_loopback_listener=yes'
  else
    echo 'backend_8081_loopback_listener=no'
  fi
  listener_scope listener_5680 5680 "$sockets"
  listener_scope listener_8000 8000 "$sockets"
else
  echo 'backend_8081_loopback_listener=unknown'
  echo 'listener_5680=unknown'
  echo 'listener_8000=unknown'
fi
echo 'container_to_backend_reachability=unknown'

flag docker_cli_available command -v docker
flag docker_socket_exists test -S /var/run/docker.sock
flag docker_socket_writable test -w /var/run/docker.sock
if test -S /var/run/docker.sock; then
  safe_identity docker_socket_group "$(stat -c %G /var/run/docker.sock 2>/dev/null || true)"
else
  echo 'docker_socket_group=unknown'
fi
if command -v sudo >/dev/null 2>&1; then
  flag sudo_n_list_available sudo -n -l
  if test -x /usr/bin/docker; then
    flag sudo_n_docker_listed sudo -n -l /usr/bin/docker
  else
    echo 'sudo_n_docker_listed=unknown'
  fi
else
  echo 'sudo_n_list_available=unknown'
  echo 'sudo_n_docker_listed=unknown'
fi
if ! docker info >/dev/null 2>&1; then
  echo 'docker_daemon_accessible=no'
  echo 'compose_available=unknown'
  echo 'backend_network_exists=unknown'
  echo 'backend_network_internal=unknown'
  for service in backend n8n gateway worker; do
    printf 'backend_network_%s_attached=unknown\n' "$service"
  done
  echo 'n8n_container_exists=unknown'
  echo 'gateway_container_exists=unknown'
  echo 'worker_container_exists=unknown'
  echo 'n8n_volume_exists=unknown'
  exit 0
fi
echo 'docker_daemon_accessible=yes'
flag compose_available docker compose version

if network="$(docker network inspect finance_backend_internal -f '{{.Internal}}' 2>/dev/null)"; then
  echo 'backend_network_exists=yes'
  case "$network" in
    true) echo 'backend_network_internal=yes' ;;
    false) echo 'backend_network_internal=no' ;;
    *) echo 'backend_network_internal=unknown' ;;
  esac
  members="$(docker network inspect finance_backend_internal -f '{{range .Containers}}{{println .Name}}{{end}}' 2>/dev/null || true)"
  for service in backend n8n gateway worker; do
    if grep -Eq "(^|[-_])${service}([-_]|$)" <<< "$members"; then
      printf 'backend_network_%s_attached=yes\n' "$service"
    else
      printf 'backend_network_%s_attached=no\n' "$service"
    fi
  done
else
  echo 'backend_network_exists=no'
  echo 'backend_network_internal=unknown'
  for service in backend n8n gateway worker; do
    printf 'backend_network_%s_attached=unknown\n' "$service"
  done
fi

for service in n8n analysis-gateway worker; do
  case "$service" in
    n8n) label=n8n; project=finance-n8n ;;
    analysis-gateway) label=gateway; project=finance-n8n ;;
    worker) label=worker; project=finance-delivery ;;
  esac
  ids="$(docker ps -aq --filter "label=com.docker.compose.project=${project}" \
    --filter "label=com.docker.compose.service=${service}" 2>/dev/null || true)"
  if test -n "$ids"; then
    printf '%s_container_exists=yes\n' "$label"
  else
    printf '%s_container_exists=no\n' "$label"
  fi
done
volumes="$(docker volume ls --format '{{.Name}}' 2>/dev/null || true)"
if grep -Eq '^finance-n8n_finance_n8n_(data|postgres_data)$' <<< "$volumes"; then
  echo 'n8n_volume_exists=yes'
else
  echo 'n8n_volume_exists=no'
fi
