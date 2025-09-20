import unittest
from io import StringIO
from unittest.mock import MagicMock, patch

import pandas as pd

# Import the main function from your main.py
from main import main


class TestMain(unittest.TestCase):
    @patch("main.load_dotenv")
    @patch("main.os.environ.get")
    @patch("main.BinanceData")
    @patch("main.StrategyFactory")
    @patch("main.Backtester")
    @patch("main.os.makedirs")
    @patch("builtins.open", new_callable=unittest.mock.mock_open)
    @patch("sys.stdout", new_callable=StringIO)
    def test_main_function_flow(
        self,
        mock_stdout,
        mock_open,
        mock_makedirs,
        MockBacktester,
        MockStrategyFactory,
        MockBinanceData,
        mock_getenv,
        mock_load_dotenv,
    ):
        # Mock environment variables
        mock_getenv.side_effect = (
            lambda x: "test_key" if x == "BINANCE_API_KEY" else "test_secret"
        )

        # Mock BinanceData
        mock_binance_data_instance = MockBinanceData.return_value
        mock_binance_data_instance.get_historical_data.return_value = pd.DataFrame(
            {
                "Open time": pd.to_datetime(["2023-01-01", "2023-01-02"]),
                "Open": [10, 11],
                "High": [12, 13],
                "Low": [9, 10],
                "Close": [11, 12],
                "Volume": [100, 110],
                "Signal": [0, 1],  # Example signal
            }
        )

        # Mock StrategyFactory
        mock_strategy_instance = MagicMock()
        MockStrategyFactory.return_value.get_strategy.return_value = (
            mock_strategy_instance
        )
        mock_strategy_instance.apply_strategy.return_value = pd.DataFrame(
            {
                "Open time": pd.to_datetime(["2023-01-01", "2023-01-02"]),
                "Open": [10, 11],
                "High": [12, 13],
                "Low": [9, 10],
                "Close": [11, 12],
                "Volume": [100, 110],
                "Signal": [0, 1],  # Example signal
            }
        )

        # Mock Backtester
        mock_backtester_instance = MockBacktester.return_value
        mock_backtester_instance.get_report_string.return_value = "Test Report Content"

        # Run the main function
        main()

        # Assertions
        mock_load_dotenv.assert_called_once()  # .env loaded
        mock_getenv.assert_any_call("BINANCE_API_KEY")
        mock_getenv.assert_any_call("BINANCE_SECRET_KEY")

        MockBinanceData.assert_called_once_with("test_key", "test_secret")
        mock_binance_data_instance.get_historical_data.assert_called_once()  # Check if data was fetched

        MockStrategyFactory.assert_called_once()  # Factory initialized
        MockStrategyFactory.return_value.get_strategy.assert_called_once()  # Strategy created
        mock_strategy_instance.apply_strategy.assert_called_once()  # Strategy applied

        MockBacktester.assert_called_once()  # Backtester initialized
        mock_backtester_instance.run.assert_called_once()  # Backtest run

        mock_makedirs.assert_called_once_with(
            "backtest_logs", exist_ok=True
        )  # Log directory created
        mock_open.assert_called_once_with(
            unittest.mock.ANY, "w", encoding="utf-8"
        )  # Report file opened
        mock_open.return_value.__enter__.return_value.write.assert_called_once_with(
            "Test Report Content"
        )  # Report written

        # Check console output (optional, but good for full flow)
        output = mock_stdout.getvalue()
        self.assertIn("Fetching data for", output)
        self.assertIn("Backtest report saved to:", output)
        self.assertIn("--- Strategy Signal Details for", output)

    @patch("main.load_dotenv")
    @patch("main.os.environ.get")
    @patch("sys.stdout", new_callable=StringIO)
    def test_main_function_no_api_keys(
        self, mock_stdout, mock_getenv, mock_load_dotenv
    ):
        mock_getenv.side_effect = lambda x: None  # Simulate no API keys

        main()

        output = mock_stdout.getvalue()
        self.assertIn(
            "Error: Please set BINANCE_API_KEY and BINANCE_SECRET_KEY in a .env file.",
            output,
        )


if __name__ == "__main__":
    unittest.main()
