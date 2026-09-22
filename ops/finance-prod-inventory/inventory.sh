#!/usr/bin/env bash
set -euo pipefail
export LC_ALL=C

echo 'schema=finance_inventory_v1'

flag() {
  local key="$1"
  shift
  if "$@" >/dev/null 2>&1; then
    printf '%s=yes\n' "$key"
  else
    printf '%s=no\n' "$key"
  fi
}

path_flags() {
  local name="$1" path="$2"
  flag "${name}_exists" test -e "$path"
  flag "${name}_readable" test -r "$path"
  flag "${name}_writable" test -w "$path"
}

release_id() {
  local name="$1" link="$2" prefix="$3" target id
  if ! test -L "$link"; then
    printf '%s=not_symlink\n' "$name"
    return
  fi
  target="$(readlink -f "$link" 2>/dev/null || true)"
  case "$target" in
    "${prefix}/"*)
      id="${target#"${prefix}/"}"
      if [[ "$id" =~ ^[A-Za-z0-9._-]+$ ]]; then
        printf '%s=%s\n' "$name" "$id"
      else
        printf '%s=outside_prefix\n' "$name"
      fi
      ;;
    *) printf '%s=outside_prefix\n' "$name" ;;
  esac
}

flag systemctl_available command -v systemctl
flag backend_service_active systemctl is-active --quiet finance-backend.service
for service in finance-delivery.service finance-n8n.service finance-gateway.service; do
  name="${service%.service}"
  name="${name//-/_}"
  flag "${name}_unit_present" systemctl cat "$service"
done
service_exec="$(systemctl show finance-backend.service -p ExecStart --value 2>/dev/null || true)"
if [[ "$service_exec" == *'/opt/finance/current/'* ]]; then
  echo 'backend_exec_uses_current=yes'
else
  echo 'backend_exec_uses_current=no'
fi

path_flags backend_releases /opt/finance/releases
path_flags frontend_releases /var/www/finance/releases
path_flags db_backup /opt/finance/backups/postgres
path_flags finance_etc /etc/finance
path_flags n8n_candidate /opt/finance/finance-n8n
path_flags worker_candidate /opt/finance/finance-delivery
release_id backend_current /opt/finance/current /opt/finance/releases
release_id frontend_current /var/www/finance/current /var/www/finance/releases

flag backend_loopback_health curl -fsS --max-time 3 -o /dev/null http://127.0.0.1:8081/health
flag n8n_loopback_health curl -fsS --max-time 3 -o /dev/null http://127.0.0.1:5680/healthz
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

backend_env=/etc/finance/backend.env
if test -r "$backend_env"; then
  echo 'backend_env_readable=yes'
  for key in FINANCE_BACKEND_DATABASE_URL FINANCE_BACKEND_DELIVERY_N8N_URL \
      FINANCE_BACKEND_DELIVERY_INGRESS_SECRET FINANCE_BACKEND_INVESTMENT_CALLBACK_HMAC_SECRET \
      FINANCE_BACKEND_FCM_ENABLED FINANCE_BACKEND_FCM_PROJECT_ID \
      FINANCE_BACKEND_FCM_CREDENTIALS_FILE FINANCE_BACKEND_FCM_CREDENTIALS_JSON; do
    if grep -q "^${key}=" "$backend_env"; then
      printf 'backend_var_%s=yes\n' "$key"
    else
      printf 'backend_var_%s=no\n' "$key"
    fi
  done
else
  echo 'backend_env_readable=no'
fi

flag docker_cli_available command -v docker
if ! docker info >/dev/null 2>&1; then
  echo 'docker_daemon_available=no'
  echo 'compose_available=unknown'
  echo 'backend_network_exists=unknown'
  echo 'n8n_container_exists=unknown'
  echo 'gateway_container_exists=unknown'
  echo 'worker_container_exists=unknown'
  echo 'n8n_volume_exists=unknown'
  exit 0
fi
echo 'docker_daemon_available=yes'
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

gateway_id="$(docker ps -q --filter 'label=com.docker.compose.project=finance-n8n' \
  --filter 'label=com.docker.compose.service=analysis-gateway' 2>/dev/null | head -n 1)"
if test -n "$gateway_id"; then
  gateway_env="$(docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' "$gateway_id" 2>/dev/null || true)"
  for key in DEEPSEEK_API_KEY FINANCE_GATEWAY_QUEUE_KEY FINANCE_GATEWAY_TOKEN \
      FINANCE_INGRESS_HMAC_SECRET FINANCE_CALLBACK_HMAC_SECRET; do
    if grep -q "^${key}=" <<< "$gateway_env"; then
      printf 'gateway_var_%s=yes\n' "$key"
    else
      printf 'gateway_var_%s=no\n' "$key"
    fi
  done
fi
