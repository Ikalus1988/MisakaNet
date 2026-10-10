using System;
using System.IO;

namespace MisakaNet.Sandbox
{
    /// <summary>
    /// Represents a file access policy for the sandboxed environment.
    /// </summary>
    public class FilePolicy
    {
        private readonly string _workspaceRoot;

        public FilePolicy(string workspaceRoot)
        {
            if (string.IsNullOrWhiteSpace(workspaceRoot))
                throw new ArgumentException("Workspace root cannot be null or empty.", nameof(workspaceRoot));

            // Normalize the workspace root to an absolute path without trailing separators.
            _workspaceRoot = Path.GetFullPath(workspaceRoot.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar));
        }

        /// <summary>
        /// Determines whether the specified path is allowed to be written to under the current policy.
        /// </summary>
        /// <param name="path">The file or directory path to check.</param>
        /// <returns>True if the path is writable; otherwise, false.</returns>
        public bool IsWritable(string path)
        {
            if (string.IsNullOrWhiteSpace(path))
                return false;

            // Resolve the absolute path of the target.
            string fullPath;
            try
            {
                fullPath = Path.GetFullPath(path);
            }
            catch (Exception)
            {
                // If the path cannot be resolved (e.g., invalid characters), deny access.
                return false;
            }

            // Normalize the target path to avoid issues with trailing separators.
            fullPath = fullPath.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);

            // The policy for "workspace-write" should allow writing to the workspace root
            // and any of its subdirectories. The original implementation mistakenly
            // compared the full path to the root using equality, which prevented
            // subdirectory writes. The corrected logic uses a prefix check.
            return fullPath.StartsWith(_workspaceRoot, StringComparison.OrdinalIgnoreCase);
        }
    }
}
