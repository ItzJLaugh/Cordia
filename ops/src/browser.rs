//! Optional Lightpanda sidecar — RESERVED, not implemented in v0.
//!
//! Why this is a stub and not the UI shell:
//!
//! Lightpanda is a *headless* browser. It runs JavaScript and exposes a DOM
//! over CDP, but it ships no renderer, no compositor and no window — there is
//! nothing to put pixels on a screen. It therefore cannot host the Ops Console
//! UI. The console's UI shell is ratatui + crossterm in `main.rs`, which is
//! also what gives us the terminal-native look and a binary that runs over SSH
//! on any operator machine.
//!
//! What Lightpanda *would* be good for, if we ever need it:
//!
//!   - Scraping a Cordia service that only exposes a JS-rendered HTML page
//!     rather than a JSON endpoint, so the data plane stays plain HTTP GETs.
//!   - Headless synthetic checks ("does the dashboard actually load?") driven
//!     from an operator box over the tailnet.
//!
//! Shape it would take: spawn `lightpanda serve --host 127.0.0.1 --port 9222`
//! as a child process, drive it over CDP, and surface results as one more
//! `Result<T, String>` field on `Snapshot` so a dead sidecar degrades exactly
//! like a dead endpoint. Same network guard applies — loopback or tailnet only.
//!
//! Until then this module is intentionally empty.
