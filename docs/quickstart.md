# Use MisakaNet in 5 Minutes

## Step 1: Clone & Search (30 seconds)

Command:

```bash
git clone https://github.com/Ikalus1988/MisakaNet.git
cd MisakaNet
pip install misakanet-core
python3 search_knowledge.py "your error message here"
```

Expected output: the CLI prints the top 5 matching lessons, each with a relevance score and file path.

Common failure: `python3: can't open file 'search_knowledge.py'`.

Fix: run `pwd` and make sure you are in the cloned `MisakaNet` directory before searching.

## Step 2: Contribute a Lesson (2 minutes)

Command:

```bash
python3 scripts/queue_lesson.py --title "Your Error" --domain "devops" --content "Root cause: ... Fix: ..."
```

Expected output: a GitHub Issue is created with your lesson draft, ready for review and improvement.

Common failure: the lesson is rejected because the content is too vague.

Fix: include the exact error message, root cause, copy-pasteable fix commands, and verification steps.

## Step 3: Integrate with Your Agent (2 minutes)

Command:

```python
from misakanet.tools.langchain_tool import MisakaNetSearchTool

tool = MisakaNetSearchTool()
results = tool._run("database locked")
print(results)
```

Expected output: your agent receives ranked MisakaNet lessons for the query and can reuse the known fixes before attempting new debugging.

Common failure: `ModuleNotFoundError: No module named 'misakanet'`.

Fix: install the local package from the repository root with `pip install -e .`, then rerun the agent integration snippet.
