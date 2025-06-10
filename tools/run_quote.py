#!/usr/bin/env python
"""CLI tool for running automated quote requests."""

import sys
import argparse
from backend.agents.quote_agent import run_quote


def main():
    """Main CLI function for running quote requests."""
    parser = argparse.ArgumentParser(
        description="Send RFQs to suppliers and collect quotes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tools/run_quote.py "eco tote bags"
  python tools/run_quote.py "custom printed mugs" --suppliers 5 --wait 120
        """
    )
    
    parser.add_argument(
        "specification",
        help="Product specification to request quotes for"
    )
    
    parser.add_argument(
        "-k", "--suppliers",
        type=int,
        default=3,
        help="Maximum number of suppliers to contact (default: 3)"
    )
    
    parser.add_argument(
        "-w", "--wait",
        type=int,
        default=30,
        help="Time to wait for responses in seconds (default: 30)"
    )
    
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    
    # Handle case where specification is passed as multiple arguments
    if len(sys.argv) > 1 and not sys.argv[1].startswith('-'):
        # If first argument doesn't start with -, treat remaining args as specification
        args = parser.parse_args()
        spec = args.specification
    else:
        # Show help if no specification provided
        parser.print_help()
        sys.exit(1)
    
    if args.verbose:
        import logging
        logging.basicConfig(level=logging.INFO)
    
    try:
        print(f"🚀 Starting quote process for: '{spec}'")
        print(f"📊 Will contact up to {args.suppliers} suppliers")
        print(f"⏱️  Will wait {args.wait} seconds for responses")
        print()
        
        run_quote(spec, k=args.suppliers, poll_duration=args.wait)
        
    except KeyboardInterrupt:
        print("\n⏸️  Quote process cancelled by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Quote process failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 