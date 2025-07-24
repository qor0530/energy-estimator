# visualization/map_utils.py

import folium
from branca.element import Template, MacroElement
from folium.plugins import BeautifyIcon

# 지역별 SMP 단가
SMP_DICT = {
    "육지": 123.06,
    "제주": 123.88
}

# 주소에서 지역 구분 함수
def check_region(address):
    if str(address).startswith("제주특별자치도"):
        return "제주"
    else:
        return "육지"

# 예상 수익 계산 함수
def calculate_revenue(row, colname):
    region = check_region(row["재산 소재지"])
    smp_price = SMP_DICT.get(region, 0)
    return row[colname] * smp_price

# 색상 결정 로직 (선택된 발전 종류에 따라 동작)
def 추천색상(등급_태양광, 등급_풍력, selected_sources):
    if selected_sources == ["태양광"]:
        return 추천색상_단일(등급_태양광)
    elif selected_sources == ["풍력"]:
        return 추천색상_단일(등급_풍력)
    else:
        # 둘 다 같은 경우 -> 높은 등급 기준으로 색상
        if 등급_태양광 == 등급_풍력:
            return 추천색상_단일(등급_태양광)

        # 하나라도 "매우 추천" 또는 "추천"이 있으면 해당 색
        우선순위 = {"매우 추천": 3, "추천": 2, "확인 필요": 1, "비추천": 0}
        등급값 = {
            "태양광": 우선순위.get(등급_태양광, 0),
            "풍력": 우선순위.get(등급_풍력, 0)
        }

        if 등급값["태양광"] >= 2 or 등급값["풍력"] >= 2:
            # 더 높은 등급 쪽으로 색상 결정
            if 등급값["태양광"] >= 등급값["풍력"]:
                return 추천색상_단일(등급_태양광)
            else:
                return 추천색상_단일(등급_풍력)

        # 둘 다 낮은 경우 회색
        return "gray"

def 추천색상_단일(등급):
    return {
        "매우 추천": "green",
        "추천": "orange",
        "확인 필요": "lightblue",
        "비추천": "gray"
    }.get(등급, "gray")

# folium 지도 생성 함수 (BeautifyIcon 적용)
def create_site_map(df, selected_sources):
    map_center = [df["위도"].mean(), df["경도"].mean()]
    m = folium.Map(location=map_center, zoom_start=7)

    for _, row in df.iterrows():
        popup_text = f"""
        <div style='font-size:14px; line-height:1.6;'>
            <b>{row['재산 소재지']}</b><br>
            <b>☀️ 태양광</b><br>
            • 발전량: {row['태양광_연간_총_발전량(kWh)']:.1f} kWh<br>
            • 추천등급: <span style='color:darkorange'>{row['태양광_추천등급']}</span><br>
            • 예상수익: {row.get('태양광_예상수익(원)', 0):,.0f} 원<br>
            <hr style='margin:4px 0;'>
            <b>💨 풍력</b><br>
            • 발전량: {row['풍력_연간_총_발전량(kWh)']:.1f} kWh<br>
            • 추천등급: <span style='color:darkblue'>{row['풍력_추천등급']}</span><br>
            • 예상수익: {row.get('풍력_예상수익(원)', 0):,.0f} 원
        </div>
        """

        icon_type = "sun" if row.get("추천종류", "") == "태양광" else "leaf"
        icon = BeautifyIcon(
            icon=icon_type,
            icon_shape="marker",
            background_color=추천색상(
                row["태양광_추천등급"],
                row["풍력_추천등급"],
                selected_sources
            ),
            border_color="white",
            text_color="white",
            number="",
            spin=False
        )

        folium.Marker(
            location=[row["위도"], row["경도"]],
            tooltip=row["재산 소재지"],
            popup=folium.Popup(popup_text, max_width=300),
            icon=icon
        ).add_to(m)

    m.get_root().add_child(get_map_legend(selected_sources))

    return m

# 범례 생성 함수 (선택된 발전 종류에 따라 조정)
def get_map_legend(selected_sources):
    if selected_sources == ["태양광"]:
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
        <b>📍 범례 (태양광 추천 기준)</b><br>
        <span style='color:green'>●</span> 매우 추천<br>
        <span style='color:orange'>●</span> 추천<br>
        <span style='color:lightblue'>●</span> 확인 필요<br>
        <span style='color:gray'>●</span> 비추천
        </div>
        {% endmacro %}
        """
    elif selected_sources == ["풍력"]:
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
        <b>📍 범례 (풍력 추천 기준)</b><br>
        <span style='color:green'>●</span> 매우 추천<br>
        <span style='color:orange'>●</span> 추천<br>
        <span style='color:lightblue'>●</span> 확인 필요<br>
        <span style='color:gray'>●</span> 비추천
        </div>
        {% endmacro %}
        """
    else:
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
        <b>📍 범례 (추천 비교 기준)</b><br>
        <span style='color:green'>●</span> 동일 등급 또는 우수 등급 우세<br>
        <span style='color:orange'>●</span> 태양광 우세<br>
        <span style='color:lightblue'>●</span> 풍력 우세<br>
        <span style='color:gray'>●</span> 기타 (모두 낮은 등급)
        </div>
        {% endmacro %}
        """

    legend = MacroElement()
    legend._template = Template(legend_html)
    return legend