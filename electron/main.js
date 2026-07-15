const { app, BrowserWindow, Menu } = require("electron");
const path = require("path");
const fs = require("fs");
const { spawn } = require("child_process");
const http = require("http");

// Two instances would both try to spawn a backend on the same hardcoded
// port - the second one fails to bind and exits, but by then it may have
// already stolen an in-flight request from the first instance's renderer.
// Only one instance may run; a second launch just focuses the first.
const gotSingleInstanceLock = app.requestSingleInstanceLock();
if (!gotSingleInstanceLock) {
  app.quit();
  return;
}

app.on("second-instance", () => {
  if (mainWindow) {
    if (mainWindow.isMinimized()) mainWindow.restore();
    mainWindow.focus();
  }
});

const BACKEND_PORT = 8000;
const BACKEND_HEALTH_URL = `http://127.0.0.1:${BACKEND_PORT}/api/health`;

let backendProcess = null;
let mainWindow = null;
let logStream = null;

// A double-clicked packaged app has no attached console, so plain
// console.log/process.stdout.write vanish - this also persists everything
// to a file so backend errors (e.g. a 500 from a search) can be diagnosed
// after the fact instead of only when launched from an existing terminal.
function initLogging() {
  const logDir = path.join(app.getPath("userData"), "logs");
  fs.mkdirSync(logDir, { recursive: true });
  logStream = fs.createWriteStream(path.join(logDir, "backend.log"), { flags: "a" });
  log(`\n[${new Date().toISOString()}] App starting (packaged=${app.isPackaged}, version=${app.getVersion()})\n`);
}

function log(text) {
  process.stdout.write(text);
  logStream?.write(text);
}

function resolveBackendCommand() {
  if (app.isPackaged) {
    // Packaged app: run the PyInstaller-built backend bundled as an
    // extraResource (see package.json "build.extraResources").
    const exeName =
      process.platform === "win32"
        ? "Battery Literature AI Backend.exe"
        : "Battery Literature AI Backend";
    return {
      command: path.join(process.resourcesPath, "backend", exeName),
      args: [],
      cwd: path.join(process.resourcesPath, "backend"),
    };
  }

  // Dev mode: run the backend straight from source with the system Python
  // (expects `pip install -r backend/requirements.txt` to have been run).
  const pythonBin = process.env.BLIP_PYTHON || (process.platform === "win32" ? "python" : "python3");
  return {
    command: pythonBin,
    args: ["run_server.py"],
    cwd: path.join(__dirname, "..", "backend"),
  };
}

function startBackend() {
  const { command, args, cwd } = resolveBackendCommand();
  log(`[backend] launching: ${command} ${args.join(" ")} (cwd=${cwd})\n`);
  backendProcess = spawn(command, args, { cwd, env: process.env, windowsHide: true });

  backendProcess.stdout?.on("data", (data) => log(`[backend] ${data}`));
  backendProcess.stderr?.on("data", (data) => log(`[backend] ${data}`));
  backendProcess.on("error", (err) => log(`[backend] failed to start: ${err.stack || err}\n`));
  backendProcess.on("exit", (code) => log(`[backend] exited with code ${code}\n`));
}

function waitForBackend(retries = 60) {
  return new Promise((resolve, reject) => {
    const attempt = (remaining) => {
      http
        .get(BACKEND_HEALTH_URL, (res) => {
          res.resume();
          if (res.statusCode === 200) {
            resolve();
          } else if (remaining > 0) {
            setTimeout(() => attempt(remaining - 1), 500);
          } else {
            reject(new Error("Backend health check returned a non-200 status."));
          }
        })
        .on("error", () => {
          if (remaining > 0) {
            setTimeout(() => attempt(remaining - 1), 500);
          } else {
            reject(new Error("Backend did not become ready in time."));
          }
        });
    };
    attempt(retries);
  });
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 900,
    title: "Battery Literature AI",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  const startUrl =
    process.env.ELECTRON_START_URL ||
    `file://${path.join(__dirname, "..", "frontend", "dist", "index.html")}`;
  return mainWindow.loadURL(startUrl);
}

app.whenReady().then(async () => {
  initLogging();
  Menu.setApplicationMenu(null);

  startBackend();
  try {
    await waitForBackend();
  } catch (err) {
    log(`[backend] not ready: ${err.message}\n`);
  }

  await createWindow();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  if (backendProcess) backendProcess.kill();
  if (process.platform !== "darwin") app.quit();
});

app.on("before-quit", () => {
  if (backendProcess) backendProcess.kill();
});
