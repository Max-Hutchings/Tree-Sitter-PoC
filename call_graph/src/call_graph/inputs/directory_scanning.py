# --- Directory scanning convenience -----------------------------------------
import os

from call_graph.src.call_graph.indexer import JavaIndexer


def read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def index_directory(indexer: JavaIndexer, root_dir: str):
    """
    Recursively index all .java files in a directory. For large repos, you might
    want to parallelize this and persist incrementally.
    """
    for dirpath, _, filenames in os.walk(root_dir):
        for fn in filenames:
            if fn.endswith(".java"):
                full = os.path.join(dirpath, fn)
                try:
                    src = read_text(full)
                    indexer.index_source(src, full)
                except Exception as e:
                    print(f"[WARN] Failed to index {full}: {e}", file=sys.stderr)