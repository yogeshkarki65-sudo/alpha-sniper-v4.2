#!/usr/bin/env python3
"""
Alpha Sniper Intelligent Optimizer
Analyzes trade performance and suggests optimal env settings
"""

import json
import re
from collections import defaultdict
from datetime import datetime, timedelta
import subprocess

def parse_trades_from_logs(days=7):
    """Extract all trades from journalctl logs"""
    cmd = f'sudo journalctl -u alpha-sniper-live.service --since "{days} days ago" --no-pager'
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    
    trades = []
    for line in result.stdout.split('\n'):
        if 'Position closed' in line:
            # Parse: Symbol/USDT side | PnL: $X (X%) | R: XR | Hold: Xh | Reason: X
            match = re.search(r'(\w+)/USDT\s+(\w+)\s+\|\s+PnL:\s+\$([+-]?\d+\.\d+)\s+\(([+-]?\d+\.\d+)%\)\s+\|\s+R:\s+([+-]?\d+\.\d+)R\s+\|\s+Hold:\s+(\d+\.\d+)h\s+\|\s+Reason:\s+(.+)', line)
            if match:
                symbol, side, pnl_usd, pnl_pct, r_multiple, hold_hours, reason = match.groups()
                trades.append({
                    'symbol': symbol,
                    'side': side,
                    'pnl_usd': float(pnl_usd),
                    'pnl_pct': float(pnl_pct),
                    'r_multiple': float(r_multiple),
                    'hold_hours': float(hold_hours),
                    'reason': reason.strip()
                })
    
    return trades

def analyze_performance(trades):
    """Analyze trade performance and identify patterns"""
    if not trades:
        return None
    
    total_trades = len(trades)
    winners = [t for t in trades if t['pnl_usd'] > 0]
    losers = [t for t in trades if t['pnl_usd'] < 0]
    
    win_rate = len(winners) / total_trades * 100 if total_trades > 0 else 0
    
    avg_win = sum(t['pnl_pct'] for t in winners) / len(winners) if winners else 0
    avg_loss = sum(t['pnl_pct'] for t in losers) / len(losers) if losers else 0
    
    avg_win_hold = sum(t['hold_hours'] for t in winners) / len(winners) if winners else 0
    avg_loss_hold = sum(t['hold_hours'] for t in losers) / len(losers) if losers else 0
    
    # Exit reason analysis
    exit_reasons = defaultdict(lambda: {'count': 0, 'profitable': 0})
    for t in trades:
        exit_reasons[t['reason']]['count'] += 1
        if t['pnl_usd'] > 0:
            exit_reasons[t['reason']]['profitable'] += 1
    
    # Hold time analysis
    max_hold_winners = max([t['hold_hours'] for t in winners]) if winners else 0
    max_hold_losers = max([t['hold_hours'] for t in losers]) if losers else 0
    
    return {
        'total_trades': total_trades,
        'win_rate': win_rate,
        'winners': len(winners),
        'losers': len(losers),
        'avg_win_pct': avg_win,
        'avg_loss_pct': avg_loss,
        'avg_win_hold': avg_win_hold,
        'avg_loss_hold': avg_loss_hold,
        'exit_reasons': dict(exit_reasons),
        'max_hold_winners': max_hold_winners,
        'max_hold_losers': max_hold_losers,
        'total_pnl_usd': sum(t['pnl_usd'] for t in trades),
        'total_pnl_pct': sum(t['pnl_pct'] for t in trades),
    }

def generate_optimizations(analysis):
    """Generate intelligent optimization recommendations"""
    if not analysis:
        return []
    
    recommendations = []
    
    # 1. Analyze hold time
    if analysis['exit_reasons'].get('Max hold time (1.5h)', {}).get('count', 0) > analysis['total_trades'] * 0.5:
        recommendations.append({
            'parameter': 'MAX_HOLD_HOURS_PUMP',
            'current': 1.5,
            'recommended': max(24, analysis['max_hold_winners']),
            'reason': f"{analysis['exit_reasons']['Max hold time (1.5h)']['count']} trades hit 1.5h limit before reaching targets",
            'priority': 'CRITICAL'
        })
    
    # 2. Analyze win rate
    if analysis['win_rate'] < 40:
        # Low win rate - might need tighter entries or better signal threshold
        recommendations.append({
            'parameter': 'MIN_SCORE_PUMP',
            'current': 0.7,
            'recommended': 0.75,
            'reason': f"Win rate is {analysis['win_rate']:.1f}% - increase signal quality threshold",
            'priority': 'HIGH'
        })
    
    # 3. Analyze average loss
    if abs(analysis['avg_loss_pct']) > 3:
        # Losses too large - tighter stops needed
        recommendations.append({
            'parameter': 'PUMP_MAX_LOSS_PCT',
            'current': 0.02,
            'recommended': 0.015,
            'reason': f"Average loss is {analysis['avg_loss_pct']:.2f}% - tighten max loss",
            'priority': 'HIGH'
        })
    
    # 4. Position sizing based on win rate
    if analysis['win_rate'] > 60 and analysis['avg_win_pct'] > 3:
        # High win rate - can increase position size
        recommendations.append({
            'parameter': 'POSITION_SIZE_PCT_SIDEWAYS',
            'current': 0.10,
            'recommended': 0.12,
            'reason': f"Win rate {analysis['win_rate']:.1f}% with avg win {analysis['avg_win_pct']:.2f}% - increase position size",
            'priority': 'MEDIUM'
        })
    elif analysis['win_rate'] < 40:
        # Low win rate - reduce position size
        recommendations.append({
            'parameter': 'POSITION_SIZE_PCT_SIDEWAYS',
            'current': 0.10,
            'recommended': 0.08,
            'reason': f"Win rate {analysis['win_rate']:.1f}% - reduce position size for safety",
            'priority': 'HIGH'
        })
    
    return recommendations

def generate_optimized_env(recommendations):
    """Generate optimized env file content"""
    changes = []
    for rec in recommendations:
        changes.append(f"# {rec['reason']}")
        changes.append(f"# Priority: {rec['priority']}")
        changes.append(f"{rec['parameter']}={rec['recommended']}")
        changes.append("")
    
    return "\n".join(changes)

def main():
    print("╔════════════════════════════════════════════════════════════════╗")
    print("║     ALPHA SNIPER INTELLIGENT OPTIMIZER                        ║")
    print("╚════════════════════════════════════════════════════════════════╝")
    print()
    
    print("📊 Analyzing trades from last 7 days...")
    trades = parse_trades_from_logs(7)
    
    if not trades:
        print("❌ No trades found in logs")
        return
    
    print(f"✅ Found {len(trades)} trades")
    print()
    
    print("🤖 Performing intelligent analysis...")
    analysis = analyze_performance(trades)
    
    print("=" * 70)
    print("PERFORMANCE ANALYSIS")
    print("=" * 70)
    print(f"Total Trades:      {analysis['total_trades']}")
    print(f"Win Rate:          {analysis['win_rate']:.1f}% ({analysis['winners']}W / {analysis['losers']}L)")
    print(f"Avg Win:           {analysis['avg_win_pct']:.2f}%")
    print(f"Avg Loss:          {analysis['avg_loss_pct']:.2f}%")
    print(f"Avg Win Hold:      {analysis['avg_win_hold']:.1f}h")
    print(f"Avg Loss Hold:     {analysis['avg_loss_hold']:.1f}h")
    print(f"Total PnL:         ${analysis['total_pnl_usd']:.2f} ({analysis['total_pnl_pct']:.2f}%)")
    print()
    
    print("EXIT REASONS:")
    for reason, stats in sorted(analysis['exit_reasons'].items(), key=lambda x: x[1]['count'], reverse=True):
        profit_rate = stats['profitable'] / stats['count'] * 100 if stats['count'] > 0 else 0
        print(f"  • {reason}: {stats['count']} ({profit_rate:.0f}% profitable)")
    print()
    
    recommendations = generate_optimizations(analysis)
    
    if not recommendations:
        print("✅ Current settings appear optimal - no changes recommended")
        return
    
    print("=" * 70)
    print("INTELLIGENT RECOMMENDATIONS")
    print("=" * 70)
    
    for i, rec in enumerate(recommendations, 1):
        priority_emoji = "🔴" if rec['priority'] == 'CRITICAL' else "🟠" if rec['priority'] == 'HIGH' else "🟡"
        print(f"{i}. {priority_emoji} {rec['parameter']}")
        print(f"   Current:     {rec['current']}")
        print(f"   Recommended: {rec['recommended']}")
        print(f"   Reason:      {rec['reason']}")
        print()
    
    # Save recommendations
    with open('/tmp/optimizer_recommendations.txt', 'w') as f:
        f.write(generate_optimized_env(recommendations))
    
    print("=" * 70)
    print("📝 Recommendations saved to: /tmp/optimizer_recommendations.txt")
    print()
    print("To apply these changes:")
    print("1. Review recommendations above")
    print("2. Edit: sudo nano /etc/alpha-sniper/alpha-sniper-live.env")
    print("3. Apply recommended changes")
    print("4. Restart: sudo systemctl restart alpha-sniper-live.service")
    print("=" * 70)

if __name__ == '__main__':
    main()
