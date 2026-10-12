import json, os, tempfile, time
from pathlib import Path
from md_cg.mdcg import MdCG


def test_rebuild_makes_hand_edits_visible():
    """Core regression: hand-edit a .md file, rebuild, verify reader sees it."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        layer = root / "test_layer"
        layer.mkdir()

        node = layer / "node1.md"
        node.write_text("---\ncondition: DEFER\n---\nold body", encoding="utf-8")

        cg = MdCG(str(root))

        # Build initial index
        cg.rebuild_index()

        # Verify initial state via the READ PATH (get_node, NOT file I/O)
        info = cg.get_node("test_layer/node1.md")
        assert info is not None
        assert info["frontmatter"]["condition"] == "DEFER"
        assert info["body"] == "old body"

        # --- Hand-edit on disk (simulates the bug report scenario) ---
        node.write_text("---\ncondition: ACCEPT\n---\nnew body", encoding="utf-8")

        # Without rebuild the reader would still see stale data
        stale = cg.get_node("test_layer/node1.md")
        assert stale["frontmatter"]["condition"] == "DEFER"  # still old

        # Rebuild through the library API
        count = cg.rebuild_index()
        assert count == 1

        # Now the READ PATH reflects the edit
        fresh = cg.get_node("test_layer/node1.md")
        assert fresh is not None
        assert fresh["frontmatter"]["condition"] == "ACCEPT"
        assert fresh["body"] == "new body"

        # Verify mtime invariant
        idx_mtime = root.joinpath("_index.json").stat().st_mtime_ns
        node_mtime = node.stat().st_mtime_ns
        assert idx_mtime >= node_mtime

        cg.close()


def test_deleted_node_disappears_after_rebuild():
    """A deleted/moved node must stop appearing post-rebuild."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        layer = root / "l"
        layer.mkdir()

        (layer / "alive.md").write_text("---\n---\nalive", encoding="utf-8")
        (layer / "dead.md").write_text("---\n---\ndead", encoding="utf-8")

        cg = MdCG(str(root))
        cg.rebuild_index()

        assert cg.get_node("l/dead.md") is not None

        # Delete on disk
        (layer / "dead.md").unlink()

        cg.rebuild_index()

        # Negative assertion: deleted node must no longer appear
        assert cg.get_node("l/dead.md") is None
        alive = cg.get_node("l/alive.md")
        assert alive is not None
        cg.close()


def test_list_nodes_filters_by_layer():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "a.md").write_text("---\n---\na", encoding="utf-8")
        sub = root / "sub"
        sub.mkdir()
        (sub / "b.md").write_text("---\n---\nb", encoding="utf-8")

        cg = MdCG(str(root))
        cg.rebuild_index()

        all_nodes = cg.list_nodes()
        assert len(all_nodes) == 2

        sub_nodes = cg.list_nodes("sub")
        assert len(sub_nodes) == 1
        assert sub_nodes[0]["path"] == "sub/b.md"
        cg.close()


def test_empty_root_rebuild():
    with tempfile.TemporaryDirectory() as tmp:
        cg = MdCG(tmp)
        count = cg.rebuild_index()
        assert count == 0
        assert cg.get_node("nonexistent") is None
        cg.close()


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
