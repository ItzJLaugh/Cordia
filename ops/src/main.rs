//! Cordia Ops Console v0 — local operator dashboard.
//!
//! LOCAL TOOL. This is not part of the cordiacode.com website and is never
//! served by Apache. It runs on an operator machine and talks to Cordia
//! services over the tailnet only.
//!
//! Data plane: plain blocking HTTP GETs on a background poller thread, plus
//! `tailscale status --json` exec for peer state. The render loop never blocks
//! on the network; it only reads whatever the last snapshot delivered.

mod browser;

use std::io::{self, Stdout};
use std::process::Command;
use std::sync::mpsc::{self, Receiver, RecvTimeoutError, Sender};
use std::thread;
use std::time::{Duration, Instant};

use anyhow::Result;
use crossterm::event::{self, Event, KeyCode, KeyEventKind, KeyModifiers};
use crossterm::execute;
use crossterm::terminal::{
    disable_raw_mode, enable_raw_mode, EnterAlternateScreen, LeaveAlternateScreen,
};
use ratatui::backend::CrosstermBackend;
use ratatui::layout::{Alignment, Constraint, Direction, Layout, Rect};
use ratatui::style::{Color, Modifier, Style};
use ratatui::symbols::border;
use ratatui::text::{Line, Span};
use ratatui::widgets::{Block, Borders, Cell, Paragraph, Row, Table};
use ratatui::{Frame, Terminal};
use serde::Deserialize;

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

/// Default VPS tailscale IP. No secrets live here — this is a tailnet address
/// that is unreachable off the tailnet. Override with `CORDIA_API_BASE`.
const DEFAULT_HOST: &str = "100.73.131.108";

const PORT_TRAIN: u16 = 9995;
const PORT_HIVE: u16 = 9999;
const PORT_SOUL: u16 = 9992;

/// Auto-refresh cadence, seconds.
const TICK_SECS: u64 = 10;
/// Per-request timeout. Kept well under TICK_SECS so a dead endpoint can never
/// stall the poller past one cycle.
const HTTP_TIMEOUT: Duration = Duration::from_secs(3);

// Palette. Single accent (green); everything else is muted. No second accent
// colour is used anywhere, including for errors.
const GREEN: Color = Color::Rgb(0x2F, 0xD0, 0x7A);
const MUTED: Color = Color::Rgb(0x75, 0x7A, 0x6C);
const FG: Color = Color::Rgb(0xD6, 0xDC, 0xD2);
const BG_OPAQUE: Color = Color::Rgb(0x0A, 0x0E, 0x0C);

/// ASCII-only frame set — no box-drawing glyphs.
const ASCII_BORDER: border::Set = border::Set {
    top_left: "+",
    top_right: "+",
    bottom_left: "+",
    bottom_right: "+",
    vertical_left: "|",
    vertical_right: "|",
    horizontal_top: "-",
    horizontal_bottom: "-",
};

struct Config {
    host: String,
    operator: String,
    /// When false the background is `Color::Reset`, letting a blurred /
    /// transparent terminal show through. `CORDIA_OPAQUE=1` paints #0A0E0C.
    opaque: bool,
}

impl Config {
    fn from_env_and_args() -> Self {
        let raw = std::env::var("CORDIA_API_BASE").unwrap_or_else(|_| DEFAULT_HOST.to_string());
        let host = normalize_host(&raw).unwrap_or_else(|| {
            // Refuse anything that is not a tailnet / loopback address rather
            // than silently reaching out to the public internet.
            eprintln!(
                "cordia-ops: CORDIA_API_BASE=\"{raw}\" is not a tailnet (100.64.0.0/10) or \
                 loopback address; falling back to {DEFAULT_HOST}"
            );
            DEFAULT_HOST.to_string()
        });

        let mut operator = String::new();
        for arg in std::env::args().skip(1) {
            if let Some(v) = arg.strip_prefix("--operator=") {
                operator = v.to_string();
            } else if !arg.starts_with('-') && operator.is_empty() {
                operator = arg;
            }
        }
        if operator.is_empty() {
            operator = std::env::var("CORDIA_OPERATOR")
                .or_else(|_| std::env::var("USER"))
                .unwrap_or_else(|_| "unknown".to_string());
        }

        Config {
            host,
            operator,
            opaque: matches!(
                std::env::var("CORDIA_OPAQUE").as_deref(),
                Ok("1") | Ok("true")
            ),
        }
    }

    fn url(&self, port: u16, path: &str) -> String {
        format!("http://{}:{}{}", self.host, port, path)
    }

    fn bg(&self) -> Color {
        if self.opaque {
            BG_OPAQUE
        } else {
            Color::Reset
        }
    }
}

/// Strip any scheme/path and accept only tailnet CGNAT space or loopback.
/// This is the network guard: the binary has no other place it can dial.
fn normalize_host(raw: &str) -> Option<String> {
    let s = raw.trim();
    let s = s.split("://").last().unwrap_or(s);
    let s = s.split('/').next().unwrap_or(s);
    let s = s.split(':').next().unwrap_or(s);
    if s.is_empty() {
        return None;
    }
    if s == "localhost" || s == "127.0.0.1" {
        return Some(s.to_string());
    }
    // 100.64.0.0/10 — the tailscale CGNAT range.
    let octets: Vec<&str> = s.split('.').collect();
    if octets.len() == 4 {
        let parsed: Option<Vec<u8>> = octets.iter().map(|o| o.parse::<u8>().ok()).collect();
        if let Some(o) = parsed {
            if o[0] == 100 && (64..=127).contains(&o[1]) {
                return Some(s.to_string());
            }
        }
    }
    None
}

// ---------------------------------------------------------------------------
// Wire types
//
// Every field is optional / defaulted. A service that changes shape or returns
// a partial body degrades to "--" in the UI instead of failing the fetch.
// ---------------------------------------------------------------------------

#[derive(Debug, Default, Clone, Deserialize)]
#[serde(default)]
struct TrainStatus {
    ok: Option<bool>,
    responses: Option<u64>,
    ratings: Option<u64>,
    ts: Option<serde_json::Value>,
}

#[derive(Debug, Default, Clone, Deserialize)]
#[serde(default)]
struct HiveStatus {
    status: Option<String>,
    uptime: Option<serde_json::Value>,
    logs: Option<serde_json::Value>,
    messages_total: Option<u64>,
}

#[derive(Debug, Default, Clone, Deserialize)]
#[serde(default)]
struct HiveLogs {
    logs: Vec<HiveLogEntry>,
}

#[derive(Debug, Default, Clone, Deserialize)]
#[serde(default)]
struct HiveLogEntry {
    name: Option<String>,
    messages: Option<u64>,
    file_size: Option<serde_json::Value>,
}

#[derive(Debug, Default, Clone, Deserialize)]
#[serde(default)]
struct SoulStatus {
    status: Option<String>,
    skills: Vec<serde_json::Value>,
    logs: Vec<serde_json::Value>,
}

#[derive(Debug, Clone)]
struct Peer {
    name: String,
    online: bool,
    is_self: bool,
}

/// One complete poll cycle. `Err(String)` is the graceful "no data" state —
/// it is rendered, never propagated.
struct Snapshot {
    train: Result<TrainStatus, String>,
    hive: Result<HiveStatus, String>,
    hive_logs: Result<HiveLogs, String>,
    soul: Result<SoulStatus, String>,
    peers: Result<Vec<Peer>, String>,
}

impl Snapshot {
    /// Pre-first-poll state: everything unreachable until proven otherwise.
    fn pending() -> Self {
        Snapshot {
            train: Err("awaiting first poll".to_string()),
            hive: Err("awaiting first poll".to_string()),
            hive_logs: Err("awaiting first poll".to_string()),
            soul: Err("awaiting first poll".to_string()),
            peers: Err("awaiting first poll".to_string()),
        }
    }
}

// ---------------------------------------------------------------------------
// Fetching
// ---------------------------------------------------------------------------

fn get_json<T: for<'de> Deserialize<'de>>(
    client: &reqwest::blocking::Client,
    url: &str,
) -> Result<T, String> {
    let resp = client.get(url).send().map_err(|e| {
        if e.is_timeout() {
            "timeout".to_string()
        } else if e.is_connect() {
            "unreachable".to_string()
        } else {
            short_err(&e.to_string())
        }
    })?;
    if !resp.status().is_success() {
        return Err(format!("HTTP {}", resp.status().as_u16()));
    }
    resp.json::<T>().map_err(|_| "bad payload".to_string())
}

fn short_err(s: &str) -> String {
    s.chars().take(48).collect()
}

/// `tailscale status --json` -> Self + Peer. Missing binary, non-zero exit and
/// unparseable output all collapse into a rendered error row.
fn fetch_peers() -> Result<Vec<Peer>, String> {
    let out = Command::new("tailscale")
        .args(["status", "--json"])
        .output()
        .map_err(|e| {
            if e.kind() == io::ErrorKind::NotFound {
                "tailscale not installed".to_string()
            } else {
                short_err(&e.to_string())
            }
        })?;

    if !out.status.success() {
        let msg = String::from_utf8_lossy(&out.stderr);
        let first = msg.lines().next().unwrap_or("tailscale error");
        return Err(short_err(first.trim()));
    }

    let v: serde_json::Value =
        serde_json::from_slice(&out.stdout).map_err(|_| "bad tailscale json".to_string())?;

    let mut peers = Vec::new();
    if let Some(me) = v.get("Self") {
        peers.push(peer_from(me, true));
    }
    // Field is "Peer" on current tailscale; accept "Peers" defensively.
    let peer_map = v.get("Peer").or_else(|| v.get("Peers"));
    if let Some(serde_json::Value::Object(map)) = peer_map {
        for (_k, p) in map {
            peers.push(peer_from(p, false));
        }
    }

    peers.sort_by(|a, b| {
        b.is_self
            .cmp(&a.is_self)
            .then(b.online.cmp(&a.online))
            .then(a.name.to_lowercase().cmp(&b.name.to_lowercase()))
    });
    Ok(peers)
}

fn peer_from(v: &serde_json::Value, is_self: bool) -> Peer {
    let name = v
        .get("HostName")
        .and_then(|x| x.as_str())
        .or_else(|| v.get("DNSName").and_then(|x| x.as_str()))
        .unwrap_or("?")
        .trim_end_matches('.')
        .to_string();
    Peer {
        name,
        // Self has no meaningful Online flag in some versions; treat as up.
        online: v.get("Online").and_then(|x| x.as_bool()).unwrap_or(is_self),
        is_self,
    }
}

fn poll_all(client: &reqwest::blocking::Client, cfg: &Config) -> Snapshot {
    Snapshot {
        train: get_json(client, &cfg.url(PORT_TRAIN, "/train/status")),
        hive: get_json(client, &cfg.url(PORT_HIVE, "/hive/status")),
        hive_logs: get_json(client, &cfg.url(PORT_HIVE, "/hive/logs")),
        soul: get_json(client, &cfg.url(PORT_SOUL, "/soul/status")),
        peers: fetch_peers(),
    }
}

/// Poller thread: emits a snapshot, then sleeps until the next tick or until
/// the UI asks for a manual refresh, whichever comes first.
fn spawn_poller(cfg: Config) -> (Receiver<Snapshot>, Sender<()>) {
    let (snap_tx, snap_rx) = mpsc::channel::<Snapshot>();
    let (req_tx, req_rx) = mpsc::channel::<()>();

    thread::spawn(move || {
        let client = reqwest::blocking::Client::builder()
            .timeout(HTTP_TIMEOUT)
            .connect_timeout(HTTP_TIMEOUT)
            .user_agent("cordia-ops/0.1")
            .build()
            .unwrap_or_else(|_| reqwest::blocking::Client::new());

        loop {
            if snap_tx.send(poll_all(&client, &cfg)).is_err() {
                break; // UI is gone
            }
            match req_rx.recv_timeout(Duration::from_secs(TICK_SECS)) {
                Ok(()) | Err(RecvTimeoutError::Timeout) => {}
                Err(RecvTimeoutError::Disconnected) => break,
            }
        }
    });

    (snap_rx, req_tx)
}

// ---------------------------------------------------------------------------
// App state
// ---------------------------------------------------------------------------

struct App {
    cfg: Config,
    snap: Snapshot,
    last_refresh: Instant,
    refreshing: bool,
}

impl App {
    fn countdown(&self) -> u64 {
        let elapsed = self.last_refresh.elapsed().as_secs();
        TICK_SECS.saturating_sub(elapsed)
    }
}

// ---------------------------------------------------------------------------
// Render helpers
// ---------------------------------------------------------------------------

fn panel<'a>(title: &'a str, bg: Color) -> Block<'a> {
    Block::default()
        .borders(Borders::ALL)
        .border_set(ASCII_BORDER)
        .border_style(Style::default().fg(MUTED))
        .title(Span::styled(
            format!(" {title} "),
            Style::default().fg(GREEN).add_modifier(Modifier::BOLD),
        ))
        .style(Style::default().bg(bg))
}

fn dot(ok: bool) -> Span<'static> {
    Span::styled(
        if ok { "*" } else { "-" },
        Style::default().fg(if ok { GREEN } else { MUTED }),
    )
}

fn kv<'a>(key: &'a str, val: String) -> Line<'a> {
    Line::from(vec![
        Span::styled(format!("{key:<10}"), Style::default().fg(MUTED)),
        Span::styled(val, Style::default().fg(FG)),
    ])
}

fn num(v: Option<u64>) -> String {
    v.map(|n| n.to_string()).unwrap_or_else(|| "--".to_string())
}

/// Render a JSON scalar compactly; strings lose their quotes.
fn scalar(v: &Option<serde_json::Value>) -> String {
    match v {
        Some(serde_json::Value::String(s)) => s.clone(),
        Some(serde_json::Value::Null) | None => "--".to_string(),
        Some(other) => {
            let s = other.to_string();
            s.chars().take(24).collect()
        }
    }
}

fn human_size(v: &Option<serde_json::Value>) -> String {
    match v {
        Some(serde_json::Value::Number(n)) => {
            let b = n.as_f64().unwrap_or(0.0);
            if b >= 1_048_576.0 {
                format!("{:.1}M", b / 1_048_576.0)
            } else if b >= 1024.0 {
                format!("{:.1}K", b / 1024.0)
            } else {
                format!("{b:.0}B")
            }
        }
        Some(serde_json::Value::String(s)) => s.clone(),
        _ => "--".to_string(),
    }
}

/// The shared degraded state for any panel whose fetch failed.
fn unreachable_lines(err: &str) -> Vec<Line<'static>> {
    vec![
        Line::from(vec![
            dot(false),
            Span::styled(" no data", Style::default().fg(MUTED)),
        ]),
        Line::from(Span::styled(
            "endpoint unreachable",
            Style::default().fg(MUTED),
        )),
        Line::from(""),
        Line::from(Span::styled(
            err.to_string(),
            Style::default().fg(MUTED).add_modifier(Modifier::DIM),
        )),
    ]
}

fn card(f: &mut Frame, area: Rect, title: &str, bg: Color, body: Vec<Line>) {
    let p = Paragraph::new(body).block(panel(title, bg));
    f.render_widget(p, area);
}

// ---------------------------------------------------------------------------
// UI
// ---------------------------------------------------------------------------

fn ui(f: &mut Frame, app: &App) {
    let bg = app.cfg.bg();
    let area = f.area();

    f.render_widget(Block::default().style(Style::default().bg(bg)), area);

    let rows = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Length(3), // top bar
            Constraint::Length(9), // cards
            Constraint::Min(6),    // tables
            Constraint::Length(1), // key hints
        ])
        .split(area);

    draw_topbar(f, rows[0], app);

    let cards = Layout::default()
        .direction(Direction::Horizontal)
        .constraints([
            Constraint::Ratio(1, 3),
            Constraint::Ratio(1, 3),
            Constraint::Ratio(1, 3),
        ])
        .split(rows[1]);

    draw_training(f, cards[0], app, bg);
    draw_hive(f, cards[1], app, bg);
    draw_soul(f, cards[2], app, bg);

    let panels = Layout::default()
        .direction(Direction::Horizontal)
        .constraints([Constraint::Percentage(50), Constraint::Percentage(50)])
        .split(rows[2]);

    draw_hive_logs(f, panels[0], app, bg);
    draw_peers(f, panels[1], app, bg);

    draw_hints(f, rows[3], app);
}

fn draw_topbar(f: &mut Frame, area: Rect, app: &App) {
    let sep = Span::styled("  |  ", Style::default().fg(MUTED));
    let countdown = if app.refreshing {
        "refreshing".to_string()
    } else {
        format!("auto {}s", app.countdown())
    };

    let line = Line::from(vec![
        Span::styled(
            "cordia-ops",
            Style::default().fg(GREEN).add_modifier(Modifier::BOLD),
        ),
        sep.clone(),
        Span::styled(app.cfg.operator.clone(), Style::default().fg(FG)),
        sep.clone(),
        Span::styled(app.cfg.host.clone(), Style::default().fg(MUTED)),
        sep,
        Span::styled(countdown, Style::default().fg(GREEN)),
    ]);

    f.render_widget(
        Paragraph::new(line).block(
            Block::default()
                .borders(Borders::ALL)
                .border_set(ASCII_BORDER)
                .border_style(Style::default().fg(MUTED))
                .style(Style::default().bg(app.cfg.bg())),
        ),
        area,
    );
}

fn draw_training(f: &mut Frame, area: Rect, app: &App, bg: Color) {
    let body = match &app.snap.train {
        Err(e) => unreachable_lines(e),
        Ok(t) => {
            let ok = t.ok.unwrap_or(false);
            vec![
                Line::from(vec![
                    dot(ok),
                    Span::styled(
                        if ok { " ok" } else { " degraded" },
                        Style::default().fg(if ok { GREEN } else { MUTED }),
                    ),
                ]),
                Line::from(Span::styled(
                    num(t.responses),
                    Style::default().fg(GREEN).add_modifier(Modifier::BOLD),
                )),
                Line::from(Span::styled("responses", Style::default().fg(MUTED))),
                Line::from(""),
                kv("ratings", num(t.ratings)),
                kv("ts", scalar(&t.ts)),
            ]
        }
    };
    card(f, area, "TRAINING", bg, body);
}

fn draw_hive(f: &mut Frame, area: Rect, app: &App, bg: Color) {
    let body = match &app.snap.hive {
        Err(e) => unreachable_lines(e),
        Ok(h) => {
            let status = h.status.clone().unwrap_or_else(|| "unknown".to_string());
            let ok = matches!(status.to_lowercase().as_str(), "ok" | "up" | "running" | "healthy");
            vec![
                Line::from(vec![
                    dot(ok),
                    Span::styled(
                        format!(" {status}"),
                        Style::default().fg(if ok { GREEN } else { MUTED }),
                    ),
                ]),
                Line::from(Span::styled(
                    num(h.messages_total),
                    Style::default().fg(GREEN).add_modifier(Modifier::BOLD),
                )),
                Line::from(Span::styled("messages total", Style::default().fg(MUTED))),
                Line::from(""),
                kv("uptime", scalar(&h.uptime)),
                kv("logs", scalar(&h.logs)),
            ]
        }
    };
    card(f, area, "HIVEBUS", bg, body);
}

fn draw_soul(f: &mut Frame, area: Rect, app: &App, bg: Color) {
    let body = match &app.snap.soul {
        Err(e) => unreachable_lines(e),
        Ok(s) => {
            let status = s.status.clone().unwrap_or_else(|| "unknown".to_string());
            let ok = matches!(status.to_lowercase().as_str(), "ok" | "up" | "running" | "healthy");
            vec![
                Line::from(vec![
                    dot(ok),
                    Span::styled(
                        format!(" {status}"),
                        Style::default().fg(if ok { GREEN } else { MUTED }),
                    ),
                ]),
                Line::from(Span::styled(
                    s.skills.len().to_string(),
                    Style::default().fg(GREEN).add_modifier(Modifier::BOLD),
                )),
                Line::from(Span::styled("skills loaded", Style::default().fg(MUTED))),
                Line::from(""),
                kv("logs", s.logs.len().to_string()),
            ]
        }
    };
    card(f, area, "SOUL", bg, body);
}

fn draw_hive_logs(f: &mut Frame, area: Rect, app: &App, bg: Color) {
    let block = panel("HIVE LOGS", bg);

    match &app.snap.hive_logs {
        Err(e) => {
            f.render_widget(Paragraph::new(unreachable_lines(e)).block(block), area);
        }
        Ok(l) if l.logs.is_empty() => {
            f.render_widget(
                Paragraph::new(Line::from(Span::styled(
                    "no log streams reported",
                    Style::default().fg(MUTED),
                )))
                .block(block),
                area,
            );
        }
        Ok(l) => {
            let rows: Vec<Row> = l
                .logs
                .iter()
                .map(|e| {
                    Row::new(vec![
                        Cell::from(e.name.clone().unwrap_or_else(|| "?".into()))
                            .style(Style::default().fg(FG)),
                        Cell::from(num(e.messages)).style(Style::default().fg(GREEN)),
                        Cell::from(human_size(&e.file_size)).style(Style::default().fg(MUTED)),
                    ])
                })
                .collect();

            let table = Table::new(
                rows,
                [
                    Constraint::Percentage(56),
                    Constraint::Percentage(22),
                    Constraint::Percentage(22),
                ],
            )
            .header(
                Row::new(vec!["NAME", "MSGS", "SIZE"])
                    .style(Style::default().fg(MUTED).add_modifier(Modifier::BOLD)),
            )
            .column_spacing(1)
            .block(block);

            f.render_widget(table, area);
        }
    }
}

fn draw_peers(f: &mut Frame, area: Rect, app: &App, bg: Color) {
    let block = panel("TAILSCALE PEERS", bg);

    match &app.snap.peers {
        Err(e) => {
            f.render_widget(Paragraph::new(unreachable_lines(e)).block(block), area);
        }
        Ok(p) if p.is_empty() => {
            f.render_widget(
                Paragraph::new(Line::from(Span::styled(
                    "no peers reported",
                    Style::default().fg(MUTED),
                )))
                .block(block),
                area,
            );
        }
        Ok(p) => {
            let rows: Vec<Row> = p
                .iter()
                .map(|peer| {
                    let name = if peer.is_self {
                        format!("{} (self)", peer.name)
                    } else {
                        peer.name.clone()
                    };
                    Row::new(vec![
                        Cell::from(name).style(Style::default().fg(FG)),
                        Cell::from(if peer.online { "online" } else { "offline" }).style(
                            Style::default().fg(if peer.online { GREEN } else { MUTED }),
                        ),
                    ])
                })
                .collect();

            let table = Table::new(
                rows,
                [Constraint::Percentage(65), Constraint::Percentage(35)],
            )
            .header(
                Row::new(vec!["NAME", "ONLINE"])
                    .style(Style::default().fg(MUTED).add_modifier(Modifier::BOLD)),
            )
            .column_spacing(1)
            .block(block);

            f.render_widget(table, area);
        }
    }
}

fn draw_hints(f: &mut Frame, area: Rect, app: &App) {
    let key = |k: &'static str| Span::styled(k, Style::default().fg(GREEN));
    let txt = |t: &'static str| Span::styled(t, Style::default().fg(MUTED));

    let line = Line::from(vec![
        key(" q"),
        txt(" quit  "),
        txt("\u{b7}"),
        key(" r"),
        txt(" refresh  "),
        txt("\u{b7}"),
        txt(" auto 10s"),
    ]);

    f.render_widget(
        Paragraph::new(line)
            .alignment(Alignment::Left)
            .style(Style::default().bg(app.cfg.bg())),
        area,
    );
}

// ---------------------------------------------------------------------------
// Terminal lifecycle
// ---------------------------------------------------------------------------

fn setup_terminal() -> Result<Terminal<CrosstermBackend<Stdout>>> {
    enable_raw_mode()?;
    let mut out = io::stdout();
    execute!(out, EnterAlternateScreen)?;
    let terminal = Terminal::new(CrosstermBackend::new(out))?;
    Ok(terminal)
}

fn restore_terminal() {
    // Best-effort: this also runs from the panic hook, so it must not fail.
    let _ = disable_raw_mode();
    let _ = execute!(io::stdout(), LeaveAlternateScreen);
}

fn main() -> Result<()> {
    let cfg = Config::from_env_and_args();

    // Release builds use panic = "abort"; panic hooks still run, so the
    // terminal is restored before the process dies.
    let default_hook = std::panic::take_hook();
    std::panic::set_hook(Box::new(move |info| {
        restore_terminal();
        default_hook(info);
    }));

    let poller_cfg = Config {
        host: cfg.host.clone(),
        operator: cfg.operator.clone(),
        opaque: cfg.opaque,
    };
    let (snap_rx, req_tx) = spawn_poller(poller_cfg);

    let mut app = App {
        cfg,
        snap: Snapshot::pending(),
        last_refresh: Instant::now(),
        refreshing: true,
    };

    let mut terminal = setup_terminal()?;
    let res = run(&mut terminal, &mut app, &snap_rx, &req_tx);
    restore_terminal();
    terminal.show_cursor().ok();
    res
}

fn run(
    terminal: &mut Terminal<CrosstermBackend<Stdout>>,
    app: &mut App,
    snap_rx: &Receiver<Snapshot>,
    req_tx: &Sender<()>,
) -> Result<()> {
    loop {
        // Drain any snapshots the poller produced since the last frame.
        while let Ok(snap) = snap_rx.try_recv() {
            app.snap = snap;
            app.last_refresh = Instant::now();
            app.refreshing = false;
        }

        terminal.draw(|f| ui(f, app))?;

        // Short poll keeps the countdown ticking without burning CPU.
        if event::poll(Duration::from_millis(200))? {
            if let Event::Key(k) = event::read()? {
                if k.kind != KeyEventKind::Press {
                    continue;
                }
                match k.code {
                    KeyCode::Char('q') | KeyCode::Esc => return Ok(()),
                    KeyCode::Char('c') if k.modifiers.contains(KeyModifiers::CONTROL) => {
                        return Ok(())
                    }
                    KeyCode::Char('r') => {
                        app.refreshing = true;
                        // Poller may be mid-cycle; a full channel is harmless.
                        let _ = req_tx.send(());
                    }
                    _ => {}
                }
            }
        }
    }
}
