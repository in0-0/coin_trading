import pandas as pd
from binance.client import Client

class BinanceData:
    def __init__(self, api_key, secret_key):
        self.client = Client(api_key, secret_key)

    def get_historical_data(self, symbol, interval, start_str, end_str=None):
        """지정된 심볼의 과거 데이터를 가져와 OHLCV DataFrame으로 반환합니다."""
        klines = self.client.get_historical_klines(symbol, interval, start_str, end_str)
        df = pd.DataFrame(klines, columns=[
            'Open time', 'Open', 'High', 'Low', 'Close', 'Volume',
            'Close time', 'Quote asset volume', 'Number of trades',
            'Taker buy base asset volume', 'Taker buy quote asset volume', 'Ignore'
        ])
        # 시간 관련 컬럼을 datetime 형식으로 변환
        df['Open time'] = pd.to_datetime(df['Open time'], unit='ms')
        # 숫자형 컬럼들을 float으로 변환
        for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
            df[col] = df[col].astype(float)
        # 필요한 컬럼만 선택하여 반환
        return df[['Open time', 'Open', 'High', 'Low', 'Close', 'Volume']]

    def add_moving_average(self, df, window):
        """DataFrame에 이동평균선 컬럼을 추가합니다."""
        df[f'MA_{window}'] = df['Close'].rolling(window=window).mean()
        return df
