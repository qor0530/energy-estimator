# utils/data_loader.py

import pandas as pd
import joblib
import streamlit as st

@st.cache_resource
def load_model_and_features(model_path, feature_path):
    model = joblib.load(model_path)
    features = joblib.load(feature_path)
    return model, features

@st.cache_data
def load_training_data():
    df_solar = pd.read_excel("data/최종_태양광.xlsx")
    df_wind = pd.read_excel("data/최종_풍력.xlsx")
    return df_solar, df_wind

@st.cache_data
def load_idle_sites():
    df_idle = pd.read_excel("data/유휴부지_월별_날씨포함.xlsx")
    df_idle["연"] = df_idle["날짜"].astype(str).str[:4].astype(int)
    df_idle["월"] = df_idle["날짜"].astype(str).str[4:6].astype(int)
    return df_idle
