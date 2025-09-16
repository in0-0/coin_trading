from strategies.base_strategy import Strategy
from strategies.atr_trailing_stop_strategy import ATRTrailingStopStrategy

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
        else:
            raise ValueError(f"Unknown strategy: {strategy_name}")
