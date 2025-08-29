# dashboard.py | data(폴더) < crime.csv, cctv.csv, police.csv, martdata.csv>
# =============================================================================
# Streamlit: Seoul Safety Dashboard
#
# 기능 요약:
# - 사이드바: 가격 / 치안 / 거리 페이지 선택
# - 본문: '치안' 선택 시에만 탭(CCTV, 경찰서, 범죄 현황) 표시
# - CCTV/경찰서/범죄 현황: '구'를 멀티셀렉트(가나다순, 기본 전체 선택)로 필터
# - 시각화: plotly.express로만 구성 (연속형 팔레트 사용)
# - '가격' 페이지: MariaDB(room 테이블)에서 데이터 조회 후 산점도/막대/라인/박스 플롯 등 표시
# - '거리' 페이지: 특정 주소와 가장 가까운 마트 계산 및 folium 지도 시각화
# =============================================================================

# ---------------------------------------------------------------------
# [1] 라이브러리 Import
# ---------------------------------------------------------------------
import io
import json
import locale
import re
from math import radians, sin, cos, sqrt, atan2

import folium
import mariadb
import numpy as np
import pandas as pd
import plotly.express as px
import requests
import streamlit as st
from streamlit_folium import st_folium

# ---------------------------------------------------------------------
# [2] 전역 설정 및 상수
# ---------------------------------------------------------------------
# Streamlit 페이지 넓게 설정
st.set_page_config(page_title="Select Dashboard", layout="wide")

# Plotly에서 사용할 연속형 색상 팔레트 목록
PLOTLY_SCALES = [
    "Blues", "Viridis", "Plasma", "Cividis", "Turbo",
    "Teal", "Agsunset", "YlGnBu", "YlOrRd", "IceFire", "Magma"
]

# ---------------------------------------------------------------------
# [3] 공통 헬퍼 함수
# ---------------------------------------------------------------------
def read_csv_safely(path, encodings=("utf-8", "cp949", "euc-kr")):
    """CSV를 여러 인코딩으로 시도하여 안전하게 읽어옵니다."""
    last_err = None
    for enc in encodings:
        try:
            return pd.read_csv(path, encoding=enc)
        except Exception as e:
            last_err = e
    raise last_err

def to_numeric_df(df, cols):
    """쉼표를 제거하고 지정된 컬럼들을 숫자형으로 변환합니다."""
    out = df.copy()
    out[cols] = out[cols].replace({",": ""}, regex=True)
    for c in cols:
        out[c] = pd.to_numeric(out[c], errors="coerce")
    return out

def extract_year_cols(df, include_preinstalled=False):
    """
    '년'이 포함된 컬럼만 추출합니다.
    - include_preinstalled=False: '이전'이 들어간 누계형 컬럼은 제외합니다.
    """
    year_cols = [c for c in df.columns if "년" in str(c)]
    if not include_preinstalled:
        year_cols = [c for c in year_cols if "이전" not in str(c)]
    return year_cols

def police_sum_by_year(df):
    """
    경찰 데이터에서 같은 연도의 세부 컬럼(지구대, 파출소 등)을 합쳐
    '{YYYY}년' 단일 컬럼으로 만들고 원본 세부 컬럼은 제거합니다.
    """
    year_pattern = re.compile(r"(20[0-3]\d)")
    year_groups = {}
    for col in df.columns:
        m = year_pattern.search(str(col))
        if m:
            year = m.group(1)
            year_groups.setdefault(year, []).append(col)

    out = df.copy()
    for year, cols in year_groups.items():
        tmp = out[cols].replace({",": ""}, regex=True)
        for c in cols:
            tmp[c] = pd.to_numeric(tmp[c], errors="coerce")
        out[f"{year}년"] = tmp.sum(axis=1)

    cols_to_drop = [c for cols in year_groups.values() for c in cols]
    out = out.drop(columns=cols_to_drop, errors="ignore")

    def is_year_col(c):
        return bool(year_pattern.search(str(c)))

    id_cols = [c for c in out.columns if not is_year_col(c)]
    year_cols = sorted(
        [c for c in out.columns if is_year_col(c)],
        key=lambda x: int(re.search(r"(20[0-3]\d)", x).group(1))
    )
    return out[id_cols + year_cols]

def apply_sort(df, value_col, order_choice):
    """정렬 옵션(내림/오름/원본)에 따라 데이터프레임을 정렬합니다."""
    if "내림차순" in order_choice:
        return df.sort_values(value_col, ascending=False)
    elif "오름차순" in order_choice:
        return df.sort_values(value_col, ascending=True)
    return df

def sort_korean(items):
    """한글 '가나다' 순으로 정렬합니다."""
    try:
        for loc in ("ko_KR.UTF-8", "Korean_Korea.949", "ko_KR"):
            try:
                locale.setlocale(locale.LC_ALL, loc)
                break
            except Exception:
                pass
        return sorted(items, key=locale.strxfrm)
    except Exception:
        return sorted(items)

def get_room2_data():
    """MariaDB에서 'room' 테이블 데이터를 조회하여 DataFrame으로 반환합니다."""
    try:
        conn = mariadb.connect(
            host='localhost', port=3310, database='bangu',
            user='root', password='1234'
        )
        df = pd.read_sql("SELECT * FROM room", conn)
        conn.close()
        return df
    except Exception as e:
        st.error(f"데이터 조회 실패: {e}")
        return None

def add_day_to_date(s):
    """'YYYY', 'YYYY-MM' 형식의 날짜 문자열을 'YYYY-MM-DD'로 보정합니다."""
    if pd.isna(s):
        return s
    s = str(s).replace('.', '-')
    parts = s.split('-')
    if len(parts) == 1:
        return f"{parts[0]}-01-01"
    elif len(parts) == 2:
        return f"{parts[0]}-{parts[1]}-01"
    return s

def get_scale_list(name: str):
    """이름에 맞는 Plotly 색상 시퀀스를 반환합니다."""
    for color_scale_type in (px.colors.sequential, px.colors.diverging, px.colors.cyclical):
        if hasattr(color_scale_type, name):
            return getattr(color_scale_type, name)
    return px.colors.sequential.Viridis  # Fallback

def make_discrete_from_scale(scale_name: str, n: int):
    """연속형 팔레트를 n개의 이산형 색상 팔레트로 샘플링합니다."""
    base = get_scale_list(scale_name)
    if n <= 0:
        return base
    idx = np.linspace(0, len(base) - 1, n)
    return [base[int(round(i))] for i in idx]

def haversine(lat1, lon1, lat2, lon2):
    """두 지점의 위도/경도를 받아 거리를 미터(m) 단위로 계산합니다."""
    R = 6371000  # 지구 반지름 (미터)
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlon / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c

# ---------------------------------------------------------------------
# [4] 사이드바 메뉴
# ---------------------------------------------------------------------
st.sidebar.header("메뉴")
page = st.sidebar.radio("옵션", ["가격", "치안", "거리"])

# ---------------------------------------------------------------------
# [5] 메인 페이지 라우팅
# ---------------------------------------------------------------------
st.title("셀렉 대시보드")

# ==============================
# 페이지 1: 가격
# ==============================
if page == "가격":
    st.subheader("💰 가격 분석")

    # DB 조회
    df = get_room2_data()
    if df is not None:
        # ===== 전처리 =====
        df['building_type'] = df.get('building_type', pd.Series(index=df.index)).fillna('unknown')
        df['room_living_type'] = df.get('room_living_type', pd.Series(index=df.index)).fillna('unknown')
        if 'completion_date' in df.columns:
            df['completion_date'] = df['completion_date'].apply(add_day_to_date)
            df['completion_date'] = pd.to_datetime(df['completion_date'], errors='coerce')

        # ===== 탭 구성 =====
        tab_scatter, tab_rent = st.tabs(["📈 조건에 따른 월세/보증금 요약", "🏢 건물유형별 월세 요약"])

        # ----------------------------------
        # 탭 1-1: 산점도/라인
        # ----------------------------------
        with tab_scatter:
            LABELS = {
                "exclusive_area": "전용면적(㎡)", "supply_area": "공급면적(㎡)",
                "completion_date": "준공인가일", "built_year": "준공년도",
                "floor": "층", "total_floor": "건물층수",
                "room_count": "방 개수", "bath_count": "욕실 개수", "parking_count": "주차 대수",
                "building_type": "건물유형", "room_living_type": "거주 형태",
                "parking_info": "주차 정보", "main_room_direction": "주실 방향",
                "deposit": "보증금", "rent": "월세",
            }
            x_keys_fixed = [
                "exclusive_area", "supply_area", "completion_date", "built_year",
                "floor", "total_floor", "room_count", "bath_count", "parking_count",
                "building_type", "room_living_type", "parking_info", "main_room_direction",
            ]
            x_keys = [c for c in x_keys_fixed if c in df.columns]
            y_keys = [c for c in ["deposit", "rent"] if c in df.columns]
            hue_keys = [c for c in ["building_type", "room_living_type", "parking_info", "main_room_direction"] if c in df.columns]

            x_map = {LABELS.get(k, k): k for k in x_keys}
            y_map = {LABELS.get(k, k): k for k in y_keys}
            hue_map = {LABELS.get(k, k): k for k in hue_keys}

            x_label = st.selectbox("X축 컬럼", options=sort_korean(list(x_map.keys())), index=None, placeholder="선택하세요", key="price_x_kor")
            y_label = st.selectbox("Y축 컬럼", options=sort_korean(list(y_map.keys())), index=None, placeholder="선택하세요", key="price_y_kor")
            hue_label = st.selectbox("색상 구분 (옵션)", options=["없음"] + sort_korean(list(hue_map.keys())), index=0, key="price_hue_kor")
            chart_type = st.selectbox("차트 유형", ["산점도(기본)", "연도별 중앙월세 추세 (라인)"], index=0, key="price_chart_type")

            x_option = x_map.get(x_label)
            y_option = y_map.get(y_label)
            hue_option = None if hue_label == "없음" else hue_map.get(hue_label)

            df_plot = df.copy()
            if "main_room_direction" in df_plot.columns and (x_option == "main_room_direction" or hue_option == "main_room_direction"):
                df_plot.dropna(subset=["main_room_direction"], inplace=True)
                split_vals = df_plot["main_room_direction"].astype(str).str.split("/", expand=True)
                if split_vals.shape[1] >= 2:
                    df_plot["main_room_direction"] = split_vals.iloc[:, 1]
                    df_plot.dropna(subset=["main_room_direction"], inplace=True)

            if x_option and y_option:
                plot_labels = {k: LABELS.get(k, k) for k in [x_option, y_option, hue_option] if k}

                if chart_type == "산점도(기본)":
                    fig = px.scatter(
                        df_plot, x=x_option, y=y_option, color=hue_option,
                        labels=plot_labels, title=f"<b>{LABELS.get(y_option, y_option)} vs {LABELS.get(x_option, x_option)}</b>"
                    )
                    fig.update_traces(marker=dict(opacity=0.6, size=8))
                    st.plotly_chart(fig, use_container_width=True)
                else:  # 라인 차트
                    if "rent" not in df_plot.columns:
                        st.warning("월세(rent) 컬럼이 없어 추세를 그릴 수 없습니다.")
                    else:
                        year_series = pd.to_numeric(df_plot.get("built_year"), errors="coerce")
                        if year_series is None or year_series.isna().all():
                            year_series = pd.to_datetime(df_plot.get("completion_date"), errors="coerce").dt.year

                        df_line = pd.DataFrame({"연도": year_series, "월세": pd.to_numeric(df_plot["rent"], errors="coerce")})
                        if hue_option:
                            df_line[hue_option] = df_plot[hue_option]
                        df_line.dropna(subset=["연도", "월세"], inplace=True)

                        if df_line.empty:
                            st.info("연도 정보가 부족합니다.")
                        else:
                            group_cols = ["연도"]
                            if hue_option:
                                group_cols.append(hue_option)
                            grp = df_line.groupby(group_cols)["월세"].median().reset_index()

                            fig = px.line(
                                grp, x="연도", y="월세", color=hue_option, markers=True,
                                labels={"연도": "연도", "월세": "중앙 월세", hue_option: LABELS.get(hue_option, hue_option)},
                                title="<b>연도별 중앙 월세 추세</b>"
                            )
                            st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("X축과 Y축을 모두 선택해 주세요.")

        # ----------------------------------
        # 탭 1-2: 건물유형별 월세 요약
        # ----------------------------------
        with tab_rent:
            st.markdown("### 🏢 건물유형별 월세 요약")
            if "building_type" not in df.columns or "rent" not in df.columns:
                st.warning("`building_type` 또는 `rent` 컬럼이 없어 요약 그래프를 표시할 수 없습니다.")
            else:
                df_bt = df[["building_type", "rent"]].copy()
                df_bt["rent"] = pd.to_numeric(df_bt["rent"], errors="coerce")
                df_bt.dropna(subset=["building_type", "rent"], inplace=True)
                
                exclude_pattern = r'^(unknown|다가구\s*\(미등기\)|빌라\s*\(미등기\))$'
                df_bt = df_bt[~df_bt['building_type'].astype(str).str.strip().str.contains(exclude_pattern, na=False, regex=True)]

                if df_bt.empty:
                    st.info("집계할 데이터가 없습니다.")
                else:
                    view_mode = st.radio("보기", ["요약(막대)", "분포(박스)", "분포(바이올린)"], horizontal=True, key="bt_view_mode")
                    
                    if view_mode == "요약(막대)":
                        stat_choice = st.radio("통계 지표", ["평균", "중앙값"], index=0, horizontal=True, key="bt_rent_stat")
                        order_choice = st.radio("정렬", ["내림차순 (높은 → 낮은)", "오름차순 (낮은 → 높은)", "원본순서"], index=0, horizontal=True, key="bt_rent_order")
                        scale_choice = st.selectbox("색상 팔레트", PLOTLY_SCALES, index=PLOTLY_SCALES.index("Blues"), key="bt_rent_scale")
                        
                        y_col = "mean" if stat_choice == "평균" else "median"
                        grouped = df_bt.groupby("building_type")["rent"].agg(['mean', 'median', 'count']).reset_index()
                        
                        if "내림차순" in order_choice: grouped = grouped.sort_values(y_col, ascending=False)
                        elif "오름차순" in order_choice: grouped = grouped.sort_values(y_col, ascending=True)

                        fig_bt = px.bar(
                            grouped, x="building_type", y=y_col, color=y_col, color_continuous_scale=scale_choice,
                            text_auto=".2s", labels={"building_type": "건물유형", y_col: f"월세 ({stat_choice})"},
                            title=f"<b>건물유형별 월세 ({stat_choice})</b>", height=500
                        )
                        fig_bt.update_layout(xaxis_tickangle=-30, plot_bgcolor="white", coloraxis_colorbar_title_text=f"월세({stat_choice})")
                        st.plotly_chart(fig_bt, use_container_width=True)
                    
                    elif view_mode == "분포(박스)":
                        fig_box = px.box(
                            df_bt, x="building_type", y="rent", points="all", height=520,
                            labels={"building_type": "건물유형", "rent": "월세"}, title="<b>건물유형별 월세 분포 (박스)</b>"
                        )
                        fig_box.update_layout(xaxis_tickangle=-20)
                        st.plotly_chart(fig_box, use_container_width=True)
                    
                    else:  # 분포(바이올린)
                        fig_vio = px.violin(
                            df_bt, x="building_type", y="rent", box=True, points="all", height=520,
                            labels={"building_type": "건물유형", "rent": "월세"}, title="<b>건물유형별 월세 분포 (바이올린)</b>"
                        )
                        fig_vio.update_layout(xaxis_tickangle=-20)
                        st.plotly_chart(fig_vio, use_container_width=True)

# ==============================
# 페이지 2: 치안
# ==============================
elif page == "치안":
    st.subheader("🛡️ 치안 분석")
    tab_cctv, tab_police, tab_crime = st.tabs(["📹 CCTV", "👮 경찰서", "⛓️ 범죄 발생 현황"])

    # ------------------------------
    # 탭 2-1: CCTV
    # ------------------------------
    with tab_cctv:
        st.subheader("CCTV 지표")
        try:
            df_cctv_raw = read_csv_safely("cctv.csv")
        except Exception as e:
            st.error(f"CCTV 데이터를 불러올 수 없습니다(cctv.csv): {e}")
            st.stop()
        
        st.markdown("**원본 미리보기**")
        st.dataframe(df_cctv_raw.head(), use_container_width=True)

        cctv_year_cols = extract_year_cols(df_cctv_raw, include_preinstalled=False)
        cctv_drop_cols = [c for c in ["총 계", "총계", "합계"] if c in df_cctv_raw.columns]
        df_cctv = df_cctv_raw.drop(columns=cctv_drop_cols, errors="ignore")
        df_cctv = to_numeric_df(df_cctv, cctv_year_cols)

        if "구분" in df_cctv.columns:
            df_cctv = df_cctv[df_cctv["구분"] != "계"]
            cctv_districts = sort_korean(df_cctv["구분"].dropna().unique().tolist())
            cctv_selected = st.multiselect("구 선택", options=cctv_districts, default=cctv_districts, key="cctv_gu_select")
            df_cctv_view = df_cctv[df_cctv["구분"].isin(cctv_selected)] if cctv_selected else pd.DataFrame()
        else:
            st.warning("'구분' 컬럼이 없어 구 선택 필터를 표시할 수 없습니다.")
            df_cctv_view = df_cctv

        if df_cctv_view.empty:
            st.info("선택한 구가 없습니다. 상단에서 구를 선택해 주세요.")
        else:
            st.markdown("### 1) 연도별 총합")
            cctv_scale_year = st.selectbox("팔레트", PLOTLY_SCALES, index=PLOTLY_SCALES.index("Blues"), key="cctv_year_scale")
            cctv_yearly_sum = df_cctv_view[cctv_year_cols].sum()
            fig_cctv_year = px.bar(
                x=cctv_yearly_sum.index, y=cctv_yearly_sum.values, labels={"x": "연도", "y": "대수"},
                color=cctv_yearly_sum.values, color_continuous_scale=cctv_scale_year,
                title="연도별 총 CCTV 대수 (선택한 구 기준)"
            )
            fig_cctv_year.update_layout(xaxis_tickangle=-45, plot_bgcolor="white", coloraxis_colorbar_title_text="대수")
            st.plotly_chart(fig_cctv_year, use_container_width=True)

            st.markdown("### 2) 구별 총 CCTV 대수")
            if "구분" in df_cctv_view.columns:
                df_total = df_cctv_view.copy()
                df_total["총합"] = df_total[cctv_year_cols].sum(axis=1)
                
                cctv_order_choice = st.radio("정렬", ["내림차순(많은→적은)", "오름차순(적은→많은)", "원본순서"], horizontal=True, key="cctv_order")
                cctv_scale_total = st.selectbox("팔레트", PLOTLY_SCALES, index=PLOTLY_SCALES.index("Viridis"), key="cctv_total_scale")
                df_total = apply_sort(df_total, "총합", cctv_order_choice)

                fig_total = px.bar(
                    df_total, x="구분", y="총합", color="총합", color_continuous_scale=cctv_scale_total,
                    title="구별 CCTV 총 대수 (선택한 구 기준)", labels={"구분": "구", "총합": "총 CCTV 대수"}
                )
                fig_total.update_layout(xaxis_tickangle=-45, plot_bgcolor="white", coloraxis_colorbar_title_text="총 CCTV 대수")
                st.plotly_chart(fig_total, use_container_width=True)

    # ------------------------------
    # 탭 2-2: 경찰서
    # ------------------------------
    with tab_police:
        st.subheader("경찰서 지표")
        try:
            df_pol_raw = read_csv_safely("police.csv")
        except Exception as e:
            st.error(f"경찰 데이터를 불러올 수 없습니다(police.csv): {e}")
            st.stop()

        st.markdown("**원본 미리보기**")
        st.dataframe(df_pol_raw.head(), use_container_width=True)

        df_pol = police_sum_by_year(df_pol_raw)
        st.markdown("**연도별 합친 데이터(미리보기)**")
        st.dataframe(df_pol.head(), use_container_width=True)

        id_col = "구분" if "구분" in df_pol.columns else st.selectbox("식별 컬럼 선택", sort_korean([c for c in df_pol.columns if "년" not in c]), key="pol_fallback_id")
        
        if id_col:
            pol_districts = sort_korean(df_pol[id_col].dropna().unique().astype(str).tolist())
            pol_selected = st.multiselect("항목 선택", options=pol_districts, default=pol_districts, key="pol_gu_select")
            df_pol_view = df_pol[df_pol[id_col].astype(str).isin(pol_selected)] if pol_selected else pd.DataFrame()
        else:
            df_pol_view = pd.DataFrame()

        if df_pol_view.empty:
            st.info("선택한 항목이 없습니다. 상단에서 항목을 선택해 주세요.")
        else:
            year_cols = [c for c in df_pol_view.columns if "년" in c]
            if year_cols:
                pol_year_choice = st.selectbox("연도 선택", year_cols, index=len(year_cols)-1, key="pol_year")
                pol_scale = st.selectbox("팔레트", PLOTLY_SCALES, index=PLOTLY_SCALES.index("Blues"), key="pol_scale")
                
                plot_df = df_pol_view[[id_col, pol_year_choice]].copy()
                plot_df[pol_year_choice] = pd.to_numeric(plot_df[pol_year_choice], errors="coerce")

                pol_order_choice = st.radio("정렬", ["내림차순(많은→적은)", "오름차순(적은→많은)", "원본순서"], horizontal=True, key="pol_order")
                plot_df = apply_sort(plot_df, pol_year_choice, pol_order_choice)

                fig_pol = px.bar(
                    plot_df, y=id_col, x=pol_year_choice, color=pol_year_choice,
                    color_continuous_scale=pol_scale, title=f"{pol_year_choice} {id_col}별 합계",
                    labels={id_col: id_col, pol_year_choice: "합계"}, height=700
                )
                fig_pol.update_layout(plot_bgcolor="white", coloraxis_colorbar_title_text="합계")
                st.plotly_chart(fig_pol, use_container_width=True)
            else:
                st.info("연도 컬럼을 찾지 못했습니다. 원본 컬럼명을 확인해 주세요.")

    # ------------------------------
    # 탭 2-3: 범죄 발생 현황
    # ------------------------------
    with tab_crime:
        st.subheader("연도별 자치구 범죄 발생 현황")
        try:
            df_crime = pd.read_csv("crime.csv")
        except Exception as e:
            st.error(f"범죄 데이터를 불러올 수 없습니다(crime.csv): {e}")
            st.stop()
        
        if "자치구별" not in df_crime.columns:
            st.error("'자치구별' 컬럼을 찾을 수 없습니다.")
            st.stop()

        # --- 애니메이션 막대 그래프 ---
        all_districts = sort_korean(df_crime["자치구별"].dropna().astype(str).unique().tolist())
        selected_districts = st.multiselect("자치구 선택", options=all_districts, default=all_districts, key="crime_gu_select")
        scale_name = st.selectbox("팔레트 선택", options=PLOTLY_SCALES, index=PLOTLY_SCALES.index("Blues"), key="crime_scale_select")

        df_view_crime = df_crime[df_crime["자치구별"].astype(str).isin(selected_districts)] if selected_districts else pd.DataFrame()
        
        if not df_view_crime.empty:
            year_cols = [c for c in df_view_crime.columns if c.endswith("년")]
            for col in year_cols:
                df_view_crime[col] = pd.to_numeric(df_view_crime[col], errors='coerce').fillna(0).astype(int)

            df_long = pd.melt(df_view_crime, id_vars=['자치구별'], var_name='년도', value_name='발생 횟수')
            df_long.sort_values(by=['년도', '발생 횟수'], ascending=[True, False], inplace=True)
            
            n_colors = max(len(selected_districts), 1)
            color_seq = make_discrete_from_scale(scale_name, n_colors)

            fig_anim = px.bar(
                df_long, x='자치구별', y='발생 횟수', color='자치구별', animation_frame='년도',
                title='<b>년도별 서울시 자치구 범죄 발생 건수</b>', labels={'자치구별': '자치구', '발생 횟수': '발생 건수'},
                color_discrete_sequence=color_seq
            )
            if not df_long.empty:
                fig_anim.update_yaxes(range=[0, df_long['발생 횟수'].max() * 1.2])
            fig_anim.update_layout(
                title_x=0.5, font=dict(size=12),
                xaxis={'categoryorder': 'array', 'categoryarray': selected_districts}
            )
            if fig_anim.layout.updatemenus:
                fig_anim.layout.updatemenus[0].buttons[0].args[1]['frame']['duration'] = 1000
                fig_anim.layout.updatemenus[0].buttons[0].args[1]['transition']['duration'] = 500
            st.plotly_chart(fig_anim, use_container_width=True)
            st.divider()

        # --- 지도 히트맵 ---
        st.subheader("서울시 자치구별 연도별 범죄 데이터 히트맵")
        seoul_geojson_url = "https://raw.githubusercontent.com/southkorea/seoul-maps/master/kostat/2013/json/seoul_municipalities_geo_simple.json"
        
        year_list = [c for c in df_crime.columns if c.endswith("년")]
        color_map_list = ['YlOrRd', 'YlGnBu', 'BuPu', 'GnBu', 'PuRd', 'RdPu', 'OrRd', 'BuGn', 'YlGn']
        
        col1, col2 = st.columns([1, 1])
        with col1:
            selected_year = st.selectbox('확인하고 싶은 연도를 선택하세요', year_list, index=len(year_list) - 1)
        with col2:
            selected_color = st.selectbox('히트맵 색상을 선택하세요', color_map_list)

        st.markdown(f"#### **{selected_year}** 서울시 자치구별 범죄 발생 횟수 히트맵")
        m = folium.Map(location=[37.5665, 126.9780], zoom_start=11, tiles="cartodbpositron",
                       zoom_control=False, scrollWheelZoom=False, dragging=False)
        
        min_val, max_val = df_crime[selected_year].min(), df_crime[selected_year].max()
        start_bin = int(np.floor(min_val / 1000) * 1000)
        end_bin = int(np.ceil(max_val / 1000) * 1000)
        num_bins = max(5, min(7, (end_bin - start_bin) // 1000 + 1))
        bins = list(np.linspace(start_bin, end_bin, num=num_bins, dtype=int))
        if len(set(bins)) < 3:
             start_bin, end_bin = int(np.floor(min_val / 100) * 100), int(np.ceil(max_val / 100) * 100)
             num_bins = max(5, min(7, (end_bin - start_bin) // 100 + 1))
             bins = list(np.linspace(start_bin, end_bin, num=num_bins, dtype=int))
        final_bins = sorted(list(set(bins)))

        folium.Choropleth(
            geo_data=seoul_geojson_url, data=df_crime, columns=['자치구별', selected_year],
            key_on='feature.properties.name', fill_color=selected_color,
            fill_opacity=0.8, line_opacity=0.3, legend_name=f'{selected_year} 범죄 발생 건수', bins=final_bins
        ).add_to(m)

        geo_data = requests.get(seoul_geojson_url).json()
        crime_data = df_crime.set_index('자치구별')[selected_year].to_dict()
        for feature in geo_data['features']:
            gu_name = feature['properties']['name']
            value = crime_data.get(gu_name, 0)
            rounded_value = int(round(value, -2))
            
            coords = feature['geometry']['coordinates']
            if feature['geometry']['type'] == 'MultiPolygon':
                coords = max(coords, key=lambda polygon: len(polygon[0]))
            
            lon, lat = zip(*coords[0])
            centroid = [sum(lat) / len(lat), sum(lon) / len(lon)]
            
            folium.Marker(
                location=centroid,
                icon=folium.DivIcon(
                    icon_size=(150, 40), icon_anchor=(75, 20),
                    html=f'<div style="font-size: 9pt; font-weight: bold; color: #333; text-align: center; width: 150px; text-shadow: -1px 0 white, 0 1px white, 1px 0 white, 0 -1px white;">{gu_name}<br>{rounded_value:,}</div>'
                )
            ).add_to(m)

        st_folium(m, use_container_width=True, height=600)
        
        st.markdown("--- \n ### 원본 데이터")
        st.dataframe(df_crime.set_index('자치구별'))

# ==============================
# 페이지 3: 거리
# ==============================
elif page == "거리":
    st.subheader("📍 거리 분석")

    villa_address = "서울특별시 영등포구 영등포동2가 34-136"
    villa_latitude = 37.518658826456
    villa_longitude = 126.90620617355
    st.write(f"**기준 주소**: {villa_address}")

    try:
        stores_df = pd.read_csv("martdata.csv")
        stores_df.dropna(subset=['latitude', 'longitude'], inplace=True)
    except Exception as e:
        st.error(f"마트 데이터를 불러오는 중 에러가 발생했습니다: {e}")
        stores_df = pd.DataFrame()

    if not stores_df.empty:
        closest_store, min_distance = None, float('inf')
        for _, row in stores_df.iterrows():
            d = haversine(villa_latitude, villa_longitude, row['latitude'], row['longitude'])
            if d < min_distance:
                min_distance, closest_store = d, row
        if closest_store is not None:
            st.info(f"가장 가까운 마트는 **{closest_store['name']}** 입니다. (거리: 약 {min_distance:,.0f} 미터)")

    m = folium.Map(location=[villa_latitude, villa_longitude], zoom_start=17)
    folium.Marker(
        location=[villa_latitude, villa_longitude], popup=f'**{villa_address}**',
        icon=folium.Icon(color='red', icon='home', prefix='fa')
    ).add_to(m)

    if not stores_df.empty and closest_store is not None:
        for _, row in stores_df.iterrows():
            is_closest = row.equals(closest_store)
            icon_color = 'green' if is_closest else 'blue'
            icon_shape = 'star' if is_closest else 'shopping-cart'
            popup_text = f"**가장 가까운 마트:** {row['name']}" if is_closest else f"**{row['name']}**"
            
            folium.Marker(
                location=[row['latitude'], row['longitude']], popup=popup_text,
                icon=folium.Icon(color=icon_color, icon=icon_shape, prefix='fa')
            ).add_to(m)

    st_folium(m, width='100%', height=800)