#!/usr/bin/env bash
set -euo pipefail
export LC_ALL=C

echo 'schema=finance_inventory_v3'

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
else
  echo 'backend_service_user=unknown'
  echo 'backend_service_group=unknown'
fi
for service in docker n8n; do
  state="$(systemctl is-active "${service}.service" 2>/dev/null || true)"
  case "$state" in
    active|inactive|failed|activating|deactivating) printf '%s_service_state=%s\n' "$service" "$state" ;;
    *) printf '%s_service_state=unknown\n' "$service" ;;
  esac
done
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

flag backend_loopback_health curl -fsS --max-time 3 -o /dev/null http://127.0.0.1:8081/health
flag n8n_loopback_health curl -fsS --max-time 3 -o /dev/null http://127.0.0.1:5680/healthz
http_status backend_8081_http_status http://127.0.0.1:8081/health
http_status n8n_5678_http_status http://127.0.0.1:5678/healthz
if command -v ss >/dev/null 2>&1; then
  sockets="$(ss -ltn 2>/dev/null || true)"
  if grep -Eq '127\.0\.0\.1:8081[[:space:]]' <<< "$sockets"; then
    echo 'backend_8081_loopback_listener=yes'
  else
    echo 'backend_8081_loopback_listener=no'
  fi
else
  echo 'backend_8081_loopback_listener=unknown'
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
