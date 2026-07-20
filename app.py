# app.py
# ==========================================
# [설명] '숨쉬는 일상' 대시보드의 프론트엔드 메인 파일입니다.
# 이 파일은 비즈니스 로직(데이터 가공, 외부 통신 등)을 직접 수행하지 않고,
# 분리된 env_api와 chat_manager로부터 데이터를 전달받아 '화면에 배치'하는 역할만 전담합니다.
# [업데이트] env_api 디버깅 강화본(Gemini 명사 추출 분석기)과의 정밀 연동 및 
# 동네 자동 동기화 예외 처리가 반영되었습니다.
# ==========================================

import streamlit as st
import time
import numpy as np
import pandas as pd
import re  # 사용자의 입력어에서 동네 이름을 추출하기 위한 정규표현식 라이브러리

# ------------------------------------------
# [모듈 임포트] 커스텀 백엔드 및 로직 관리 파일 로드
# ------------------------------------------
import env_api        # 실시간 환경 데이터(대기질, 교통) 수집 및 Gemini API 담당 모듈
import chat_manager   # 대화 세션 상태(State) 유지 및 말풍선 렌더링 담당 모듈

# ------------------------------------------
# [페이지 초기 세팅] 브라우저 탭 및 레이아웃 설정
# ------------------------------------------
st.set_page_config(
    page_title="숨쉬는 일상 - 관리자 대시보드 (데모)", # 브라우저 탭에 표시되는 제목
    page_icon="😷",                                    # 브라우저 탭에 표시되는 이모티콘 아이콘
    layout="wide"                                      # 화면 좌우 너비를 꽉 채우는 와이드 모드 활성화
)

# ------------------------------------------
# [CSS 스타일 시트 로드] 화면 레이아웃 및 디자인 주입
# ------------------------------------------
with open("style.css", "r", encoding="utf-8") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# ------------------------------------------
# [세션 상태 설정] 사용자가 마지막으로 검색한 동네 추적용 변수 초기화
# ------------------------------------------
if "current_region" not in st.session_state:
    st.session_state["current_region"] = "오산동" # 최초 기본값

# ------------------------------------------
# [헤더 영역] 대시보드의 메인 타이틀 선언
# ------------------------------------------
st.markdown('<span style="font-size: 18px; font-weight: bold; color: #ffffff;">🍀 숨쉬는 일상</span>', unsafe_allow_html=True)
st.write("실시간 공기 질 상태와 AI 에이전트 작동 현황을 한눈에 파악합니다.")


# ==========================================
# 1. 사이드바 (사용자 프로필 및 대시보드 제어판)
# ==========================================
with st.sidebar:
    st.header("👤 사용자 정보 설정")
    user_name = st.text_input("사용자 이름", value="성주")
    user_disease = st.selectbox("알레르기/질환군", ["비염", "천식", "아토피", "없음"])
    
    st.markdown("---") 
    
    st.header("⚙️ 대시보드 설정")
    # 현재 조회 중인 측정 기준 지역 표시
    st.info(f"📍 현재 측정소 기준 지역: **{st.session_state['current_region']}**")
    
    auto_refresh = st.checkbox("센서 데이터 자동 업데이트 (5초)", value=False)
    if st.button("데이터 수동 업데이트"):
        st.rerun()

# ------------------------------------------
# [데이터 연동] 세션에 기록된 마지막 검색 지역 정보를 get_realtime_air_quality에 '인자'로 전달!
# ------------------------------------------
air_data = env_api.get_realtime_air_quality(st.session_state["current_region"])


# ==========================================
# 2. 메인 화면 - 핵심 지표 (Metrics Card 영역)
# ==========================================
st.subheader(f"📊 실시간 도심 환경 데이터 정보 ({st.session_state['current_region']} / {user_name}님 기준)")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        label=f"현재 초미세먼지(PM 2.5) - [{air_data.get('station', '측정소')}]", 
        value=f"{air_data['pm25']} ㎍/㎥", 
        delta=air_data['status'], 
        delta_color="inverse"
    )

with col2:
    st.metric(
        label="도로 소통 상황 (주변 주요 도로)", 
        value=air_data['traffic'], 
        delta="매연 급증 위험", 
        delta_color="inverse"
    )

with col3:
    st.metric(
        label="현재 온도 / 습도", 
        value=f"{air_data['temp']} °C / {air_data['humi']} %", 
        delta="양호", 
        delta_color="normal"
    )


# ==========================================
# 3. 메인 화면 - 상세 분석 정보 (탭 레이아웃 영역)
# ==========================================
st.markdown("---") 
st.subheader("🤖 AI 에이전트 작동 현황 및 행동 지침")

tab1, tab2 = st.tabs(["AI 분석 리포트", "데이터 시각화"])

with tab1:
    st.success(f"🤖 AI 에이전트의 {user_disease} 질환 맞춤형 행동 지침")
    st.markdown(f"""
    **{user_name}님께 드리는 오늘의 행동 지침:**
    1. 현재 {st.session_state['current_region']} 주변 미세먼지가 **{air_data['pm25']} ㎍/㎥**로 **{air_data['status']}** 상태입니다. {user_disease} 증상 완화를 위해 보건용 마스크를 착용해 주세요.
    2. 주변 도로 교통이 **{air_data['traffic']}** 상태이므로 배기가스 배출량이 높습니다. 호흡기를 보호하기 위해 가급적 큰길을 피해 이동해 주세요.
    """)

with tab2:
    st.write(f"최근 1시간 동안의 초미세먼지(PM2.5) 추이 - {st.session_state['current_region']} 기준")
    # 데모용 임시 데이터 프레임을 생성합니다. (실제 실시간 수치 PM2.5 기준 근처에서 위아래로 흔들리도록 노이즈 추가 생성)
    base_val = air_data['pm25']
    chart_data = pd.DataFrame(
        np.random.randint(max(10, base_val - 15), base_val + 15, size=24), 
        columns=["PM2.5"],
        index=pd.date_range(start=pd.Timestamp.now().floor('h'), periods=24, freq='h')
    )
    st.line_chart(chart_data)


# ==========================================
# 4. AI 대화창 컴포넌트 (모듈식 전면 분리 영역)
# ==========================================
st.markdown("---")
st.subheader("💬 AI 에이전트에게 물어보기")

chat_manager.init_chat_session(user_name)
chat_manager.display_chat_history()

if user_input := st.chat_input("질문할 다른 지역이나 궁금한 점을 입력하세요..."):
    
    # ----------------------------------------------------
    # [인텔리전트 지역 파싱 및 동기화 엔진 예외 처리]
    # 1차로 정규식 매칭을 시도하고, 매칭에 실패하더라도 env_api의 
    # 내장형 Gemini 모델이 분석해낸 실제 측정소 지역 명칭(station)을 
    # 역추적하여 대시보드 상태를 유기적으로 자동 변환시킵니다.
    # ----------------------------------------------------
    matched_regions = re.findall(r'([가-힣]+(?:동|읍|면|시|구))', user_input)
    
    if matched_regions:
        target_new_region = matched_regions[0]
        st.session_state["current_region"] = target_new_region
        air_data = env_api.get_realtime_air_quality(target_new_region)
        st.toast(f"📍 대시보드 조회 지역이 '{target_new_region}'(으)로 자동 변경되었습니다!")
    else:
        # 사용자가 문장 내에 구체적인 지명을 쓰지 않은 경우(예: "지금 미세먼지 어때?")
        # 기존 세션에 있던 지역을 기반으로 에어코리아 API를 원격 재호출합니다.
        air_data = env_api.get_realtime_air_quality(st.session_state["current_region"])
        
        # 만약 env_api단에서 측정소 정보가 변경되었거나 백업 정보가 있다면 세션에 실시간 동기화
        if air_data.get("station") and air_data["station"] != "오산동":
            st.session_state["current_region"] = air_data["station"]

    # AI 응답 핸들러 호출
    chat_manager.handle_user_question(user_input, user_name, user_disease, air_data)
    
    # 화면 강제 갱신을 수행하여 상단 스태틱 카드와 차트가 변경된 지역 정보를 즉각 반영하도록 함
    st.rerun()


# ==========================================
# 5. 자동 실시간 루프 (Polling 제어)
# ==========================================
if auto_refresh:
    time.sleep(5)
    st.rerun()

# ==========================================
# [푸터 영역] 화면 최하단 저작권 표시
# ==========================================
st.markdown("---")
st.write("© 2026 숨쉬는 일상 Team.")

