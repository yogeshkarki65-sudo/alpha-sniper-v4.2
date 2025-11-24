from signals.long_engine import LongEngine
from signals.short_engine import ShortEngine
from signals.pump_engine import PumpEngine
from signals.bear_micro_long import BearMicroLongEngine

class Scanner:
    def __init__(self, config, exchange, risk_engine):
        self.config = config
        self.exchange = exchange
        self.risk_engine = risk_engine
        self.long_engine = LongEngine(config)
        self.short_engine = ShortEngine(config)
        self.pump_engine = PumpEngine(config)
        self.bear_micro_long_engine = BearMicroLongEngine(config)

    def run(self):
        market_data = self.fetch_market_data()
        long_signals = self.long_engine.generate_signals(market_data)
        short_signals = self.short_engine.generate_signals(market_data)
        pump_signals = self.pump_engine.generate_signals(market_data)
        bear_micro_long_signals = self.bear_micro_long_engine.generate_signals(market_data)

        # Combine and process signals
        all_signals = long_signals + short_signals + pump_signals + bear_micro_long_signals
        self.risk_engine.evaluate_signals(all_signals)

    def fetch_market_data(self):
        # Logic to fetch market data
        return []
