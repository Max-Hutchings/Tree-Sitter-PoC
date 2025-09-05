import json

from call_graph.src.call_graph.indexer import JavaIndexer


# --- Pretty printing & JSON export ------------------------------------------

def print_summary(indexer: JavaIndexer):
    """
    Human-friendly printout of what we found.
    """
    print("\n=== PACKAGES ===")
    for p in sorted(indexer.packages):
        print(" -", p)

    print("\n=== CLASSES & METHODS ===")
    for fqcn, ci in sorted(indexer.classes.items(), key=lambda kv: kv[0]):
        print(f"\n[{fqcn}]  (line {ci.line + 1}, col {ci.col + 1})")
        for mname, overloads in ci.methods.items():
            for mi in overloads:
                sig = f"{mi.name}({', '.join(mi.params)})"
                rtype = f" -> {mi.return_type}" if mi.return_type else ""
                print(f"  - {sig}{rtype}  @ {mi.line + 1}:{mi.col + 1}")
                for c in mi.calls:
                    recv = f"{c.receiver}." if c.receiver else ""
                    print(f"      calls: {recv}{c.name}  @ {c.line + 1}:{c.col + 1}")


def to_json(indexer: JavaIndexer) -> str:
    """
    Serializes the index to JSON. This is what you'd store in a DB.
    """
    out = {
        "packages": sorted(indexer.packages),
        "classes": []
    }
    for fqcn, ci in indexer.classes.items():
        out["classes"].append({
            "fqcn": fqcn,
            "simpleName": ci.simple_name,
            "line": ci.line,
            "col": ci.col,
            "methods": [
                {
                    "name": mi.name,
                    "params": mi.params,
                    "returnType": mi.return_type,
                    "line": mi.line,
                    "col": mi.col,
                    "calls": [
                        {
                            "name": mc.name,
                            "receiver": mc.receiver,
                            "line": mc.line,
                            "col": mc.col
                        } for mc in mi.calls
                    ]
                }
                for mlist in ci.methods.values()
                for mi in mlist
            ]
        })
    return json.dumps(out, indent=2)
