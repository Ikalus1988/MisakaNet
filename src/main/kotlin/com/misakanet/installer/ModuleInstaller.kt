package com.misakanet.installer

import com.misakanet.ksu.VersionChecker
import java.io.File
import java.io.IOException
import java.util.zip.ZipFile

/**
 * ModuleInstaller is a tiny helper that demonstrates how the relaxed
 * KernelSU version check can be used during module installation.
 *
 * In the original repository the installer aborted when the KernelSU
 * version string did not match the strict “submodule‑*” pattern.
 * After applying the fix in `VersionChecker`, numeric‑only version strings
 * (e.g. `32525`) are accepted, which enables installation on MuMu
 * emulator and other environments where KernelSU is integrated by copying
 * the source code.
 *
 * This class does **not** implement a full‑blown module installer – the
 * project’s primary purpose is educational – but it provides a clear,
 * compile‑time‑safe example that can be expanded by downstream users.
 */
object ModuleInstaller {

    /**
     * Installs a Zygisk module from the supplied [zipFile].
     *
     * @param zipFile The module zip archive (must exist).
     * @throws IllegalArgumentException if the zip file does not exist.
     * @throws IllegalStateException if the current KernelSU version is not supported.
     * @throws IOException if extracting the zip fails.
     */
    @JvmStatic
    @Throws(IllegalArgumentException::class, IllegalStateException::class, IOException::class)
    fun install(zipFile: File) {
        require(zipFile.exists()) { "Zip file does not exist: ${zipFile.absolutePath}" }

        // --------------------------------------------------------------------
        // 1️⃣ Retrieve
