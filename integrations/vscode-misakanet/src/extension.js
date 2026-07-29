// MisakaNet Search — VS Code Extension
// Searches the MisakaNet knowledge base and shows results in a quick pick.

const vscode = require("vscode");
const { execSync } = require("child_process");
const path = require("path");
const fs = require("fs");

function findRepoPath(configPath) {
  if (configPath && fs.existsSync(configPath)) return configPath;
  // Common locations
  const candidates = [
    path.join(require("os").homedir(), "MisakaNet"),
    path.join(require("os").homedir(), "Desktop", "MisakaNet"),
    path.join(require("os").homedir(), "projects", "MisakaNet"),
  ];
  for (const c of candidates) {
    if (fs.existsSync(path.join(c, "search_knowledge.py"))) return c;
  }
  return null;
}

function searchMisakaNet(repoPath, query, topK) {
  const script = path.join(repoPath, "search_knowledge.py");
  const cmd = `python3 "${script}" "${query.replace(/"/g, '\\"')}" --json --top ${topK}`;
  try {
    const output = execSync(cmd, {
      cwd: repoPath,
      encoding: "utf-8",
      timeout: 15000,
      shell: true,
    });
    return JSON.parse(output);
  } catch (e) {
    // Fallback: try python instead of python3
    try {
      const cmd2 = `python "${script}" "${query.replace(/"/g, '\\"')}" --json --top ${topK}`;
      const output = execSync(cmd2, { cwd: repoPath, encoding: "utf-8", timeout: 15000, shell: true });
      return JSON.parse(output);
    } catch (e2) {
      return null;
    }
  }
}

function activate(context) {
  const disposable = vscode.commands.registerCommand("misakanet.search", async () => {
    const config = vscode.workspace.getConfiguration("misakanet");
    const repoPath = findRepoPath(config.get("repoPath", ""));

    if (!repoPath) {
      vscode.window.showErrorMessage(
        "MisakaNet repo not found. Set misakanet.repoPath in settings."
      );
      return;
    }

    const query = await vscode.window.showInputBox({
      prompt: "Search MisakaNet knowledge base",
      placeHolder: "e.g., pip timeout, docker M1, git rebase",
    });

    if (!query) return;

    const topK = config.get("topResults", 5);

    vscode.window.withProgress(
      { location: vscode.ProgressLocation.Notification, title: "Searching MisakaNet..." },
      () => {
        return new Promise((resolve) => {
          setTimeout(() => {
            const results = searchMisakaNet(repoPath, query, topK);
            resolve(results);
          }, 100);
        });
      }
    ).then((results) => {
      if (!results || results.length === 0) {
        vscode.window.showInformationMessage(`No MisakaNet results for "${query}"`);
        return;
      }

      const items = results.map((r) => ({
        label: `$(book) ${r.title}`,
        description: `[${r.domain || "?"}] score: ${r.score}`,
        detail: r.preview || r.match_reason || "",
        filePath: r.path,
      }));

      vscode.window.showQuickPick(items, {
        placeHolder: `${results.length} result(s) for "${query}"`,
      }).then((selected) => {
        if (selected && selected.filePath) {
          const fullPath = path.join(repoPath, selected.filePath);
          if (fs.existsSync(fullPath)) {
            vscode.window.showTextDocument(vscode.Uri.file(fullPath));
          }
        }
      });
    });
  });

  context.subscriptions.push(disposable);
}

function deactivate() {}

module.exports = { activate, deactivate };
