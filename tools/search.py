#!/usr/bin/env python
"""CLI tool for searching similar documents in the vector store."""

import sys
import pprint
from backend.app.db import query_similar


def main():
    if len(sys.argv) < 2:  # pragma: no cover
        print("Usage: python tools/search.py \"text to search\"")
        print("Example: python tools/search.py \"product recommendations\"")
        sys.exit(1)
    
    query_text = sys.argv[1]
    try:
        results = query_similar(query_text)
        print(f"Search results for: '{query_text}'")
        print("-" * 50)
        for content, similarity in results:
            print(f"Similarity: {similarity:.3f}")
            print(f"Content: {content}")
            print("-" * 30)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 