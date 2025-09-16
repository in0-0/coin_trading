import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from skopt import gp_minimize
from skopt.space import Real
from skopt.utils import use_named_args

# -------------------------------
# 1. 기존 데이터 로드
# -------------------------------
df = pd.read_csv("grid_search_summary.csv")

# 현재 데이터 확인
print("기존 데이터 요약:")
print(df.describe())

# -------------------------------
# 2. 확장된 파라미터 범위 생성
# -------------------------------
atr_values = np.arange(0.5, 5.25, 0.25)  # 0.5~5.0
risk_values = np.arange(0.002, 0.052, 0.002)  # 0.002~0.05

expanded_params = [(atr, risk) for atr in atr_values for risk in risk_values]
expanded_df = pd.DataFrame(expanded_params, columns=["atr", "risk"])
print(f"확장된 파라미터 조합 개수: {len(expanded_df)}")

# -------------------------------
# 3. 베이지안 최적화 설정
# -------------------------------
# 예시: Sharpe를 최대화 목표
space = [
    Real(0.5, 5.0, name='atr'),
    Real(0.002, 0.05, name='risk')
]

# 예시 목적 함수 (실제로는 백테스트 결과에서 Sharpe를 계산해야 함)
# 여기서는 df에서 가까운 값의 Sharpe를 흉내내서 반환
@use_named_args(space)
def objective(atr, risk):
    nearest = df.iloc[((df["atr_mul"] - atr)**2 + (df["risk"] - risk)**2).argmin()]
    return -nearest["sharpe"]  # skopt는 최소화를 하므로 음수로 반환

print("베이지안 최적화 시작...")
res = gp_minimize(objective, space, n_calls=20, random_state=42)

print(f"최적 파라미터: ATR={res.x[0]:.3f}, Risk={res.x[1]:.4f}, 예상 Sharpe={-res.fun:.4f}")

# -------------------------------
# 4. 시각화: 성능 맵
# -------------------------------
pivot_sharpe = df.pivot_table(index="risk", columns="atr_mul", values="sharpe")
plt.figure(figsize=(10, 6))
plt.imshow(pivot_sharpe, cmap="viridis", aspect="auto", origin="lower",
           extent=[df["atr_mul"].min(), df["atr_mul"].max(), df["risk"].min(), df["risk"].max()])
plt.colorbar(label="Sharpe Ratio")
plt.scatter(res.x[0], res.x[1], color="red", s=100, label="Best (Bayesian)")
plt.xlabel("ATR Multiplier")
plt.ylabel("Risk")
plt.title("Sharpe Ratio Heatmap")
plt.legend()
plt.show()

# -------------------------------
# 5. 확장 파라미터 CSV 저장
# -------------------------------
expanded_df.to_csv("expanded_parameters.csv", index=False)
print("확장된 파라미터 CSV 저장 완료: expanded_parameters.csv")