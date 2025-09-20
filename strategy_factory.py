from strategies.atr_trailing_stop_strategy import ATRTrailingStopStrategy
from strategies.base_strategy import Strategy
from strategies.composite_signal_strategy import CompositeSignalStrategy


class StrategyFactory:
    @staticmethod
    def create_strategy(strategy_name: str, **kwargs) -> Strategy:
        if strategy_name == "atr_trailing_stop":
            # Explicitly map allowed kwargs for clarity
            return ATRTrailingStopStrategy(
                symbol=kwargs["symbol"],
                atr_multiplier=kwargs["atr_multiplier"],
                risk_per_trade=kwargs["risk_per_trade"],
            )
        elif strategy_name == "composite_signal":
            # Pass through config object
            return CompositeSignalStrategy(config=kwargs["config"]) 
        else:
            raise ValueError(f"Unknown strategy: {strategy_name}")
