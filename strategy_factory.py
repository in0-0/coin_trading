from strategies.base_strategy import Strategy
from strategies.atr_trailing_stop_strategy import ATRTrailingStopStrategy

class StrategyFactory:
    @staticmethod
    def create_strategy(strategy_name: str, **kwargs) -> Strategy:
        if strategy_name == "atr_trailing_stop":
            return ATRTrailingStopStrategy(**kwargs)
        else:
            raise ValueError(f"Unknown strategy: {strategy_name}")
