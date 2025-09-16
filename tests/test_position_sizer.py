import unittest
from position_sizer import AllInSizer, FixedFractionalSizer, PositionSizerFactory


class TestPositionSizers(unittest.TestCase):
    def test_all_in_sizer(self):
        """AllInSizer가 가용 자본 전체를 사용하는지 테스트합니다."""
        sizer = AllInSizer()
        self.assertAlmostEqual(sizer.calculate_size(capital=10000, price=50000), 0.2)
        self.assertEqual(sizer.calculate_size(capital=10000, price=0), 0)

    def test_fixed_fractional_sizer(self):
        """FixedFractionalSizer가 고정 비율 리스크에 따라 정확한 크기를 계산하는지 테스트합니다."""
        # 리스크 비율 2%
        sizer = FixedFractionalSizer(risk_fraction=0.02)

        # 자본 $10000, 리스크 금액 $200
        # 진입가 $50000, 손절가 $49000 -> 주당 리스크 $1000
        # 포지션 크기 = $200 / $1000 = 0.2
        size = sizer.calculate_size(capital=10000, price=50000, stop_loss_price=49000)
        self.assertAlmostEqual(size, 0.2)

        # 손절가가 제공되지 않으면 0을 반환해야 함
        size_no_sl = sizer.calculate_size(capital=10000, price=50000)
        self.assertEqual(size_no_sl, 0)

        # 진입가가 손절가보다 낮거나 같으면 0을 반환해야 함
        size_invalid_price = sizer.calculate_size(
            capital=10000, price=49000, stop_loss_price=50000
        )
        self.assertEqual(size_invalid_price, 0)

    def test_position_sizer_factory(self):
        """PositionSizerFactory가 올바른 사이저 객체를 생성하는지 테스트합니다."""
        factory = PositionSizerFactory()

        all_in_sizer = factory.get_sizer("all_in")
        self.assertIsInstance(all_in_sizer, AllInSizer)

        ff_sizer = factory.get_sizer("fixed_fractional", risk_fraction=0.05)
        self.assertIsInstance(ff_sizer, FixedFractionalSizer)
        self.assertEqual(ff_sizer.risk_fraction, 0.05)

        with self.assertRaises(ValueError):
            factory.get_sizer("non_existent_sizer")


if __name__ == "__main__":
    unittest.main()
