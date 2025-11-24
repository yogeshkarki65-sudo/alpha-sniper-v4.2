class PumpEngine:
    def __init__(self, config):
        self.config = config

    def generate_signals(self, market_data):
        # Example logic to generate pump signals
        signals = []
        for data in market_data:
            if (data['age'] >= 3 and data['age'] <= 48 and
                data['volume'] >= 50000 and
                data['rvol'] >= 2.0 and
                data['momentum'] >= 25 and
                data['spread'] <= 1.5):
                signals.append({
                    'symbol': data['symbol'],
                    'direction': 'LONG',
                    'engine': 'pump_long'
                })
        return signals
