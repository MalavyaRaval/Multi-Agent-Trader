from __future__ import annotations

import json

from config import DEFAULT_SYMBOL
from orchestrator import get_orchestrator


def main() -> None:
    symbol = input("Enter a symbol (default: AAPL): ").strip().upper() or DEFAULT_SYMBOL

    result = get_orchestrator().analyze_symbol(symbol)
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
