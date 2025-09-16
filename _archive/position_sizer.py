from abc import ABC, abstractmethod


class PositionSizer(ABC):
    """포지션 사이징 전략에 대한 추상 베이스 클래스입니다."""

    @abstractmethod
    def calculate_size(self, capital: float, price: float, **kwargs) -> float:
        """매수할 포지션의 크기를 계산합니다."""
        pass


class AllInSizer(PositionSizer):
    """가용 자본 전체를 사용하여 포지션 크기를 결정합니다."""

    def calculate_size(self, capital: float, price: float, **kwargs) -> float:
        if price <= 0:
            return 0
        return capital / price


class FixedFractionalSizer(PositionSizer):
    """자본의 고정 비율을 리스크로 감수하여 포지션 크기를 결정합니다."""

    def __init__(self, risk_fraction: float = 0.02):
        if not 0 < risk_fraction <= 1:
            raise ValueError("Risk fraction must be between 0 and 1.")
        self.risk_fraction = risk_fraction

    def calculate_size(self, capital: float, price: float, **kwargs) -> float:
        stop_loss_price = kwargs.get("stop_loss_price")
        if stop_loss_price is None:
            # print("Warning: Stop loss price not provided for FixedFractionalSizer. Returning 0.")
            return 0

        if price <= stop_loss_price:
            return 0

        risk_per_share = price - stop_loss_price
        risk_amount = capital * self.risk_fraction

        return risk_amount / risk_per_share


class PositionSizerFactory:
    """포지션 사이저 객체를 생성하는 팩토리 클래스입니다."""

    def __init__(self):
        self._sizers = {"all_in": AllInSizer, "fixed_fractional": FixedFractionalSizer}

    def register_sizer(self, name: str, sizer_class):
        """새로운 사이저를 등록합니다."""
        self._sizers[name] = sizer_class

    def get_sizer(self, name: str, **kwargs):
        """지정된 이름의 사이저 인스턴스를 반환합니다."""
        sizer = self._sizers.get(name)
        if not sizer:
            raise ValueError(f"Sizer '{name}' not found.")
        return sizer(**kwargs)
