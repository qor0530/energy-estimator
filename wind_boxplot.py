# wind_boxplot.py

import pandas as pd
import numpy as np
import joblib
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.impute import SimpleImputer

# 🔧 파일 경로 설정
MODEL_PATH = "models/best_model_wind_lgb.pkl"
FEATURE_PATH = "models/wind_feature_columns.pkl"
TRAIN_DATA_PATH = "최종_풍력.xlsx"
IDLE_SITE_PATH = "유휴부지_월별_날씨포함.xlsx"
CAPACITY_KW = 300  # 분석할 설비용량

# 📦 데이터 로드
model = joblib.load(MODEL_PATH)
features = joblib.load(FEATURE_PATH)
df_train = pd.read_excel(TRAIN_DATA_PATH)
df_idle = pd.read_excel(IDLE_SITE_PATH)

# 날짜 파싱
df_train["연"] = df_train["날짜"].astype(str).str[:4].astype(int)
df_train["월"] = df_train["날짜"].astype(str).str[4:6].astype(int)
df_idle["연"] = df_idle["날짜"].astype(str).str[:4].astype(int)
df_idle["월"] = df_idle["날짜"].astype(str).str[4:6].astype(int)

# ✅ 사분위수 계산용 함수
def compute_quartiles(model, train_df, features, capacity_kw):
    df = train_df.copy()
    if '설비용량' in features and '설비용량' not in df.columns and '설비용량(kW)' in df.columns:
        df['설비용량'] = df['설비용량(kW)']
    df["설비용량(kW)"] = capacity_kw
    df = df[features].dropna()
    X = pd.DataFrame(SimpleImputer().fit_transform(df), columns=features)
    preds = model.predict(X)
    return np.percentile(preds, [25, 50, 75])

# ✅ 유휴부지 예측
def predict_on_idle(model, features, idle_df, capacity_kw, area_per_kw=23):
    df = idle_df[idle_df["면적(m^2)"] >= capacity_kw * area_per_kw].copy()
    if "설비용량" in features:
        df["설비용량"] = capacity_kw
    if "설비용량(kW)" in features:
        df["설비용량(kW)"] = capacity_kw
    for col in features:
        if col not in df.columns:
            df[col] = 0
    df = df.dropna(subset=features)
    X = pd.DataFrame(SimpleImputer().fit_transform(df[features]), columns=features)
    preds = model.predict(X)
    df["예측_발전량(kWh)"] = preds
    return df

# 🎯 실행
wind_q1, wind_q2, wind_q3 = compute_quartiles(model, df_train, features, CAPACITY_KW)
df_result = predict_on_idle(model, features, df_idle, CAPACITY_KW)

# 📊 시각화
plt.figure(figsize=(10, 5))
sns.boxplot(y=df_result["예측_발전량(kWh)"], color="skyblue")
plt.axhline(wind_q1, color="purple", linestyle="--", label=f"Q1: {wind_q1:.0f}")
plt.axhline(wind_q2, color="blue", linestyle="--", label=f"Q2 (Median): {wind_q2:.0f}")
plt.axhline(wind_q3, color="green", linestyle="--", label=f"Q3: {wind_q3:.0f}")
plt.title("풍력 유휴부지 예측 발전량 Boxplot")
plt.ylabel("예측 발전량 (kWh)")
plt.grid(True)
plt.legend()
plt.tight_layout()
plt.show()
