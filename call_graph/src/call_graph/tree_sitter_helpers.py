# --- Tree-sitter plumbing ----------------------------------------------------

def node_text(source_bytes: bytes, node) -> str:
    """
    Converts a node's [start_byte:end_byte] into the corresponding string.
    Tree-sitter nodes only store byte offsets, so we slice the original source.
    """
    return source_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="replace")


def node_point(node) -> tuple[int, int]:
    """
    Returns the (line, column) of a node's start in 0-based coordinates.
    Handy for displaying where a method/call was found.
    """
    return (node.start_point[0], node.start_point[1])
