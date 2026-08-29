# Docker Installation and Usage

## Quick Start (Pre-built Image - Recommended)

Pre-built production images are published to GitHub Container Registry on every push to `master`.

```bash
docker run --pull always -it -v openoutreach_db:/app/data ghcr.io/eracle/openoutreach:latest
```

VNC is disabled by default for safety. Enable it only with a password file and loopback-only port bindings as described below.

> **VNC is an explicitly secured opt-in feature.** Set `ENABLE_VNC=true` only together with a non-empty `VNC_PASSWORD_FILE`; bind ports to `127.0.0.1` and never expose them publicly.

The interactive onboarding will guide you through LinkedIn credentials, LLM API key, and campaign setup on first run. All data (CRM database, cookies, model blobs, embeddings) persists in the `openoutreach_db` Docker volume.

### Available Tags

| Tag | Description |
|:----|:------------|
| `latest` | Latest build from `master` |
| `sha-<commit>` | Pinned to a specific commit |
| `1.0.0` / `1.0` | Semantic version (when tagged) |

### Live Browser View (noVNC, optional)

The container ships an optional noVNC viewer for watching the automation live. It requires a password file and should remain bound to localhost:

```
http://localhost:6080/vnc.html
```

Prefer a native VNC client? One is also exposed on `localhost:5900`. On Linux with `vinagre`:
```bash
vinagre vnc://127.0.0.1:5900
```

> Both ports must be published, `ENABLE_VNC=true` must be set, and `VNC_PASSWORD_FILE` must point to a non-empty mounted secret. Use `-p 127.0.0.1:6080:6080 -p 127.0.0.1:5900:5900`; never publish these ports on all interfaces.

> **Seeing `SyntaxError: ... does not provide an export named 'encodeUTF8'`?** That's a stale browser cache of noVNC assets from an older image, not a container bug. Hard-reload the page (Ctrl+Shift+R) or open it in a private window.

### Stopping & Restarting

```bash
# Find the container
docker ps

# Stop it
docker stop <container-id>

# Restart (data persists in the openoutreach_db volume)
docker run --pull always -it -v openoutreach_db:/app/data ghcr.io/eracle/openoutreach:latest
```

---

## Build from Source (Docker Compose)

For development or customization, you can build the image locally. The compose file (`local.yml`)
mounts the entire project directory into the container for live code editing.

### Prerequisites

- [Make](https://www.gnu.org/software/make/)
- [Docker](https://www.docker.com/)
- [Docker Compose](https://docs.docker.com/compose/)

### Build & Run

```bash
git clone https://github.com/eracle/OpenOutreach.git
cd OpenOutreach

# Build and start
make up
```

This builds the Docker image from source with `BUILD_ENV=local` (includes test dependencies) and starts the daemon.

**Note:** The compose file uses `HOST_UID` / `HOST_GID` environment variables (defaulting to 1000)
for file ownership. If your host UID differs from 1000, set them explicitly:

```bash
HOST_UID=$(id -u) HOST_GID=$(id -g) make up
```

### Useful Commands

| Command | Description |
|:--------|:------------|
| `make build` | Build the Docker image without starting |
| `make up` | Build and start the service |
| `make stop` | Stop the running containers |
| `make logs` | Follow application logs |
| `make up-view` | Start + open VNC viewer (Linux, requires `vinagre`) |
| `make view` | Open VNC viewer standalone (requires `vinagre`) |
| `make docker-test` | Run the test suite in Docker |

### VNC with Docker Compose

The live browser view is exposed two ways: the noVNC web viewer at **http://localhost:6080/vnc.html** (open in any browser), or the native VNC port `localhost:5900`. Use `make up-view` to auto-open the native viewer, or connect manually with any VNC client.

### Volume Mounts

The pre-built `docker run` command uses a named Docker volume (`openoutreach_db`) mounted at `/app/data` for data persistence (database, config). The compose setup (`local.yml`) mounts the entire repo `.:/app` for live code editing during development.

### Use an existing `db.sqlite3`

To run against a database file you already have, bind-mount the host **directory** containing it onto `/app/data` (the app opens `/app/data/db.sqlite3`):

```bash
docker run --pull always -it -v ~/.openoutreach/data:/app/data ghcr.io/eracle/openoutreach:latest
```

Place your `db.sqlite3` inside the mounted directory (`~/.openoutreach/data/` above; swap for your own path). Two caveats: the dir and file must be writable by uid 1000 (the container's `ubuntu` user) or writes fail with `readonly database`; and `rundaemon` runs `migrate` on startup, so back the file up first (`cp db.sqlite3{,.bak}`) if it's precious.
