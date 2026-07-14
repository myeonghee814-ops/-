const { app, BrowserWindow, Menu } = require("electron");
const path = require("path");
const { spawn } = require("child_process");
const http = require("http");

const BACKEND_PORT = 8000;
const BACKEND_HEALTH_URL = `http://127.0.0.1:${BACKEND_PORT}/api/health`;

let backendProcess = null;
let mainWindow = null;

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
  backendProcess = spawn(command, args, { cwd, env: process.env, windowsHide: true });

  backendProcess.stdout?.on("data", (data) => process.stdout.write(`[backend] ${data}`));
  backendProcess.stderr?.on("data", (data) => process.stderr.write(`[backend] ${data}`));
  backendProcess.on("error", (err) => console.error("[backend] failed to start:", err));
  backendProcess.on("exit", (code) => console.log(`[backend] exited with code ${code}`));
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
  Menu.setApplicationMenu(null);

  startBackend();
  try {
    await waitForBackend();
  } catch (err) {
    console.error("[backend] not ready:", err.message);
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
