#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::time::{Duration, Instant};

use tauri::path::BaseDirectory;
use tauri::Manager;
use tauri_plugin_shell::process::CommandEvent;
use tauri_plugin_shell::ShellExt;

const BACKEND_HEALTH_URL: &str = "http://127.0.0.1:8000/api/v1/health";
const BACKEND_URL: &str = "http://127.0.0.1:8000";
const READY_TIMEOUT: Duration = Duration::from_secs(30);

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            let handle = app.handle().clone();

            // Resolve the bundled frontend build (see tauri.conf.json's
            // bundle.resources -> "frontend_dist/") and hand its absolute
            // path to the sidecar via an env var, rather than having
            // backend/main.py guess it from its own binary's location --
            // that guess would otherwise depend on exactly how each
            // installer format (MSI/NSIS) lays out resource files, which
            // this scaffold hasn't verified against a real Windows build.
            let frontend_dist = app
                .path()
                .resolve("frontend_dist", BaseDirectory::Resource)
                .expect("failed to resolve bundled frontend_dist resource path");

            // Spawn the frozen Python backend (see backend/pyinstaller.spec,
            // built into src-tauri/binaries/blip-backend-<target-triple>.exe)
            // as a sidecar. Tauri terminates it automatically when the app
            // window closes -- see desktop-app/README.md for the build step
            // that puts the binary there.
            let sidecar = handle
                .shell()
                .sidecar("blip-backend")
                .expect(
                    "blip-backend sidecar not found -- build it with backend/pyinstaller.spec \
                     and copy it into src-tauri/binaries/ first, see desktop-app/README.md",
                )
                .env("BLIP_FRONTEND_DIST", frontend_dist.to_string_lossy().to_string());
            let (mut events, _child) = sidecar.spawn().expect("failed to spawn blip-backend sidecar");

            // Surface backend stdout/stderr in `tauri dev`'s terminal so a
            // startup failure (e.g. a missing hidden import -- see
            // backend/pyinstaller.spec) is visible instead of the window
            // just staying on the splash page forever with no clue why.
            tauri::async_runtime::spawn(async move {
                while let Some(event) = events.recv().await {
                    match event {
                        CommandEvent::Stdout(line) => {
                            print!("[backend] {}", String::from_utf8_lossy(&line));
                        }
                        CommandEvent::Stderr(line) => {
                            eprint!("[backend] {}", String::from_utf8_lossy(&line));
                        }
                        _ => {}
                    }
                }
            });

            // The main window opens on the bundled splash page (see
            // ../splash/index.html); once the backend responds to a health
            // check, navigate it to the real app. This runs on a plain OS
            // thread (not async_runtime) since it's just a few blocking
            // HTTP calls.
            let window = app.get_webview_window("main").expect("main window not found");
            std::thread::spawn(move || {
                wait_for_backend(BACKEND_HEALTH_URL, READY_TIMEOUT);
                // Navigate regardless of whether the wait timed out: if the
                // backend is genuinely broken, the request to BACKEND_URL
                // will fail visibly in the webview instead of the app
                // hanging on the splash screen with no explanation.
                let _ = window.eval(&format!("window.location.replace('{}')", BACKEND_URL));
            });

            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running the BLIP desktop shell");
}

/// Polls the backend's health endpoint until it responds 200 or `timeout`
/// elapses. Uses a short per-request timeout via an ureq Agent so a single
/// slow/hanging attempt can't blow past the overall deadline.
fn wait_for_backend(url: &str, timeout: Duration) -> bool {
    let agent = ureq::AgentBuilder::new().timeout(Duration::from_secs(2)).build();
    let deadline = Instant::now() + timeout;
    while Instant::now() < deadline {
        if let Ok(resp) = agent.get(url).call() {
            if resp.status() == 200 {
                return true;
            }
        }
        std::thread::sleep(Duration::from_millis(500));
    }
    false
}
