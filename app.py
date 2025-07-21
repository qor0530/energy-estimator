# app.py

import streamlit as st
import pandas as pd
import numpy as np
import joblib
import folium
from streamlit_folium import st_folium
from sklearn.impute import SimpleImputer

# -------------------------------
# 📌 페이지 설정
st.set_page_config(page_title="태양광·풍력 유휴부지 예측", layout="wide")
st.title("🌞💨 유휴부지 태양광·풍력 발전량 예측 대시보드")

# -------------------------------
# 📦 캐싱 함수
@st.cache_resource
def load_model_and_features(model_path, feature_path):
    model = joblib.load(model_path)
    features = joblib.load(feature_path)
    return model, features

@st.cache_data
def load_training_data():
    df_solar = pd.read_excel("최종_태양광.xlsx")
    df_wind = pd.read_excel("최종 풍력.xlsx")
    return df_solar, df_wind

@st.cache_data
def load_idle_sites():
    df_idle = pd.read_excel("유휴부지_월별_날씨포함.xlsx")
    df_idle["연"] = df_idle["날짜"].astype(str).str[:4].astype(int)
    df_idle["월"] = df_idle["날짜"].astype(str).str[4:6].astype(int)
    return df_idle

# -------------------------------
# 🔧 초기화
model_solar, solar_features = load_model_and_features("models/best_model_solar_lgb.pkl", "models/solar_feature_columns.pkl")
model_wind, wind_features = load_model_and_features("models/best_model_wind_lgb.pkl", "models/wind_feature_columns.pkl")
df_solar_train, df_wind_train = load_training_data()
df_idle = load_idle_sites()

for df in [df_solar_train, df_wind_train]:
    df["연"] = df["날짜"].astype(str).str[:4].astype(int)
    df["월"] = df["날짜"].astype(str).str[4:6].astype(int)

# -------------------------------
# ⚙️ 사이드바 설정
st.sidebar.header("⚙️ 사용자 설정")
max_solar_kw = int(df_solar_train["설비용량(kW)"].max())
max_wind_kw = int(df_wind_train["설비용량(kW)"].max())

solar_kw = st.sidebar.number_input("☀️ 태양광 설비용량", 50, max_solar_kw, 300, 50)
wind_kw = st.sidebar.number_input("💨 풍력 설비용량", 50, max_wind_kw, 300, 50)
area_per_kw = st.sidebar.slider("1kW당 필요한 면적 (㎡)", 10, 30, 23)

min_area = min(solar_kw, wind_kw) * area_per_kw
selected_sources = st.sidebar.multiselect("📡 발전 종류 선택", ["태양광", "풍력"], default=["태양광", "풍력"])
selected_grades = st.sidebar.multiselect("🏷️ 추천 등급 필터", ["매우 추천", "추천", "확인 필요", "비추천"],
                                         default=["매우 추천", "추천", "확인 필요", "비추천"])

# -------------------------------
# 📈 예측 및 라벨링
def label_sites(preds, q1, q2, q3):
    return np.where(preds >= q3, "매우 추천",
           np.where(preds >= q2, "추천",
           np.where(preds >= q1, "확인 필요", "비추천")))

@st.cache_data
def compute_quartiles(_model, train_df, features, capacity_kw):
    df = train_df.copy()

    # '설비용량' 컬럼이 없고 '설비용량(kW)'가 있을 경우 변환
    if '설비용량' in features and '설비용량' not in df.columns and '설비용량(kW)' in df.columns:
        df['설비용량'] = df['설비용량(kW)']

    df["설비용량(kW)"] = capacity_kw  # 사분위수 기준값 재계산을 위해 강제 삽입
    df = df[features].dropna()
    X = pd.DataFrame(SimpleImputer().fit_transform(df), columns=features)
    preds = _model.predict(X)
    return np.percentile(preds, [25, 50, 75])

def predict_and_label(model, features, train_df, idle_df, capacity_kw, q1, q2, q3):
    df = idle_df[idle_df["면적(m^2)"] >= capacity_kw * area_per_kw].copy()
    df["설비용량(kW)"] = capacity_kw
    for col in features:
        if col not in df.columns:
            df[col] = 0
    df = df.dropna(subset=features)
    X = pd.DataFrame(SimpleImputer().fit_transform(df[features]), columns=features)
    preds = model.predict(X)
    df["예측_발전량(kWh)"] = preds
    df["추천등급"] = label_sites(preds, q1, q2, q3)
    return df

# 사분위 계산 및 예측
solar_q1, solar_q2, solar_q3 = compute_quartiles(model_solar, df_solar_train, solar_features, solar_kw)
wind_q1, wind_q2, wind_q3 = compute_quartiles(model_wind, df_wind_train, wind_features, wind_kw)

df_solar_result = predict_and_label(model_solar, solar_features, df_solar_train, df_idle, solar_kw, solar_q1, solar_q2, solar_q3)
df_wind_result = predict_and_label(model_wind, wind_features, df_wind_train, df_idle, wind_kw, wind_q1, wind_q2, wind_q3)

# -------------------------------
# 📊 요약 정보
def summarize(df, source_label):
    return (
        df.groupby("재산 소재지", as_index=False)
        .agg({
            "위도": "first",
            "경도": "first",
            "면적(m^2)": "first",
            "예측_발전량(kWh)": "mean",
            "추천등급": "first"
        })
        .assign(발전종류=source_label)
        .rename(columns={
            "면적(m^2)": "면적",
            "예측_발전량(kWh)": "예측_평균_발전량(kWh)"
        })
    )

df_all = pd.concat([
    summarize(df_solar_result, "태양광"),
    summarize(df_wind_result, "풍력")
], ignore_index=True)

df_filtered = df_all[
    df_all["발전종류"].isin(selected_sources) &
    df_all["추천등급"].isin(selected_grades)
]

# -------------------------------
# 🗺️ 지도 시각화
st.subheader("🗺️ 추천 유휴부지 위치 (필터 반영됨)")
if not df_filtered.empty:
    m = folium.Map(location=[df_filtered["위도"].mean(), df_filtered["경도"].mean()], zoom_start=7)
    color_map = {"매우 추천": "green", "추천": "blue", "확인 필요": "orange", "비추천": "red"}
    for _, row in df_filtered.iterrows():
        folium.CircleMarker(
            location=[row["위도"], row["경도"]],
            radius=7,
            popup=(f"{row['재산 소재지']}<br>{row['발전종류']}<br>{row['추천등급']}<br>예측: {row['예측_평균_발전량(kWh)']:.1f} kWh"),
            color=color_map[row["추천등급"]],
            fill=True,
            fill_color=color_map[row["추천등급"]],
            fill_opacity=0.6
        ).add_to(m)
    st_folium(m, width=1000, height=600)
else:
    st.warning("조건에 맞는 유휴부지가 없습니다.")

# -------------------------------
# 📋 표 출력
st.subheader("📊 유휴부지 추천 요약")
st.dataframe(df_filtered.reset_index(drop=True))
