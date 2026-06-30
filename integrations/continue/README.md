# Continue.dev MisakaNet Search Context Provider

This integration lets Continue users search MisakaNet lessons from inside the AI
chat panel by typing `@misaka <query>`. It returns the lesson title, score, file
path, and a relevant snippet so the model can ground its answer in swarm
knowledge instead of asking you to leave the editor.

## What it provides

- **AI-tool integration:** runs inside Continue as a custom context provider.
- **Stable result shape:** each item includes `title`, `score`, `path`, and
  `snippet`.
- **Local/offline search:** uses the checked-out MisakaNet repository and the
  existing BM25/RRF search engine.

## Install

1. Clone MisakaNet and install its core dependency:

   ```bash
   git clone https://github.com/Ikalus1988/MisakaNet.git ~/MisakaNet
   cd ~/MisakaNet
   python3 -m pip install misakanet-core
   ```

2. Copy [`config.ts`](./config.ts) into your Continue configuration, or merge the
   `contextProviders` entry into your existing `~/.continue/config.ts`.

3. If your checkout is somewhere else, update `MISAKANET_REPO` in `config.ts`.

4. Restart Continue.

## Usage

In Continue chat, type:

```text
@misaka database locked sqlite
```

Continue will inject results like:

```text
MisakaNet search results for "database locked sqlite":

1. SQLite database locked on WSL/NTFS
   Score: 0.92
   Path: lessons/contrib/sqlite-database-locked-wsl-ntfs.md
   Snippet: ... move the sqlite database to the ext4 filesystem ...
```

You can then ask the assistant to apply the relevant fix in your project.

## Standalone JSON helper

The provider shells out to [`scripts/misaka_search_json.py`](../../scripts/misaka_search_json.py),
which is also useful for other AI tools:

```bash
cd ~/MisakaNet
python3 scripts/misaka_search_json.py "database locked" --top 3
```

The command prints JSON containing lesson titles, normalized scores, paths, and
snippets.
