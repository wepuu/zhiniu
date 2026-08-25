import { spawn, spawnSync } from "node:child_process";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const webRoot = dirname(dirname(fileURLToPath(import.meta.url)));
const nextBin = join(webRoot, "node_modules", "next", "dist", "bin", "next");
const playwrightBin = join(
  webRoot,
  "node_modules",
  "@playwright",
  "test",
  "cli.js",
);
const externalBaseUrl = process.env.E2E_BASE_URL;
const baseUrl = externalBaseUrl ?? "http://127.0.0.1:3100";

function run(args, options = {}) {
  return new Promise((resolve, reject) => {
    const child = spawn(process.execPath, args, {
      cwd: webRoot,
      stdio: "inherit",
      ...options,
    });
    child.once("error", reject);
    child.once("exit", (code) => resolve(code ?? 1));
  });
}

async function waitForServer(url) {
  const deadline = Date.now() + 60_000;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(url);
      if (response.ok) return;
    } catch {}
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw new Error(`E2E server did not become ready: ${url}`);
}

function stopTree(child) {
  if (!child || child.exitCode !== null) return;
  if (process.platform === "win32") {
    spawnSync("taskkill", ["/pid", String(child.pid), "/T", "/F"], {
      stdio: "ignore",
    });
  } else {
    child.kill("SIGTERM");
  }
}

let server;
try {
  if (!externalBaseUrl) {
    const buildCode = await run([nextBin, "build"]);
    if (buildCode !== 0) process.exitCode = buildCode;
    if (process.exitCode) process.exit();
    server = spawn(
      process.execPath,
      [nextBin, "start", "--hostname", "127.0.0.1", "--port", "3100"],
      { cwd: webRoot, stdio: "ignore" },
    );
    server.unref();
    await waitForServer(baseUrl);
  }
  process.exitCode = await run([playwrightBin, "test"], {
    env: { ...process.env, E2E_BASE_URL: baseUrl },
  });
} finally {
  stopTree(server);
}
