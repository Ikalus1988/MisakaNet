# 手动安装 Shamiko 模块（MuMu 模拟器，KernelSU 版本异常）

在 MuMu 6.8.4（Android 15）中，使用官方的 **KernelSU** 模块安装器会因为
`KernelSU version abnormal!` 而中止安装。  
本指南提供一种 **手动** 安装方式，绕过版本检查，确保模块能够正常工作。

## 前置条件

| 条件 | 说明 |
|------|------|
| ADB | 已经在系统 `PATH` 中，可通过 `adb devices` 看到设备 |
| Root 权限 | 在设备上执行 `adb root`（MuMu 需要先 `adb root`） |
| 解压工具 | `bsdtar`（Windows 自带，Linux/macOS 可使用 `tar`） |
| Shamiko 包 | `Shamiko-v1.2.5-414-release.zip`（或更新的版本） |

## 步骤

1. **解压 ZIP**  
   ```bash
   mkdir -p /tmp/shamiko
   bsdtar -xf Shamiko-v1.2.5-414-release.zip -C /tmp/shamiko
   ```

2. **在设备上创建模块目录**  
   ```bash
   adb shell "mkdir -p /data/adb/modules/zygisk_shamiko"
   ```

3. **推送文件并扁平化目录结构**  
   ```bash
   adb push /tmp/shamiko /data/adb/modules/zygisk_shamiko
   adb shell "cd /data/adb/modules/zygisk_shamiko && mv -f */* . && rmdir */* || true"
   ```

4. **设置权限**  
   ```bash
   adb shell "chmod 755 /data/adb/modules/zygisk_shamiko/*.sh \
               /data/adb/modules/zygisk_shamiko/machikado.* \
               /data/adb/modules/zygisk_shamiko/zygisk/*.so"
   adb shell "chmod 644 /data/adb/modules/zygisk_shamiko/module.prop"
   ```

5. **确认没有 `disable` 文件并重启**  
   ```bash
   adb shell "rm -f /data/adb/modules/zygisk_shamiko/disable"
   adb shell reboot
   ```

6. **验证安装**  
   ```bash
   adb shell "/system/xbin/dusk module list"          # 应出现 id=zygisk_shamiko, enabled=true
   adb shell "ls /data/adb/zygisksu/"                # 出现 no_mount_znctl
   adb shell "ls /data/adb/post-fs-data.d/"          # 出现 .shamiko_cleanup.sh
   ```

> **提示**：如果你想一次性完成上述所有步骤，可直接运行仓库提供的脚本：
> ```bash
> ./scripts/shamiko_manual_install.sh Shamiko-v1.2.5-414-release.zip
> ```

## 为什么需要手动安装？

MuMu 使用的是 **复制源码方式** 集成的 KernelSU，`ksud -V` 只会返回一个纯数字（如 `32525`），而
Shamiko 的 `customize.sh` 只接受 “submodule‑*” 形式的版本字符串，导致安装器误判为异常版本并 abort。

通过本手动方式：

* 跳过 `customize.sh` 的版本校验；
* 直接把模块文件放到 Zygisk 模块目录；
* 保持模块 `enabled=true`，隐藏功能正常工作。

## 参考

* Issue #3176 – “Shamiko 在 MuMu 模拟器的 KernelSU 上拒装（KernelSU version abnormal）的手工安装解法”
* 官方 KernelSU 文档
* ZygiskNext / Vector 兼容性说明

---  
*本页由 MisakaNet 项目维护，欢迎贡献改进。*
