# =============================================================================
# Streamlit: Seoul Safety Dashboard
#  - 사이드바: 가격 / 치안 / 거리
#  - 본문: '치안' 선택 시에만 탭(📹 CCTV, 👮 경찰서) 표시
#  - CCTV/경찰서 모두 '구'를 멀티셀렉트(가나다순, 기본 전체 선택)로 필터
#  - 시각화는 plotly.express로만 구성 (연속형 팔레트)
#  - '가격' 페이지에는 MariaDB(room 테이블)에서 데이터 조회 후 산점도
#  - 경찰서 수 그래프(height=700)로 세로 공간 확대
#  - ⚠️ 분위수(상한구간) 슬라이더 전면 제거
# =============================================================================

import io
import re
import pandas as pd
import streamlit as st
import plotly.express as px

st.set_page_config(page_title="Select Dashboard", layout="wide")

# ---------------------------------------------------------------------
# [Helpers] 공통 유틸 함수
# ---------------------------------------------------------------------
def read_csv_safely(path, encodings=("utf-8", "cp949", "euc-kr")):
    """CSV를 인코딩 후보 목록을 바꿔가며 안전하게 읽기."""
    last_err = None
    for enc in encodings:
        try:
            return pd.read_csv(path, encoding=enc)
        except Exception as e:
            last_err = e
    raise last_err


def to_numeric_df(df, cols):
    """쉼표 제거 후, 지정한 컬럼들을 숫자형으로 변환."""
    out = df.copy()
    out[cols] = out[cols].replace({",": ""}, regex=True)
    for c in cols:
        out[c] = pd.to_numeric(out[c], errors="coerce")
    return out


def extract_year_cols(df, include_preinstalled=False):
    """
    '년'이 포함된 컬럼만 추출 (연도형 컬럼 후보).
    - include_preinstalled=False 이면 '이전' 이 들어간 누계형 컬럼은 제외
    """
    year_cols = [c for c in df.columns if "년" in str(c)]
    if not include_preinstalled:
        year_cols = [c for c in year_cols if "이전" not in str(c)]
    return year_cols


def police_sum_by_year(df):
    """
    (경찰 데이터) 같은 연도의 지구대/파출소/치안센터 등 세부 컬럼을 합쳐
    '{YYYY}년' 단일 컬럼으로 만들고 원본 세부 컬럼은 제거.
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
    """정렬 옵션(내림/오름/원본)에 따라 정렬 적용."""
    if order_choice == "내림차순(많은→적은)":
        return df.sort_values(value_col, ascending=False)
    elif order_choice == "오름차순(적은→많은)":
        return df.sort_values(value_col, ascending=True)
    return df


def sort_korean(items):
    """한글 '가나다' 순 정렬 (로케일 미지원 환경에서는 일반 정렬 폴백)."""
    try:
        import locale
        for loc in ("ko_KR.UTF-8", "Korean_Korea.949", "ko_KR"):
            try:
                locale.setlocale(locale.LC_ALL, loc)
                break
            except Exception:
                pass
        return sorted(items, key=locale.strxfrm)
    except Exception:
        return sorted(items)


# plotly 연속형 팔레트 목록
PLOTLY_SCALES = [
    "Blues", "Viridis", "Plasma", "Cividis", "Turbo",
    "Teal", "Agsunset", "YlGnBu", "YlOrRd", "IceFire", "Magma"
]

# ---------------------------------------------------------------------
# [Sidebar] 메뉴
# ---------------------------------------------------------------------
st.sidebar.header("메뉴")
page = st.sidebar.radio("옵션", ["가격", "치안", "거리"])

# ---------------------------------------------------------------------
# [Main] 페이지 라우팅
# ---------------------------------------------------------------------
st.title("셀렉 대시보드")

# ==============================
# 1) 가격
# ==============================
if page == "가격":
    st.subheader("💰 가격 분석")

    # mariadb는 설치 환경에 따라 없을 수 있으므로 페이지 내부에서 import
    try:
        import mariadb
    except Exception as e:
        st.error(f"mariadb 모듈이 필요합니다. 설치 후 다시 시도하세요. (pip install mariadb)\n에러: {e}")
        st.stop()

    def get_room2_data():
        """MariaDB에서 room 테이블 전체 데이터를 조회하여 DataFrame으로 반환."""
        try:
            conn = mariadb.connect(
                host='localhost',
                port=3310,
                database='bangu',
                user='root',
                password='1234'
            )
            df = pd.read_sql("SELECT * FROM room", conn)
            conn.close()
            return df
        except Exception as e:
            st.error(f"데이터 조회 실패: {e}")
            return None

    def add_day_to_date(s):
        """날짜 문자열 보정: 'YYYY' → 'YYYY-01-01', 'YYYY-MM' → 'YYYY-MM-01'."""
        if pd.isna(s):
            return s
        s = str(s).replace('.', '-')
        parts = s.split('-')
        if len(parts) == 1:
            return f"{parts[0]}-01-01"
        elif len(parts) == 2:
            return f"{parts[0]}-{parts[1]}-01"
        return s

    # DB 조회
    df = get_room2_data()
    if df is not None:
        # ===== 전처리 (기존 그대로) =====
        df['building_type'] = df.get('building_type', pd.Series(index=df.index)).fillna('unknown')
        df['room_living_type'] = df.get('room_living_type', pd.Series(index=df.index)).fillna('unknown')
        if 'completion_date' in df.columns:
            df['completion_date'] = df['completion_date'].apply(add_day_to_date)
            df['completion_date'] = pd.to_datetime(df['completion_date'], errors='coerce')

        # ===== 탭 구성 =====
        tab_scatter, tab_rent = st.tabs(["📈 조건에 따른 월세/보증금 요약", "🏢 건물유형별 월세 요약"])

        # ------------------------------------------------------------------
        # 📈 산점도 탭
        # ------------------------------------------------------------------
        with tab_scatter:
            # 표시용 한글 라벨 매핑
            LABELS = {
                "exclusive_area": "전용면적(㎡)",
                "completion_date": "준공인가일",
                "deposit": "보증금",
                "rent": "월세",
                "building_type": "건물유형",
                "room_living_type": "거주 형태",
                "parking_info": "주차 정보",
                "main_room_direction": "주실 방향",
            }

            # 존재하는 컬럼만 대상
            x_keys = [c for c in ['exclusive_area', 'completion_date'] if c in df.columns]
            y_keys = [c for c in ['deposit', 'rent'] if c in df.columns]
            hue_keys = [c for c in ['building_type','room_living_type','parking_info','main_room_direction'] if c in df.columns]

            # label <-> key 매핑 생성
            x_map = {LABELS.get(k, k): k for k in x_keys}
            y_map = {LABELS.get(k, k): k for k in y_keys}
            hue_map = {LABELS.get(k, k): k for k in hue_keys}

            # 선택 UI (한국어 표기)
            x_label = st.selectbox(
                'X축 컬럼',
                options=list(x_map.keys()),
                index=None,
                placeholder="선택하세요",
                key="price_x_kor",
            )
            y_label = st.selectbox(
                'Y축 컬럼',
                options=list(y_map.keys()),
                index=None,
                placeholder="선택하세요",
                key="price_y_kor",
            )
            hue_label = st.selectbox(
                '색상 구분 (옵션)',
                options=['없음'] + list(hue_map.keys()),
                index=0,
                key="price_hue_kor",
            )

            # 내부적으로 원래 컬럼명으로 변환
            x_option = x_map.get(x_label) if x_label else None
            y_option = y_map.get(y_label) if y_label else None
            hue_option = None if hue_label == '없음' else hue_map[hue_label]

            if (x_option is not None) and (y_option is not None):
                # 축/범례에 표시될 한국어 레이블 매핑
                labels_kor = {
                    x_option: LABELS.get(x_option, x_option),
                    y_option: LABELS.get(y_option, y_option),
                }
                if hue_option is not None:
                    labels_kor[hue_option] = LABELS.get(hue_option, hue_option)

                # 그래프 제목도 한국어로
                title_txt = f"<b>{labels_kor[y_option]} vs {labels_kor[x_option]}</b>"

                fig = px.scatter(
                    data_frame=df,
                    x=x_option,
                    y=y_option,
                    color=hue_option if hue_option is not None else None,
                    labels=labels_kor,              # ⬅️ 축/범례/호버에 적용될 한국어 라벨
                    title=title_txt,
                )

                # 축 제목/범례 제목 한국어로 확실히 지정
                fig.update_layout(
                    xaxis_title=labels_kor[x_option],
                    yaxis_title=labels_kor[y_option],
                )
                if hue_option is not None:
                    fig.update_layout(legend_title_text=labels_kor[hue_option])

                fig.update_traces(marker=dict(opacity=0.6, size=8))
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("X축과 Y축을 모두 선택해 주세요.")


        # ------------------------------------------------------------------
        # 🏢 건물유형별 월세 요약 탭
        # ------------------------------------------------------------------
        with tab_rent:
            st.markdown("### 🏢 건물유형별 월세 요약")

            if "building_type" not in df.columns or "rent" not in df.columns:
                st.warning("`building_type` 또는 `rent` 컬럼이 없어 요약 그래프를 표시할 수 없습니다.")
            else:
                df_bt = df[["building_type", "rent"]].copy()
                df_bt["rent"] = pd.to_numeric(df_bt["rent"], errors="coerce")
                df_bt = df_bt.dropna(subset=["building_type", "rent"])

                # ✅ 여기 추가: 미등기·unknown 제외
                exclude_pattern = r'^(unknown|다가구\s*\(미등기\)|빌라\s*\(미등기\))$'
                df_bt = df_bt[~df_bt['building_type'].astype(str).str.strip().str.contains(exclude_pattern, na=False)]

                if df_bt.empty:
                    st.info("집계할 데이터가 없습니다.")
                else:
                    # 통계 선택 + 정렬 + 팔레트
                    stat_choice = st.radio("통계 지표", ["평균", "중앙값"], index=0, horizontal=True, key="bt_rent_stat")
                    order_choice = st.radio("정렬", ["내림차순 (높은 → 낮은)", "오름차순 (낮은 → 높은)", "원본순서"], index=0, horizontal=True, key="bt_rent_order")
                    scale_choice = st.selectbox("색상 팔레트", PLOTLY_SCALES, index=PLOTLY_SCALES.index("Blues"), key="bt_rent_scale")

                    # 집계
                    grouped = (
                        df_bt.groupby("building_type")["rent"]
                        .agg(mean="mean", median="median", count="count")
                        .reset_index()
                    )

                    y_col = "mean" if stat_choice == "평균" else "median"

                    # 정렬 적용
                    if order_choice == "내림차순 (높은 → 낮은)":
                        grouped = grouped.sort_values(y_col, ascending=False)
                    elif order_choice == "오름차순 (낮은 → 높은)":
                        grouped = grouped.sort_values(y_col, ascending=True)
                    # "원본순서"는 그대로 둠

                    # 그래프
                    fig_bt = px.bar(
                        grouped,
                        x="building_type",
                        y=y_col,
                        color=y_col,
                        color_continuous_scale=scale_choice,
                        text_auto=".2s",
                        labels={"building_type": "건물유형", y_col: f"월세 ({stat_choice})", "count": "표본 수"},
                        title=f"<b>건물유형별 월세 ({stat_choice})</b>",
                        height=500,
                    )
                    fig_bt.update_layout(
                        xaxis_tickangle=-30,
                        plot_bgcolor="white",
                        coloraxis_colorbar=dict(title=f"월세({stat_choice})"),
                    )
                    st.plotly_chart(fig_bt, use_container_width=True)

# ==============================
# 2) 거리
# ==============================
elif page == "거리":
    st.subheader("📍 거리 분석")

    # 필요한 라이브러리
    import folium
    from streamlit_folium import st_folium
    from math import radians, sin, cos, sqrt, atan2

    # --- 1) 빌라 정보 & UI ---
    st.markdown("### 지도에 영등포구 주소 표시하기")

    # 사용자가 제공한 빌라 위경도
    villa_address = "서울특별시 영등포구 영등포동2가 34-136"
    villa_latitude = 37.518658826456
    villa_longitude = 126.90620617355

    st.write(f"**주소**: {villa_address}")
    st.write(f"**위도**: {villa_latitude}")
    st.write(f"**경도**: {villa_longitude}")

    # --- 2) martdata.csv 읽기 ---
    try:
        stores_df = pd.read_csv("martdata.csv")  # 필요 시 'data/martdata.csv'로 변경
        st.success("대규모점포 데이터를 성공적으로 불러왔습니다.")
        # 위도/경도 없는 행 제거
        stores_df = stores_df.dropna(subset=['latitude', 'longitude']).copy()
        st.write(f"지도에 표시될 유효한 데이터 수: **{len(stores_df)}**개")
    except FileNotFoundError:
        st.error("`martdata.csv` 파일을 찾을 수 없습니다. 파일을 업로드하거나 올바른 경로에 위치시켜주세요.")
        stores_df = pd.DataFrame()
    except Exception as e:
        st.error(f"데이터를 불러오는 중 에러가 발생했습니다: {e}")
        stores_df = pd.DataFrame()

    # --- 3) 가장 가까운 마트 계산 (Haversine) ---
    def haversine(lat1, lon1, lat2, lon2):
        R = 6371000  # m
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlon / 2)**2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))
        return R * c

    closest_store, min_distance = None, float('inf')
    if not stores_df.empty:
        for _, row in stores_df.iterrows():
            d = haversine(villa_latitude, villa_longitude, row['latitude'], row['longitude'])
            if d < min_distance:
                min_distance, closest_store = d, row

        if closest_store is not None:
            st.info(f"가장 가까운 마트는 **{closest_store['name']}** 입니다. (거리: 약 {min_distance:,.0f} 미터)")

    # --- 4) Folium 지도 표시 ---
    m = folium.Map(location=[villa_latitude, villa_longitude], zoom_start=17)

    # 빌라(빨간 집 아이콘)
    folium.Marker(
        location=[villa_latitude, villa_longitude],
        popup=f'**{villa_address}**',
        icon=folium.Icon(color='red', icon='home', prefix='fa')
    ).add_to(m)

    # 마트 마커
    if not stores_df.empty:
        for _, row in stores_df.iterrows():
            if closest_store is not None and row.equals(closest_store):
                # 가장 가까운 마트: 초록 별
                icon = folium.Icon(color='green', icon='star', prefix='fa')
                popup = f"**가장 가까운 마트:** {row['name']}"
            else:
                # 그 외 마트: 파란 쇼핑카트
                icon = folium.Icon(color='blue', icon='shopping-cart', prefix='fa')
                popup = f"**{row['name']}**"

            folium.Marker(
                location=[row['latitude'], row['longitude']],
                popup=popup,
                icon=icon
            ).add_to(m)

    # 지도 출력
    st_folium(m, width=1200, height=800)


# ==============================
# 3) 치안
# ==============================
elif page == "치안":
    st.subheader("🛡️ 치안 분석")

    # -----------------------------------------------------------------
    # 탭: CCTV / 경찰서  (치안에서만 표시)
    # -----------------------------------------------------------------
    tab_cctv, tab_police, tab_crime = st.tabs(["📹 CCTV", "👮 경찰서", "⛓️범죄 발생 현황"])

    # ------------------------------
    # (탭) 📹 CCTV
    # ------------------------------
    with tab_cctv:
        st.subheader("CCTV 지표")

        # CCTV CSV 읽기
        try:
            df_cctv_raw = read_csv_safely("cctv.csv")
        except Exception as e:
            st.error(f"CCTV 데이터를 불러올 수 없습니다(cctv.csv): {e}")
            st.stop()

        st.markdown("**원본 미리보기**")
        st.dataframe(df_cctv_raw.head(), use_container_width=True)

        # 연도형 컬럼 + 숫자 변환
        cctv_year_cols = extract_year_cols(df_cctv_raw, include_preinstalled=False)
        cctv_drop_cols = [c for c in ["총 계","총계","합계"] if c in df_cctv_raw.columns]
        df_cctv = df_cctv_raw.drop(columns=cctv_drop_cols, errors="ignore")
        df_cctv = to_numeric_df(df_cctv, cctv_year_cols)

        # '계' 행 제거
        if "구분" in df_cctv.columns:
            df_cctv = df_cctv[df_cctv["구분"] != "계"]

        # 구 멀티셀렉트(가나다순) — 기본: 전체 선택
        if "구분" in df_cctv.columns:
            cctv_districts = sort_korean(df_cctv["구분"].dropna().unique().tolist())
            cctv_selected = st.multiselect(
                "구 선택 (여러 개 선택 가능)",
                options=cctv_districts,
                default=cctv_districts,
                key="cctv_gu_select"
            )
            df_cctv_view = df_cctv[df_cctv["구분"].isin(cctv_selected)] if cctv_selected else df_cctv.iloc[0:0]
        else:
            st.warning("'구분' 컬럼이 없어 구 선택 필터를 표시할 수 없습니다.")
            df_cctv_view = df_cctv

        if df_cctv_view.empty:
            st.info("선택한 구가 없습니다. 상단에서 구를 선택해 주세요.")
        else:
            # 연도별 총합 (선택한 구만 반영)
            st.markdown("### 1) 연도별 총합")
            cctv_scale_year = st.selectbox("팔레트", PLOTLY_SCALES, index=PLOTLY_SCALES.index("Blues"), key="cctv_year_scale")

            cctv_yearly_sum = df_cctv_view[cctv_year_cols].sum()

            fig_cctv_year = px.bar(
                x=cctv_yearly_sum.index, y=cctv_yearly_sum.values,
                labels={"x":"연도","y":"대수"},
                color=cctv_yearly_sum.values,
                color_continuous_scale=cctv_scale_year,
                title="연도별 총 CCTV 대수 (선택한 구 기준)"
            )
            fig_cctv_year.update_layout(
                xaxis_tickangle=-45,
                plot_bgcolor="white",
                coloraxis_colorbar=dict(title="대수"),
            )
            st.plotly_chart(fig_cctv_year, use_container_width=True)

            # 구별 총합 (선택한 구만 반영)
            st.markdown("### 2) 구별 총 CCTV 대수")
            if "구분" in df_cctv_view.columns:
                df_total = df_cctv_view.copy()
                df_total["총합"] = df_total[cctv_year_cols].sum(axis=1)

                cctv_order_choice = st.radio("정렬", ["내림차순(많은 → 적은)", "오름차순(적은  →많은)", "원본순서"],
                                             horizontal=True, key="cctv_order")
                cctv_scale_total = st.selectbox("팔레트", PLOTLY_SCALES,
                                                index=PLOTLY_SCALES.index("Viridis"), key="cctv_total_scale")

                df_total = apply_sort(df_total, "총합", cctv_order_choice)

                fig_total = px.bar(
                    df_total, x="구분", y="총합",
                    color="총합",
                    color_continuous_scale=cctv_scale_total,
                    title="구별 CCTV 총 대수 (선택한 구 기준)",
                    labels={"구분":"구","총합":"총 CCTV 대수"}
                )
                fig_total.update_layout(
                    xaxis_tickangle=-45,
                    plot_bgcolor="white",
                    coloraxis_colorbar=dict(title="총 CCTV 대수"),
                )
                st.plotly_chart(fig_total, use_container_width=True)

    # ------------------------------
    # (탭) 👮 경찰서
    # ------------------------------
    with tab_police:
        st.subheader("경찰서 지표")

        # 경찰 CSV 읽기
        try:
            df_pol_raw = read_csv_safely("police.csv")
        except Exception as e:
            st.error(f"경찰 데이터를 불러올 수 없습니다(police.csv): {e}")
            st.stop()

        st.markdown("**원본 미리보기**")
        st.dataframe(df_pol_raw.head(), use_container_width=True)

        # 연도별 합치기(지구대/파출소/치안센터 → '{YYYY}년')
        df_pol = police_sum_by_year(df_pol_raw)
        st.markdown("**연도별 합친 데이터(미리보기)**")
        st.dataframe(df_pol.head(), use_container_width=True)

        # '구분' 컬럼이 있으면 구 멀티셀렉트(가나다순) — 기본: 전체 선택
        if "구분" in df_pol.columns:
            pol_districts = sort_korean(df_pol["구분"].dropna().unique().tolist())
            pol_selected = st.multiselect(
                "구 선택 (여러 개 선택 가능)",
                options=pol_districts,
                default=pol_districts,
                key="pol_gu_select"
            )
            df_pol_view = df_pol[df_pol["구분"].isin(pol_selected)] if pol_selected else df_pol.iloc[0:0]
            id_col = "구분"
        else:
            # '구분'이 없는 데이터의 경우, 식별 컬럼을 선택하여 멀티 선택
            id_candidates_all = [c for c in df_pol.columns if "년" not in c]
            id_col = st.selectbox("식별 컬럼 선택", sort_korean(id_candidates_all), index=0, key="pol_fallback_id")
            id_vals = sort_korean(df_pol[id_col].dropna().astype(str).unique().tolist())
            chosen_ids = st.multiselect(
                "항목 선택 (여러 개 선택 가능)",
                options=id_vals,
                default=id_vals,
                key="pol_fallback_vals"
            )
            df_pol_view = df_pol[df_pol[id_col].astype(str).isin(chosen_ids)] if chosen_ids else df_pol.iloc[0:0]

        if df_pol_view.empty:
            st.info("선택한 구가 없습니다. 상단에서 구를 선택해 주세요.")
        else:
            # 연도 선택 (막대그래프용)
            year_cols = [c for c in df_pol_view.columns if "년" in c]
            if year_cols:
                pol_year_choice = st.selectbox("연도 선택", year_cols, index=len(year_cols)-1, key="pol_year")
                pol_scale = st.selectbox("팔레트", PLOTLY_SCALES,
                                         index=PLOTLY_SCALES.index("Blues"), key="pol_scale")

                plot_df = df_pol_view[[id_col, pol_year_choice]].copy()
                plot_df[pol_year_choice] = pd.to_numeric(plot_df[pol_year_choice], errors="coerce")

                pol_order_choice = st.radio("정렬", ["내림차순(많은 → 적은)", "오름차순(적은 → 많은)", "원본순서"],
                                            horizontal=True, key="pol_order")
                plot_df = apply_sort(plot_df, pol_year_choice, pol_order_choice)

                # 경찰서 그래프
                fig_pol = px.bar(
                    plot_df, y=id_col, x=pol_year_choice,
                    color=pol_year_choice,
                    color_continuous_scale=pol_scale,
                    title=f"{pol_year_choice} {id_col}별 합계",
                    labels={id_col:id_col, pol_year_choice:"합계"},
                    height=700
                )
                fig_pol.update_layout(plot_bgcolor="white", coloraxis_colorbar=dict(title="합계"))
                st.plotly_chart(fig_pol, use_container_width=True)
            else:
                st.info("연도 컬럼을 찾지 못했습니다. 원본 컬럼명을 확인해 주세요.")
                
    # ------------------------------
    # (탭) "범죄 발생 현황"
    # ------------------------------
    with tab_crime:
        st.subheader("연도별 자치구 범죄 발생 횟수")

        # -----------------------------
        # (추가) 연속형 팔레트 목록 + 샘플링 함수
        # -----------------------------
        PLOTLY_SCALES = [
            "Blues", "Viridis", "Plasma", "Cividis", "Turbo",
            "Teal", "Agsunset", "YlGnBu", "YlOrRd", "IceFire", "Magma"
        ]

        import plotly.express as px

        def get_scale_list(name: str):
            """이름에 맞는 plotly 색상 시퀀스(list[str]) 반환 (sequential/diverging/cyclical 탐색)."""
            if hasattr(px.colors.sequential, name):
                return getattr(px.colors.sequential, name)
            if hasattr(px.colors.diverging, name):
                return getattr(px.colors.diverging, name)
            if hasattr(px.colors.cyclical, name):
                return getattr(px.colors.cyclical, name)
            return px.colors.sequential.Viridis  # 폴백

        def make_discrete_from_scale(scale_name: str, n: int):
            """연속 팔레트를 n개 색상의 discrete 팔레트로 균등 샘플링."""
            base = get_scale_list(scale_name)
            if n <= 0:
                return base
            # base 길이에 맞춰 균등 인덱스 추출
            import numpy as np
            idx = np.linspace(0, len(base) - 1, n)
            return [base[int(round(i))] for i in idx]

        # -----------------------------
        # (추가) 가나다 정렬 + 구 멀티 선택
        # -----------------------------
        def sort_korean(items):
            try:
                import locale
                for loc in ("ko_KR.UTF-8", "Korean_Korea.949", "ko_KR"):
                    try:
                        locale.setlocale(locale.LC_ALL, loc)
                        break
                    except:
                        pass
                return sorted(items, key=locale.strxfrm)
            except:
                return sorted(items)

        try:
            # 데이터 불러오기 (기존 유지)
            df_year = pd.read_csv("crime2.csv")
        except FileNotFoundError:
            st.error("범죄 데이터를 불러올 수 없습니다 (crime2.csv 파일을 확인해주세요.)")
            st.stop()
        except Exception as e:
            st.error(f"데이터를 불러오는 중 에러가 발생했습니다: {e}")
            st.stop()

        if "자치구별" not in df_year.columns:
            st.error("'자치구별' 컬럼을 찾을 수 없습니다.")
            st.stop()

        all_districts = sort_korean(df_year["자치구별"].dropna().astype(str).unique().tolist())
        selected_districts = st.multiselect(
            "자치구 선택 (여러 개 선택 가능)",
            options=all_districts,
            default=all_districts
        )
        # 팔레트 선택 (연속형 이름)
        scale_name = st.selectbox("팔레트 선택", options=PLOTLY_SCALES, index=PLOTLY_SCALES.index("Blues"))

        # 선택된 구만 필터
        df_year = df_year[df_year["자치구별"].astype(str).isin(selected_districts)] if selected_districts else df_year.iloc[0:0]
        current_order = selected_districts if selected_districts else all_districts

        # 타입 변환 (기존 유지)
        columns_to_convert = ['2019년', '2020년', '2021년', '2022년', '2023년']
        for column in columns_to_convert:
            if column in df_year.columns:
                df_year[column] = pd.to_numeric(df_year[column], errors='coerce').fillna(0).astype(int)

        # Wide → Long (기존 유지)
        df_long = pd.melt(df_year, id_vars=['자치구별'], var_name='년도', value_name='발생 횟수')
        df_long = df_long.sort_values(by=['년도', '발생 횟수'], ascending=[True, False])

        # 선택한 구 개수만큼 연속 팔레트를 샘플링해서 discrete 팔레트 생성
        n_colors = max(len(current_order), 1)
        color_seq = make_discrete_from_scale(scale_name, n_colors)

        # 그래프 (기존 구조 유지, 팔레트만 교체)
        fig = px.bar(
            df_long,
            x='자치구별',
            y='발생 횟수',
            color='자치구별',
            animation_frame='년도',
            title='<b>년도별 서울시 자치구 범죄 발생 건수</b>',
            labels={'자치구별': '자치구', '발생 횟수': '발생 건수'},
            color_discrete_sequence=color_seq
        )

        # y축 범위 고정 (기존 유지)
        if not df_long.empty:
            fig.update_yaxes(range=[0, df_long['발생 횟수'].max() * 1.2])

        # 레이아웃 (x축 카테고리 가나다 고정)
        fig.update_layout(
            title_x=0.5,
            font=dict(family="Malgun Gothic, Apple SD Gothic Neo, Nanum Gothic, sans-serif", size=12),
            xaxis={'categoryorder': 'array', 'categoryarray': current_order}
        )

        # 애니 속도 (기존 유지)
        if fig.layout.updatemenus:
            fig.layout.updatemenus[0].buttons[0].args[1]['frame']['duration'] = 1000
            fig.layout.updatemenus[0].buttons[0].args[1]['transition']['duration'] = 500

        st.plotly_chart(fig, use_container_width=True)