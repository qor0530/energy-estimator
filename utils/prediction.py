# utils/prediction.py

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
import streamlit as st

# 추천 등급 라벨링 함수
def label_sites(preds, q1, q2, q3):
    return np.where(
        preds >= q3, "매우 추천",
        np.where(preds >= q2, "추천",
        np.where(preds >= q1, "확인 필요", "비추천"))
    )

# 분위수 계산 함수
@st.cache_data
def compute_quartiles(_model, train_df, features, capacity_kw):
    df = train_df.copy()
    if '설비용량' in features and '설비용량' not in df.columns and '설비용량(kW)' in df.columns:
        df['설비용량'] = df['설비용량(kW)']
    df['설비용량(kW)'] = capacity_kw
    df = df[features].dropna()
    X = pd.DataFrame(SimpleImputer().fit_transform(df), columns=features)
    preds = _model.predict(X)
    preds = np.clip(preds, 0, None)
    preds *= 12  # 연간 환산
    return np.percentile(preds, [25, 50, 75])

# 예측 및 추천등급 라벨링

def predict_and_label(_model, features, train_df, idle_df, capacity_kw, area_per_kw):
    area_col = [col for col in idle_df.columns if "면적" in col][0]
    df = idle_df[idle_df[area_col] >= capacity_kw * area_per_kw].copy()

    if "설비용량" in features:
        df["설비용량"] = capacity_kw
    if "설비용량(kW)" in features:
        df["설비용량(kW)"] = capacity_kw

    for col in features:
        if col not in df.columns:
            df[col] = 0

    df = df.dropna(subset=features)
    X = pd.DataFrame(SimpleImputer().fit_transform(df[features]), columns=features)

    preds = _model.predict(X)
    preds = np.clip(preds, 0, None)

    df["예측_발전량(kWh)"] = preds

    # ✅ 유휴부지 기준 분위수 계산 및 라벨링 (월 기준)
    q1, q2, q3 = np.percentile(preds, [25, 50, 75])
    df["추천등급"] = label_sites(preds, q1, q2, q3)

    return df
