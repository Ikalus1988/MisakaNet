#!/usr/bin/env bash
# =============================================================================
# Shamiko manual installation script for MuMu emulator (KernelSU version abnormal)
# =============================================================================
#
# This script automates the steps described in the lesson submission
# https://github.com/Ikalus1988/MisakaNet/issues/3176 .
#
# Prerequisites:
#   • ADB is installed and accessible in PATH.
#   • The device/emulator is already booted and reachable via `adb devices`.
#   • You have root access on the device (`adb root`).
#
# Usage:
#   ./scripts/shamiko_manual_install.sh /path/to/Shamiko-v1.2.5-414-release.zip
#
# The script will:
#   1. Extract the zip (which uses ZSTD compression) using `bsdtar`.
#   2. Push the extracted files to /data/adb/modules/zygisk_shamiko.
#   3. Set the correct permissions.
#   4. Clean up temporary files.
#
# Note: The script does NOT rely on the KernelSU module installer, so it works
#       on MuMu where the installer aborts due to the “KernelSU version abnormal”
#       check.

set -euo pipefail

if [[ $# -ne 1 ]]; then
    echo "Usage: $0 /path/to/Shamiko-v1.2.5-414-release.zip"
    exit 1
fi

ZIP_PATH="$1"
TMP_DIR="$(mktemp -d)"
MODULE_NAME="zygisk_shamiko"
MODULE_PATH="/data/adb/modules/${MODULE_NAME}"

echo "[*] Extracting $ZIP_PATH to temporary directory..."
# bsdtar can handle the ZSTD compression used inside the zip.
bsdtar -xf "$ZIP_PATH" -C "$TMP_DIR"

echo "[*] Creating module directory on device..."
adb shell "mkdir -p ${MODULE_PATH}"

echo "[*] Pushing module files to device (flattening one level)..."
adb push "$TMP_DIR" "${MODULE_PATH}"
# The push creates an extra directory level (the zip root). Flatten it.
adb shell "cd ${MODULE_PATH} && mv -f */* . && rmdir */* || true"

echo "[*] Setting executable permissions..."
adb shell "chmod 755 ${MODULE_PATH}/*.sh ${MODULE_PATH}/machikado.* ${MODULE_PATH}/zygisk/*.so"
adb shell "chmod 644 ${MODULE_PATH}/module.prop"

echo "[*] Cleaning up temporary files..."
rm -rf "$TMP_DIR"

echo "[+] Installation complete. Reboot the device to finalize:"
echo "    adb shell reboot"
