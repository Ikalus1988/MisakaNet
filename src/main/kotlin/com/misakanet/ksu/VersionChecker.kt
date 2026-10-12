package com.misakanet.ksu

/**
 * Utility object used by the module installer to verify that the running KernelSU
 * version string follows the expected format.
 *
 * The original implementation only accepted version strings that contain the
 * substring “submodule” (e.g. `submodule-3.2.5-32525`).  On some emulators – notably
 * MuMu – KernelSU is integrated by copying the source code directly into the
 * kernel.  In that case the version string is a plain integer (e.g. `32525`).
 *
 * This caused the installer to abort with the message:
 *
 *   ! KernelSU version abnormal!
 *   ! Please integrate KernelSU into your kernel as submodule instead of copying the source code
 *
 * The fix relaxes the validation logic:
 *   • Accept the original “submodule‑*” format.
 *   • Accept a plain numeric version (e.g. `32525`).
 *   • Keep the strict check for completely malformed strings.
 *
 * The function returns `true` when the version string is considered valid.
 */
object VersionChecker {

    // Regex for the original expected format: something like "submodule-3.2.5-32525"
    private val SUBMODULE_REGEX = Regex("""(?i)submodule[-_]\d+(?:\.\d+)*[-_]\d+""")

    // Regex for the numeric‑only format used by MuMu (e.g. "32525")
    private val NUMERIC_REGEX = Regex("""^\d+$""")

    /**
     * Checks whether the supplied [version] string is a valid KernelSU version.
     *
     * @param version The raw version string reported by `ksud -V` or `su -V`.
     * @return `true` if the version is acceptable, `false` otherwise.
     */
    @JvmStatic
    fun isValidVersion(version: String?): Boolean {
        if (version.isNullOrBlank()) return false

        // Trim whitespace and possible surrounding brackets.
        val cleaned = version.trim()

        // Accept either the submodule format or a plain numeric version.
        return SUBMODULE_REGEX.matches(cleaned) || NUMERIC_REGEX.matches(cleaned)
    }
}
