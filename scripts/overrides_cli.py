#!/usr/bin/env python3
"""
Runtime Overrides CLI for Alpha Sniper v4.2

Manage runtime setting overrides without restart.

Usage:
    python scripts/overrides_cli.py show
    python scripts/overrides_cli.py get --key EARLY_RET_5M_MIN
    python scripts/overrides_cli.py set --key MIN_SCORE --value 10
    python scripts/overrides_cli.py reset
    python scripts/overrides_cli.py reset --key MIN_SCORE
"""

import argparse
import json
import sys
from pathlib import Path

# Add alpha-sniper to path
sys.path.insert(0, str(Path(__file__).parent.parent / "alpha-sniper"))

from config.settings import get_settings
from config.runtime_settings import RuntimeSettings


def main():
    ap = argparse.ArgumentParser(description="Manage runtime setting overrides")
    ap.add_argument(
        "cmd",
        choices=["show", "get", "set", "reset", "notional"],
        help="Command to execute"
    )
    ap.add_argument("--key", help="Setting key")
    ap.add_argument("--value", help="Setting value")
    ap.add_argument(
        "--path",
        default="./data/overrides.json",
        help="Path to overrides file (default: ./data/overrides.json)"
    )

    args = ap.parse_args()

    # Load settings and runtime overlay
    settings = get_settings()
    overlay = RuntimeSettings(settings, args.path)
    overlay.load()

    # Execute command
    if args.cmd == "show":
        # Show all overrides
        overrides = overlay.dump()
        print(json.dumps(overrides, indent=2, sort_keys=True))
        return

    if args.cmd == "get":
        # Get specific override
        if not args.key:
            sys.exit("ERROR: --key required for 'get' command")

        value = overlay.get(args.key)
        print(json.dumps({args.key: value}, indent=2))
        return

    if args.cmd == "set":
        # Set override
        if not args.key or args.value is None:
            sys.exit("ERROR: --key and --value required for 'set' command")

        # Naive type inference
        v = args.value

        # Try boolean
        if v.lower() in ("true", "false"):
            v = (v.lower() == "true")
        else:
            # Try numeric
            try:
                if "." in v:
                    v = float(v)
                else:
                    v = int(v)
            except ValueError:
                # Keep as string
                pass

        try:
            overlay.set(args.key, v)
            print(f"OK: {args.key} = {v}")

            # Auto-sync vspike keys for consistency
            if args.key in ("EARLY_VOL_SPIKE_MIN", "EAGER_VSPIKE_MIN"):
                other = "EAGER_VSPIKE_MIN" if args.key == "EARLY_VOL_SPIKE_MIN" else "EARLY_VOL_SPIKE_MIN"
                try:
                    overlay.set(other, v)
                    print(f"SYNC: Set both {args.key} and {other} to {v} for consistency.")
                except AttributeError:
                    # Other key might not exist, that's ok
                    pass

        except AttributeError as e:
            sys.exit(f"ERROR: {e}")
        return

    if args.cmd == "reset":
        # Reset overrides
        if args.key:
            # Reset specific key
            changed = overlay.reset(args.key)
            print(f"OK: Reset {changed} override(s)")
        else:
            # Reset all
            overlay.reset()
            print("OK: Reset all overrides")
        return

    if args.cmd == "notional":
        # Convenience command: set notional sizing mode
        if not args.value:
            sys.exit("ERROR: --value required for 'notional' command (specify USD amount, e.g., --value 5.0)")

        try:
            notional_usd = float(args.value)
            if notional_usd < 1.0 or notional_usd > 1000.0:
                sys.exit(f"ERROR: Notional USD must be between 1.0 and 1000.0, got {notional_usd}")

            # Set both SIZING_MODE and SIZING_NOTIONAL_USD
            overlay.set("SIZING_MODE", "notional")
            overlay.set("SIZING_NOTIONAL_USD", notional_usd)

            print(f"OK: Enabled notional sizing mode")
            print(f"  SIZING_MODE = 'notional'")
            print(f"  SIZING_NOTIONAL_USD = ${notional_usd:.2f}")
            print(f"\nBot will now use fixed ${notional_usd:.2f} per trade (subject to exchange minimums and balance).")

        except ValueError:
            sys.exit(f"ERROR: Invalid value '{args.value}', must be a number")
        except AttributeError as e:
            sys.exit(f"ERROR: {e}")
        return


if __name__ == "__main__":
    main()
