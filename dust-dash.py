import streamlit as st
import random
import time
import numpy as np
import pandas as pd

# ==========================================
# 0. 웹 화면 초기 세팅
# ==========================================
st.set_page_config(
    page_title="숨쉬는 일상 - 관리자 대시보드 (데모)",
    page_icon="😷",
    layout="wide"  # 화면을 넓게 쓰도록 설정
)

# 겹침 방지 및 모바일 UI 최적화 스타일 (최상단 적용)
st.markdown("""
    <style>
    /* 1. 당겨서 새로고침(Pull-to-refresh) 강제 차단 및 스크롤 고정 해제 */
    html, body {
        overscroll-behavior-y: contain !important;
        overflow-y: auto !important;
        -webkit-overflow-scrolling: touch !important;
    }
    
    [data-testid="stAppViewContainer"] {
        overflow-y: auto !important;
        -webkit-overflow-scrolling: touch !important;
    }
    
    /* 2. 스트림릿 배너 숨기기 및 헤더 투명화 */
    header {
        background-color: transparent !important;
    }
    
    /* Fork 버튼, 깃허브 로고, 점 3개 메뉴 숨기기 */
    div[data-testid="stToolbarActions"] { display: none !important; }
    #MainMenu { visibility: hidden !important; }
    footer { visibility: hidden !important; }
    div[class*="viewerBadge"] { display: none !important; }
    div[data-testid="stStatusWidget"] { visibility: hidden !important; }
    
    /* [★핵심] 사이드바 여는 화살표(collapsedControl) 위치를 좌측 상단 구석으로 고정 */
    div[data-testid="collapsedControl"] {
        position: fixed !important;
        top: 10px !important;
        left: 10px !important;
        z-index: 999999 !important;
        background-color: rgba(17, 17, 17, 0.7) !important; /* 어두운 테마에 어울리는 반투명 배경 추가 */
        border-radius: 8px !important;
        padding: 4px !important;
    }
    
    /* 3. 본문 전체 영역을 화살표 아래로 안전하게 밀어내기 (겹침 차단) */
    .block-container {
        padding-top: 4.5rem !important; /* 상단 여백을 충분히 주어 겹치지 않게 합니다 */
        padding-bottom: 5rem !important; /* 하단 입력창 여유 공간 */
        padding-left: 1rem !important;
        padding-right: 1rem !important;
    }
    </style>
    """, unsafe_allow_html=True)

# 타이틀 설정
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
    pm25_value = 145 # 더미값
    st.metric(
        label="현재 초미세먼지(PM 2.5)",
        value=f"{pm25_value} ㎍/㎥",
        delta="매우 나쁨", 
        delta_color="inverse"
    )

with col2:
    traffic_status = "매우 정체" # 더미값
    st.metric(
        label="도로 소통 상황 (강남역 주변)",
        value=traffic_status,
        delta="매연 급증 위험", 
        delta_color="inverse"
    )

with col3:
    temp_value = 24.5 # 더미값
    humi_value = 65 # 더미값
    st.metric(
        label="현재 온도 / 습도",
        value=f"{temp_value} °C / {humi_value} %",
        delta="양호", 
        delta_color="normal"
    )

# ==========================================
# 3. 메인 화면 - 상세 데이터 및 분석 (Tab)
# ==========================================
st.markdown("---")
st.subheader("🤖 AI 에이전트 작동 현황 및 행동 지침")

tab1, tab2 = st.tabs(["AI 분석 리포트", "데이터 시각화"])

with tab1:
    st.success(f"🤖 AI 에이전트의 {user_disease} 질환 맞춤형 행동 지침")
    st.markdown(f"""
    **{user_name}님께 드리는 오늘의 행동 지침:**

    1.  현재 강남역 주변 미세먼지가 **{pm25_value} ㎍/㎥**로 **매우 나쁨** 상태입니다. 비염 증상 완화를 위해 **KF94 마스크**를 반드시 착용해 주세요.
    2.  {traffic_status}로 인한 차량 매연이 심각합니다. 귀가 시 **강남대로변 보도 대신 이면도로**를 이용하는 것을 권장합니다.
    3.  실내 환기는 피하시고 공기청정기를 가동해 주세요.
    """)

with tab2:
    st.write("최근 1시간 동안의 초미세먼지 추이")
    chart_data = pd.DataFrame(
        np.random.randint(100, 160, size=24), 
        columns=["PM2.5"],
        index=pd.date_range(start=pd.Timestamp.now().floor('h'), periods=24, freq='h')
    )
    st.line_chart(chart_data)

# ==========================================
# 4. [새로 추가됨 🔥] AI 대화창 (Gemini 미연동 가상 챗봇)
# ==========================================
st.markdown("---")
st.subheader("💬 AI 에이전트에게 물어보기")
st.write("대시보드에 없는 다른 지역의 공기질이나 대처법이 궁금하시면 언제든 질문하세요!")

# 세션 대화 저장소 초기화 (새로고침해도 대화가 유지됩니다)
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": f"안녕하세요, {user_name}님! 궁금하신 다른 지역(예: '홍대입구역 미세먼지 어때?', '마포구 날씨는?')을 입력해 주시면 가상 분석 결과를 알려드릴게요! 😊"}
    ]

# 대화 기록 화면에 표시
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# 사용자 입력창 (모바일 하단 고정형)
if user_input := st.chat_input("질문할 다른 지역이나 궁금한 점을 입력하세요..."):
    # 사용자 질문 말풍선 즉시 표시 및 저장
    with st.chat_message("user"):
        st.write(user_input)
    st.session_state.messages.append({"role": "user", "content": user_input})
    
    # 챗봇 가짜 답변 생성 프로세스 (딜레이를 주어 분석하는 느낌 연출)
    with st.chat_message("assistant"):
        with st.spinner("가상 에이전트가 해당 구역을 수색 및 분석 중..."):
            time.sleep(1) # 1초 동안 로딩바 도는 연출
            
            # 입력값 분석하여 데모용 그럴듯한 답변 리턴
            dummy_responses = [
                f"문의하신 지역은 현재 미세먼지 '보통' 수준입니다. {user_name}님의 {user_disease} 증상을 고려했을 때, 일반 덴탈 마스크만 가볍게 착용하셔도 안전한 활동이 가능합니다!",
                f"해당 구역은 현재 퇴근 시간 정체로 인해 매연 수치가 높습니다. 호흡기가 예민하신 편이니 가급적 지하철 등 실내 대중교통 경로를 이용해 이동하세요.",
                f"현재 그 지역의 대기 상태는 양호합니다! 편안하게 외출하셔도 좋습니다. 다만 실시간 온도가 낮으니 가벼운 외투를 챙기시는 것을 권장합니다."
            ]
            response_text = random.choice(dummy_responses)
            
            st.write(response_text)
            st.session_state.messages.append({"role": "assistant", "content": response_text})

# ==========================================
# 5. 자동 업데이트 기능 (더미용)
# ==========================================
if auto_refresh:
    time.sleep(5)
    st.rerun()

st.markdown("---")
st.write("© 2024 숨쉬는 일상 Team. 이 화면은 외부 API를 호출하지 않는 데모 버전입니다.")
