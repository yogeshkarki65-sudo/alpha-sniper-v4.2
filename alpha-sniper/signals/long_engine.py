class LongEngine:
    def __init__(self, config):
        self.config = config

    def generate_signals(self, market_data):
        # Example logic to generate long signals
        signals = []
        for data in market_data:
            if data['rvol'] >= 1.15 and data['score'] >= self.config.MIN_SCORE:
                signals.append({
                    'symbol': data['symbol'],
                    'direction': 'LONG',
                    'score': data['score'],
                    'stop_loss': data['stop_loss'],
                    'take_profit': data['take_profit'],
                    'engine': 'standard_long'
                })
        return signals
