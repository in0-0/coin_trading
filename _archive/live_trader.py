# live_trader.py
import time
import datetime
import numpy as np
import pandas as pd
from binance.client import Client
from binance.exceptions import BinanceAPIException

import config
from state_manager import StateManager
from binance_data import BinanceData
from strategy import StrategyFactory
from position_sizer import PositionSizerFactory


class LiveTrader:
    """
    실제 바이낸스 계좌와 상호작용하여 주문을 실행하고 포지션을 관리합니다.
    """

    def __init__(self, api_key, secret_key, symbol):
        self.client = Client(api_key, secret_key)
        self.symbol = symbol

    def get_account_balance(self, asset="USDT"):
        """지정된 자산(USDT 등)의 잔고를 조회합니다."""
        try:
            balance = self.client.get_asset_balance(asset=asset)
            return float(balance["free"])
        except BinanceAPIException as e:
            print(f"Error fetching balance for {asset}: {e}")
            return 0.0

    def get_current_position(self):
        """현재 보유 중인 코인의 수량을 조회합니다."""
        try:
            account_info = self.client.get_account()
            for balance in account_info["balances"]:
                if balance["asset"] == self.symbol.replace(
                    "USDT", ""
                ):  # 'BTCUSDT' -> 'BTC'
                    return float(balance["free"])
            return 0.0
        except BinanceAPIException as e:
            print(f"Error fetching current position for {self.symbol}: {e}")
            return 0.0

    def _get_formatted_quantity(self, quantity: float) -> str:
        """주문 수량을 바이낸스가 요구하는 형식(정밀도)에 맞게 변환합니다."""
        try:
            info = self.client.get_symbol_info(self.symbol)
            step_size = 0.0
            for f in info["filters"]:
                if f["filterType"] == "LOT_SIZE":
                    step_size = float(f["stepSize"])
                    break

            if step_size > 0:
                precision = int(round(-np.log10(step_size)))
                return f"{quantity:.{precision}f}"
            return str(quantity)
        except (BinanceAPIException, KeyError) as e:
            print(
                f"Could not get symbol info for {self.symbol}: {e}. Using default quantity formatting."
            )
            return f"{quantity:.8f}"  # 기본값으로 8자리 소수점 사용

    def create_order(self, side, quantity, order_type="MARKET"):
        """
        지정된 수량과 유형으로 실제 매수/매도 주문을 생성합니다.
        side: 'BUY' 또는 'SELL'
        """
        try:
            formatted_quantity = self._get_formatted_quantity(quantity)
            print(f"Creating order: {side} {formatted_quantity} {self.symbol}")
            order = self.client.create_order(
                symbol=self.symbol,
                side=side,
                type=order_type,
                quantity=formatted_quantity,
            )
            print("Order created successfully:")
            print(order)
            return order
        except BinanceAPIException as e:
            print(f"Error creating order: {e}")
            return None

    def check_order_status(self, order_id):
        """주문의 현재 상태를 확인합니다."""
        try:
            return self.client.get_order(symbol=self.symbol, orderId=order_id)
        except BinanceAPIException as e:
            print(f"Error checking order status for orderId {order_id}: {e}")
            return None


class TradingBot:
    """실시간 거래 로직을 총괄하는 트레이딩 봇 클래스"""

    def __init__(self):
        self._load_config()
        self._initialize_components()

    def _load_config(self):
        """config 파일에서 설정을 로드합니다."""
        self.symbol = config.LIVE_TRADE_SETTINGS["symbol"]
        self.interval = config.LIVE_TRADE_SETTINGS["interval"]
        self.strategy_name = config.LIVE_TRADE_SETTINGS["strategy_name"]
        self.state_file = config.LIVE_TRADE_SETTINGS["state_file"]

        strategy_config = config.STRATEGY_CONFIG.get(self.strategy_name)
        if not strategy_config:
            raise ValueError(f"Strategy '{self.strategy_name}' not found.")

        self.strategy_params = strategy_config.get("params", {})
        self.position_sizer_config = strategy_config.get(
            "position_sizer", {"name": "all_in"}
        )
        self.exit_params = strategy_config.get("exit_params", {})

    def _initialize_components(self):
        """거래에 필요한 컴포넌트들을 초기화합니다."""
        self.state_manager = StateManager(self.state_file)
        self.trader = LiveTrader(config.API_KEY, config.SECRET_KEY, self.symbol)
        self.data_handler = BinanceData(config.API_KEY, config.SECRET_KEY)
        self.strategy = StrategyFactory().get_strategy(
            self.strategy_name, **self.strategy_params
        )
        self.sizer = PositionSizerFactory().get_sizer(
            self.position_sizer_config.get("name", "all_in"),
            **self.position_sizer_config.get("params", {}),
        )
        self.interval_seconds = self._get_interval_in_seconds()
        if self.interval_seconds == 0:
            raise ValueError(f"Invalid interval format '{self.interval}'.")

    def _get_interval_in_seconds(self) -> int:
        """인터벌 문자열을 초로 변환합니다."""
        unit = self.interval[-1]
        value = int(self.interval[:-1])
        if unit == "m":
            return value * 60
        elif unit == "h":
            return value * 3600
        elif unit == "d":
            return value * 86400
        return 0

    def run(self):
        """트레이딩 봇의 메인 루프를 실행합니다."""
        print("--- Initializing Live Trader ---")
        print(
            f"Symbol: {self.symbol}, Interval: {self.interval}, Strategy: {self.strategy_name}"
        )

        while True:
            try:
                loop_start_time = time.time()
                self._execute_trading_cycle()
                elapsed_time = time.time() - loop_start_time
                wait_time = max(0, self.interval_seconds - elapsed_time)
                print(
                    f"Loop finished in {elapsed_time:.2f}s. Waiting for {wait_time:.2f}s."
                )
                time.sleep(wait_time)
            except KeyboardInterrupt:
                print("--- Stopping Live Trader ---")
                break
            except Exception as e:
                print(f"An error occurred: {e}")
                time.sleep(60)

    def _execute_trading_cycle(self):
        """한 번의 거래 사이클을 실행합니다."""
        # 1. 상태 및 데이터 로드
        state = self.state_manager.load_state()
        df = self.data_handler.get_historical_data(
            self.symbol, self.interval, "3 day ago UTC"
        )

        # 2. 신호 생성
        df_strategy = self.strategy.apply_strategy(df.copy())
        latest_signal = df_strategy["Signal"].iloc[-1]
        latest_price = df["Close"].iloc[-1]

        print(
            f"[{datetime.datetime.now()}] Price: {latest_price}, Signal: {latest_signal}, In position: {state.get('in_position')}"
        )

        # 3. 주문 실행
        if not state.get("in_position") and latest_signal == 1:
            self._handle_buy(state, latest_price)
        elif state.get("in_position"):
            self._handle_sell(state, latest_price, latest_signal)

    def _handle_buy(self, state, price):
        """매수 로직을 처리합니다."""
        print(f"BUY signal detected at price {price}")
        balance = self.trader.get_account_balance("USDT")
        sl_price = (
            price * (1 - self.exit_params.get("stop_loss_pct", 0))
            if self.exit_params.get("stop_loss_pct")
            else None
        )
        quantity = self.sizer.calculate_size(
            capital=balance, price=price, stop_loss_price=sl_price
        )

        if quantity > 0:
            order = self.trader.create_order("BUY", quantity)
            if order:
                new_state = {
                    "in_position": True,
                    "position_size": float(order["executedQty"]),
                    "entry_price": float(order["fills"][0]["price"]),
                    "entry_time": datetime.datetime.now().isoformat(),
                }
                self.state_manager.save_state(new_state)
                print("BUY order successful. State updated.")
        else:
            print("Calculated position size is 0. No trade executed.")

    def _handle_sell(self, state, price, signal):
        """매도 로직을 처리합니다."""
        entry_price = state.get("entry_price", 0)
        should_sell, reason = self._check_sell_conditions(
            state, price, signal, entry_price
        )

        if should_sell:
            print(f"{reason} condition met at price {price}. Attempting to SELL.")
            pos_size = state.get("position_size", 0)
            if pos_size > 0:
                order = self.trader.create_order("SELL", pos_size)
                if order:
                    self.state_manager.save_state(
                        {"in_position": False, "position_size": 0, "entry_price": 0}
                    )
                    print("SELL order successful. State updated.")
            else:
                self.state_manager.save_state(
                    {"in_position": False, "position_size": 0, "entry_price": 0}
                )

    def _check_sell_conditions(self, state, price, signal, entry_price):
        """모든 매도 조건을 확인합니다."""
        if "take_profit_pct" in self.exit_params and price >= entry_price * (
            1 + self.exit_params["take_profit_pct"]
        ):
            return True, "TAKE PROFIT"
        if "stop_loss_pct" in self.exit_params and price <= entry_price * (
            1 - self.exit_params["stop_loss_pct"]
        ):
            return True, "STOP LOSS"
        if "time_cut_period" in self.exit_params:
            entry_time = datetime.datetime.fromisoformat(state.get("entry_time"))
            time_since = (datetime.datetime.now() - entry_time).total_seconds()
            if time_since >= self.exit_params["time_cut_period"] * self.interval_seconds:
                return True, "TIME CUT"
        if signal == -1:
            return True, "SELL SIGNAL"
        return False, ""
