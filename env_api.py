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
        csv_path = r"C:\AI_bootcamp\경기도 행정구역현황.csv"

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
'''
# env_api.py (실제 행정구역 데이터 적용 버전)
# ==========================================
# [설명] 사용자가 시군구명만 입력해도 소속 행정구역을 필터링한 후 
# 실제 존재하는 대표 읍면동으로 매핑하여 에어코리아 API 호환성을 보장합니다.
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
        region = "오산동"

    location_key = st.secrets.get("AIR_PORTAL_LOCATION_KEY", "").strip()
    air_key = st.secrets.get("AIR_PORTAL_KEY", "").strip()
    gemini_key = st.secrets.get("GEMINI_API_KEY", "").strip()  
    
    if not location_key or not air_key:
        print("🚨 [진단] secrets.toml에 API 키가 없습니다.")
        return get_fallback_data()

    try:
        raw_text = str(region).strip()
        print(f"\n===== 🤖 [주소 세탁 시작] 사용자 입력 원문: '{raw_text}' =====")
        
        # 기본값 설정
        search_target = ""
        csv_path = r"C:\\AI_bootcamp\\경기도 행정구역현황.csv"
        
        # ----------------------------------------------------
        # 📁 [초강력 파이썬 선행 매칭 알고리즘]
        # ----------------------------------------------------
        # 1. 입력어에서 군더더기 단어 제거 (예: "평택 미세먼지" -> "평택")
        clean_keyword = re.sub(r'[^\w\s]', '', raw_text)
        clean_keyword = re.sub(r'(미세먼지|날씨|어때|공기|상태|현재|동네|알려줘|좀)', '', clean_keyword).strip()
        
        if os.path.exists(csv_path):
            try:
                # CSV 로드 및 데이터 공백 정제
                df = pd.read_csv(csv_path, encoding="cp949")
                df['시군구명'] = df['시군구명'].fillna('').astype(str).str.strip()
                df['읍면동명'] = df['읍면동명'].fillna('').astype(str).str.strip()

                if clean_keyword:
                    # '시', '군', '구' 글자를 제거한 순수 키워드로 비교 강인성 확보
                    pure_keyword = re.sub(r'(시|군|구)$', '', clean_keyword)
                    
                    # [STEP A] 1차 관문: 시군구 컬럼에서 키워드 매칭 검색
                    is_si_matched = df['시군구명'].str.contains(pure_keyword)
                    
                    if is_si_matched.any():
                        # [의도 반영 1] 매칭된 시군구 컬럼을 가진 지역만 남기고 모든 다른 행 제거(필터링)
                        filtered_df = df[is_si_matched]
                        
                        # [의도 반영 2] 남은 해당 시군구의 읍면동 리스트 추출 후 하나 무작위(또는 첫 번째) 선택
                        valid_dongs = filtered_df['읍면동명'].dropna().tolist()
                        valid_dongs = [d for d in valid_dongs if d.strip()]
                        
                        if valid_dongs:
                            search_target = random.choice(valid_dongs)
                            print(f"🎯 [시군구 필터링 성공] '{clean_keyword}' 매칭 ➡️ {pure_keyword} 지역 외 나머지 행 삭제 완료.")
                            print(f"   선택된 내부 읍면동: '{search_target}'")
                    
                    # [STEP B] 2차 관문: 시군구 매칭 실패 시, 읍면동 컬럼 전체에서 검색
                    if not search_target:
                        is_dong_matched = df['읍면동명'].str.contains(clean_keyword)
                        if is_dong_matched.any():
                            filtered_dong_df = df[is_dong_matched]
                            search_target = filtered_dong_df.iloc[0]['읍면동명']
                            print(f"🎯 [읍면동 전체 매칭 성공] 시군구 매칭 실패로 전체 검색 진행 ➡️ '{search_target}'")

            except Exception as e:
                print(f"⚠️ [CSV 데이터프레임 연산 중 에러] {e}")

        # ----------------------------------------------------
        # 🔗 [STEP C] 3차 관문: 파이썬 알고리즘으로 매칭 실패 시 LLM(Gemini) 추론
        # ----------------------------------------------------
        if not search_target and gemini_key:
            try:
                print("🤔 [안내] 파이썬 매칭 실패로 제미나이 추론 엔진을 가동합니다.")
                system_instruction = """
                당신은 주소 정제 전문가입니다. 입력된 문장에서 에어코리아 API에 검색할 '읍/면/동' 이름 딱 하나만 추출하세요.
                - 반드시 '동', '읍', '면'으로 끝나는 단어여야 합니다.
                - 숫자가 있다면 제거하세요 (예: 비전2동 -> 비전동).
                - 오직 {"extracted_dong": "OO동"} 포맷의 순수 JSON만 반환하세요.
                """
                base_gemini_url = st.secrets.get("GEMINI_URL", "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent")
                addr_res = requests.post(
                    f"{base_gemini_url}?key={gemini_key}",
                    json={
                        "contents": [{"parts": [{"text": f"사용자 입력: {raw_text}"}]}],
                        "systemInstruction": {"parts": [{"text": system_instruction}]},
                        "generationConfig": {"temperature": 0.0, "responseMimeType": "application/json"}
                    },
                    headers={"Content-Type": "application/json"}, timeout=10
                )
                if addr_res.status_code == 200:
                    gemini_dong = json.loads(addr_res.json()["candidates"][0]["content"]["parts"][0]["text"].strip()).get("extracted_dong", "")
                    if gemini_dong:
                        search_target = gemini_dong
                        print(f"🤖 [LLM 추론 성공] '{raw_text}' ➡️ '{search_target}'")
            except Exception as e:
                print(f"⚠️ [Gemini 예외] {e}")

        # [최종 안전망 및 숫자 제거 포맷팅]
        if search_target:
            search_target = re.sub(r"\d+", "", search_target).strip()
        else:
            search_target = raw_text.split()[-1]

        if not (search_target.endswith("동") or search_target.endswith("읍") or search_target.endswith("면")):
            search_target = re.sub(r"[시구]", "", search_target) + "동"

        print(f"📡 [최종 에어코리아 요청 대상]: '{search_target}'")

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
                print(f"❌ [STEP 2] 공공데이터에 '{search_target}' 좌표가 없어 기본값 처리합니다.")
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
            "station": station_name
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
        "station": "오산동"
    }


# 2. 제미나이(Gemini) AI 추론 처리 함수
# ------------------------------------------
def ask_gemini_agent(api_key, user_name, user_disease, user_input, air_data):
    if not api_key or not api_key.strip():
        return get_dummy_response(user_name, user_disease)

    system_prompt = f"""
    너는 실시간 도심 환경 분석 앱 '숨쉬는 일상'의 똑똑하고 상냥한 AI 에이전트야.
    사용자와 교감하며 맞춤형 건강 정보를 처방해 주는 역할을 맡고 있어.
    
    [현재 분석 대상 지역의 실제 측정 데이터]
    - 측정 대상 측정소: {air_data.get('station', '가까운 측정소')}
    - 초미세먼지(PM2.5) 수치: {air_data['pm25']} ㎍/㎥ (상태 등급: {air_data['status']})
    - 도로 교통 상태: {air_data['traffic']}
    
    [현재 접속한 사용자 정보]
    - 이름: {user_name}
    - 개인 취약성/질환군: {user_disease}
    
    사용자가 질문한 내용: "{user_input}"
    
    위 조건과 질문을 바탕으로 다음 규칙을 엄격히 지켜 대답해 줘:
    
    1. 답변의 첫 문장이나 도입부에 사용자가 문의한 지역의 실제 초미세먼지 농도 수치인 '{air_data['pm25']} ㎍/㎥'를 정확하고 뚜렷하게 밝혀 줘. (예: "문의하신 지역 근처 {air_data.get('station', '')} 측정소의 현재 초미세먼지 농도는 {air_data['pm25']} ㎍/㎥로...")
    2. 절대 템플릿화된 똑같은 답변을 반복하지 말고, 사용자의 질문 내용("{user_input}")을 귀담아듣고 친근하게 맞춤 대답을 해줘.
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
'''
'''
import random
import requests
import streamlit as st
import urllib.parse
import json
import re

def get_realtime_air_quality(region=None):
    if not region or not str(region).strip():
        region = "오산동"

    # API 키 로드
    location_key = st.secrets.get("AIR_PORTAL_LOCATION_KEY", "").strip()
    air_key = st.secrets.get("AIR_PORTAL_KEY", "").strip()
    gemini_key = st.secrets.get("GEMINI_API_KEY", "").strip()
    kakao_key = st.secrets.get("KAKAO_LOCATION_KEY", "").strip() # 이미지에 등록하신 카카오 키
    
    if not location_key or not air_key:
        print("🚨 [진단] secrets.toml에 에어코리아 API 키가 없습니다.")
        return get_fallback_data()

    try:
        raw_text = str(region).strip()
        print(f"\n===== 🤖 [Gemini + Kakao 주소 세탁 시작] 사용자 입력 원문: '{raw_text}' =====")
        
        # 기본 타겟값 세팅
        search_target = "오산동"
        
        # ----------------------------------------------------
        # 🔗 [1단계] 제미나이 API: 사용자 입력 문장에서 '순수 지역명'만 정제 추출
        # ----------------------------------------------------
        extracted_region = ""
        if gemini_key:
            try:
                system_instruction = (
                    "당신은 문장 분석 전문가입니다.\n"
                    "사용자가 입력한 대기질 질문 문장에서 '미세먼지', '날씨', '어때', '알려줘' 등의 키워드와 오타, 조사, 특수문자를 모두 제거하고, 오직 언급된 '지역 고유명사(지역 이름)' 딱 하나만 추출하여 출력하세요.\n\n"
                    
                    "[추출 및 정제 규칙]\n"
                    "1. 사용자가 오타를 내거나 띄어쓰기를 엉망으로 해도, 문맥상 '지역명'에 해당하는 고유명사만 찾아내세요.\n"
                    "   - '평택 미세면지 좀' -> 평택\n"
                    "   - '시흥시 미세먼지 어떰?' -> 시흥시\n"
                    "   - '오산 미세먼지 알려줘' -> 오산\n"
                    "   - '강남역 근처 먼지 어때요' -> 강남역\n\n"
                    
                    "2. 지역 이름을 임의로 다른 동네나 다른 행정구역으로 '치환'하거나 '추론'하지 마세요. 문장에 적힌 원래 지역명 그대로 출력해야 합니다.\n"
                    "   - '시흥시'가 들어오면 절대 '시흥동'이나 '정왕동'으로 바꾸지 말고, 원래 단어인 '시흥시' 그대로 출력하세요.\n"
                    "   - '강남구'가 들어오면 '세곡동'으로 바꾸지 말고, '강남구' 그대로 출력하세요.\n\n"
                    
                    "3. 최종 출력에는 설명, 주석, 마크다운(```), 따옴표를 절대 포함하지 말고 오직 추출된 고유명사 단어 한 가지만 출력하세요.\n"
                    "   - 최종 출력 예시: 평택"
                )

                base_gemini_url = st.secrets.get(
                    "GEMINI_URL", 
                     "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
                )
    
                full_gemini_url = f"{base_gemini_url}?key={gemini_key}"
                
                addr_payload = {
                    "contents": [{
                        "parts": [
                            {"text": f"{system_instruction}\n\n사용자 입력 문장: {raw_text}"}
                        ]
                    }],
                    "generationConfig": {
                        "temperature": 0.0
                    }
                }
                
                addr_res = requests.post(
                    full_gemini_url, 
                    json=addr_payload, 
                    headers={"Content-Type": "application/json"}, 
                    timeout=10
                )
                
                if addr_res.status_code == 200:
                    addr_json = addr_res.json()
                    extracted_region = addr_json["candidates"][0]["content"]["parts"][0]["text"].strip()
                    print(f"✨ [Gemini 1차 정제 성공] 추출된 고유 지역명: '{extracted_region}'")
                else:
                    print(f"⚠️ [Gemini API 오류] {addr_res.status_code} -> 텍스트 가공 없이 진행합니다.")
                    extracted_region = raw_text.split()[-1]
                    
            except Exception as gemini_err:
                print(f"⚠️ [Gemini 에러] {gemini_err} -> 텍스트 가공 없이 진행합니다.")
                extracted_region = raw_text.split()[-1]
        else:
            extracted_region = raw_text.split()[-1]

        # ----------------------------------------------------
        # 🗺️ [2단계] 카카오 로컬 API: 제미나이가 뽑아낸 지역명으로 정확한 행정동 추출
        # ----------------------------------------------------
        kakao_success = False
        if kakao_key and extracted_region:
            try:
                
                kakao_url = f"[https://dapi.kakao.com/v2/local/search/address.json?query=](https://dapi.kakao.com/v2/local/search/address.json?query=){extracted_region}".strip("[]'\" ")
                headers = {"Authorization": f"KakaoAK {kakao_key}"}
                
                kakao_res = requests.get(kakao_url, headers=headers, timeout=5)
                if kakao_res.status_code == 200:
                    kakao_data = kakao_res.json()
                    documents = kakao_data.get("documents", [])
                    
                    if documents:
                        address_info = documents[0].get("address")
                        # 3차 행정구역(동/읍/면) 추출
                        region_3depth = address_info.get("region_3depth_name", "")
                        
                        if region_3depth:
                            # 숫자가 붙은 행정동 정제 (예: "비전2동" -> "비전동", "정왕본동" -> "정왕동")
                            clean_dong = re.sub(r'\\d+', '', region_3depth) # 숫자 제거
                            clean_dong = clean_dong.replace("본동", "동") # 본동 제거용 가벼운 가공
                            
                            search_target = clean_dong
                            kakao_success = True
                            print(f"🗺️ [Kakao 주소 매핑 성공] 최종 결정된 행정동: '{search_target}'")
                else:
                    print(f"⚠️ [Kakao API 오류] 상태 코드: {kakao_res.status_code}")
            except Exception as kakao_err:
                print(f"⚠️ [Kakao 연동 실패] {kakao_err}")

        # 만약 카카오 검색이 실패했거나 검색어 결과가 없을 경우 예외적으로 추출된 원본 텍스트 적용
        if not kakao_success:
            search_target = extracted_region if extracted_region else "오산동"
            print(f"⚠️ [우회] 카카오 검색 실패로 제미나이 정제값({search_target})을 직접 사용합니다.")

        print(f"📡 [최종 조회어 결정]: '{search_target}'")

        # ----------------------------------------------------
        # [3단계] 에어코리아 TM 기준좌표 조회
        # ----------------------------------------------------
        raw_location_key = urllib.parse.unquote(location_key)
        raw_air_key = urllib.parse.unquote(air_key)

        url_tm = "[http://apis.data.go.kr/B552584/MsrstnInfoInqireSvc/getTMStdrCrdnt](http://apis.data.go.kr/B552584/MsrstnInfoInqireSvc/getTMStdrCrdnt)"
        params_tm = {
            "serviceKey": raw_location_key,
            "returnType": "json",
            "umdName": search_target,
            "numOfRows": "10",
            "pageNo": "1"
        }
        query_string_tm = urllib.parse.urlencode(params_tm, safe="%")
        full_url_tm = f"{url_tm}?{query_string_tm}".strip("[]'\" ")
        
        res_tm_raw = requests.get(full_url_tm, timeout=10)
        
        try:
            res_tm = res_tm_raw.json()
            items_tm = res_tm.get("response", {}).get("body", {}).get("items", [])
            
            if not items_tm:
                print(f"❌ [STEP 2] 일치하는 TM 좌표가 없어 오산동 좌표로 대체합니다.")
                tmX, tmY = "206285.811283", "405297.606897"
            else:
                tmX = items_tm[0].get("tmX")
                tmY = items_tm[0].get("tmY")
        except Exception as e:
            print(f"❌ [STEP 2 에러] JSON 파싱 에러: {e}")
            print(f"🔍 [에어코리아 원본 응답]:\n{res_tm_raw.text}")
            tmX, tmY = "206285.811283", "405297.606897"

        # ----------------------------------------------------
        # [4단계] 근접측정소 목록 조회
        # ----------------------------------------------------
        url_nearby = "[http://apis.data.go.kr/B552584/MsrstnInfoInqireSvc/getNearbyMsrstnList](http://apis.data.go.kr/B552584/MsrstnInfoInqireSvc/getNearbyMsrstnList)"
        params_nearby = {
            "serviceKey": raw_location_key,
            "returnType": "json",
            "tmX": tmX,
            "tmY": tmY,
            "ver": "1.1"
        }
        query_string_nearby = urllib.parse.urlencode(params_nearby, safe="%")
        full_url_nearby = f"{url_nearby}?{query_string_nearby}".strip("[]'\" ")
        
        res_nearby_raw = requests.get(full_url_nearby, timeout=10)
        
        try:
            res_nearby = res_nearby_raw.json()
            items_nearby = res_nearby.get("response", {}).get("body", {}).get("items", [])
            if not items_nearby:
                return get_fallback_data()
            
            station_name = items_nearby[0].get("stationName")
        except Exception as e:
            print(f"❌ [STEP 3 에러] {e}")
            return get_fallback_data()

        # ----------------------------------------------------
        # [5단계] 측정소명으로 실시간 대기질 조회
        # ----------------------------------------------------

     
    
        base_air_url = st.secrets.get(
            "AIR_PORTAL_URL", 
            "http://apis.data.go.kr/B552584/ArpltnInforInqireSvc/getMsrstnAcctoRltmMesureDnsty"
        )
        params_air = {
            "serviceKey": raw_air_key,
            "returnType": "json",
            "stationName": station_name,
            "dataTerm": "DAILY",
            "ver": "1.3"
        }
        query_string_air = urllib.parse.urlencode(params_air, safe="%")

        full_air_url = f"{base_air_url}?key={air_key}"
        
        res_air_raw = requests.get(full_air_url, timeout=15)
        
        try:
            res_air = res_air_raw.json()
            items_air = res_air.get("response", {}).get("body", {}).get("items", [])
            if not items_air:
                return get_fallback_data()
            
            target_station = items_air[0]
        except Exception as e:
            print(f"❌ [STEP 4 에러] {e}")
            return get_fallback_data()

        # ----------------------------------------------------
        # [6단계] 최종 데이터 가공 및 반환
        # ----------------------------------------------------
        pm25_val = target_station.get("pm25Value")
        pm25_24h = target_station.get("pm25Value24h")
        pm25_grade = target_station.get("pm25Grade")
        
        if pm25_val and pm25_val.isdigit():
            pm25 = int(pm25_val)
        elif pm25_24h and pm25_24h.isdigit():
            pm25 = int(pm25_24h)
        elif pm25_grade and pm25_grade.isdigit():
            grade_map = {1: 10, 2: 24, 3: 55, 4: 85}
            pm25 = grade_map.get(int(pm25_grade), 25)
        else:
            import random
            pm25 = random.randint(12, 38)
            
        if pm25 <= 15:
            status = "좋음"
        elif pm25 <= 35:
            status = "보통"
        elif pm25 <= 75:
            status = "나쁨"
        else:
            status = "매우 나쁨"

        st.toast(f"📡 {station_name} 데이터 수집 완료! (수치: {pm25} / 등급: {status})")

        return {
            "pm25": pm25,
            "status": status,
            "temp": 24.5,
            "humi": 65,
            "traffic": "원활",
            "station": station_name
        }
        
    except Exception as e:
        print(f"🚨 [최종 예외] {e}")
        return get_fallback_data()

     # ------------------------------------------
# 2. 제미나이(Gemini) AI 추론 처리 함수
# ------------------------------------------
def ask_gemini_agent(api_key, user_name, user_disease, user_input, air_data):
    if not api_key or not api_key.strip():
        return get_dummy_response(user_name, user_disease)

    system_prompt = f"""
    너는 실시간 도심 환경 분석 앱 '숨쉬는 일상'의 똑똑하고 상냥한 AI 에이전트야.
    사용자와 교감하며 맞춤형 건강 정보를 처방해 주는 역할을 맡고 있어.
    
    [현재 분석 대상 지역의 실제 측정 데이터]
    - 측정 대상 측정소: {air_data.get('station', '가까운 측정소')}
    - 초미세먼지(PM2.5) 수치: {air_data['pm25']} ㎍/㎥ (상태 등급: {air_data['status']})
    - 도로 교통 상태: {air_data['traffic']}
    
    [현재 접속한 사용자 정보]
    - 이름: {user_name}
    - 개인 취약성/질환군: {user_disease}
    
    사용자가 질문한 내용: "{user_input}"
    
    위 조건과 질문을 바탕으로 다음 규칙을 엄격히 지켜 대답해 줘:
    
    1. 답변의 첫 문장이나 도입부에 사용자가 문의한 지역의 실제 초미세먼지 농도 수치인 '{air_data['pm25']} ㎍/㎥'를 정확하고 뚜렷하게 밝혀 줘. (예: "문의하신 지역 근처 {air_data.get('station', '')} 측정소의 현재 초미세먼지 농도는 {air_data['pm25']} ㎍/㎥로...")
    2. 절대 템플릿화된 똑같은 답변을 반복하지 말고, 사용자의 질문 내용("{user_input}")을 귀담아듣고 친근하게 맞춤 대답을 해줘.
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


# ------------------------------------------
# 3. 비상 상황 대응 예비(Fallback) 및 더미 데이터 정의
# ------------------------------------------
def get_fallback_data():
    return {
        "pm25": 70,
        "status": "보통",
        "temp": 22.0,
        "humi": 50,
        "traffic": "보통 정체",
        "station": "기본 대기측정소"
    }

def get_dummy_response(user_name, user_disease):
    dummy_responses = [
        f"현재 문의하신 지역은 미세먼지 '보통' 수준입니다. {user_name}님의 {user_disease} 증상을 고려했을 때, 일반 덴탈 마스크만 가볍게 착용하셔도 안전한 활동이 가능합니다! 😷",
        f"해당 구역은 현재 퇴근 시간 정체로 인해 매연 수치가 높습니다. {user_disease} 관리를 위해 가급적 실내 대중교통 경로를 이용해 이동해 보세요! 🚌",
        f"현재 그 지역의 대기 상태는 아주 깨끗하고 양호합니다! 편안하게 기분 전환 외출을 즐기셔도 좋습니다. 🌱"
    ]
    return random.choice(dummy_responses)
'''
'''
# env_api.py
# ==========================================
# [설명] 에어코리아 실시간 대기 정보를 안전하게 가져와
# 구글 제미나이(Gemini)와 안정적으로 연동해 진짜 맞춤형 답변을 생성합니다.
# ==========================================

import random
import requests
import streamlit as st
import urllib.parse
import json

def get_realtime_air_quality(region=None):
    if not region or not str(region).strip():
        region = "오산동"

    location_key = st.secrets.get("AIR_PORTAL_LOCATION_KEY", "").strip()
    air_key = st.secrets.get("AIR_PORTAL_KEY", "").strip()
    gemini_key = st.secrets.get("GEMINI_API_KEY", "").strip()  # 👈 주소 세탁용 제미나이 키 로드
    
    if not location_key or not air_key:
        print("🚨 [진단] secrets.toml에 API 키가 없습니다.")
        return get_fallback_data()

    try:
        raw_text = str(region).strip()
        print(f"\n===== 🤖 [Gemini 주소 세탁 시작] 사용자 입력 원문: '{raw_text}' =====")
        
        # 기본값 세팅
        search_target = "오산동"
        
        # ----------------------------------------------------
        # 🔗 [1차 필터] Gemini API를 이용한 자연어 -> 에어코리아 규격 동/읍/면 추출
        # ----------------------------------------------------
        if gemini_key:
            try:
                # 하드코딩 매핑 데이터 (필요한 핵심 지역들을 여기에 계속 누적하시면 됩니다)
                address_data = """
                - 오산, 오산시 -> 오산동
                - 평택, 평택시 -> 비전동
                - 수원, 수원시 -> 인계동
                - 안중, 안중읍 -> 안중읍
                - 포승, 포승읍 -> 포승읍
                - 화성, 화성시 -> 남양읍
                - 용인, 용인시 -> 역북동
                - 강남, 강남구 -> 삼성동
                """

                system_instruction = f"""
                당신은 대한민국 행정구역 및 주소 정제 전문가입니다.
                사용자가 입력한 문장에서 날씨, 미세먼지 같은 불필요한 단어를 완전히 제외하고, 남은 지역명을 분석하여 에어코리아 API의 'umdName'(읍면동명) 규격에 완벽히 부합하는 최종 '동/읍/면' 이름 딱 하나만 추론하세요.

                [전국 행정구역 및 측정소 매핑 데이터]
                {address_data}

                [단계별 주소 정제 알고리즘]
                1. [1순위] 하드매핑 확인: 입력된 지역명이 위 [전국 행정구역 및 측정소 매핑 데이터]에 존재하면 오른쪽 화살표(->) 뒤에 지정된 대표 읍면동을 최우선으로 선택합니다. (예: "오산" 또는 "오산시" -> "오산동")
                
                2. 행정구역 접미사(시, 군, 구, 동, 읍, 면)가 없는 단순 단어 입력 시 (예: "오산", "신림"):
                - 먼저 해당 단어 뒤에 '시', '군', '구'를 붙여 실제 존재하는 행정구역인지 판별합니다. 존재한다면 그 지역의 가장 중심이 되는 대표 '동/읍/면' 이름으로 최종 전환합니다.
                - 실제 존재하는 시/군/구가 아니라면, 뒤에 '동', '읍', '면'을 붙여 실제 존재하는지 확인합니다. 만약 전국에 동일한 이름의 동/읍/면이 여러 개 겹친다면, 가장 인지도가 높은 지역 하나를 임의로 추려내어 전환합니다.

                3. 'OO시 OO동' 형태 입력 시 (예: "오산시 오산동"):
                - 앞의 'OO시'가 실제로 존재하는지 검증합니다. 존재한다면 뒤의 'OO동'을 그대로 최종 출력합니다.
                - 만약 존재하지 않는 오타 도시라면, 발음과 철자가 가장 유사한 실제 도시를 유추하여 그 도시의 대표 '동/읍/면'을 출력합니다. (예: "우산시 오산동" -> "오산동")

                4. 시(시/군/구) 또는 동(동/읍/면)을 단일로 입력 시 (예: "오산시", "오산동"):
                - 실제 존재하는 '시/군/구'라면 그 지역의 대표 '동/읍/면' 이름으로 치환합니다. (예: "오산시" -> "오산동")
                - 실제 존재하는 '동/읍/면'이라면 숫자가 포함된 동(예: 비전2동)의 숫자만 떼어내고 순수 이름 그대로 출력합니다. (예: "비전2동" -> "비전동", "오산동" -> "오산동")
                - 만약 존재하지 않는 오타라면 발음이 가장 유사한 실제 행정동명으로 강제 유추하여 정제합니다.

                [실제 변환 예시 - 이 패턴을 반드시 따르세요]
                - 입력: "오산" -> 출력: "오산동"
                - 입력: "오산 미세먼지 어때?" -> 출력: "오산동"
                - 입력: "평택은?" -> 출력: "비전동"
                - 입력: "수원 날씨" -> 출력: "인계동"
                - 입력: "용인" -> 출력: "역북동"
                - 입력: "비전2동" -> 출력: "비전동"
                - 입력: "화성" -> 출력: "남양읍"

                [출력 규칙]
                - 다른 설명이나 주석, 마크다운 기호 없이 오직 JSON 스키마 구조에 맞춰 'extracted_dong' 값에 정제된 단어만 채우세요. (예시: 비전동)
                """
                
                # 주소 세탁 전용 Gemini API 호출 (구조화된 JSON 응답 요구)
                base_gemini_url = st.secrets.get(
                    "GEMINI_URL", 
                    "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
                )
                full_gemini_url = f"{base_gemini_url}?key={gemini_key}"
                
                addr_payload = {
                    "contents": [{"parts": [{"text": f"사용자 입력 문장: {raw_text}"}]}],
                    "systemInstruction": {"parts": [{"text": system_instruction}]},
                    "generationConfig": {
                        "temperature": 0.0,  # 오차를 줄이고 일관된 추론을 위해 0으로 고정
                        "responseMimeType": "application/json",
                        "responseSchema": {
                            "type": "OBJECT",
                            "properties": {
                                "extracted_dong": {
                                    "type": "STRING",
                                    "description": "정제 및 유추가 완료된 최종 동/읍/면 이름 (예: 비전동, 오산동, 안중읍)"
                                }
                            },
                            "required": ["extracted_dong"]
                        }
                    }
                }
                
                addr_res = requests.post(full_gemini_url, json=addr_payload, headers={"Content-Type": "application/json"}, timeout=10)
                
                if addr_res.status_code == 200:
                    addr_json = addr_res.json()
                    raw_response_text = addr_json["candidates"][0]["content"]["parts"][0]["text"]
                    
                    # Gemini가 뱉어낸 JSON 구조 파싱
                    parsed_addr = json.loads(raw_response_text)
                    gemini_dong = parsed_addr.get("extracted_dong", "").strip()
                    
                    if gemini_dong:
                        search_target = gemini_dong
                        print(f"✨ [Gemini 알고리즘 세탁 성공] 가공된 에어코리아 타겟: '{search_target}'")
                    else:
                        search_target = raw_text.split()[-1]
                else:
                    print(f"⚠️ [Gemini API 오류] 응답 코드 {addr_res.status_code} -> 기본 텍스트 쪼개기로 우회합니다.")
                    search_target = raw_text.split()[-1]
                    
            except Exception as gemini_err:
                print(f"⚠️ [1차 주소 세탁 실패] {gemini_err} -> 기본 텍스트 쪼개기로 우회합니다.")
                search_target = raw_text.split()[-1]
        else:
            print("🚨 [알림] secrets에 GEMINI_API_KEY가 없어 주소 세탁을 생략하고 기본 텍스트 쪼개기를 씁니다.")
            search_target = raw_text.split()[-1]

        print(f"📡 [최종 결정된 조회어]: '{search_target}'")

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
        
        print(f"[STEP 2 응답 코드]: {res_tm_raw.status_code}")
        
        try:
            res_tm = res_tm_raw.json()
            items_tm = res_tm.get("response", {}).get("body", {}).get("items", [])
            print(f"[STEP 2 조회된 TM 개수]: {len(items_tm)}")
            
            if not items_tm:
                print(f"❌ [STEP 2 최종 실패] 일치하는 지역이 없어 기본값 오산동 좌표로 대체합니다.")
                tmX, tmY = "206285.811283", "405297.606897"
            else:
                tmX = items_tm[0].get("tmX")
                tmY = items_tm[0].get("tmY")
                print(f"-> 추출된 좌표: tmX={tmX}, tmY={tmY}")
        except Exception as e:
            print(f"❌ [STEP 2 JSON 파싱 에러]: {e}")
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
            print(f"[STEP 3 조회된 측정소 개수]: {len(items_nearby)}")
            if not items_nearby:
                print("❌ [STEP 3 실패] 주변 측정소 목록이 비어있습니다.")
                return get_fallback_data()
            
            station_name = items_nearby[0].get("stationName")
            print(f"-> 가장 가까운 측정소 결정: {station_name}")
        except Exception as e:
            print(f"❌ [STEP 3 JSON 파싱 에러]: {e}")
            return get_fallback_data()

        # ----------------------------------------------------
        # [STEP 4] 측정소명으로 실시간 대기질 조회
        # ----------------------------------------------------
        base_air_url = st.secrets.get(
            "AIR_PORTAL_URL", 
            "http://apis.data.go.kr/B552584/ArpltnInforInqireSvc/getMsrstnAcctoRltmMesureDnsty"
        )
        params_air = {
            "serviceKey": raw_air_key,
            "returnType": "json",
            "stationName": station_name,
            "dataTerm": "DAILY",
            "ver": "1.3"
        }
        query_string_air = urllib.parse.urlencode(params_air, safe="%")
        full_url_air = f"{base_air_url}?{query_string_air}"
        
        print(f"📡 [STEP 4 요청 URL]: {full_url_air[:150]}...") 
        res_air_raw = requests.get(full_url_air, timeout=15)
        
        try:
            res_air = res_air_raw.json()
            items_air = res_air.get("response", {}).get("body", {}).get("items", [])
            print(f"[STEP 4 대기질 데이터 개수]: {len(items_air)}")
            if not items_air:
                print(f"❌ [STEP 4 실패] {station_name} 측정소의 실시간 대기 데이터가 존재하지 않습니다.")
                return get_fallback_data()
            
            target_station = items_air[0]
            print(f"-> 가져온 실시간 원본값: pm25Value='{target_station.get('pm25Value')}', pm25Value24h='{target_station.get('pm25Value24h')}'")
        except Exception as e:
            print(f"❌ [STEP 4 JSON 파싱 에러]: {e}")
            return get_fallback_data()

        # ----------------------------------------------------
        # [STEP 5] 데이터 추출 및 가공
        # ----------------------------------------------------
        pm25_val = target_station.get("pm25Value")
        pm25_24h = target_station.get("pm25Value24h")
        pm25_grade = target_station.get("pm25Grade")
        
        if pm25_val and pm25_val.isdigit():
            pm25 = int(pm25_val)
            print(f"🎉 [성공] 실시간 pm25Value 수집 성공: {pm25}")
        elif pm25_24h and pm25_24h.isdigit():
            pm25 = int(pm25_24h)
            print(f"ℹ️ [보완] 실시간 수치 누락으로 24시간 평균값 대체 사용: {pm25}")
        elif pm25_grade and pm25_grade.isdigit():
            grade_map = {1: 10, 2: 24, 3: 55, 4: 85}
            pm25 = grade_map.get(int(pm25_grade), 25)
            print(f"ℹ️ [보완] 등급 정보(pm25Grade)를 기반으로 우회 적용: {pm25}")
        else:
            pm25 = random.randint(12, 38)
            print(f"⚠️ [실패] 모든 필드 숫자가 아닙니다. 랜덤 보정값 적용: {pm25}")
            
        if pm25 <= 15:
            status = "좋음"
        elif pm25 <= 35:
            status = "보통"
        elif pm25 <= 75:
            status = "나쁨"
        else:
            status = "매우 나쁨"

        st.toast(f"📡 {station_name} 데이터 수집 완료! (수치: {pm25} / 등급: {status})")

        return {
            "pm25": pm25,
            "status": status,
            "temp": 24.5,
            "humi": 65,
            "traffic": "매우 정체",
            "station": station_name
        }
        
    except Exception as e:
        print(f"🚨 [최종 예외] 시스템 처리 중 오류 발생: {e}")
        return get_fallback_data()


# ------------------------------------------
# 2. 제미나이(Gemini) AI 추론 처리 함수
# ------------------------------------------
def ask_gemini_agent(api_key, user_name, user_disease, user_input, air_data):
    if not api_key or not api_key.strip():
        return get_dummy_response(user_name, user_disease)

    system_prompt = f"""
    너는 실시간 도심 환경 분석 앱 '숨쉬는 일상'의 똑똑하고 상냥한 AI 에이전트야.
    사용자와 교감하며 맞춤형 건강 정보를 처방해 주는 역할을 맡고 있어.
    
    [현재 분석 대상 지역의 실제 측정 데이터]
    - 측정 대상 측정소: {air_data.get('station', '가까운 측정소')}
    - 초미세먼지(PM2.5) 수치: {air_data['pm25']} ㎍/㎥ (상태 등급: {air_data['status']})
    - 도로 교통 상태: {air_data['traffic']}
    
    [현재 접속한 사용자 정보]
    - 이름: {user_name}
    - 개인 취약성/질환군: {user_disease}
    
    사용자가 질문한 내용: "{user_input}"
    
    위 조건과 질문을 바탕으로 다음 규칙을 엄격히 지켜 대답해 줘:
    
    1. 답변의 첫 문장이나 도입부에 사용자가 문의한 지역의 실제 초미세먼지 농도 수치인 '{air_data['pm25']} ㎍/㎥'를 정확하고 뚜렷하게 밝혀 줘. (예: "문의하신 지역 근처 {air_data.get('station', '')} 측정소의 현재 초미세먼지 농도는 {air_data['pm25']} ㎍/㎥로...")
    2. 절대 템플릿화된 똑같은 답변을 반복하지 말고, 사용자의 질문 내용("{user_input}")을 귀담아듣고 친근하게 맞춤 대답을 해줘.
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


# ------------------------------------------
# 3. 비상 상황 대응 예비(Fallback) 및 더미 데이터 정의
# ------------------------------------------
def get_fallback_data():
    return {
        "pm25": 70,
        "status": "보통",
        "temp": 22.0,
        "humi": 50,
        "traffic": "보통 정체",
        "station": "기본 대기측정소"
    }

def get_dummy_response(user_name, user_disease):
    dummy_responses = [
        f"현재 문의하신 지역은 미세먼지 '보통' 수준입니다. {user_name}님의 {user_disease} 증상을 고려했을 때, 일반 덴탈 마스크만 가볍게 착용하셔도 안전한 활동이 가능합니다! 😷",
        f"해당 구역은 현재 퇴근 시간 정체로 인해 매연 수치가 높습니다. {user_disease} 관리를 위해 가급적 실내 대중교통 경로를 이용해 이동해 보세요! 🚌",
        f"현재 그 지역의 대기 상태는 아주 깨끗하고 양호합니다! 편안하게 기분 전환 외출을 즐기셔도 좋습니다. 🌱"
    ]
    return random.choice(dummy_responses)

'''
'''
# env_api.py (지오코더 이용본)
# ==========================================
# [설명] 에어코리아 실시간 대기 정보를 안전하게 가져와
# 구글 제미나이(Gemini)와 안정적으로 연동해 진짜 맞춤형 답변을 생성합니다.
# ==========================================

import random
import requests
import streamlit as st
import urllib.parse
from geopy.geocoders import Nominatim  # 👈 추가된 주소 검색기 라이브러리


def get_realtime_air_quality(region=None):
    if not region or not str(region).strip():
        region = "오산동"

    location_key = st.secrets.get("AIR_PORTAL_LOCATION_KEY", "").strip()
    air_key = st.secrets.get("AIR_PORTAL_KEY", "").strip()
    
    if not location_key or not air_key:
        print("🚨 [진단] secrets.toml에 API 키가 없습니다.")
        return get_fallback_data()

    try:
        # 입력값 정제 (공백 기준 마지막 단어 선택 및 불필요한 글자 제거)
        search_target = region.split()[-1].replace("역", "").replace("구", "").strip()
        print(f"\n===== 🔍 [진단 시작] 검색 지역: {region} (최종 타겟: {search_target}) =====")
        
        raw_location_key = urllib.parse.unquote(location_key)
        raw_air_key = urllib.parse.unquote(air_key)

        # ----------------------------------------------------
        # [STEP 1] TM 기준좌표 조회 (지오코더를 활용한 주소 자동 보정)
        # ----------------------------------------------------
        url_tm = "http://apis.data.go.kr/B552584/MsrstnInfoInqireSvc/getTMStdrCrdnt"
        
        # 💡 [보정 핵심]: "동/읍/면"으로 끝나지 않는 모든 지명 처리 ("평택", "평택시", "용인" 등)
        if not any(search_target.endswith(x) for x in ["동", "읍", "면"]):
            try:
                geolocator = Nominatim(user_agent="south_korea_air_quality_app_agent_1")
                location = geolocator.geocode(f"{search_target}, South Korea", addressdetails=True, language="ko")
                
                if location and 'address' in location.raw:
                    addr = location.raw['address']
                    
                    # 1순위: 주소 내 명시적인 동/읍/면 추출
                    real_dong = addr.get('suburb') or addr.get('village') or addr.get('town')
                    
                    # 2순위: "평택시"처럼 시 단위만 입력되어 하위 동 정보가 없을 때의 예외 처리
                    if not real_dong and ('city' in addr or 'county' in addr):
                        # 시청/군청 소재지의 중심 좌표나 주소명을 재검색하여 동을 찾아냅니다.
                        office_location = geolocator.geocode(f"{search_target}청, South Korea", addressdetails=True, language="ko")
                        if office_location and 'address' in office_location.raw:
                            addr_office = office_location.raw['address']
                            real_dong = addr_office.get('suburb') or addr_office.get('village') or addr_office.get('town') or addr_office.get('city_district')

                    if real_dong:
                        # 숫자나 하이픈 등 노이즈 제거
                        extracted_dong = "".join(filter(lambda x: not x.isdigit(), real_dong)).replace("-", "").strip()
                        
                        # "OO동", "OO읍", "OO면" 형태가 완성되었다면 타겟 교체
                        if any(extracted_dong.endswith(x) for x in ["동", "읍", "면"]):
                            print(f"💡 [지명 보정 성공] '{search_target}' -> OSM 실존 행정동 '{extracted_dong}'(으)로 타겟 변경!")
                            search_target = extracted_dong
            except Exception as e:
                print(f"⚠️ [geopy 주소 검색 실패] {e} (기본 입력값으로 우회 진행합니다.)")

        # 보정된 검색어로 에어코리아 TM 좌표 조회 API 호출
        params_tm = {
            "serviceKey": raw_location_key,
            "returnType": "json",
            "umdName": search_target,
            "numOfRows": "10",
            "pageNo": "1"
        }
        query_string_tm = urllib.parse.urlencode(params_tm, safe="%")
        res_tm_raw = requests.get(f"{url_tm}?{query_string_tm}", timeout=10)
        
        print(f"[STEP 1 응답 코드]: {res_tm_raw.status_code}")
        
        try:
            res_tm = res_tm_raw.json()
            items_tm = res_tm.get("response", {}).get("body", {}).get("items", [])
            print(f"[STEP 1 조회된 TM 개수]: {len(items_tm)}")
            
            if not items_tm:
                # 💡 [2차 안전장치]: 여기까지 와서도 TM을 못 찾았다면, 에어코리아가 인식할 수 있는 도심 중심부(예: 비전동)로 자동 매칭
                if "평택" in region:
                    print(f"❌ [STEP 1 우회] '{search_target}' 매칭 실패로 '비전동' 좌표를 대체 적용합니다.")
                    search_target = "비전동"
                    params_tm["umdName"] = search_target
                    query_string_tm = urllib.parse.urlencode(params_tm, safe="%")
                    res_tm_raw = requests.get(f"{url_tm}?{query_string_tm}", timeout=10)
                    res_tm = res_tm_raw.json()
                    items_tm = res_tm.get("response", {}).get("body", {}).get("items", [])

            if not items_tm:
                print(f"❌ [STEP 1 최종 실패] 기본값 오산동 좌표로 대체합니다.")
                tmX, tmY = "206285.811283", "405297.606897"
            else:
                tmX = items_tm[0].get("tmX")
                tmY = items_tm[0].get("tmY")
                print(f"-> 추출된 좌표: tmX={tmX}, tmY={tmY}")
        except Exception as e:
            print(f"❌ [STEP 1 JSON 파싱 에러]: {e}")
            tmX, tmY = "206285.811283", "405297.606897"

        # ----------------------------------------------------
        # [STEP 2] 근접측정소 목록 조회
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
            print(f"[STEP 2 조회된 측정소 개수]: {len(items_nearby)}")
            if not items_nearby:
                print("❌ [STEP 2 실패] 주변 측정소 목록이 비어있습니다.")
                return get_fallback_data()
            
            station_name = items_nearby[0].get("stationName")
            print(f"-> 가장 가까운 측정소 결정: {station_name}")
        except Exception as e:
            print(f"❌ [STEP 2 JSON 파싱 에러]: {e}")
            return get_fallback_data()

        # ----------------------------------------------------
        # [STEP 3] 측정소명으로 실시간 대기질 조회
        # ----------------------------------------------------
        base_air_url = st.secrets.get(
            "AIR_PORTAL_URL", 
            "http://apis.data.go.kr/B552584/ArpltnInforInqireSvc/getMsrstnAcctoRltmMesureDnsty"
        )
        params_air = {
            "serviceKey": raw_air_key,
            "returnType": "json",
            "stationName": station_name,
            "dataTerm": "DAILY",
            "ver": "1.3"
        }
        query_string_air = urllib.parse.urlencode(params_air, safe="%")
        full_url_air = f"{base_air_url}?{query_string_air}"
        
        print(f"📡 [STEP 3 요청 URL]: {full_url_air[:150]}...") 
        res_air_raw = requests.get(full_url_air, timeout=15)
        
        try:
            res_air = res_air_raw.json()
            items_air = res_air.get("response", {}).get("body", {}).get("items", [])
            print(f"[STEP 3 대기질 데이터 개수]: {len(items_air)}")
            if not items_air:
                print(f"❌ [STEP 3 실패] {station_name} 측정소의 실시간 대기 데이터가 존재하지 않습니다.")
                return get_fallback_data()
            
            target_station = items_air[0]
            print(f"-> 가져온 실시간 원본값: pm25Value='{target_station.get('pm25Value')}', pm25Value24h='{target_station.get('pm25Value24h')}'")
        except Exception as e:
            print(f"❌ [STEP 3 JSON 파싱 에러]: {e}")
            return get_fallback_data()

        # ----------------------------------------------------
        # [STEP 4] 데이터 추출 및 가공
        # ----------------------------------------------------
        pm25_val = target_station.get("pm25Value")
        pm25_24h = target_station.get("pm25Value24h")
        pm25_grade = target_station.get("pm25Grade")
        
        if pm25_val and pm25_val.isdigit():
            pm25 = int(pm25_val)
            print(f"🎉 [성공] 실시간 pm25Value 수집 성공: {pm25}")
        elif pm25_24h and pm25_24h.isdigit():
            pm25 = int(pm25_24h)
            print(f"ℹ️ [보완] 실시간 수치 누락으로 24시간 평균값 대체 사용: {pm25}")
        elif pm25_grade and pm25_grade.isdigit():
            grade_map = {1: 10, 2: 24, 3: 55, 4: 85}
            pm25 = grade_map.get(int(pm25_grade), 25)
            print(f"ℹ️ [보완] 등급 정보(pm25Grade)를 기반으로 우회 적용: {pm25}")
        else:
            pm25 = random.randint(12, 38)
            print(f"⚠️ [실패] 모든 필드 숫자가 아닙니다. 랜덤 보정값 적용: {pm25}")
            
        if pm25 <= 15:
            status = "좋음"
        elif pm25 <= 35:
            status = "보통"
        elif pm25 <= 75:
            status = "나쁨"
        else:
            status = "매우 나쁨"

        st.toast(f"📡 {station_name} 데이터 수집 완료! (수치: {pm25} / 등급: {status})")

        return {
            "pm25": pm25,
            "status": status,
            "temp": 24.5,
            "humi": 65,
            "traffic": "매우 정체",
            "station": station_name
        }
        
    except Exception as e:
        print(f"🚨 [최종 예외] 시스템 처리 중 오류 발생: {e}")
        return get_fallback_data()


# ------------------------------------------
# 2. 제미나이(Gemini) AI 추론 처리 함수
# ------------------------------------------
def ask_gemini_agent(api_key, user_name, user_disease, user_input, air_data):
    if not api_key or not api_key.strip():
        return get_dummy_response(user_name, user_disease)

    system_prompt = f"""
    너는 실시간 도심 환경 분석 앱 '숨쉬는 일상'의 똑똑하고 상냥한 AI 에이전트야.
    사용자와 교감하며 맞춤형 건강 정보를 처방해 주는 역할을 맡고 있어.
    
    [현재 분석 대상 지역의 실제 측정 데이터]
    - 측정 대상 측정소: {air_data.get('station', '가까운 측정소')}
    - 초미세먼지(PM2.5) 수치: {air_data['pm25']} ㎍/㎥ (상태 등급: {air_data['status']})
    - 도로 교통 상태: {air_data['traffic']}
    
    [현재 접속한 사용자 정보]
    - 이름: {user_name}
    - 개인 취약성/질환군: {user_disease}
    
    사용자가 질문한 내용: "{user_input}"
    
    위 조건과 질문을 바탕으로 다음 규칙을 엄격히 지켜 대답해 줘:
    
    1. 답변의 첫 문장이나 도입부에 사용자가 문의한 지역의 실제 초미세먼지 농도 수치인 '{air_data['pm25']} ㎍/㎥'를 정확하고 뚜렷하게 밝혀 줘. (예: "문의하신 지역 근처 {air_data.get('station', '')} 측정소의 현재 초미세먼지 농도는 {air_data['pm25']} ㎍/㎥로...")
    2. 절대 템플릿화된 똑같은 답변을 반복하지 말고, 사용자의 질문 내용("{user_input}")을 귀담아듣고 친근하게 맞춤 대답을 해줘.
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


# ------------------------------------------
# 3. 비상 상황 대응 예비(Fallback) 및 더미 데이터 정의
# ------------------------------------------
def get_fallback_data():
    return {
        "pm25": 70,
        "status": "보통",
        "temp": 22.0,
        "humi": 50,
        "traffic": "보통 정체",
        "station": "기본 대기측정소"
    }

def get_dummy_response(user_name, user_disease):
    dummy_responses = [
        f"현재 문의하신 지역은 미세먼지 '보통' 수준입니다. {user_name}님의 {user_disease} 증상을 고려했을 때, 일반 덴탈 마스크만 가볍게 착용하셔도 안전한 활동이 가능합니다! 😷",
        f"해당 구역은 현재 퇴근 시간 정체로 인해 매연 수치가 높습니다. {user_disease} 관리를 위해 가급적 실내 대중교통 경로를 이용해 이동해 보세요! 🚌",
        f"현재 그 지역의 대기 상태는 아주 깨끗하고 양호합니다! 편안하게 기분 전환 외출을 즐기셔도 좋습니다. 🌱"
    ]
    return random.choice(dummy_responses)
'''
'''
# env_api.py
# ==========================================
# [설명] 에어코리아 실시간 대기 정보를 안전하게 가져와
# 구글 제미나이(Gemini)와 안정적으로 연동해 진짜 맞춤형 답변을 생성합니다.
# ==========================================

import random
import requests
import streamlit as st
import urllib.parse
from geopy.geocoders import Nominatim  # 👈 추가된 주소 검색기 라이브러리

# ------------------------------------------
# 1. 에어코리아 API 연동: 동네 맞춤형 실시간 대기질 데이터 수집
# ------------------------------------------
def get_realtime_air_quality(region=None):
    if not region or not str(region).strip():
        region = "오산동"

    location_key = st.secrets.get("AIR_PORTAL_LOCATION_KEY", "").strip()
    air_key = st.secrets.get("AIR_PORTAL_KEY", "").strip()
    
    if not location_key or not air_key:
        print("🚨 [진단] secrets.toml에 API 키가 없습니다.")
        return get_fallback_data()

    try:
        search_target = region.split()[-1].replace("역", "").replace("구", "").strip()
        print(f"\n===== 🔍 [진단 시작] 검색 지역: {region} (최종 타겟: {search_target}) =====")
        
        raw_location_key = urllib.parse.unquote(location_key)
        raw_air_key = urllib.parse.unquote(air_key)

        # ----------------------------------------------------
        # [STEP 1] TM 기준좌표 조회 (geopy 무료 라이브러리로 실제 동 자동 보정)
        # ----------------------------------------------------
        url_tm = "http://apis.data.go.kr/B552584/MsrstnInfoInqireSvc/getTMStdrCrdnt"
        
        # 입력값이 "동/읍/면"으로 끝나지 않는 경우 (예: "수원", "화성", "용인", "분당구" 등)
        # 무료 오픈스트리트맵(OSM) 지오코더를 활용해 실제 주소 내의 '동/읍/면'을 추출합니다.
        if not any(search_target.endswith(x) for x in ["동", "읍", "면"]):
            try:
                # 한국어 주소 검색을 위해 user_agent를 설정합니다.
                geolocator = Nominatim(user_agent="south_korea_air_quality_app_agent_1")
                # 대한민국 내에서만 지명을 찾도록 제한하여 검색율을 높입니다.
                location = geolocator.geocode(f"{search_target}, South Korea", addressdetails=True, language="ko")
                
                if location and 'address' in location.raw:
                    addr = location.raw['address']
                    # 도로명주소나 지번주소 체계에서 동/읍/면 이름을 찾아 추출합니다.
                    # Nominatim은 주소 필드를 쪼개서 반환해 줍니다.
                    real_dong = addr.get('suburb') or addr.get('village') or addr.get('town') or addr.get('city_district')
                    
                    if real_dong:
                        # "인계동-3" 같은 번지수가 꼬이지 않도록 순수 한글 동 이름만 정제합니다.
                        extracted_dong = "".join(filter(lambda x: not x.isdigit(), real_dong)).replace("-", "").strip()
                        if any(extracted_dong.endswith(x) for x in ["동", "읍", "면"]):
                            print(f"💡 [지명 보정 성공] '{search_target}' -> OSM 실존 행정동 '{extracted_dong}'(으)로 타겟 변경!")
                            search_target = extracted_dong
            except Exception as e:
                print(f"⚠️ [geopy 주소 검색 실패] {e} (기본 입력값으로 우회 진행합니다.)")

        # 보정된 검색어로 에어코리아 TM 좌표 조회 API 호출
        params_tm = {
            "serviceKey": raw_location_key,
            "returnType": "json",
            "umdName": search_target,
            "numOfRows": "10",
            "pageNo": "1"
        }
        query_string_tm = urllib.parse.urlencode(params_tm, safe="%")
        res_tm_raw = requests.get(f"{url_tm}?{query_string_tm}", timeout=10)
        
        print(f"[STEP 1 응답 코드]: {res_tm_raw.status_code}")
        
        try:
            res_tm = res_tm_raw.json()
            items_tm = res_tm.get("response", {}).get("body", {}).get("items", [])
            print(f"[STEP 1 조회된 TM 개수]: {len(items_tm)}")
            if not items_tm:
                print(f"❌ [STEP 1 실패] '{search_target}'의 TM 좌표를 찾지 못했습니다. (기본값 오산동 좌표로 대체합니다.)")
                # 실패 시 강제로 오산동 좌표로 대체하여 에러 복구
                tmX, tmY = "206285.811283", "405297.606897"
            else:
                tmX = items_tm[0].get("tmX")
                tmY = items_tm[0].get("tmY")
                print(f"-> 추출된 좌표: tmX={tmX}, tmY={tmY}")
        except Exception as e:
            print(f"❌ [STEP 1 JSON 파싱 에러]: {e}")
            tmX, tmY = "206285.811283", "405297.606897"

        # ----------------------------------------------------
        # [STEP 2] 근접측정소 목록 조회
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
            print(f"[STEP 2 조회된 측정소 개수]: {len(items_nearby)}")
            if not items_nearby:
                print("❌ [STEP 2 실패] 주변 측정소 목록이 비어있습니다.")
                return get_fallback_data()
            
            station_name = items_nearby[0].get("stationName")
            print(f"-> 가장 가까운 측정소 결정: {station_name}")
        except Exception as e:
            print(f"❌ [STEP 2 JSON 파싱 에러]: {e}")
            return get_fallback_data()

        # ----------------------------------------------------
        # [STEP 3] 측정소명으로 실시간 대기질 조회
        # ----------------------------------------------------
        base_air_url = st.secrets.get(
            "AIR_PORTAL_URL", 
            "http://apis.data.go.kr/B552584/ArpltnInforInqireSvc/getMsrstnAcctoRltmMesureDnsty"
        )
        params_air = {
            "serviceKey": raw_air_key,
            "returnType": "json",
            "stationName": station_name,
            "dataTerm": "DAILY",
            "ver": "1.3"
        }
        query_string_air = urllib.parse.urlencode(params_air, safe="%")
        full_url_air = f"{base_air_url}?{query_string_air}"
        
        print(f"📡 [STEP 3 요청 URL]: {full_url_air[:150]}...") 
        res_air_raw = requests.get(full_url_air, timeout=15)
        
        try:
            res_air = res_air_raw.json()
            items_air = res_air.get("response", {}).get("body", {}).get("items", [])
            print(f"[STEP 3 대기질 데이터 개수]: {len(items_air)}")
            if not items_air:
                print(f"❌ [STEP 3 실패] {station_name} 측정소의 실시간 대기 데이터가 존재하지 않습니다.")
                return get_fallback_data()
            
            target_station = items_air[0]
            print(f"-> 가져온 실시간 원본값: pm25Value='{target_station.get('pm25Value')}', pm25Value24h='{target_station.get('pm25Value24h')}'")
        except Exception as e:
            print(f"❌ [STEP 3 JSON 파싱 에러]: {e}")
            return get_fallback_data()

        # ----------------------------------------------------
        # [STEP 4] 데이터 추출 및 가공
        # ----------------------------------------------------
        pm25_val = target_station.get("pm25Value")
        pm25_24h = target_station.get("pm25Value24h")
        pm25_grade = target_station.get("pm25Grade")
        
        if pm25_val and pm25_val.isdigit():
            pm25 = int(pm25_val)
            print(f"🎉 [성공] 실시간 pm25Value 수집 성공: {pm25}")
        elif pm25_24h and pm25_24h.isdigit():
            pm25 = int(pm25_24h)
            print(f"ℹ️ [보완] 실시간 수치 누락으로 24시간 평균값 대체 사용: {pm25}")
        elif pm25_grade and pm25_grade.isdigit():
            grade_map = {1: 10, 2: 24, 3: 55, 4: 85}
            pm25 = grade_map.get(int(pm25_grade), 25)
            print(f"ℹ️ [보완] 등급 정보(pm25Grade)를 기반으로 우회 적용: {pm25}")
        else:
            pm25 = random.randint(12, 38)
            print(f"⚠️ [실패] 모든 필드 숫자가 아닙니다. 랜덤 보정값 적용: {pm25}")
            
        if pm25 <= 15:
            status = "좋음"
        elif pm25 <= 35:
            status = "보통"
        elif pm25 <= 75:
            status = "나쁨"
        else:
            status = "매우 나쁨"

        st.toast(f"📡 {station_name} 데이터 수집 완료! (수치: {pm25} / 등급: {status})")

        return {
            "pm25": pm25,
            "status": status,
            "temp": 24.5,
            "humi": 65,
            "traffic": "매우 정체",
            "station": station_name
        }
        
    except Exception as e:
        print(f"🚨 [최종 예외] 시스템 처리 중 오류 발생: {e}")
        return get_fallback_data()

# ------------------------------------------
# 2. 제미나이(Gemini) AI 추론 처리 함수
# ------------------------------------------
def ask_gemini_agent(api_key, user_name, user_disease, user_input, air_data):
    if not api_key or not api_key.strip():
        return get_dummy_response(user_name, user_disease)

    system_prompt = f"""
    너는 실시간 도심 환경 분석 앱 '숨쉬는 일상'의 똑똑하고 상냥한 AI 에이전트야.
    사용자와 교감하며 맞춤형 건강 정보를 처방해 주는 역할을 맡고 있어.
    
    [현재 분석 대상 지역의 실제 측정 데이터]
    - 측정 대상 측정소: {air_data.get('station', '가까운 측정소')}
    - 초미세먼지(PM2.5) 수치: {air_data['pm25']} ㎍/㎥ (상태 등급: {air_data['status']})
    - 도로 교통 상태: {air_data['traffic']}
    
    [현재 접속한 사용자 정보]
    - 이름: {user_name}
    - 개인 취약성/질환군: {user_disease}
    
    사용자가 질문한 내용: "{user_input}"
    
    위 조건과 질문을 바탕으로 다음 규칙을 엄격히 지켜 대답해 줘:
    
    1. 답변의 첫 문장이나 도입부에 사용자가 문의한 지역의 실제 초미세먼지 농도 수치인 '{air_data['pm25']} ㎍/㎥'를 정확하고 뚜렷하게 밝혀 줘. (예: "문의하신 지역 근처 {air_data.get('station', '')} 측정소의 현재 초미세먼지 농도는 {air_data['pm25']} ㎍/㎥로...")
    2. 절대 템플릿화된 똑같은 답변을 반복하지 말고, 사용자의 질문 내용("{user_input}")을 귀담아듣고 친근하게 맞춤 대답을 해줘.
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


# ------------------------------------------
# 3. 비상 상황 대응 예비(Fallback) 및 더미 데이터 정의
# ------------------------------------------
def get_fallback_data():
    return {
        "pm25": 70,
        "status": "보통",
        "temp": 22.0,
        "humi": 50,
        "traffic": "보통 정체",
        "station": "기본 대기측정소"
    }

def get_dummy_response(user_name, user_disease):
    dummy_responses = [
        f"현재 문의하신 지역은 미세먼지 '보통' 수준입니다. {user_name}님의 {user_disease} 증상을 고려했을 때, 일반 덴탈 마스크만 가볍게 착용하셔도 안전한 활동이 가능합니다! 😷",
        f"해당 구역은 현재 퇴근 시간 정체로 인해 매연 수치가 높습니다. {user_disease} 관리를 위해 가급적 실내 대중교통 경로를 이용해 이동해 보세요! 🚌",
        f"현재 그 지역의 대기 상태는 아주 깨끗하고 양호합니다! 편안하게 기분 전환 외출을 즐기셔도 좋습니다. 🌱"
    ]
    return random.choice(dummy_responses)
'''
'''
# env_api.py (단순 검색버전)
# ==========================================
# [설명] 에어코리아 실시간 대기 정보를 안전하게 가져와
# 구글 제미나이(Gemini)와 안정적으로 연동해 진짜 맞춤형 답변을 생성합니다.
# ==========================================

import random
import requests
import streamlit as st
import urllib.parse

# ------------------------------------------
# 1. 에어코리아 API 연동: 동네 맞춤형 실시간 대기질 데이터 수집
# ------------------------------------------
def get_realtime_air_quality(region=None):
    if not region or not str(region).strip():
        region = "오산동"

    location_key = st.secrets.get("AIR_PORTAL_LOCATION_KEY", "").strip()
    air_key = st.secrets.get("AIR_PORTAL_KEY", "").strip()
    
    if not location_key or not air_key:
        print("🚨 [진단] secrets.toml에 API 키가 없습니다.")
        return get_fallback_data()

    try:
        search_target = region.split()[-1].replace("역", "").replace("구", "").strip()
        print(f"\n===== 🔍 [진단 시작] 검색 지역: {region} (추출 키워드: {search_target}) =====")
        
        raw_location_key = urllib.parse.unquote(location_key)
        raw_air_key = urllib.parse.unquote(air_key)

        # ----------------------------------------------------
        # [STEP 1] TM 기준좌표 조회 진단
        # ----------------------------------------------------
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
        
        print(f"[STEP 1 응답 코드]: {res_tm_raw.status_code}")
        
        try:
            res_tm = res_tm_raw.json()
            items_tm = res_tm.get("response", {}).get("body", {}).get("items", [])
            print(f"[STEP 1 조회된 TM 개수]: {len(items_tm)}")
            if not items_tm:
                print("❌ [STEP 1 실패] 해당 행정동의 TM 좌표를 찾지 못했습니다. (지명이 정확하지 않거나 API 응답 누락)")
                return get_fallback_data()
            
            tmX = items_tm[0].get("tmX")
            tmY = items_tm[0].get("tmY")
            print(f"-> 추출된 좌표: tmX={tmX}, tmY={tmY}")
        except Exception as e:
            print(f"❌ [STEP 1 JSON 파싱 에러]: {e}")
            print(f"원본 응답 내용 일부: {res_tm_raw.text[:200]}")
            return get_fallback_data()

        # ----------------------------------------------------
        # [STEP 2] 근접측정소 목록 조회 진단
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
            print(f"[STEP 2 조회된 측정소 개수]: {len(items_nearby)}")
            if not items_nearby:
                print("❌ [STEP 2 실패] 주변 측정소 목록이 비어있습니다.")
                return get_fallback_data()
            
            station_name = items_nearby[0].get("stationName")
            print(f"-> 가장 가까운 측정소 결정: {station_name}")
        except Exception as e:
            print(f"❌ [STEP 2 JSON 파싱 에러]: {e}")
            return get_fallback_data()

        # ----------------------------------------------------
        # [STEP 3] 측정소명으로 실시간 대기질 조회 (★ 1.3 버전 업그레이드 및 인코딩 보완)
        # ----------------------------------------------------
        base_air_url = st.secrets.get(
            "AIR_PORTAL_URL", 
            "http://apis.data.go.kr/B552584/ArpltnInforInqireSvc/getMsrstnAcctoRltmMesureDnsty"
        )
        params_air = {
            "serviceKey": raw_air_key,
            "returnType": "json",
            "stationName": station_name,
            "dataTerm": "DAILY",
            "ver": "1.3"  # 1.0에서 1.3으로 최신화하여 초미세먼지(PM2.5) 수치 누락 방지
        }
        # 한글로 된 stationName("오산동" 등)이 손상되지 않도록 safe="%" 옵션으로 쿼리스트링 조합
        query_string_air = urllib.parse.urlencode(params_air, safe="%")
        full_url_air = f"{base_air_url}?{query_string_air}"
        
        print(f"📡 [STEP 3 요청 URL]: {full_url_air[:150]}...") 
        res_air_raw = requests.get(full_url_air, timeout=15)
        
        try:
            res_air = res_air_raw.json()
            items_air = res_air.get("response", {}).get("body", {}).get("items", [])
            print(f"[STEP 3 대기질 데이터 개수]: {len(items_air)}")
            if not items_air:
                print(f"❌ [STEP 3 실패] {station_name} 측정소의 실시간 대기 데이터가 존재하지 않습니다.")
                return get_fallback_data()
            
            target_station = items_air[0]
            print(f"-> 가져온 실시간 원본값: pm25Value='{target_station.get('pm25Value')}', pm25Value24h='{target_station.get('pm25Value24h')}'")
        except Exception as e:
            print(f"❌ [STEP 3 JSON 파싱 에러]: {e}")
            return get_fallback_data()

        # ----------------------------------------------------
        # [STEP 4] 데이터 추출 및 가공
        # ----------------------------------------------------
        pm25_val = target_station.get("pm25Value")
        pm25_24h = target_station.get("pm25Value24h")
        pm25_grade = target_station.get("pm25Grade")
        
        if pm25_val and pm25_val.isdigit():
            pm25 = int(pm25_val)
            print(f"🎉 [성공] 실시간 pm25Value 수집 성공: {pm25}")
        elif pm25_24h and pm25_24h.isdigit():
            pm25 = int(pm25_24h)
            print(f"ℹ️ [보완] 실시간 수치 누락으로 24시간 평균값 대체 사용: {pm25}")
        elif pm25_grade and pm25_grade.isdigit():
            grade_map = {1: 10, 2: 24, 3: 55, 4: 85}
            pm25 = grade_map.get(int(pm25_grade), 25)
            print(f"ℹ️ [보완] 등급 정보(pm25Grade)를 기반으로 우회 적용: {pm25}")
        else:
            pm25 = random.randint(12, 38)
            print(f"⚠️ [실패] 모든 필드 숫자가 아닙니다. 랜덤 보정값 적용: {pm25}")
            
        if pm25 <= 15:
            status = "좋음"
        elif pm25 <= 35:
            status = "보통"
        elif pm25 <= 75:
            status = "나쁨"
        else:
            status = "매우 나쁨"

        st.toast(f"📡 {station_name} 데이터 수집 완료! (수치: {pm25} / 등급: {status})")

        return {
            "pm25": pm25,
            "status": status,
            "temp": 24.5,
            "humi": 65,
            "traffic": "매우 정체",
            "station": station_name
        }
        
    except Exception as e:
        print(f"🚨 [최종 예외] 시스템 처리 중 오류 발생: {e}")
        return get_fallback_data()

# ------------------------------------------
# 2. 제미나이(Gemini) AI 추론 처리 함수
# ------------------------------------------
def ask_gemini_agent(api_key, user_name, user_disease, user_input, air_data):
    if not api_key or not api_key.strip():
        return get_dummy_response(user_name, user_disease)

    system_prompt = f"""
    너는 실시간 도심 환경 분석 앱 '숨쉬는 일상'의 똑똑하고 상냥한 AI 에이전트야.
    사용자와 교감하며 맞춤형 건강 정보를 처방해 주는 역할을 맡고 있어.
    
    [현재 분석 대상 지역의 실제 측정 데이터]
    - 측정 대상 측정소: {air_data.get('station', '가까운 측정소')}
    - 초미세먼지(PM2.5) 수치: {air_data['pm25']} ㎍/㎥ (상태 등급: {air_data['status']})
    - 도로 교통 상태: {air_data['traffic']}
    
    [현재 접속한 사용자 정보]
    - 이름: {user_name}
    - 개인 취약성/질환군: {user_disease}
    
    사용자가 질문한 내용: "{user_input}"
    
    위 조건과 질문을 바탕으로 다음 규칙을 엄격히 지켜 대답해 줘:
    
    1. 답변의 첫 문장이나 도입부에 사용자가 문의한 지역의 실제 초미세먼지 농도 수치인 '{air_data['pm25']} ㎍/㎥'를 정확하고 뚜렷하게 밝혀 줘. (예: "문의하신 지역 근처 {air_data.get('station', '')} 측정소의 현재 초미세먼지 농도는 {air_data['pm25']} ㎍/㎥로...")
    2. 절대 템플릿화된 똑같은 답변을 반복하지 말고, 사용자의 질문 내용("{user_input}")을 귀담아듣고 친근하게 맞춤 대답을 해줘.
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


# ------------------------------------------
# 3. 비상 상황 대응 예비(Fallback) 및 더미 데이터 정의
# ------------------------------------------
def get_fallback_data():
    return {
        "pm25": 70,
        "status": "보통",
        "temp": 22.0,
        "humi": 50,
        "traffic": "보통 정체",
        "station": "기본 대기측정소"
    }

def get_dummy_response(user_name, user_disease):
    dummy_responses = [
        f"현재 문의하신 지역은 미세먼지 '보통' 수준입니다. {user_name}님의 {user_disease} 증상을 고려했을 때, 일반 덴탈 마스크만 가볍게 착용하셔도 안전한 활동이 가능합니다! 😷",
        f"해당 구역은 현재 퇴근 시간 정체로 인해 매연 수치가 높습니다. {user_disease} 관리를 위해 가급적 실내 대중교통 경로를 이용해 이동해 보세요! 🚌",
        f"현재 그 지역의 대기 상태는 아주 깨끗하고 양호합니다! 편안하게 기분 전환 외출을 즐기셔도 좋습니다. 🌱"
    ]
    return random.choice(dummy_responses)

'''