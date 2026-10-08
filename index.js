const { spawn } = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

/**
 * Executes a command in a subprocess and captures its output.
 *
 * In the Windows sandbox, spawning a child process with piped stdio
 * (`stdio: 'pipe'`) can fail with `EPERM` because the sandbox does not
 * allow opening named pipes — which is how Node.js implements pipe stdio.
 *
 * This is a documented boundary, not a transient error, so we must not
 * retry the same spawn. Instead, we redirect the child's stdout/stderr
 * to a temporary file and read the result from disk.
 *
 * @param {string} cmd   - Command to execute.
 * @param {string[]} [args=[]] - Arguments for the command.
 * @returns {{ exitCode: number, stdout: string, stderr: string }}
 */
function runCommand(cmd, args = []) {
  const tmpFile = path.join(os.tmpdir(), `misaka-out-${Date.now()}.txt`);

  return new Promise((resolve, reject) => {
    const child = spawn(cmd, args, {
      shell: true,
      stdio: ['ignore', 'pipe', 'pipe'],
    });

    const chunks = [];
    const stderrChunks = [];

    child.stdout.on('data', (chunk) => chunks.push(chunk));
    child.stderr.on('data', (chunk) => stderrChunks.push(chunk));

    child.on('error', (err) => {
      if (err.code === 'EPERM') {
        // Fallback: use file-based redirection when the sandbox blocks pipes
        const fileChild = spawn(
          process.platform === 'win32' ? 'cmd.exe' : 'sh',
          process.platform === 'win32'
            ? ['/c', `${cmd} ${args.join(' ')} > "${tmpFile}" 2>&1`]
            : ['-c', `${cmd} ${args.join(' ')} > "${tmpFile}" 2>&1`],
          { shell: true }
        );

        fileChild.on('close', (code) => {
          let stdout = '';
          let stderr = '';
          try {
            stdout = fs.readFileSync(tmpFile, 'utf8');
          } catch (e) {
            // File may not exist if command failed before writing
          }
          try { fs.unlinkSync(tmpFile); } catch (_) {}
          resolve({ exitCode: code ?? 0, stdout, stderr });
        });

        fileChild.on('error', () => {
          try { fs.unlinkSync(tmpFile); } catch (_) {}
          reject(new Error(`Command failed: ${cmd} ${args.join(' ')}`));
        });

        return;
      }
      reject(err);
    });

    child.on('close', (code) => {
      resolve({
        exitCode: code ?? 0,
        stdout: Buffer.concat(chunks).toString('utf8'),
        stderr: Buffer.concat(stderrChunks).toString('utf8'),
      });
    });
  });
}

/**
 * Demonstrates capturing command output safely under the Windows sandbox.
 */
async function main() {
  console.log('=== MisakaNet Child Process Demo ===\n');

  try {
    console.log('[1] Running "echo hello world"...');
    const result1 = await runCommand('echo', ['hello', 'world']);
    console.log('    Exit code:', result1.exitCode);
    console.log('    Output:', result1.stdout.trim());
  } catch (err) {
    console.error('    Error:', err.message);
  }

  try {
    console.log('\n[2] Running "node --version"...');
    const result2 = await runCommand('node', ['--version']);
    console.log('    Exit code:', result2.exitCode);
    console.log('    Output:', result2.stdout.trim());
  } catch (err) {
    console.error('    Error:', err.message);
  }

  try {
    console.log('\n[3] Running "date"...');
    const result3 = await runCommand('date');
    console.log('    Exit code:', result3.exitCode);
    console.log('    Output:', result3.stdout.trim());
  } catch (err) {
    console.error('    Error:', err.message);
  }

  console.log('\n=== Done ===');
}

main().catch(console.error);
</file>

Now let me provide the PR description:
