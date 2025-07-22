# app.py

import streamlit as st
import pandas as pd
import numpy as np
import joblib
import folium
from streamlit_folium import st_folium
from sklearn.impute import SimpleImputer
from branca.element import Template, MacroElement

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
    df_wind = pd.read_excel("최종_풍력.xlsx")
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

solar_area_per_kw = st.sidebar.slider("☀️ 태양광: 1kW당 필요한 면적 (㎡)", 10, 30, 23)
wind_area_per_kw = st.sidebar.slider("💨 풍력: 1kW당 필요한 면적 (㎡)", 10, 30, 23)

selected_sources = st.sidebar.multiselect("📡 발전 종류 선택", ["태양광", "풍력"], default=["태양광", "풍력"])
selected_grades = st.sidebar.multiselect("🏷️ 추천 등급 필터", ["매우 추천", "추천", "확인 필요", "비추천"], default=["매우 추천", "추천", "확인 필요", "비추천"])

# -------------------------------
# 📈 예측 및 라벨링
def label_sites(preds, q1, q2, q3):
    return np.where(preds >= q3, "매우 추천", np.where(preds >= q2, "추천", np.where(preds >= q1, "확인 필요", "비추천")))

@st.cache_data
def compute_quartiles(_model, train_df, features, capacity_kw):
    df = train_df.copy()
    if '설비용량' in features and '설비용량' not in df.columns and '설비용량(kW)' in df.columns:
        df['설비용량'] = df['설비용량(kW)']
    df["설비용량(kW)"] = capacity_kw
    df = df[features].dropna()
    X = pd.DataFrame(SimpleImputer().fit_transform(df), columns=features)
    preds = _model.predict(X)

    # ✅ 음수 클리핑 후 연간 발전량 기준으로 분위수 계산
    preds = np.clip(preds, 0, None)
    preds = preds * 12

    return np.percentile(preds, [25, 50, 75])

def predict_and_label(model, features, train_df, idle_df, capacity_kw, q1, q2, q3, area_per_kw):
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

    # ✅ 음수값 제거
    preds = np.clip(preds, 0, None)

    # ✅ 연간 발전량 기반 추천 등급
    annual_preds = preds * 12
    df["예측_발전량(kWh)"] = preds
    df["연간_예측_발전량(kWh)"] = annual_preds
    df["추천등급"] = label_sites(annual_preds, q1, q2, q3)

    return df

solar_q1, solar_q2, solar_q3 = compute_quartiles(model_solar, df_solar_train, solar_features, solar_kw)
wind_q1, wind_q2, wind_q3 = compute_quartiles(model_wind, df_wind_train, wind_features, wind_kw)

df_solar_result = predict_and_label(model_solar, solar_features, df_solar_train, df_idle, solar_kw, solar_q1, solar_q2, solar_q3, solar_area_per_kw)
df_wind_result = predict_and_label(model_wind, wind_features, df_wind_train, df_idle, wind_kw, wind_q1, wind_q2, wind_q3, wind_area_per_kw)

# -------------------------------
# 📊 병합 및 시각화용 집계
df_solar_result["월"] = df_solar_result["날짜"].astype(str).str[4:6].astype(int)
df_wind_result["월"] = df_wind_result["날짜"].astype(str).str[4:6].astype(int)

solar = df_solar_result.rename(columns={"예측_발전량(kWh)": "태양광_월간_발전량(kWh)", "추천등급": "태양광_추천등급"})
wind = df_wind_result.rename(columns={"예측_발전량(kWh)": "풍력_월간_발전량(kWh)", "추천등급": "풍력_추천등급"})

merged = pd.merge(solar, wind, on=["재산 소재지", "위도", "경도", "날짜"], suffixes=("_solar", "_wind"))

agg_df = merged.groupby(["재산 소재지", "위도", "경도"]).agg({
    "태양광_월간_발전량(kWh)": "sum",
    "풍력_월간_발전량(kWh)": "sum",
    "태양광_추천등급": lambda x: x.mode().iloc[0],
    "풍력_추천등급": lambda x: x.mode().iloc[0]
}).reset_index().rename(columns={
    "태양광_월간_발전량(kWh)": "태양광_연간_총_발전량(kWh)",
    "풍력_월간_발전량(kWh)": "풍력_연간_총_발전량(kWh)"
})

def 추천색상(등급_태양광, 등급_풍력):
    if 등급_태양광 == 등급_풍력:
        return "green"
    elif 등급_태양광 in ["매우 추천", "추천"] and 등급_풍력 in ["확인 필요", "비추천"]:
        return "orange"
    elif 등급_풍력 in ["매우 추천", "추천"] and 등급_태양광 in ["확인 필요", "비추천"]:
        return "lightblue"
    else:
        return "gray"

agg_df["추천종류"] = agg_df.apply(lambda x: "태양광" if x["태양광_연간_총_발전량(kWh)"] >= x["풍력_연간_총_발전량(kWh)"] else "풍력", axis=1)
agg_df["색상"] = agg_df.apply(lambda x: 추천색상(x["태양광_추천등급"], x["풍력_추천등급"]), axis=1)

# -------------------------------
# 🗺️ 지도 시각화
st.subheader("🗺️ 추천 유휴부지 위치")
map_center = [agg_df["위도"].mean(), agg_df["경도"].mean()]
m = folium.Map(location=map_center, zoom_start=7)

for _, row in agg_df.iterrows():
    folium.Marker(
        location=[row["위도"], row["경도"]],
        tooltip=row["재산 소재지"],
        popup=f"{row['재산 소재지']}\n태양광: {row['태양광_연간_총_발전량(kWh)']:.1f} kWh\n풍력: {row['풍력_연간_총_발전량(kWh)']:.1f} kWh",
        icon=folium.Icon(color=row["색상"])
    ).add_to(m)

legend_html = """
{% macro html(this, kwargs) %}
<div style="
    position: fixed;
    bottom: 50px;
    left: 50px;
    z-index: 9999;
    background-color: white;
    padding: 10px;
    border: 2px solid grey;
    font-size: 14px;    
    color: black;
">
<b>📍 범례 (추천 기준)</b><br>
<span style='color:green'>●</span> 동일 추천 등급<br>
<span style='color:orange'>●</span> 태양광 우세<br>
<span style='color:lightblue'>●</span> 풍력 우세<br>
<span style='color:gray'>●</span> 기타
</div>
{% endmacro %}
"""
legend = MacroElement()
legend._template = Template(legend_html)
m.get_root().add_child(legend)

st_data = st_folium(m, width=1000, height=600)

# -------------------------------
# 📋 핀 클릭 시 상세 출력
if st_data and st_data.get("last_object_clicked_tooltip"):
    clicked = st_data["last_object_clicked_tooltip"]
    st.subheader(f"📌 선택한 유휴부지: {clicked}")
    detail_df = merged[merged["재산 소재지"] == clicked].sort_values("날짜")

    col1, col2 = st.columns(2)
    with col1:
        st.bar_chart(detail_df.set_index("날짜")["태양광_월간_발전량(kWh)"])
    with col2:
        st.bar_chart(detail_df.set_index("날짜")["풍력_월간_발전량(kWh)"])

    st.dataframe(detail_df)

# -------------------------------
# 📈 전체 통계 페이지
st.subheader("📊 전체 유휴부지 통계 (월별 합산 데이터)")
st.dataframe(merged.sort_values(["재산 소재지", "날짜"]))
