#!/usr/bin/env python
"""CLI tool for finding suppliers using the supplier discovery service."""

import sys
import pprint
from backend.suppliers import find_suppliers, SupplierSearchError


def main():
    """Main CLI function."""
    if len(sys.argv) < 2:  # pragma: no cover
        print("Usage: python tools/find_suppliers.py \"search query\"")
        print("Example: python tools/find_suppliers.py \"eco tote bags\"")
        sys.exit(1)
    
    # Join all arguments to form the query
    query = " ".join(sys.argv[1:])
    
    try:
        print(f"🔍 Searching for suppliers: '{query}'")
        print("-" * 50)
        
        suppliers = find_suppliers(query)
        
        if not suppliers:
            print("No suppliers found.")
            return
        
        print(f"Found {len(suppliers)} supplier(s):")
        print()
        
        for i, supplier in enumerate(suppliers, 1):
            print(f"{i}. {supplier['name']}")
            print(f"   URL: {supplier['url']}")
            print(f"   Description: {supplier['description'][:100]}{'...' if len(supplier['description']) > 100 else ''}")
            print(f"   Source: {supplier['source']}")
            print()
            
    except SupplierSearchError as e:
        print(f"❌ Search failed: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n⏸️  Search cancelled")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 