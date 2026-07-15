import streamlit as st
import random
import time

# ==========================================
# 0. 웹 화면 초기 세팅
# ==========================================
st.set_page_config(
    page_title="숨쉬는 일상 - 관리자 대시보드 (데모)",
    page_icon="😷",
    layout="wide"  # 화면을 넓게 쓰도록 설정
)

# 타이틀 및 대시보드 설명
#st.title("🍀 숨쉬는 일상 - 관리자 통합 대시보드")
# span 태그 안에 style을 넣어 원하는 크기(px)로 직접 지정합니다.
# font-size: 20px -> 숫자를 키우면 커지고, 줄이면 작아집니다.
# font-weight: bold -> 글자를 두껍게 만듭니다.
st.markdown(
    '<span style="font-size: 18px; font-weight: bold; color: #ffffff;">🍀 숨쉬는 일상</span>', 
    unsafe_allow_html=True
)
st.write("실시간 공기 질 상태와 AI 에이전트 작동 현황을 한눈에 파악합니다.")

# ==========================================
# 1. 사이드바 (사용자 정보 입력 및 설정)
# ==========================================
with st.sidebar:
    st.header("👤 사용자 정보 설정")
    user_name = st.text_input("사용자 이름", value="성주")
    user_disease = st.selectbox("알레르기/질환군", ["비염", "천식", "아토피", "없음"])
    
    st.markdown("---")
    st.header("⚙️ 대시보드 설정")
    auto_refresh = st.checkbox("센서 데이터 자동 업데이트 (5초)", value=False)
    
    # 더미 데이터 업데이트 버튼 (자동 업데이트 안 쓸 때 사용)
    if st.button("데이터 수동 업데이트"):
        st.rerun()

# ==========================================
# 2. 메인 화면 - 핵심 지표 (Metrics)
# ==========================================
st.subheader(f"📊 실시간 도심 환경 데이터 정보 ({user_name}님 기준)")

# 화면을 3개의 열로 나눕니다.
col1, col2, col3 = st.columns(3)

with col1:
    # 초미세먼지 더미 데이터
    pm25_value = 145 # 더미값
    st.metric(
        label="현재 초미세먼지(PM 2.5)",
        value=f"{pm25_value} ㎍/㎥",
        delta="매우 나쁨", # delta_color는 inverse로 빨간색 표시
        delta_color="inverse"
    )

with col2:
    # 도로 소통 상황 더미 데이터
    traffic_status = "매우 정체" # 더미값
    st.metric(
        label="도로 소통 상황 (강남역 주변)",
        value=traffic_status,
        delta="매연 급증 위험", # delta_color는 inverse로 빨간색 표시
        delta_color="inverse"
    )

with col3:
    # 온도/습도 더미 데이터
    temp_value = 24.5 # 더미값
    humi_value = 65 # 더미값
    st.metric(
        label="현재 온도 / 습도",
        value=f"{temp_value} °C / {humi_value} %",
        delta="양호", # delta_color는 normal로 초록색 표시
        delta_color="normal"
    )

# ==========================================
# 3. 메인 화면 - 상세 데이터 및 분석 (Dummy)
# ==========================================
st.markdown("---")
st.subheader("🤖 AI 에이전트 작동 현황 및 행동 지침")

# 탭으로 화면을 구분합니다.
tab1, tab2 = st.tabs(["AI 분석 리포트", "데이터 시각화"])

with tab1:
    # AI 분석 리포트 (API 없이 더미 텍스트로 미리보기)
    st.success(f"🤖 AI 에이전트의 {user_disease} 질환 맞춤형 행동 지침")
    st.markdown(f"""
    **{user_name}님께 드리는 오늘의 행동 지침:**

    1.  현재 강남역 주변 미세먼지가 **{pm25_value} ㎍/㎥**로 **매우 나쁨** 상태입니다. 비염 증상 완화를 위해 **KF94 마스크**를 반드시 착용해 주세요.
    2.  {traffic_status}로 인한 차량 매연이 심각합니다. 귀가 시 **강남대로변 보도 대신 이면도로**를 이용하는 것을 권장합니다.
    3.  실내 환기는 피하시고 공기청정기를 가동해 주세요.
    """)

with tab2:
    # 데이터 시각화 더미 (간단한 선 그래프)
    st.write("최근 1시간 동안의 초미세먼지 추이")
    
    # 꺾은선 그래프 더미 데이터 생성
    import numpy as np
    import pandas as pd
    chart_data = pd.DataFrame(
        np.random.randint(100, 160, size=24), # 랜덤한 수치 24개 생성
        columns=["PM2.5"],
        index=pd.date_range(start=pd.Timestamp.now().floor('h'), periods=24, freq='h') # 시간 기반 인덱스
    )
    
    # 스트림릿 내장 그래프 함수로 그리기
    st.line_chart(chart_data)

# ==========================================
# 4. 자동 업데이트 기능 (더미용)
# ==========================================
# 사이드바에서 자동 업데이트를 켰을 때만 작동합니다.
if auto_refresh:
    time.sleep(5)
    st.rerun()

st.markdown("---")
st.write("© 2024 숨쉬는 일상 Team. 이 화면은 외부 API를 호출하지 않는 데모 버전입니다.")


st.markdown("""
    <style>
    /* 1. 모바일 화면에서 부드러운 스크롤 강제 활성화 */
    html, body, [data-testid="stAppViewContainer"] {
        overflow-y: auto !important;
        overflow-x: hidden !important;
        -webkit-overflow-scrolling: touch !important;
        height: 100% !important;
    }
    
    /* 2. 상단 툴바, 배너 및 WebIntoApp 툴바(dash) 강제 숨기기 */
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    footer {visibility: hidden;}
    .viewerBadge_container__1QSob {display: none !important;}
    div[data-testid="stStatusWidget"] {visibility: hidden;}
    
    /* [★추가] WebIntoApp 상단 검은 띠(dash) 영역 제거 */
    iframe, .app-toolbar, #toolbar, .toolbar {
        display: none !important;
        height: 0px !important;
    }
    
    /* 3. 모바일 화면 양옆 및 위아래 여백 최적화 */
    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 3rem !important;
        padding-left: 1rem !important;
        padding-right: 1rem !important;
    }
    </style>
    """, unsafe_allow_html=True)
