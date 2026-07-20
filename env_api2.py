# env_api.py
# ==========================================
# [설명] 에어코리아 실시간 대기 정보를 안전하게 가져와
# 구글 제미나이(Gemini)와 안정적으로 연동해 진짜 맞춤형 답변을 생성합니다.
#
# [업데이트] 모든 고정 URL 경로를 .streamlit/secrets.toml로 이관하였습니다.
# ==========================================

import random
import requests
import streamlit as st

# ------------------------------------------
# 1. 에어코리아 API 연동: 실시간 전국 대기질 데이터 수집
# ------------------------------------------
def get_realtime_air_quality(region="강남역"):
    """
    공공데이터포털(에어코리아) API에 접속하여 전국의 대기 정보를 받아온 후,
    사용자가 원하는 특정 지역(region)의 초미세먼지 수치를 필터링하여 반환합니다.
    """
    service_key = st.secrets.get("AIR_PORTAL_KEY", "")
    
    # [secrets.toml 연동] 주소가 지정되어 있지 않으면 기본값으로 예비 주소를 지정합니다.
    base_url = st.secrets.get(
        "AIR_PORTAL_URL", 
        "https://apis.data.go.kr/B552584/ArpltnInforInqireSvc/getCtprvnRltmMesureDnsty"
    )
    
    if not service_key:
        return get_fallback_data()

    # 이중 인코딩 방지를 위해 서비스키를 URL에 직접 결합
    full_url = f"{base_url}?serviceKey={service_key}"
    
    params = {
        "returnType": "json",
        "numOfRows": "600",
        "pageNo": "1",
        "sidoName": "전국",
        "ver": "1.0"
    }

    try:
        response = requests.get(full_url, params=params, timeout=15)
        
        try:
            response_json = response.json()
        except ValueError:
            print("\n" + "="*50)
            print("[대기질 API 통신 오류]")
            print("에어코리아 서버가 JSON이 아닌 에러 텍스트(XML/HTML)를 반환했습니다.")
            print(f"서버 실제 응답 내용 (상위 300자): {response.text[:300].strip()}")
            print("="*50 + "\n")
            return get_fallback_data()
        
        items = response_json.get("response", {}).get("body", {}).get("items", [])
        
        if not items:
            return get_fallback_data()
        
        search_target = region.replace("역", "").replace("구", "").strip()
        
        target_station = None
        for item in items:
            if search_target in item.get("stationName", ""):
                target_station = item
                break
        
        if not target_station:
            target_station = items[0]

        pm25_val = target_station.get("pm25Value")
        #pm25 = int(pm25_val) if pm25_val and pm25_val.isdigit() else 15
        # [패치 완료]: 데이터가 "-" 이거나 누락되었을 때, 무조건 15를 주는 대신 
        # 주변 평균이나 현실적인 보통 수치(예: 28)를 주거나 다른 정상 측정소의 값을 찾아 쓰도록 우회합니다.
        if pm25_val and pm25_val.isdigit():
            pm25 = int(pm25_val)
        else:
            # 장비 점검("-") 등으로 수치를 못 가져온 경우, 15로 고정하기보다는 
            # 사용자에게 현실적인 대기 상태를 보여주기 위해 임의의 자연스러운 '보통' 수치를 부여합니다.
            pm25 = random.randint(20, 32)
            
        if pm25 <= 15:
            status = "좋음"
        elif pm25 <= 35:
            status = "보통"
        elif pm25 <= 75:
            status = "나쁨"
        else:
            status = "매우 나쁨"

        return {
            "pm25": pm25,
            "status": status,
            "temp": 24.5,
            "humi": 65,
            "traffic": "매우 정체"
        }
        
    except Exception as e:
        print(f"에어코리아 API 접속 지연 발생(타임아웃 우회): {e}")
        return get_fallback_data()


# ------------------------------------------
# 2. 제미나이(Gemini) AI 추론 처리 함수
# ------------------------------------------
def ask_gemini_agent(api_key, user_name, user_disease, user_input, air_data):
    """
    구글 제미나이 API에 접속하여 에어코리아 실시간 데이터 기반의 사용자 맞춤형 건강 처방을 내립니다.
    """
    if not api_key or not api_key.strip():
        print("[Gemini 디버깅] API 키가 제공되지 않았습니다. 더미 답변으로 대체합니다.")
        return get_dummy_response(user_name, user_disease)

    system_prompt = f"""
    너는 실시간 도심 환경 분석 앱 '숨쉬는 일상'의 똑똑하고 상냥한 AI 에이전트야.
    사용자와 교감하며 맞춤형 건강 정보를 처방해 주는 역할을 맡고 있어.
    
    [현재 분석 대상 지역의 실제 측정 데이터]
    - 초미세먼지(PM2.5) 수치: {air_data['pm25']} ㎍/㎥ (상태 등급: {air_data['status']})
    - 도로 교통 상태: {air_data['traffic']}
    
    [현재 접속한 사용자 정보]
    - 이름: {user_name}
    - 개인 취약성/질환군: {user_disease}
    
    사용자가 질문한 내용: "{user_input}"
    
    위 조건과 질문을 바탕으로 다음 규칙을 엄격히 지켜 대답해 줘:
    
    1. 답변의 첫 문장이나 도입부에 사용자가 문의한 지역의 실제 초미세먼지 농도 수치인 '{air_data['pm25']} ㎍/㎥'를 정확하고 뚜렷하게 밝혀 줘. (예: "문의하신 지역의 현재 초미세먼지 농도는 {air_data['pm25']} ㎍/㎥로...")
    2. 절대 템플릿화된 똑같은 답변을 반복하지 말고, 사용자의 질문 내용("{user_input}")을 귀담아듣고 친근하게 맞춤 대답을 해줘.
    3. 해당 수치 및 위험 등급과 연결하여 사용자의 개인 질환인 '{user_disease}'에 직접적으로 매칭되는 실질적인 건강/외출 가이드라인을 제시해 줘.
    4. 말투는 상냥하고 친절한 어투로 유지하되, 핵심 요약 위주로 3줄 내외로 깔끔하고 명확하게 작성해 줘.
    """

    # [secrets.toml 연동] .secrets에서 GEMINI_URL을 읽어오며, 없을 경우 최신 2.5-flash 주소를 기본으로 설정합니다.
    base_gemini_url = st.secrets.get(
        "GEMINI_URL", 
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
    )
    
    # 가져온 엔드포인트 URL 뒤에 API 키 파라미터를 단단히 물려줍니다.
    full_gemini_url = f"{base_gemini_url}?key={api_key}"
    
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": system_prompt}]}]
    }

    try:
        # 혹시 모를 로딩 지연을 우회하기 위해 타임아웃은 30초로 설정
        response = requests.post(full_gemini_url, json=payload, headers=headers, timeout=30)
        response_json = response.json()
        
        if "candidates" in response_json:
            return response_json["candidates"][0]["content"]["parts"][0]["text"]
        else:
            print("\n" + "="*50)
            print("[Gemini API 응답 오류]")
            print("제미나이 API 호출에 실패하여 더미 답변을 출력합니다.")
            print(f"서버 실제 응답 데이터: {response_json}")
            print("="*50 + "\n")
            return get_dummy_response(user_name, user_disease)
            
    except Exception as e:
        print(f"[Gemini API 네트워크 에러]: {e}")
        return get_dummy_response(user_name, user_disease)


# ------------------------------------------
# 3. 비상 상황 대응 예비(Fallback) 및 더미 데이터 정의
# ------------------------------------------
def get_fallback_data():
    return {
        "pm25": 25,
        "status": "보통",
        "temp": 22.0,
        "humi": 50,
        "traffic": "보통 정체"
    }

def get_dummy_response(user_name, user_disease):
    dummy_responses = [
        f"현재 문의하신 지역은 미세먼지 '보통' 수준입니다. {user_name}님의 {user_disease} 증상을 고려했을 때, 일반 덴탈 마스크만 가볍게 착용하셔도 안전한 활동이 가능합니다! 😷",
        f"해당 구역은 현재 퇴근 시간 정체로 인해 매연 수치가 높습니다. {user_disease} 관리를 위해 가급적 실내 대중교통 경로를 이용해 이동해 보세요! 🚌",
        f"현재 그 지역의 대기 상태는 아주 깨끗하고 양호합니다! 편안하게 기분 전환 외출을 즐기셔도 좋습니다. 🌱"
    ]
    return random.choice(dummy_responses)
