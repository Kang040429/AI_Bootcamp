# env_api.py
# ==========================================
# [디버깅 강화본 - 문장 내 모든 명사 리스트 CMD 로그 추가]
# Gemini가 지역명, 환경정보 외에 문장에 포함된 주요 명사(Noun)들을 
# 추가로 추출하여 터미널에 투명하게 출력합니다.
# ==========================================

import random
import requests
import streamlit as st
import urllib.parse
import json
import os
import re  
import pandas as pd  

def get_realtime_air_quality(region=None):
    if not region or not str(region).strip():
        region = "오산동 미세먼지"

    location_key = st.secrets.get("AIR_PORTAL_LOCATION_KEY", "").strip()
    air_key = st.secrets.get("AIR_PORTAL_KEY", "").strip()
    gemini_key = st.secrets.get("GEMINI_API_KEY", "").strip()  
    
    if not location_key or not air_key:
        print("🚨 [진단] secrets.toml에 API 키가 없습니다.")
        return get_fallback_data()

    try:
        raw_text = str(region).strip()
        print(f"\n===== 🤖 [파이프라인 시작] 사용자 입력 원문: '{raw_text}' =====")
        
        # 기본 변수 초기화
        extracted_location = ""
        extracted_env_info = "미세먼지"  
        extracted_nouns = [] # 추가된 명사 저장 리스트
        search_target = ""

        # 현재 env_api.py 파일이 있는 폴더(최상위) 위치를 자동으로 찾음
        base_dir = os.path.dirname(os.path.abspath(__file__))
        # 그 폴더 바로 아래에 있는 CSV 파일과 결합
        csv_path = os.path.join(base_dir, "경기도 행정구역현황.csv")
        #csv_path = r"경기도 행정구역현황.csv"

        # ----------------------------------------------------
        # 🔗 [PHASE 1] Gemini API: 유연한 키워드 및 명사 추출
        # ----------------------------------------------------
        if gemini_key:
            try:
                system_instruction = """
                당신은 문장 분석 전문가입니다. 입력된 문장에서 아래 지침에 따라 3가지 요소를 추출하여 지정된 JSON 포맷으로 반환하세요.

                1. location: 사용자가 언급한 지역명입니다.
                   - 뒤에 '시', '구', '동' 등의 행정구역 단위가 생략된 '시흥', '평택', '안산' 같은 단어라도 지명이 확실하다면 추출하세요. 없다면 ""을 반환합니다.

                2. env_info: 환경 정보 키워드 (예: "미세먼지", "초미세먼지", "날씨", "공기상태"). 없다면 "미세먼지"를 반환합니다.

                3. all_nouns: 입력 문장에 등장하는 모든 '명사형 단어(고유명사, 일반명사 등)'를 추출하여 문자열 배열(List)로 반환하세요.
                   - 조사나 어미, 동사, 형용사는 제외하고 체언(명사)만 골라내야 합니다.
                   - 예: "시흥 지금 공기 어때" -> ["시흥", "지금", "공기"]
                   - 예: "평택 고등동 미세먼지 알려줘" -> ["평택", "고등동", "미세먼지"]

                오직 {"location": "값", "env_info": "값", "all_nouns": ["명사1", "명사2"]} 포맷의 순수 JSON만 반환해야 합니다. 다른 텍스트는 절대 금지합니다.
                """
                base_gemini_url = st.secrets.get("GEMINI_URL", "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent")
                
                parse_res = requests.post(
                    f"{base_gemini_url}?key={gemini_key}",
                    json={
                        "contents": [{"parts": [{"text": f"사용자 문장: {raw_text}"}]}],
                        "systemInstruction": {"parts": [{"text": system_instruction}]},
                        "generationConfig": {"temperature": 0.0, "responseMimeType": "application/json"}
                    },
                    headers={"Content-Type": "application/json"}, timeout=10
                )
                
                if parse_res.status_code == 200:
                    parsed_json = json.loads(parse_res.json()["candidates"][0]["content"]["parts"][0]["text"].strip())
                    extracted_location = parsed_json.get("location", "").strip()
                    extracted_env_info = parsed_json.get("env_info", "미세먼지").strip()
                    extracted_nouns = parsed_json.get("all_nouns", [])
                    
                    # 💡 [CMD 출력 추가] 분석된 명사 로그까지 포함하여 터미널에 시각화
                    print("\n========================================")
                    print("🔍 [CMD 터미널 확인 - Gemini 분석 완료]")
                    print(f"📍 추출된 지역명   : {extracted_location if extracted_location else '(없음)'}")
                    print(f"🍃 추출된 환경정보 : {extracted_env_info}")
                    print(f"📦 문장 내 명사 배열: {extracted_nouns}")
                    print("========================================\n")
                    
            except Exception as e:
                print(f"⚠️ [Gemini 개체 추출 중 예외 발생] {e}")

        # LLM이 실패했거나 지역명을 못 잡았을 때를 대비한 파이썬 백업 정제
        if not extracted_location:
            clean_backup = re.sub(r'[^\w\s]', '', raw_text)
            clean_backup = re.sub(r'(미세먼지|날씨|어때|공기|상태|현재|동네|알려줘|좀)', '', clean_backup).strip()
            extracted_location = clean_backup if clean_backup else "오산"
            
            print("\n========================================")
            print("🔍 [CMD 터미널 확인 - 파이썬 백업 정제 가동]")
            print(f"📍 추출된 지역명   : {extracted_location}")
            print(f"🍃 추출된 환경정보 : {extracted_env_info} (기본값)")
            print("========================================\n")

        # ----------------------------------------------------
        # 📁 [PHASE 2] 파이썬 판다스 알고리즘: 추출된 지역명 매칭 및 필터링
        # ----------------------------------------------------
        if os.path.exists(csv_path) and extracted_location:
            try:
                df = pd.read_csv(csv_path, encoding="cp949")
                df['시군구명'] = df['시군구명'].fillna('').astype(str).str.strip()
                df['읍면동명'] = df['읍면동명'].fillna('').astype(str).str.strip()

                if len(extracted_location) >= 2:
                    is_si_matched = df['시군구명'].str.contains(extracted_location)
                    
                    if is_si_matched.any():
                        filtered_df = df[is_si_matched]
                        valid_dongs = filtered_df['읍면동명'].dropna().tolist()
                        valid_dongs = [d for d in valid_dongs if d.strip()]
                        
                        if valid_dongs:
                            search_target = random.choice(valid_dongs)
                            print(f"✅ [시군구 규칙 통과] '{extracted_location}' 포함 확인 ➡️ 행 필터링 완료.")
                            print(f"   선택된 내부 읍면동: '{search_target}'")

                if not search_target:
                    is_dong_matched = df['읍면동명'].str.contains(extracted_location)
                    if is_dong_matched.any():
                        filtered_dong_df = df[is_dong_matched]
                        search_target = filtered_dong_df.iloc[0]['읍면동명']
                        print(f"✅ [읍면동 규칙 통과] '{search_target}' 매칭 성공")

            except Exception as e:
                print(f"⚠️ [Pandas 필터링 처리 연산 중 에러] {e}")

        # ----------------------------------------------------
        # [PHASE 3] 최종 주소 보정 및 예외 처리 (안전망 코드)
        # ----------------------------------------------------
        if search_target:
            search_target = re.sub(r"\d+", "", search_target).strip()
        else:
            search_target = extracted_location if extracted_location else "오산동"

        if not (search_target.endswith("동") or search_target.endswith("읍") or search_target.endswith("면")):
            search_target = re.sub(r"[시구]", "", search_target) + "동"

        print(f"📡 [최종 에어코리아 API 전송 대상]: '{search_target}'")

        # ----------------------------------------------------
        # [STEP 2] 에어코리아 TM 기준좌표 조회
        # ----------------------------------------------------
        raw_location_key = urllib.parse.unquote(location_key)
        raw_air_key = urllib.parse.unquote(air_key)

        url_tm = "http://apis.data.go.kr/B552584/MsrstnInfoInqireSvc/getTMStdrCrdnt"
        params_tm = {
            "serviceKey": raw_location_key,
            "returnType": "json",
            "umdName": search_target,
            "numOfRows": "10",
            "pageNo": "1"
        }
        query_string_tm = urllib.parse.urlencode(params_tm, safe="%")
        res_tm_raw = requests.get(f"{url_tm}?{query_string_tm}", timeout=10)
        
        try:
            res_tm = res_tm_raw.json()
            items_tm = res_tm.get("response", {}).get("body", {}).get("items", [])
            if not items_tm:
                tmX, tmY = "206285.811283", "405297.606897"
            else:
                tmX = items_tm[0].get("tmX")
                tmY = items_tm[0].get("tmY")
        except Exception as e:
            tmX, tmY = "206285.811283", "405297.606897"

        # ----------------------------------------------------
        # [STEP 3] 근접측정소 목록 조회
        # ----------------------------------------------------
        url_nearby = "http://apis.data.go.kr/B552584/MsrstnInfoInqireSvc/getNearbyMsrstnList"
        params_nearby = {
            "serviceKey": raw_location_key,
            "returnType": "json",
            "tmX": tmX,
            "tmY": tmY,
            "ver": "1.1"
        }
        query_string_nearby = urllib.parse.urlencode(params_nearby, safe="%")
        res_nearby_raw = requests.get(f"{url_nearby}?{query_string_nearby}", timeout=10)
        
        try:
            res_nearby = res_nearby_raw.json()
            items_nearby = res_nearby.get("response", {}).get("body", {}).get("items", [])
            if not items_nearby:
                return get_fallback_data()
            station_name = items_nearby[0].get("stationName")
        except Exception as e:
            return get_fallback_data()

        # ----------------------------------------------------
        # [STEP 4] 측정소명으로 실시간 대기질 조회
        # ----------------------------------------------------
        base_air_url = st.secrets.get("AIR_PORTAL_URL", "http://apis.data.go.kr/B552584/ArpltnInforInqireSvc/getMsrstnAcctoRltmMesureDnsty")
        params_air = {
            "serviceKey": raw_air_key,
            "returnType": "json",
            "stationName": station_name,
            "dataTerm": "DAILY",
            "ver": "1.3"
        }
        query_string_air = urllib.parse.urlencode(params_air, safe="%")
        res_air_raw = requests.get(f"{base_air_url}?{query_string_air}", timeout=15)
        
        try:
            res_air = res_air_raw.json()
            items_air = res_air.get("response", {}).get("body", {}).get("items", [])
            if not items_air:
                return get_fallback_data()
            target_station = items_air[0]
        except Exception as e:
            return get_fallback_data()

        # ----------------------------------------------------
        # [STEP 5] 데이터 추출 및 가공
        # ----------------------------------------------------
        pm25_val = target_station.get("pm25Value")
        pm25_24h = target_station.get("pm25Value24h")
        
        if pm25_val and pm25_val.isdigit():
            pm25 = int(pm25_val)
        elif pm25_24h and pm25_24h.isdigit():
            pm25 = int(pm25_24h)
        else:
            pm25 = random.randint(12, 38)
            
        if pm25 <= 15: status = "좋음"
        elif pm25 <= 35: status = "보통"
        elif pm25 <= 75: status = "나쁨"
        else: status = "매우 나쁨"

        st.toast(f"📡 {station_name} 데이터 수집 완료! ({pm25} / {status})")

        return {
            "pm25": pm25,
            "status": status,
            "temp": 24.5,
            "humi": 65,
            "traffic": "매우 정체",
            "station": station_name,
            "env_info": extracted_env_info  
        }
        
    except Exception as e:
        return get_fallback_data()

def get_fallback_data():
    return {
        "pm25": 23,
        "status": "보통",
        "temp": 22.0,
        "humi": 50,
        "traffic": "보통 정체",
        "station": "오산동",
        "env_info": "미세먼지"
    }

# 2. 제미나이(Gemini) AI 답변 생성 함수
# ------------------------------------------
def ask_gemini_agent(api_key, user_name, user_disease, user_input, air_data):
    if not api_key or not api_key.strip():
        return get_dummy_response(user_name, user_disease)

    env_info_target = air_data.get('env_info', '미세먼지')

    system_prompt = f"""
    너는 실시간 도심 환경 분석 앱 '숨쉬는 일상'의 똑똑하고 상냥한 AI 에이전트야.
    사용자와 교감하며 맞춤형 건강 정보를 처방해 주는 역할을 맡고 있어.
    
    [현재 분석 대상 지역의 실제 측정 데이터]
    - 측정 대상 측정소: {air_data.get('station', '가깝운 측정소')}
    - 초미세먼지(PM2.5) 수치: {air_data['pm25']} ㎍/㎥ (상태 등급: {air_data['status']})
    - 도로 교통 상태: {air_data['traffic']}
    - 사용자가 질문한 환경 정보 종류: {env_info_target}
    
    [현재 접속한 사용자 정보]
    - 이름: {user_name}
    - 개인 취약성/질환군: {user_disease}
    
    사용자가 질문한 내용: "{user_input}"
    
    위 조건과 질문을 바탕으로 다음 규칙을 엄격히 지켜 대답해 줘:
    
    1. 답변 초반부에 사용자가 알고 싶어했던 환경 정보 종류인 '{env_info_target}'의 실제 농도 수치 '{air_data['pm25']} ㎍/㎥'를 자연스럽게 엮어서 밝혀 줘.
    2. 절대 템플릿화된 똑같은 답변을 반복하지 말고, 사용자의 질문 내용("{user_input}")을 적극적으로 반영하여 친근하게 대답해줘.
    3. 해당 수치 및 위험 등급과 연결하여 사용자의 개인 질환인 '{user_disease}'에 직접적으로 매칭되는 실질적인 건강/외출 가이드라인을 제시해 줘.
    4. 말투는 상냥하고 친절한 어투로 유지하되, 핵심 요약 위주로 3줄 내외로 깔끔하고 명확하게 작성해 줘.
    """

    base_gemini_url = st.secrets.get(
        "GEMINI_URL", 
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
    )
    
    full_gemini_url = f"{base_gemini_url}?key={api_key}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": system_prompt}]}]
    }

    try:
        response = requests.post(full_gemini_url, json=payload, headers=headers, timeout=30)
        response_json = response.json()
        
        if "candidates" in response_json:
            return response_json["candidates"][0]["content"]["parts"][0]["text"]
        else:
            return get_dummy_response(user_name, user_disease)
            
    except Exception as e:
        return get_dummy_response(user_name, user_disease)

def get_dummy_response(user_name, user_disease):
    dummy_responses = [
        f"현재 문의하신 지역은 미세먼지 '보통' 수준입니다. {user_name}님의 {user_disease} 증상을 고려했을 때, 일반 덴탈 마스크만 가볍게 착용하셔도 안전한 활동이 가능합니다! 😷",
        f"해당 구역은 현재 퇴근 시간 정체로 인해 매연 수치가 높습니다. {user_disease} 관리를 위해 가급적 실내 대중교통 경로를 이용해 이동해 보세요! 🚌",
        f"현재 그 지역의 대기 상태는 아주 깨끗하고 양호합니다! 편안하게 기분 전환 외출을 즐기셔도 좋습니다. 🌱"
    ]
    return random.choice(dummy_responses)
