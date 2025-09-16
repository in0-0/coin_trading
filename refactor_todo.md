# TODO: live_trader_gpt.py Refactoring

- [ ] **1. Setup & Imports:**
    - [ ] Import necessary modules: `os`, `time`, `signal`, `logging`, `requests`, `dotenv`.
    - [ ] Import custom modules: `BinanceData` from `binance_data`, `StrategyFactory` from `strategy`, `StateManager`, `Position` from `state_manager`.
    - [ ] Define global configurations (SYMBOLS, EXEC_INTERVAL, TIMEFRAMES, etc.).

- [ ] **2. Create `LiveTrader` Class:**
    - [ ] Define `__init__` method:
        - [ ] Initialize instance variables: `_running`, `positions`.
        - [ ] Call `_setup_client` to initialize Binance client.
        - [ ] Instantiate `BinanceData`, `StateManager`, and `StrategyFactory`.
        - [ ] Call `state_manager.load_positions()` to restore state.
    - [ ] Define `_setup_client` method to handle API key loading and client creation.
    - [ ] Define `_setup_strategy` method to get the `ensemble_signal` strategy from the factory.

- [ ] **3. Implement Core Logic Methods:**
    - [ ] Define `run` method for the main trading loop.
    - [ ] Define `_check_stops` method to monitor and execute stop-losses.
    - [ ] Define `_find_and_execute_entries` method:
        - [ ] Get data for all timeframes using `data_provider.get_and_update_klines`.
        - [ ] Get signal score using `strategy.apply`.
        - [ ] If score > threshold, call `_calculate_position_size`.
        - [ ] If valid size, call `_place_buy_order`.
    - [ ] Define `_calculate_position_size` method:
        - [ ] Use `data_provider` to get data for the execution timeframe.
        - [ ] Calculate ATR based on **closed candles** (`iloc[:-1]` or similar) to prevent repainting.
        - [ ] Return the calculated USDT amount to spend.
    - [ ] Define `_place_buy_order` and `_place_sell_order` methods:
        - [ ] Execute orders via Binance client.
        - [ ] **Crucially, call `state_manager.save_positions(self.positions)` immediately after `self.positions` is modified.**
    - [ ] Define helper methods like `_get_account_balance_usdt` and `tg_send`.

- [ ] **4. Implement Graceful Shutdown:**
    - [ ] Define `stop` method to set `_running` to `False`.
    - [ ] Define `_shutdown` method to close all open positions by calling `_place_sell_order`.
    - [ ] Create a global `shutdown_handler` function that calls the `LiveTrader` instance's `stop` method.
    - [ ] Register the handler for `SIGINT` and `SIGTERM`.

- [ ] **5. Finalize Main Execution Block:**
    - [ ] In `if __name__ == "__main__":`:
        - [ ] Instantiate `LiveTrader`.
        - [ ] Register the shutdown handler.
        - [ ] Call the `run` method within a `try...except` block for fatal error logging.
        - [ ] Remove all old global functions and variables that are now part of the class.
