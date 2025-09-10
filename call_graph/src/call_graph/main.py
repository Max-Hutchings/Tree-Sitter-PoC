#!/usr/bin/env python3
"""
Tree-sitter Java Indexer (Python)
---------------------------------
Parses Java code to collect:
- package names
- classes and their fully qualified names (FQCN)
- methods in each class (with simple signature info)
- method calls found inside each method body

USAGE EXAMPLES
--------------
# 1) Run against an in-code sample (no files needed):
python ts_java_indexer.py

# 2) Run against a directory of .java files (recursive):
python ts_java_indexer.py /path/to/java/project

DEPENDENCIES
------------
Option A (recommended for quick start):
    pip install tree_sitter tree_sitter_languages

Option B (manual build):
    git clone https://github.com/tree-sitter/tree-sitter-java
    python -c "from tree_sitter import Language; Language.build_library('build/my-languages.so', ['tree-sitter-java'])"
    export TS_LANGUAGE_SO=build/my-languages.so
"""

import sys

from call_graph.src.call_graph.indexer import JavaIndexer
from call_graph.src.call_graph.inputs.directory_scanning import index_directory
from call_graph.src.call_graph.outputs.output import print_summary, to_json

# --- Demo main ---------------------------------------------------------------

SAMPLE_JAVA = r"""
package com.acme.demo;

import java.util.*;

public class UserService {
    private final UserRepository repo = new UserRepository();

    public UserService() {
        System.out.println("UserService constructed");
    }

    public User addUser(String name) {
        // Call into our repository and also use a static helper
        repo.save(name);
        String trimmed = StringUtils.trim(name);
        return new User(trimmed);
    }

    public void printAll() {
        List<String> all = repo.findAll();
        for (String n : all) {
            System.out.println(n);
        }
    }

    static class StringUtils {
        static String trim(String s) { return s.trim(); }
    }
}

class UserRepository {
    List<String> store = new ArrayList<>();
    public void save(String name) { store.add(name); }
    public List<String> findAll() { return store; }
}

class User {
    private final String name;
    public User(String name) { this.name = name; }
}
"""


def main():
    # Create indexer (builds/loads Tree-sitter Java once)
    indexer = JavaIndexer()

    # If a directory is given, index .java files in it; else use SAMPLE_JAVA
    if len(sys.argv) > 1:
        root = sys.argv[1]
        index_directory(indexer, root)
    else:
        indexer.index_source(SAMPLE_JAVA, "<sample>")

    # Print a concise human-readable summary
    print_summary(indexer)

    # Also print JSON (easy to persist)
    j = to_json(indexer)
    print("\n=== JSON ===")
    print(j)


    # Perform queries
    print("Imports:", indexer.query_imports(SAMPLE_JAVA))
    print("Has deleteUser method:", indexer.query_method(SAMPLE_JAVA, "deleteUser"))
    print("Has addUser method:", indexer.query_method(SAMPLE_JAVA, "addUser"))
    print("Methods creating ArrayList:", indexer.query_new_arraylist(SAMPLE_JAVA))
    print("Methods with .add() calls:", indexer.query_add_method_calls(SAMPLE_JAVA))


if __name__ == "__main__":
    main()
