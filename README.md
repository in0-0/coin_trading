# Coin Trading Bot

This is a Python-based cryptocurrency trading bot that uses the Binance API to execute trades.

## Project Structure

The project is structured as follows:

-   `live_trader_gpt.py`: The main entry point for the live trading bot.
-   `binance_data.py`: Handles data fetching from the Binance API.
-   `state_manager.py`: Manages the state of the trading bot, including open positions.
-   `models.py`: Contains the data models for the application.
-   `strategies/`: This directory contains the different trading strategies.
    -   `base_strategy.py`: Defines the interface for all strategies.
    -   `atr_trailing_stop_strategy.py`: A concrete implementation of a trading strategy.
-   `strategy_factory.py`: A factory for creating strategy objects.
-   `tests/`: Contains unit tests for the project.
-   `data/`: Contains historical market data.
-   `_archive/`: Contains old files that are no longer in use.

## Design Patterns

The project uses the following design patterns:

-   **Strategy Pattern**: The trading logic is encapsulated in different strategy classes, which can be easily swapped. This is implemented in the `strategies` directory.
-   **Factory Pattern**: A factory is used to create strategy objects, decoupling the `LiveTrader` from the concrete strategy implementations. This is implemented in the `strategy_factory.py` file.
