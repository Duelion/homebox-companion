# Deployment and troubleshooting

See the [Quick Start](../README.md#-quick-start) for a basic Docker deployment and
[`.env.example`](../.env.example) for configuration variables.

## Persistent settings

Mount `/app/data` to retain settings across container replacement:

| Settings | Docker storage path |
|----------|---------------------|
| LLM profiles and custom fields | `/app/data/settings.yaml` |
| Default tag, output language and AI field instructions | `/app/data/config/field_preferences.json` |

The application's `/app/config/field_preferences.json` path is a file symlink to
the JSON file in the data volume. A separate `/app/config` directory mount uses
its own JSON file instead; include that mount in backups if configured.

Field preferences are sparse overrides: hardcoded defaults → current `HBC_AI_*`
environment values → saved JSON values. Reset clears only the JSON overrides,
retaining profiles and custom fields. Invalid settings files are preserved rather
than replaced with defaults. Back up the mounted settings before changing storage
or repairing permissions.

### Storage permissions

These troubleshooting steps apply only when startup reports unwritable settings
storage. Settings saves replace files atomically, so the runtime user needs write
access to the containing directory as well as read access to saved settings.

The image runs as the non-root `appuser`. Fresh named volumes inherit the image
directory's ownership. Existing volumes and host bind mounts retain their own
permissions; the image cannot override host filesystem permissions. Startup
checks that both settings directories support creating, replacing and deleting
files before serving requests.

Stop Companion and back up the selected mount first. Obtain the UID and GID from
the exact image you deploy:

```bash
docker run --rm --entrypoint id ghcr.io/duelion/homebox-companion:latest -u
docker run --rm --entrypoint id ghcr.io/duelion/homebox-companion:latest -g
```

For a named volume, replace `YOUR_COMPANION_VOLUME` and `UID:GID` below with the
verified volume name and numeric identity from those commands. This changes only
the data directory, its settings file, and the JSON preferences directory/file
when present, preserving contents; the application continues to run non-root:

```bash
docker run --rm --user 0:0 --entrypoint sh \
  -v YOUR_COMPANION_VOLUME:/repair \
  ghcr.io/duelion/homebox-companion:latest \
  -c 'for path in /repair /repair/settings.yaml /repair/config /repair/config/field_preferences.json; do if [ -e "$path" ]; then chown UID:GID "$path" || exit; fi; done'
```

For a Linux host bind mount, verify the absolute host directory and use
`sudo chown UID:GID /absolute/companion-data`. Apply the same ownership to
`settings.yaml`, `config/`, and `config/field_preferences.json` inside that
directory when present. If `/app/config` is mounted separately, verify and repair
that mount's directory and JSON file too. Ensure the owner has write and directory
traversal permissions. For Docker Desktop bind mounts, grant the runtime account
access using the host filesystem's sharing/ACL controls.

Read-only mounts must be made writable. Do not delete settings, recursively change
ownership of unrelated directories, or grant world-write permissions as a repair.
Restart Companion after correcting the selected mount.

## Homebox API keys and access

A configured `HBC_HOMEBOX_API_KEY` is used only by the server. Everyone who can
reach Companion acts as that key's Homebox owner. Use a dedicated Homebox user
with the intended collection permissions and control access through your network
or reverse proxy.

Companion does not renew Homebox API keys automatically. Check the chosen expiry
when creating a key. To rotate it, create a replacement, update the Companion
server environment, restart Companion and verify its connection, then revoke the
old key in Homebox. See [Homebox compatibility](homebox-compatibility.md#api-key-expiry)
for version-specific expiry behavior.

Homebox requires its own stable `HBOX_AUTH_API_KEY_PEPPER` of at least 32 bytes;
changing it invalidates issued keys. Configure it on **Homebox**, never on
Companion. See the [Homebox v0.27 configuration documentation](https://github.com/sysadminsmedia/homebox/blob/v0.27.0/docs/src/content/docs/en/quick-start/configure/index.mdx).

### Chat server requirements

Browser chat contexts separate conversation history and pending approvals; they
are not accounts or access credentials. Clearing browser data creates a new chat
context. Server chat state is held in memory and expires automatically. Run a
single server worker so conversations and approvals use the same state.

## Logs

Authenticated users can view and download server and LLM debug logs from Settings.
Access uses the configured Homebox key's identity in API-key mode or the logged-in
Homebox user in username/password mode. Credentials are revalidated for access.

New entries redact configured credentials and common credential fields before
emission, and exception logs do not include diagnostic local variables. Historical
log files are not rewritten. Logs can contain inventory prompts, responses and
other sensitive details, so review exports before sharing them.
