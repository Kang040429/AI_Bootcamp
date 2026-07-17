# chat_manager.py
# ==========================================
# [설명] '숨쉬는 일상'의 AI 대화방 로직 및 세션 관리를 전담하는 컨트롤러 모듈입니다.
# 
# [업데이트 사항] 사용자가 질문을 입력했을 때, 텅 빈 말풍선만 생기는 현상을 방지하기 위해 
# st.empty()를 사용하여 말풍선 내부에 "🔍 검색 및 분석 중..." 메시지를 즉시 띄우고, 
# API 통신(답변 생성)이 완료되는 순간 실제 답변으로 부드럽게 교체해 줍니다.
# ==========================================

import streamlit as st
import env_api # 질문에 대답하기 위해 백엔드 API 모듈(Gemini 호출)을 연동합니다.

# ------------------------------------------
# 1. 대화 세션 초기화 (최초 접속 시 작동)
# ------------------------------------------
def init_chat_session(user_name):
    """
    사용자가 대시보드 웹앱에 처음 접속했을 때, 
    대화 기록을 저장할 빈 바구니('messages' 리스트)를 세션에 안전하게 만들어 둡니다.
    """
    # st.session_state는 브라우저 탭이 열려있는 동안 유지되는 전역 메모리 사전(dict)입니다.
    # 세션에 'messages' 키가 없다는 것은 '완전히 처음 접속한 상태'를 의미합니다.
    if "messages" not in st.session_state:
        # 최초 접속 시 웰컴 메시지를 Assistant(AI 챗봇) 역할로 저장해 둡니다.
        st.session_state.messages = [
            {
                "role": "assistant", # 메시지 작성 주체: assistant(AI 챗봇) / user(사용자)
                "content": f"안녕하세요, {user_name}님! 궁금하신 다른 지역(예: '홍대입구역 미세먼지 어때?', '마포구 날씨는?')을 입력해 주시면 분석 결과를 알려드릴게요! 😊"
            }
        ]

# ------------------------------------------
# 2. 누적 대화 내역 화면 렌더링
# ------------------------------------------
def display_chat_history():
    """
    세션 메모리(st.session_state.messages)에 차곡차곡 누적 저장된 모든 메시지를 
    순서대로 화면에 하나씩 말풍선 UI(st.chat_message)로 다시 그려줍니다.
    """
    # 저장되어 있는 메시지 리스트를 순서대로 하나씩 꺼내어 처리합니다.
    for msg in st.session_state.messages:
        # msg["role"] 값('user' 또는 'assistant')에 맞춰 스트림릿이 알아서
        # 사람 아이콘(User) 또는 로봇 아이콘(Assistant) 말풍선 컨테이너를 생성합니다.
        with st.chat_message(msg["role"]):
            # 해당 말풍선 내부에 텍스트 콘텐츠를 출력합니다.
            st.write(msg["content"])

# ------------------------------------------
# 3. 실시간 질문 및 답변 처리 (핵심 이벤트 핸들러)
# ------------------------------------------
def handle_user_question(user_input, user_name, user_disease, air_data):
    """
    사용자가 질문 입력창(st.chat_input)에 글을 작성하고 엔터를 쳤을 때 작동하는 핵심 이벤트 함수입니다.
    사용자 메시지를 화면에 띄우고 저장한 뒤, 챗봇 말풍선 내부에 임시 로딩 문구를 노출했다가
    제미나이 AI 에이전트로부터 응답이 완료되면 실제 텍스트로 교체해 줍니다.
    """
    # 방어 코드: 사용자 입력이 비어있는 경우 아무 작업도 하지 않고 함수를 즉시 종료합니다.
    if not user_input:
        return

    # --------------------------------------
    # [단계 1] 사용자의 질문 처리 및 세션 기록
    # --------------------------------------
    # 사용자 역할('user') 아이콘을 달고 말풍선 창을 띄워 질문을 즉시 출력합니다.
    with st.chat_message("user"):
        st.write(user_input)
    
    # 새로고침 시에도 질문이 유지되도록 전역 세션 바구니에 {"role": "user", "content": ...} 형태로 저장해 둡니다.
    st.session_state.messages.append({"role": "user", "content": user_input})
    
    # --------------------------------------
    # [단계 2] 챗봇의 답변 처리 및 API 통신 (로딩 업데이트 반영)
    # --------------------------------------
    # AI 챗봇 역할('assistant') 아이콘을 단 말풍선 창을 열어둡니다.
    with st.chat_message("assistant"):
        
        # [핵심] 챗봇 말풍선 컨테이너 안에 실시간으로 글자를 교체해서 밀어 넣을 수 있는 '가상의 빈 자리(placeholder)'를 먼저 확보합니다.
        message_placeholder = st.empty()
        
        # API 답변을 구하기 전에, 방금 만든 빈 자리(placeholder)에 로딩 중임을 알려주는 안내 문구를 실시간 렌더링합니다.
        # 이렇게 하면 챗봇 아이콘 옆에 텅 빈 공간이 아닌 문구가 즉시 채워집니다.
        message_placeholder.write("🔍 에이전트가 실시간 정보를 검색 및 분석하는 중입니다...")
        
        # 스트림릿 클라우드의 환경변수(Secrets) 또는 .streamlit/secrets.toml 파일에서 
        # 안전하게 관리 중인 'GEMINI_API_KEY' 인증키를 은밀하게 가져옵니다.
        api_key = st.secrets.get("GEMINI_API_KEY", "")
        
        # 외부 연동 통신 모듈인 `env_api.py` 내부의 AI 추론 함수를 호출합니다.
        # (이 호출이 진행되는 수 초 동안 화면에는 위의 "검색 및 분석하는 중" 문구가 안전하게 유지됩니다.)
        answer = env_api.ask_gemini_agent(api_key, user_name, user_disease, user_input, air_data)
        
        # [교체 완료] 구글 제미나이 서버로부터 응답이 성공적으로 도착하면, 
        # 기존 로딩 문구가 있던 자리에 실제 AI 에이전트의 답변 텍스트를 덮어씌워 갈아끼웁니다.
        message_placeholder.write(answer)
        
        # 새로고침(Rerun) 시에도 AI가 했던 답변이 유지되도록 전역 세션 바구니에 누적 저장합니다.
        st.session_state.messages.append({"role": "assistant", "content": answer})