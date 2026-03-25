#!/usr/bin/env python3
"""
Per-trade sizing calculator. Run before each entry.

Usage:
  python run_sizing.py --entry 47.50 --stop 46.80 --setup orb
  python run_sizing.py --entry 52.10 --stop 52.60 --setup vwap_reclaim --open_risk 250
  python run_sizing.py --entry 47.50 --stop 46.80 --setup orb --orb_high 47.40 --atr 1.12
"""
import argparse
from sizing.calculator import calculate_size, load_regime

VALID_SETUPS = ["orb", "ema_pullback", "vwap_reclaim"]


def main():
    parser = argparse.ArgumentParser(description="Intraday position sizing calculator")
    parser.add_argument("--entry",    type=float, required=True)
    parser.add_argument("--stop",     type=float, required=True)
    parser.add_argument("--setup",    type=str, required=True, choices=VALID_SETUPS)
    parser.add_argument("--open_risk",type=float, default=0.0)
    parser.add_argument("--orb_high", type=float, default=None)
    parser.add_argument("--atr",      type=float, default=None)
    args = parser.parse_args()

    regime = load_regime()
    if regime is None:
        print("Warning: No regime file found. Run python run_regime.py first.")
        print("  Defaulting to Choppy/Neutral (0.75% risk).")
        risk_pct = 0.0075
        regime = {"regime": "Choppy/Neutral", "risk_pct": risk_pct,
                  "dollar_risk": 150.0, "long_setups": ["orb", "ema_pullback", "vwap_reclaim"],
                  "short_setups": ["orb", "ema_pullback", "vwap_reclaim"]}
    else:
        risk_pct = regime["risk_pct"]

    is_long = args.stop < args.entry
    direction = "LONG" if is_long else "SHORT"
    allowed = regime["long_setups"] if is_long else regime["short_setups"]

    if args.setup not in allowed:
        print(f"\nBLOCKED: {args.setup.upper()} {direction} not allowed in "
              f"{regime['regime']} regime.")
        print(f"   Allowed {'long' if is_long else 'short'} setups: "
              f"{', '.join(allowed) if allowed else 'NONE'}\n")
        return

    result = calculate_size(
        entry=args.entry, stop=args.stop, setup=args.setup,
        risk_pct=risk_pct, atr=args.atr,
        open_risk=args.open_risk, orb_high=args.orb_high,
    )

    if result["blocks"]:
        print(f"\nBLOCKED:")
        for b in result["blocks"]:
            print(f"   {b}")
        print()
        return

    atr_stop_str = (f"  {result['atr_multiples_stop']}x ATR"
                    if result["atr_multiples_stop"] else "")
    atr_tgt_str = (f"  {result['atr_multiples_target']}x ATR from entry"
                   if result["atr_multiples_target"] else "")

    print(f"\n=== POSITION SIZING: {args.setup.upper()} {direction} ===\n")
    print(f"Regime:          {regime['regime']}  ->  Risk: "
          f"{risk_pct*100:.2f}% (${regime['dollar_risk']:.0f})")
    print(f"Trade:           {direction}\n")
    print(f"Entry:           ${args.entry:.2f}")
    print(f"Stop:            ${args.stop:.2f}")
    print(f"Stop Distance:   ${result['stop_distance']:.2f}{atr_stop_str}")
    print(f"\nShares:          {result['shares']}")
    print(f"Dollar Risk:     ${result['dollar_risk']:.2f}")
    print(f"Position Value:  ${result['position_value']:,.0f}")
    print(f"\nTarget 1 (1:1):  ${result['target_1']:.2f}  ->  "
          f"${result['dollar_risk']:.0f} profit  [exit {result['shares']//2} shares]")
    print(f"Target 2 (2:1):  ${result['target_2']:.2f}  ->  "
          f"${result['dollar_risk']*2:.0f} profit  [exit {result['shares'] - result['shares']//2} shares]")
    rr_ratio = abs(result["target_2"] - args.entry) / result["stop_distance"]
    print(f"\nR:R:             {rr_ratio:.2f}:1{atr_tgt_str}")

    for w in result["warnings"]:
        print(f"Warning: {w}")
    print()


if __name__ == "__main__":
    main()
