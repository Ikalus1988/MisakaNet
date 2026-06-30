import { execFileSync } from "child_process";
import os from "os";
import path from "path";
import type { ContinueConfig } from "@continuedev/config-yaml";

const MISAKANET_REPO = process.env.MISAKANET_REPO ?? path.join(os.homedir(), "MisakaNet");
const MISAKANET_SEARCH = path.join(MISAKANET_REPO, "scripts", "misaka_search_json.py");

type MisakaResult = {
  title: string;
  score: number;
  path: string;
  domain?: string;
  status?: string;
  snippet: string;
};

function formatMisakaResults(query: string, results: MisakaResult[]): string {
  if (!results.length) {
    return `No MisakaNet results found for "${query}".`;
  }

  const lines = [`MisakaNet search results for "${query}":`, ""];
  results.forEach((result, index) => {
    const score = Math.round(result.score * 100);
    const tags = [result.domain, result.status].filter(Boolean).join(" · ");
    lines.push(`${index + 1}. ${result.title}`);
    lines.push(`   Score: ${score}%${tags ? ` (${tags})` : ""}`);
    lines.push(`   Path: ${result.path}`);
    lines.push(`   Snippet: ${result.snippet}`);
    lines.push("");
  });
  return lines.join("\n").trim();
}

const config: ContinueConfig = {
  contextProviders: [
    {
      title: "misaka",
      displayTitle: "MisakaNet Search",
      description: "Search local MisakaNet lessons and inject title, score, path, and snippet.",
      type: "query",
      getContextItems: async (query: string) => {
        const raw = execFileSync(
          "python3",
          [MISAKANET_SEARCH, query, "--top", "5"],
          {
            cwd: MISAKANET_REPO,
            encoding: "utf8",
            maxBuffer: 1024 * 1024,
          },
        );
        const payload = JSON.parse(raw) as { results: MisakaResult[] };
        return [
          {
            name: `MisakaNet: ${query}`,
            description: "Top MisakaNet lesson matches",
            content: formatMisakaResults(query, payload.results),
          },
        ];
      },
    },
  ],
};

export default config;
