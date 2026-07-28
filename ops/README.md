# cordia-ops

Cordia Ops Console v0 — a local terminal dashboard for Cordia services.

**Internal operator tool.** It is not part of the cordiacode.com website, is not
served by Apache, and touches nothing under `/opt/cordia/web`. It runs on an
operator's own machine and reaches Cordia services **over Tailscale only**.

```
+----------------------------------------------------------------------------+
| cordia-ops  |  you@cordiacode.com  |  100.73.131.108  |  auto 7s            |
+----------------------------------------------------------------------------+
+- TRAINING --------+ +- HIVEBUS ---------+ +- SOUL ---------------+
| * ok              | | * running         | | - no data            |
| 1284              | | 90311             | | endpoint unreachable |
| responses         | | messages total    | |                      |
|                   | |                   | | unreachable          |
| ratings   417     | | uptime    3d 02h  | |                      |
+-------------------+ +-------------------+ +----------------------+
+- HIVE LOGS ------------------+ +- TAILSCALE PEERS ----------------+
| NAME        MSGS      SIZE   | | NAME                 ONLINE      |
| soul        41022     8.1M   | | ops-thinkpad (self)  online      |
| relay       18744     3.2M   | | cordia-vps           online      |
+------------------------------+ +----------------------------------+
 q quit  · r refresh  · auto 10s
```

## Build

Requires a Rust toolchain (stable) and a C linker.

```bash
cd /opt/cordia-ops
cargo build --release
```

The binary lands at `/opt/cordia-ops/target/release/cordia-ops`.

If `cargo` is not installed on the machine, use the bundled installer — it
installs Rust via rustup (non-interactive, minimal profile), then builds:

```bash
cd /opt/cordia-ops
./install.sh            # install toolchain if needed + build
./install.sh --install  # ...and copy to /usr/local/bin/cordia-ops
```

`install.sh` uses `sudo` only for the apt/dnf package step and for copying into
`/usr/local/bin`. If you installed rustup in the same shell session, run
`source ~/.cargo/env` before calling `cargo` directly.

## Install

```bash
sudo install -m 0755 target/release/cordia-ops /usr/local/bin/cordia-ops
```

## Run

```bash
cordia-ops you@cordiacode.com
```

The first positional argument is the operator identity shown in the top bar.
`--operator=you@cordiacode.com` works too. If omitted, `$CORDIA_OPERATOR` then
`$USER` are used.

You must be on the tailnet (`tailscale status` should show the VPS as online)
for any panel to report data.

### Keys

| key      | action                  |
| -------- | ----------------------- |
| `q`/`Esc`| quit                    |
| `r`      | refresh now             |
| `Ctrl-C` | quit                    |

Auto-refresh runs every 10s; the top bar shows the countdown.

## Configuration

No secrets live in this repo. Endpoints are constants, overridable by env var.

| env var            | default           | meaning                                             |
| ------------------ | ----------------- | --------------------------------------------------- |
| `CORDIA_API_BASE`  | `100.73.131.108`  | Host for all service endpoints. Scheme/port optional and ignored — the per-service ports below are fixed. |
| `CORDIA_OPERATOR`  | `$USER`           | Fallback operator label for the top bar.             |
| `CORDIA_OPAQUE`    | unset             | `1` paints the background `#0A0E0C`. Unset leaves it transparent so a blurred terminal shows through. |

`CORDIA_API_BASE` is validated: only the Tailscale CGNAT range
`100.64.0.0/10`, `127.0.0.1` and `localhost` are accepted. Anything else prints
a warning and falls back to the default tailnet IP — the binary has no code
path that can dial the public internet.

## Data sources

| panel            | source                                              |
| ---------------- | --------------------------------------------------- |
| Training         | `GET http://<host>:9995/train/status`                |
| HiveBus          | `GET http://<host>:9999/hive/status`                 |
| Hive logs        | `GET http://<host>:9999/hive/logs`                   |
| SOUL             | `GET http://<host>:9992/soul/status`                 |
| Tailscale peers  | `tailscale status --json` (Self + Peer)              |

All five are fetched on a background thread with a 3s per-request timeout, so
the UI never blocks. Any failure — connection refused, timeout, non-2xx,
malformed JSON, missing `tailscale` binary — renders as
`no data / endpoint unreachable` in that panel with a short reason. Nothing
panics on fetch failure, and one dead service never affects the others.

## Layout

- **Top bar** — `cordia-ops | operator | host | refresh countdown`
- **Row 1** — three status cards: Training, HiveBus, SOUL (status dot + key number)
- **Row 2** — Hive logs table (name, msgs, size) | Tailscale peers table (name, online)
- **Bottom** — key hints

Style: dark `#0A0E0C`, single green accent `#2FD07A`, muted `#757A6C`, ASCII
box borders, no emoji.

## Layout note: why not Lightpanda

`src/browser.rs` is a stub. Lightpanda is a headless browser — it has a DOM and
a JS engine but no renderer, so it cannot draw a UI. The console's shell is
ratatui + crossterm. Lightpanda stays reserved as an optional later sidecar for
scraping JS-rendered service pages or running synthetic checks; see the comment
in that file.

## Layout of the repo

```
/opt/cordia-ops
├── Cargo.toml
├── install.sh
├── README.md
└── src
    ├── main.rs      # TUI loop, poller thread, all rendering
    └── browser.rs   # reserved Lightpanda sidecar (stub, comments only)
```
