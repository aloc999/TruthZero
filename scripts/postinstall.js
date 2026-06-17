const { execSync, spawn } = require("child_process");
const path = require("path");
const fs = require("fs");
const os = require("os");

const ROOT = path.resolve(__dirname, "..");
const IS_WIN = os.platform() === "win32";
const VENV_DIR = path.join(ROOT, ".venv");
const PYTHON_BIN = IS_WIN
  ? path.join(VENV_DIR, "Scripts", "python.exe")
  : path.join(VENV_DIR, "bin", "python3");
const PIP_BIN = IS_WIN
  ? path.join(VENV_DIR, "Scripts", "pip.exe")
  : path.join(VENV_DIR, "bin", "pip");

const GREEN = "\x1b[32m";
const RED = "\x1b[31m";
const CYAN = "\x1b[36m";
const DIM = "\x1b[2m";
const RESET = "\x1b[0m";
const BOLD = "\x1b[1m";

function log(msg) {
  console.log(`${GREEN}[zer0code]${RESET} ${msg}`);
}

function err(msg) {
  console.error(`${RED}[zer0code]${RESET} ${msg}`);
}

function findPython() {
  const candidates = IS_WIN
    ? ["python", "python3", "py -3"]
    : ["python3", "python"];

  for (const cmd of candidates) {
    try {
      const version = execSync(`${cmd} --version 2>&1`, {
        encoding: "utf-8",
        timeout: 10000,
      }).trim();

      const match = version.match(/Python (\d+)\.(\d+)/);
      if (match) {
        const major = parseInt(match[1]);
        const minor = parseInt(match[2]);
        if (major === 3 && minor >= 10) {
          log(`Found ${version} (${DIM}${cmd}${RESET})`);
          return cmd;
        }
      }
    } catch (_) {}
  }
  return null;
}

function createVenv(pythonCmd) {
  log("Creating Python virtual environment...");
  try {
    execSync(`${pythonCmd} -m venv "${VENV_DIR}"`, {
      stdio: "pipe",
      timeout: 60000,
    });
    return true;
  } catch (e) {
    err(`Failed to create venv: ${e.message}`);
    return false;
  }
}

function installPackage() {
  log("Installing ZER0CODE and dependencies...");
  try {
    execSync(`"${PIP_BIN}" install --upgrade pip`, {
      stdio: "pipe",
      cwd: ROOT,
      timeout: 120000,
    });

    execSync(`"${PIP_BIN}" install -e "${ROOT}"`, {
      stdio: ["pipe", "pipe", "pipe"],
      cwd: ROOT,
      timeout: 300000,
    });

    return true;
  } catch (e) {
    err(`pip install failed: ${e.message}`);
    if (e.stderr) {
      const stderr = e.stderr.toString().split("\n").slice(-5).join("\n");
      err(stderr);
    }
    return false;
  }
}

function verifyInstall() {
  try {
    const result = execSync(`"${PYTHON_BIN}" -c "from zer0code import __version__; print(__version__)"`, {
      encoding: "utf-8",
      timeout: 15000,
    }).trim();
    return result;
  } catch (_) {
    return null;
  }
}

function makeBinExecutable() {
  if (!IS_WIN) {
    try {
      fs.chmodSync(path.join(ROOT, "bin", "zer0code"), 0o755);
    } catch (_) {}
  }
}

function main() {
  console.log("");
  console.log(`${GREEN}${BOLD}  _______ ____  ___   ____ ___  ____  _____${RESET}`);
  console.log(`${GREEN}${BOLD} |__  / __| _ \\/ _ \\ / ___/ _ \\|  _ \\| ____|${RESET}`);
  console.log(`${GREEN}${BOLD}   / /|  _|  _/ | | | |  | | | | | | |  _|${RESET}`);
  console.log(`${GREEN}${BOLD}  / /_| |_| | | |_| | |__| |_| | |_| | |___${RESET}`);
  console.log(`${GREEN}${BOLD} /____|___|_|  \\___/ \\____\\___/|____/|_____|${RESET}`);
  console.log("");
  log("Installing ZER0CODE...");
  console.log("");

  const pythonCmd = findPython();
  if (!pythonCmd) {
    err("Python 3.10+ is required but was not found.");
    err("");
    err("Install Python:");
    err("  macOS:   brew install python@3.12");
    err("  Ubuntu:  sudo apt install python3.12 python3.12-venv");
    err("  Windows: https://www.python.org/downloads/");
    err("  Any:     https://github.com/pyenv/pyenv");
    process.exit(1);
  }

  if (fs.existsSync(VENV_DIR)) {
    log("Existing venv found, reinstalling...");
  }

  if (!fs.existsSync(VENV_DIR)) {
    if (!createVenv(pythonCmd)) {
      err("Failed to create virtual environment.");
      err("Make sure python3-venv is installed:");
      err("  sudo apt install python3-venv");
      process.exit(1);
    }
  }

  if (!installPackage()) {
    err("Failed to install ZER0CODE.");
    err("Try manual installation:");
    err(`  cd ${ROOT}`);
    err(`  ${pythonCmd} -m venv .venv`);
    err(`  .venv/bin/pip install -e .`);
    process.exit(1);
  }

  const version = verifyInstall();
  if (!version) {
    err("Installation completed but verification failed.");
    err("Try running: zer0code version");
    process.exit(1);
  }

  makeBinExecutable();

  console.log("");
  log(`${BOLD}ZER0CODE v${version} installed successfully!${RESET}`);
  console.log("");
  log(`${CYAN}Quick start:${RESET}`);
  log(`  export OPENAI_API_KEY="sk-..."     ${DIM}# or ANTHROPIC_API_KEY or DEEPSEEK_API_KEY${RESET}`);
  log(`  zer0code                            ${DIM}# start interactive session${RESET}`);
  log(`  zer0code -p deepseek -m deepseek-v4-pro  ${DIM}# use DeepSeek${RESET}`);
  log(`  zer0code run "scan target.com"      ${DIM}# single command${RESET}`);
  console.log("");
}

main();
