# MisakaNet

MisakaNet is a collection of utilities and libraries for Android development,
root handling, and module management.  It provides helpers for KernelSU,
Zygisk, LSPosed and other Xposed‑like frameworks.

---

## 📚 Documentation

- **Getting Started** – How to set up the project.
- **KernelSU Integration** – Using KernelSU APIs.
- **Zygisk Module Management** – Installing and managing modules.

---

## 🛠️ Emulator Support

### MuMu Emulator (Android 15 / x86_64)

The MuMu emulator ships with KernelSU but **does not provide a traditional `su` binary**.
Instead, the userspace CLI is renamed to `dusk`, which cannot be used as a drop‑in
replacement for `su`.  Many apps (e.g., LSPosed modules) expect `su` to exist and
will fail to obtain root privileges.

#### Why does this happen?

- MuMu’s **Root permission** toggle only enables *adb root*; it does **not** install
  a `su` binary.
- KernelSU’s su‑compatibility layer intercepts `execve` calls for files named `su`.
  Therefore, placing an executable named `su` in a directory that is part of the
  app’s `PATH` gives the app root access, even though the file itself does not
  have the set‑uid bit.

#### Quick fix

Copy the bundled `busybox` binary to `/system/xbin/su`.  The KernelSU hook will
grant root to any process that executes this file, while the binary itself simply
forwards the command to the underlying shell.

```bash
# 1️⃣ Enable MuMu's "Root permission" (Settings → Developer options → Root permission)
#    or via CLI:
#    MuMuManager.exe setting -k root_permission -val true

# 2️⃣ Restart adbd as root
adb connect 127.0.0.1:16384
adb root          # → restarting adbd as root
adb shell id      # should show uid=0(root) ...

# 3️⃣ Deploy busybox as a fake `su`
adb shell "cp /system/xbin/busybox /system/xbin/su; chmod 755 /system/xbin/su"

# 4️⃣ Verify
adb shell "ls -l /system/xbin/su"
# -rwxr-xr-x 1 root root <size> /system/xbin/su
```

After this, apps that call `su -c …` will obtain root privileges via KernelSU’s
su‑compat layer.

#### Automated script

We now provide an automated helper script:

```
./scripts/mumu_su_fix.sh [-i path/to/module.zip]
```

The script:

1. Checks that MuMu’s root permission is enabled (reminds the user).
2. Connects to the emulator and restarts `adbd` as root.
3. Copies `busybox` → `/system/xbin/su` and sets the correct permissions.
4. (Optional) Installs a KernelSU module using the renamed `dusk` CLI.

See `scripts/mumu_su_fix.sh` for full usage details.

---

## 🎯 Pull Request Checklist

- [x] Added `scripts/mumu_su_fix.sh` – automates the su‑compat workaround for MuMu.
- [x] Updated `README.md` with detailed explanation and manual steps.
- [x] Documented why the issue occurs and how the fix works.

--- 

*For more information about KernelSU, Zygisk, and LSPosed, refer to the
corresponding sections in the documentation.*
