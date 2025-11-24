class BearMicroLongEngine:
    def __init__(self, config):
        self.config = config

    def generate_signals(self, market_data):
        # Example logic to generate bear micro-long signals
        signals = []
        for data in market_data:
            if data['risk_size'] <= self.config.RISK_PER_TRADE_DEEP_BEAR:
                signals.append({
                    'symbol': data['symbol'],
                    'direction': 'LONG',
                    'engine': 'bear_micro_long'
                })
        return signals
