from core.data_models import StrategyConfig
from improved_strategy_factory import StrategyFactory
from strategies.composite_signal_strategy import CompositeSignalStrategy


def test_composite_strategy_init_ignores_symbol_kwarg():
    cfg = StrategyConfig(strategy_name="composite_signal", symbol="BTCUSDT", timeframe="5m")
    fac = StrategyFactory()
    s = fac.create_strategy("composite_signal", symbol="BTCUSDT", config=cfg)
    assert isinstance(s, CompositeSignalStrategy)
