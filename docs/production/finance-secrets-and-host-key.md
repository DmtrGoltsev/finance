# Finance production secrets and SSH host key

Scope: GitHub Actions production deployment to HexCore for Finance only.

## Required GitHub secrets

Configure these secrets in the repository or environment used by the
`production` environment:

- `HEXCORE_PROD_SSH_HOST`: SSH host name or address.
- `HEXCORE_PROD_SSH_USER`: SSH user allowed to deploy Finance release artifacts.
- `HEXCORE_PROD_SSH_PRIVATE_KEY`: private key for that deploy user.
- `HEXCORE_PROD_SSH_KNOWN_HOSTS`: pinned known_hosts line for the production SSH
  host.

Optional:

- `HEXCORE_PROD_SSH_PORT`: SSH port. The workflow defaults to `22` when unset.

Do not store database passwords, `FINANCE_BACKEND_DATABASE_URL`, auth token hash
secrets, cookie secrets, one-time operator passwords, backup encryption keys, or
host environment file contents in GitHub for this workflow.

## Pinned host-key requirement

The workflows write `HEXCORE_PROD_SSH_KNOWN_HOSTS` to `~/.ssh/known_hosts` and
use:

```text
StrictHostKeyChecking=yes
UserKnownHostsFile=~/.ssh/known_hosts
```

The workflows must not use:

```text
StrictHostKeyChecking=no
```

Do not use trust-on-first-use values such as `accept-new` for production deploys.
If the host key changes, treat it as an operational security event until the
change is verified out of band.

## Capturing the host key

An operator should obtain the production SSH host key through an approved channel
and compare it to the server owner record. After verification, store the exact
known_hosts line in `HEXCORE_PROD_SSH_KNOWN_HOSTS`.

Example shape only:

```text
hexcore.example.invalid ssh-ed25519 AAAA...
```

For non-default ports, known_hosts commonly uses bracketed host syntax:

```text
[hexcore.example.invalid]:2222 ssh-ed25519 AAAA...
```

The examples above are placeholders. Do not commit real host keys unless your
security policy explicitly classifies them as public configuration.

## Secret handling rules

- Never print secret values in workflow logs.
- Never copy `/etc/finance/backend.env` into artifacts.
- Never include DB DSNs or passwords in issue comments, deployment notes, or
  rollback evidence.
- Use `backup_proof` only for evidence identifiers, not secret material.
- Rotate the deploy key if it is exposed in logs, local files, chat, or an
  artifact.

## Verification

Before a production deployment is allowed:

- GitHub `production` environment has no Required reviewer under the approved
  Finance solo-owner waiver.
- Selected deployment branches are enabled and the only allowed pattern is
  `prod/release-*`; an explicit owner push to that pattern is production
  authorization.
- `HEXCORE_PROD_SSH_KNOWN_HOSTS` is present and parses with `ssh-keygen -l`.
- SSH and SCP commands use `StrictHostKeyChecking=yes`.
- No workflow step contains `StrictHostKeyChecking=no`.
- DB settings remain host-side in `/etc/finance/backend.env`.
- Direct SSH/SCP production deployment is prohibited. These transports may run
  only inside approved GitHub Actions jobs using environment-scoped secrets.
