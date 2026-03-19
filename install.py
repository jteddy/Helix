"""
Helix — First-time setup
Run once before starting the server for the first time.

  python install.py

Does three things:
  1. Installs Python dependencies (including the correct makcu build for your firmware)
  2. Adds your user account to the USB device groups  (Linux)
  3. Writes a udev rule so the MAKCU is accessible without root  (Linux)
"""
import os
import subprocess
import sys


# ── Package sources ───────────────────────────────────────────────────────────

MAKCU_STABLE   = "makcu==2.3.1"
MAKCU_FORK_V37 = "git+https://github.com/jteddy/makcu-py-lib.git@firmware-v3.7"

BASE_DEPS = [
    "fastapi",
    "uvicorn[standard]",
]

FIRMWARE_OPTIONS = {
    "1": ("3.4 (stable)", MAKCU_STABLE),
    "2": ("3.7",          MAKCU_FORK_V37),
}

UDEV_RULE_PATH = "/etc/udev/rules.d/99-makcu.rules"
UDEV_RULE_CONTENT = """\
# MAKCU — allow all users to access HID devices without root
SUBSYSTEM=="hidraw", MODE="0666"
SUBSYSTEM=="usb", ATTRS{bInterfaceClass}=="03", MODE="0666"
"""


# ── Helpers ───────────────────────────────────────────────────────────────────

def pip_install(package: str) -> bool:
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--break-system-packages", package],
        capture_output=False,
    )
    return result.returncode == 0


def sudo_run(args: list) -> bool:
    result = subprocess.run(["sudo"] + args)
    return result.returncode == 0


def is_linux() -> bool:
    return sys.platform.startswith("linux")


# ── Steps ─────────────────────────────────────────────────────────────────────

def step_dependencies(makcu_package: str) -> list:
    """Install Python deps. Returns list of any that failed."""
    failed = []
    for dep in BASE_DEPS + [makcu_package]:
        print(f"  Installing {dep} ...")
        if not pip_install(dep):
            failed.append(dep)
    return failed


def step_usb_groups(username: str):
    """Add user to plugdev and dialout groups."""
    for group in ("plugdev", "dialout"):
        print(f"  Adding {username} to {group} ...")
        sudo_run(["usermod", "-aG", group, username])


def step_udev():
    """Write udev rule and reload."""
    print(f"  Writing {UDEV_RULE_PATH} ...")
    proc = subprocess.run(
        ["sudo", "tee", UDEV_RULE_PATH],
        input=UDEV_RULE_CONTENT.encode(),
        capture_output=True,
    )
    if proc.returncode != 0:
        print("  Warning: failed to write udev rule — try running with sudo")
        return
    sudo_run(["udevadm", "control", "--reload-rules"])
    sudo_run(["udevadm", "trigger"])


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print()
    print("=" * 50)
    print("  Helix — Setup")
    print("=" * 50)
    print()

    # ── Firmware selection ────────────────────────────────────────────────────
    print("What firmware version is your MAKCU running?")
    for key, (label, _) in FIRMWARE_OPTIONS.items():
        print(f"  {key}) v{label}")
    print()

    while True:
        choice = input("Enter choice (1 or 2): ").strip()
        if choice in FIRMWARE_OPTIONS:
            break
        print("  Please enter 1 or 2.")

    firmware_label, makcu_package = FIRMWARE_OPTIONS[choice]
    print()

    # ── Step 1 — Python dependencies ─────────────────────────────────────────
    print("[ 1/3 ] Installing Python dependencies...")
    failed = step_dependencies(makcu_package)
    if failed:
        print()
        print("  The following packages failed to install:")
        for f in failed:
            print(f"    - {f}")
        print()
        print("  Check your internet connection and try again.")
        sys.exit(1)
    print("        Done.")
    print()

    # ── Steps 2 & 3 — Linux USB setup ────────────────────────────────────────
    if is_linux():
        username = os.environ.get("SUDO_USER") or os.environ.get("USER") or os.getlogin()

        print(f"[ 2/3 ] Adding {username} to USB device groups...")
        step_usb_groups(username)
        print("        Done.")
        print()

        print("[ 3/3 ] Writing udev rule for MAKCU HID access...")
        step_udev()
        print("        Done.")
        print()
    else:
        print("[ 2/3 ] Skipping USB group setup (Linux only)")
        print("[ 3/3 ] Skipping udev rule (Linux only)")
        print()

    # ── Done ──────────────────────────────────────────────────────────────────
    print("=" * 50)
    print("  Setup complete.")
    if is_linux():
        print()
        print("  IMPORTANT: Log out and back in (or reboot)")
        print("  for group changes to take effect.")
    print()
    print("  Then run:  python main.py")
    print("=" * 50)
    print()


if __name__ == "__main__":
    main()
