import unittest
from unittest.mock import MagicMock, patch

from binance.exceptions import BinanceAPIException
from live_trader import LiveTrader


class TestLiveTrader(unittest.TestCase):
    def setUp(self):
        """테스트를 위한 LiveTrader 인스턴스와 mock client를 설정합니다."""
        self.mock_client = MagicMock()

        # LiveTrader를 인스턴스화할 때 mock client를 주입하기 위해 patch 사용
        self.patcher = patch("live_trader.Client", return_value=self.mock_client)
        self.mock_client_class = self.patcher.start()

        self.trader = LiveTrader(
            api_key="test_key", secret_key="test_secret", symbol="BTCUSDT"
        )

    def tearDown(self):
        """모든 테스트 후에 patch를 중지합니다."""
        self.patcher.stop()

    def test_get_account_balance(self):
        """계좌 잔고 조회 기능을 테스트합니다."""
        self.mock_client.get_asset_balance.return_value = {
            "asset": "USDT",
            "free": "10000.0",
        }
        balance = self.trader.get_account_balance("USDT")

        self.mock_client.get_asset_balance.assert_called_once_with(asset="USDT")
        self.assertEqual(balance, 10000.0)

    def test_get_account_balance_api_error(self):
        """API 에러 발생 시 잔고 조회 실패를 테스트합니다."""
        self.mock_client.get_asset_balance.side_effect = BinanceAPIException(
            "API Error"
        )
        balance = self.trader.get_account_balance("USDT")
        self.assertEqual(balance, 0.0)

    @patch("numpy.log10")
    def test_create_order_formatting(self, mock_log10):
        """주문 생성 시 수량이 올바르게 포맷되는지 테스트합니다."""
        mock_log10.return_value = -2  # 정밀도 2로 가정
        self.mock_client.get_symbol_info.return_value = {
            "filters": [{"filterType": "LOT_SIZE", "stepSize": "0.01"}]
        }
        self.trader.create_order("BUY", 1.23456)

        # create_order가 '1.23'으로 호출되었는지 확인
        self.mock_client.create_order.assert_called_once()
        call_args = self.mock_client.create_order.call_args
        self.assertEqual(call_args[1]["quantity"], "1.23")

    def test_create_order_success(self):
        """주문 생성 성공 케이스를 테스트합니다."""
        self.mock_client.create_order.return_value = {"symbol": "BTCUSDT", "orderId": 1}
        # _get_formatted_quantity를 모의 처리하여 네트워크 호출 방지
        with patch.object(
            self.trader, "_get_formatted_quantity", return_value="1.0"
        ) as mock_format:
            order = self.trader.create_order("BUY", 1.0)
            mock_format.assert_called_once_with(1.0)
            self.mock_client.create_order.assert_called_once_with(
                symbol="BTCUSDT", side="BUY", type="MARKET", quantity="1.0"
            )
            self.assertEqual(order["orderId"], 1)

    def test_create_order_api_error(self):
        """API 에러 발생 시 주문 생성 실패를 테스트합니다."""
        self.mock_client.create_order.side_effect = BinanceAPIException("Order Error")
        with patch.object(self.trader, "_get_formatted_quantity", return_value="1.0"):
            order = self.trader.create_order("SELL", 1.0)
            self.assertIsNone(order)


if __name__ == "__main__":
    unittest.main()
