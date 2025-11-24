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
        # Logic to run the scanner and generate signals
        pass
