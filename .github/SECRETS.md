# GitHub Actions secrets

Configure these in **Settings → Secrets and variables → Actions → New repository secret**.

CI runs without any secrets — the `backend` and `frontend` jobs use dummy
values for `SECRET_KEY` / `FIELD_ENCRYPTION_KEY` / etc. baked into the
workflow. Only the `deploy` job requires secrets.

## Required (for `deploy` job)

| Name              | Value                                                  | Notes                                                                                   |
| ----------------- | ------------------------------------------------------ | --------------------------------------------------------------------------------------- |
| `SSH_HOST`        | `194.59.205.20` (or domain pointing to the VPS)        | Server hostname / IP that the workflow connects to.                                     |
| `SSH_PRIVATE_KEY` | Full content of a private SSH key (PEM, with newlines) | Generate dedicated key (`ssh-keygen -t ed25519 -C github-actions -f deploy_key`) and add `deploy_key.pub` to `/root/.ssh/authorized_keys` on the VPS. Paste the **private** key here, including `-----BEGIN/END-----` lines. |
| `SSH_PORT`        | `22` (or custom port if configured)                    | **Optional.** Defaults to `22` when absent.                                             |

## One-time server-side setup

On the VPS, as root:

```bash
# Generate a deploy key on your laptop (not on the server):
#   ssh-keygen -t ed25519 -C "github-actions-deploy" -f ~/.ssh/prvms_crm_deploy
# Then paste the .pub content into authorized_keys:

cat >> /root/.ssh/authorized_keys <<'EOF'
ssh-ed25519 AAAA... github-actions-deploy
EOF
chmod 600 /root/.ssh/authorized_keys

# Verify (from your laptop):
#   ssh -i ~/.ssh/prvms_crm_deploy root@<SSH_HOST> "uname -a"
```

Then upload the **private** key (`~/.ssh/prvms_crm_deploy` content) as
`SSH_PRIVATE_KEY` secret in GitHub.

## Branch protection (recommended)

Since `deploy` runs on every push to `main`, prevent direct pushes:

1. **Settings → Branches → Branch protection rules → Add rule** for `main`.
2. Enable:
   - **Require a pull request before merging** (with at least 1 approval if you want).
   - **Require status checks to pass before merging** → select `Backend — Django check + migrations guard + tests` and `Frontend — typecheck + tests + build`.
   - **Require branches to be up to date before merging**.
3. Save.

This ensures `main` only advances via merged PRs whose CI is green, and
each push to `main` then triggers exactly one deploy.

## Optional: GitHub Environment with approval gate

If you want a manual confirmation before each production deploy:

1. **Settings → Environments → New environment** → `production`.
2. Add **Required reviewers** (yourself, or a team).
3. The workflow already declares `environment: production`, so GitHub
   will pause the `deploy` job until a reviewer clicks "Approve and deploy".

Disable this for full continuous deployment.
