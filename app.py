# app.py

import streamlit as st
import pandas as pd
import numpy as np
from streamlit_folium import st_folium
import matplotlib.pyplot as plt

from utils.data_loader import load_model_and_features, load_training_data, load_idle_sites
from utils.prediction import predict_and_label, label_sites
from visualization.map_utils import create_site_map, 추천색상

# -------------------------------
# 📌 페이지 설정
st.set_page_config(page_title="태양광·풍력 유휴부지 예측", layout="wide")
st.title("🌞💨 유휴부지 태양광·풍력 발전량 예측 대시보드")

# -------------------------------
# 🔧 모델 및 데이터 로딩
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

solar_area_per_kw = st.sidebar.slider("☀️ 태양광: 1kW당 필요한 면적 (㎡)", 10, 30, 23)
wind_area_per_kw = st.sidebar.slider("💨 풍력: 1kW당 필요한 면적 (㎡)", 10, 30, 23)

selected_sources = st.sidebar.multiselect("📡 발전 종류 선택", ["태양광", "풍력"], default=["태양광", "풍력"])
selected_grades = st.sidebar.multiselect("🏷️ 추천 등급 필터", ["매우 추천", "추천", "확인 필요", "비추천"], default=["매우 추천", "추천", "확인 필요", "비추천"])

if not selected_sources:
    st.error("❗ 최소 하나의 발전 종류를 선택해주세요.")
    st.stop()

# -------------------------------
# 📈 예측 및 라벨링

df_solar_result = predict_and_label(model_solar, solar_features, df_solar_train, df_idle, solar_kw, solar_area_per_kw)
df_wind_result = predict_and_label(model_wind, wind_features, df_wind_train, df_idle, wind_kw, wind_area_per_kw)

solar = df_solar_result.rename(columns={"예측_발전량(kWh)": "태양광_월간_발전량(kWh)"})
wind = df_wind_result.rename(columns={"예측_발전량(kWh)": "풍력_월간_발전량(kWh)"})

merged = pd.merge(solar, wind, on=["재산 소재지", "위도", "경도", "날짜"], suffixes=('_solar', '_wind'))

agg_df = merged.groupby(["재산 소재지", "위도", "경도"]).agg({
    "태양광_월간_발전량(kWh)": "sum",
    "풍력_월간_발전량(kWh)": "sum"
}).reset_index().rename(columns={
    "태양광_월간_발전량(kWh)": "태양광_연간_총_발전량(kWh)",
    "풍력_월간_발전량(kWh)": "풍력_연간_총_발전량(kWh)"
})

# -------------------------------
# 📏 연간 발전량 기준 분위수 → 추천등급
solar_q1, solar_q2, solar_q3 = np.percentile(agg_df["태양광_연간_총_발전량(kWh)"], [25, 50, 75])
wind_q1, wind_q2, wind_q3 = np.percentile(agg_df["풍력_연간_총_발전량(kWh)"], [25, 50, 75])

agg_df["태양광_추천등급"] = label_sites(agg_df["태양광_연간_총_발전량(kWh)"], solar_q1, solar_q2, solar_q3)
agg_df["풍력_추천등급"] = label_sites(agg_df["풍력_연간_총_발전량(kWh)"], wind_q1, wind_q2, wind_q3)

agg_df["추천종류"] = agg_df.apply(lambda x: "태양광" if x["태양광_연간_총_발전량(kWh)"] >= x["풍력_연간_총_발전량(kWh)"] else "풍력", axis=1)
agg_df["색상"] = agg_df.apply(lambda x: 추천색상(x["태양광_추천등급"], x["풍력_추천등급"], selected_sources), axis=1)

# -------------------------------
# 🗺️ 지도 출력
st.subheader("🗺️ 추천 유휴부지 위치")
m = create_site_map(agg_df, selected_sources)
st_data = st_folium(m, width=1000, height=600)

# -------------------------------
# 📋 상세 출력 (클릭 시)
if st_data and st_data.get("last_object_clicked_tooltip"):
    clicked = st_data["last_object_clicked_tooltip"]
    st.subheader(f"📌 선택한 유휴부지: {clicked}")

    detail_df = merged[merged["재산 소재지"] == clicked].sort_values("날짜")
    태등급 = agg_df.loc[agg_df["재산 소재지"] == clicked, "태양광_추천등급"].values[0]
    풍등급 = agg_df.loc[agg_df["재산 소재지"] == clicked, "풍력_추천등급"].values[0]
    st.markdown(f"☀️ **태양광 추천등급:** `{태등급}`  💨 **풍력 추천등급:** `{풍등급}`")

    col1, col2 = st.columns(2)
    with col1:
        st.bar_chart(detail_df.set_index("날짜")["태양광_월간_발전량(kWh)"])
    with col2:
        st.bar_chart(detail_df.set_index("날짜")["풍력_월간_발전량(kWh)"])

    st.dataframe(detail_df)

# -------------------------------
# 📈 전체 통계 및 TOP10 출력
st.subheader("📊 전체 유휴부지 통계")

col1, col2 = st.columns(2)
with col1:
    st.markdown("**📦 발전량 기준 TOP 10 (태양광)**")
    st.dataframe(agg_df.sort_values("태양광_연간_총_발전량(kWh)", ascending=False).head(10))

with col2:
    st.markdown("**📦 발전량 기준 TOP 10 (풍력)**")
    st.dataframe(agg_df.sort_values("풍력_연간_총_발전량(kWh)", ascending=False).head(10))

# -------------------------------
# 📑 월별 상세 데이터 테이블
st.subheader("📅 월별 유휴부지 예측 데이터")
st.dataframe(merged.sort_values(["재산 소재지", "날짜"]))
