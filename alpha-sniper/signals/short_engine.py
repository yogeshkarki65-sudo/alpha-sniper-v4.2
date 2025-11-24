class ShortEngine:
    def __init__(self, config):
        self.config = config

    def generate_signals(self, market_data):
        # Example logic to generate short signals
        signals = []
        for data in market_data:
            if data['trend'] == 'bearish' and data['funding'] <= self.config.MAX_FUNDING_8H_SHORT:
                signals.append({
                    'symbol': data['symbol'],
                    'direction': 'SHORT',
                    'engine': 'standard_short'
                })
        return signals
