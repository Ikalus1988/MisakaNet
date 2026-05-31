import sys
from pathlib import Path

# Try to import langchain BaseTool, fallback to a standalone class if not available
try:
    from langchain_core.tools import BaseTool
    HAS_LANGCHAIN = True
except ImportError:
    try:
        from langchain.tools import BaseTool
        HAS_LANGCHAIN = True
    except ImportError:
        BaseTool = object
        HAS_LANGCHAIN = False

class MisakaNetSearchTool(BaseTool):
    name: str = "misakanet_search"
    description: str = "Search the MisakaNet distributed knowledge base for solved developer bugs and experience."

    def __init__(self, **kwargs):
        if HAS_LANGCHAIN:
            super().__init__(**kwargs)
        else:
            # Standalone mock implementation fields
            pass

    def _run(self, query: str) -> str:
        # Import core engine elements
        from misakanet.search.engine import _load_docs, _rank_docs, LESSONS, REFERENCES
        
        lessons_docs = _load_docs(LESSONS, is_lesson=True)
        ref_docs = _load_docs(REFERENCES, is_lesson=False)
        all_docs = lessons_docs + ref_docs
        
        # Rank docs using BM25
        ranked = _rank_docs(query, all_docs)
        if not ranked:
            return f"No results found in MisakaNet for '{query}'"
            
        results = []
        for score, doc in ranked[:3]:
            # Clean preview
            preview = doc.content.replace('\r\n', '\n').split('\n')
            preview_lines = [l for l in preview if l.strip() and not l.startswith('---')][:8]
            content_preview = '\n'.join(preview_lines)
            results.append(f"📄 File: lessons/{doc.filename}\n📌 Title: {doc.title}\n🔍 Domain: {doc.domain}\n📝 Preview:\n{content_preview}\n")
            
        return "\n" + "\n----------------------------------------\n".join(results)

    def run(self, query: str) -> str:
        return self._run(query)

    async def _arun(self, query: str) -> str:
        return self._run(query)
