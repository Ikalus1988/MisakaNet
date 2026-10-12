#!/usr/bin/env bash
# =============================================================================
# mumu_su_fix.sh
#
# This script automates the workaround described in issue #3177 for the
# MuMu Android emulator (v6.8.4, Android 15 / x86_64) which does not ship a
# traditional `su` binary.  KernelSU is present, but its userspace CLI is
# renamed to `dusk` and cannot be used as a drop‑in replacement for `su`.
#
# The script performs the following actions:
#   1. Enables the emulator's "Root permission" toggle (requires MuMuManager.exe).
#   2. Restarts ADB as root.
#   3. Copies the bundled busybox binary to /system/xbin/su (no setuid needed).
#   4. Optionally installs a KernelSU module using the `dusk` command.
#
# Prerequisites
#   • MuMu emulator must have "System disk writable" enabled
#     (Settings → Disk Settings → Disk Sharing → Writable system disk) and be
#     rebooted after enabling.
#   • `adb` from the MuMu installation directory must be in PATH or you can
#     provide the full path via the ADAPTER variable.
#   • busybox must already exist at /system/xbin/busybox inside the emulator.
#
# Usage:
#   $ ./scripts/mumu_su_fix.sh [options] [module.zip]
#
# Options:
#   -h, --help        Show this help message.
#   -i, --install     Install a KernelSU module (provide path to zip as argument).
#
# Example:
#   $ ./scripts/mumu_su_fix.sh -i Zygisk-Next-1.5.0-843-5217106-release.zip
#
# =============================================================================

set -euo pipefail

# -------------------------- Helper Functions ---------------------------------

print_help() {
    grep '^#' "$0" | cut -c4-
    exit 0
}

error() {
    echo "Error: $*" >&2
    exit 1
}

# -------------------------- Argument Parsing ---------------------------------

INSTALL_MODULE=false
MODULE_PATH=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help)
            print_help
            ;;
        -i|--install)
            INSTALL_MODULE=true
            shift
            if [[ $# -eq 0 ]]; then
                error "Missing module zip path after -i/--install"
            fi
            MODULE_PATH="$1"
            ;;
        *)
            error "Unknown argument: $1"
            ;;
    esac
    shift
done

# -------------------------- Core Logic ---------------------------------------

# 1) Ensure MuMu's root permission is enabled.
#    This step cannot be performed programmatically from within the emulator,
#    but we remind the user.
echo "[*] Ensure MuMu's \"Root permission\" is turned ON (Settings → Developer options → Root permission)."
echo "    If you prefer the CLI, run:"
echo "        MuMuManager.exe setting -k root_permission -val true"
echo ""

# 2) Connect to the emulator and restart adbd as root.
ADB="${ADB:-adb}"
echo "[*] Connecting to MuMu ADB..."
$ADB connect 127.0.0.1:16384 || error "Failed to connect to MuMu ADB"

echo "[*] Restarting adbd as root..."
$ADB root || error "Failed to restart adbd as root"

echo "[*] Verifying root access..."
ROOT_ID=$($ADB shell id)
echo "    $ROOT_ID"

# 3) Deploy busybox as a fake `su` binary.
echo "[*] Copying busybox to /system/xbin/su ..."
$ADB shell "cp /system/xbin/busybox /system/xbin/su && chmod 755 /system/xbin/su" \
    || error "Failed to copy busybox to /system/xbin/su"

echo "[+] busybox successfully copied as /system/xbin/su"
echo "    Verify with: $ADB shell \"ls -l /system/xbin/su\""

# 4) Optional: install a KernelSU module using `dusk`.
if $INSTALL_MODULE; then
    if [[ ! -f "$MODULE_PATH" ]]; then
        error "Module zip not found at $MODULE_PATH"
    fi

    echo "[*] Pushing module zip to the device..."
    $ADB push "$MODULE_PATH" /data/local/tmp/ || error "Failed to push module zip"

    echo "[*] Installing module via dusk..."
    $ADB shell "dusk module install /data/local/tmp/$(basename "$MODULE_PATH")" \
        || error "dusk module install failed"

    echo "[*] Listing installed modules (will show pending updates)..."
    $ADB shell "dusk module list"
    echo "[+] Module installed. Reboot the emulator for the module to become active."
fi

echo ""
echo "[*] All done. Applications that rely on `su` (e.g., LSPosed modules) should now work."
echo "    To test, run:"
echo "        $ADB shell \"su -c id\""
echo "    Expected output: uid=0(root) gid=0(root) ..."
echo ""

exit 0
