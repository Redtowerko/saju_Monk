import streamlit as st
from google import genai
from google.genai import types
from supabase import create_client, Client
import pandas as pd
import plotly.graph_objects as go
import datetime
import os
import textwrap
from dotenv import load_dotenv
from korean_lunar_calendar import KoreanLunarCalendar
from personas import PERSONAS

# 1. 환경 변수 로드
load_dotenv()

# API 키 설정
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
TARGET_MODEL_NAME = "gemini-2.0-flash"

# 2. 클라이언트 초기화
gemini_client = None
if GEMINI_API_KEY:
    gemini_client = genai.Client(api_key=GEMINI_API_KEY)

supabase: Client = None
if SUPABASE_URL and SUPABASE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- [헬퍼 함수: 약관 파일 읽기] ---
def load_term_file(filename):
    """terms 폴더 내의 마크다운 파일을 읽어옵니다."""
    try:
        file_path = os.path.join("terms", filename)
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "약관 내용을 불러올 수 없습니다."

# --- [상수 데이터: 오행/간지] ---
OHEANG_DATA = {
    "갑": {"elem": "목(木)", "bg": "#1565C0", "label": "양목"},
    "을": {"elem": "목(木)", "bg": "#1565C0", "label": "음목"},
    "병": {"elem": "화(火)", "bg": "#C62828", "label": "양화"},
    "정": {"elem": "화(火)", "bg": "#C62828", "label": "음화"},
    "무": {"elem": "토(土)", "bg": "#F9A825", "label": "양토"},
    "기": {"elem": "토(土)", "bg": "#F9A825", "label": "음토"},
    "경": {"elem": "금(金)", "bg": "#616161", "label": "양금"},
    "신": {"elem": "금(金)", "bg": "#616161", "label": "음금"},
    "임": {"elem": "수(水)", "bg": "#000000", "label": "양수"},
    "계": {"elem": "수(水)", "bg": "#000000", "label": "음수"},
    "인": {"elem": "목(木)", "bg": "#1565C0", "label": "양목"},
    "묘": {"elem": "목(木)", "bg": "#1565C0", "label": "음목"},
    "사": {"elem": "화(火)", "bg": "#C62828", "label": "음화"},
    "오": {"elem": "화(火)", "bg": "#C62828", "label": "양화"},
    "진": {"elem": "토(土)", "bg": "#F9A825", "label": "양토"},
    "술": {"elem": "토(土)", "bg": "#F9A825", "label": "양토"},
    "축": {"elem": "토(土)", "bg": "#F9A825", "label": "음토"},
    "미": {"elem": "토(土)", "bg": "#F9A825", "label": "음토"},
    "신": {"elem": "금(金)", "bg": "#616161", "label": "양금"},
    "유": {"elem": "금(金)", "bg": "#616161", "label": "음금"},
    "해": {"elem": "수(水)", "bg": "#000000", "label": "양수"},
    "자": {"elem": "수(水)", "bg": "#000000", "label": "음수"},
}
GAN_LIST = ["갑", "을", "병", "정", "무", "기", "경", "신", "임", "계"]
JI_LIST = ["자", "축", "인", "묘", "진", "사", "오", "미", "신", "유", "술", "해"]
GAN_HANJA = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]
JI_HANJA = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]
OHEANG_MAP = {
    "갑": "목(木)", "을": "목(木)", "인": "목(木)", "묘": "목(木)",
    "병": "화(火)", "정": "화(火)", "사": "화(火)", "오": "화(火)",
    "무": "토(土)", "기": "토(土)", "진": "토(土)", "술": "토(土)", "축": "토(土)", "미": "토(土)",
    "경": "금(金)", "신": "금(金)", "申": "금(金)", "유": "금(金)",
    "임": "수(水)", "계": "수(水)", "해": "수(水)", "자": "수(水)"
}

# --- [함수: 만세력 및 AI 로직] ---
def calculate_saju_pillars(year, month, day, hour, minute):
    calendar = KoreanLunarCalendar()
    calendar.setSolarDate(year, month, day)
    year_idx = (year - 4) % 60
    year_gan = GAN_LIST[year_idx % 10]
    year_ji = JI_LIST[year_idx % 12]
    month_base_idx = (year - 4) % 10
    start_month_gan_map = {0: 2, 1: 4, 2: 6, 3: 8, 4: 0, 5: 2, 6: 4, 7: 6, 8: 8, 9: 0}
    if month == 2 and day < 4: target_month_idx = 11
    else: target_month_idx = 11 if month < 2 else month - 2
    month_gan = GAN_LIST[(start_month_gan_map[month_base_idx] + target_month_idx) % 10]
    month_ji = JI_LIST[(2 + target_month_idx) % 12]
    base = datetime.date(1900, 1, 1)
    target = datetime.date(year, month, day)
    diff = (target - base).days
    day_idx = (10 + diff) % 60
    day_gan = GAN_LIST[day_idx % 10]
    day_ji = JI_LIST[day_idx % 12]
    day_gan_idx = GAN_LIST.index(day_gan)
    start_time_gan_map = {0: 0, 1: 2, 2: 4, 3: 6, 4: 8, 5: 0, 6: 2, 7: 4, 8: 6, 9: 8}
    time_ji_idx = 0 if (hour >= 23 or hour < 1) else (hour + 1) // 2
    time_gan = GAN_LIST[(start_time_gan_map[day_gan_idx] + time_ji_idx) % 10]
    time_ji = JI_LIST[time_ji_idx % 12]
    def to_str(gan, ji):
        g_h = GAN_HANJA[GAN_LIST.index(gan)]
        j_h = JI_HANJA[JI_LIST.index(ji)]
        return {"gan": gan, "gan_hanja": g_h, "ji": ji, "ji_hanja": j_h}
    return {"year": to_str(year_gan, year_ji), "month": to_str(month_gan, month_ji), "day": to_str(day_gan, day_ji), "time": to_str(time_gan, time_ji)}

def generate_detailed_analysis(saju, user_info, element_counts, persona_key):
    try:
        if not gemini_client: return "API 키 오류"
        full_saju_str = f"년주:{saju['year']['gan']}{saju['year']['ji']}, 월주:{saju['month']['gan']}{saju['month']['ji']}, 일주:{saju['day']['gan']}{saju['day']['ji']}, 시주:{saju['time']['gan']}{saju['time']['ji']}"
        persona = PERSONAS[persona_key]
        prompt = f"""
        {persona['prompt_instruction']}
        [사용자] {user_info['name']} ({user_info['gender']}), 사주: {full_saju_str}, 오행: {element_counts}
        [요청] 인사, 사주 도표, 전체 형국, 성격, 직업/재물, 대운/세운, 한마디 순으로 작성. 말투: {persona['tone']}
        """
        response = gemini_client.models.generate_content(model=TARGET_MODEL_NAME, contents=prompt)
        return response.text
    except Exception as e: return f"오류 발생: {str(e)}"

def get_saju_card_html(saju):
    pillars = [saju["time"], saju["day"], saju["month"], saju["year"]]
    headers = ["시주 (時)", "일주 (日)", "월주 (月)", "년주 (年)"]
    style = """<style>.saju-wrapper { display: flex; justify-content: space-between; gap: 8px; margin-bottom: 20px; } .pillar-card { background-color: #262730; border: 1px solid #464b59; border-radius: 8px; width: 24%; text-align: center; } .card-header { background-color: #31333F; padding: 8px 0; font-weight: bold; color: #FAFAFA; border-bottom: 1px solid #464b59; } .char-section { padding: 15px 0; color: white; } .char-big { font-size: 2rem; font-weight: bold; } .char-desc { font-size: 0.8rem; margin-top: 2px; } .char-tag { font-size: 0.7rem; margin-top: 5px; background: rgba(0,0,0,0.3); padding: 2px 6px; border-radius: 4px; } .card-footer { padding: 6px; font-size: 0.75rem; color: #909090; border-top: 1px solid #464b59; }</style>"""
    html = '<div class="saju-wrapper">'
    for i, p in enumerate(pillars):
        gd, jd = OHEANG_DATA.get(p["gan"]), OHEANG_DATA.get(p["ji"])
        html += f"""<div class="pillar-card"><div class="card-header">{headers[i]}</div><div class="char-section" style="background-color:{gd['bg']}"><div class="char-big">{p['gan_hanja']}</div><div class="char-desc">{p['gan']}:{gd['elem']}</div><div class="char-tag">{gd['label']}</div></div><div class="char-section" style="background-color:{jd['bg']}"><div class="char-big">{p['ji_hanja']}</div><div class="char-desc">{p['ji']}:{jd['elem']}</div><div class="char-tag">{jd['label']}</div></div><div class="card-footer">오행:{gd['elem'][0]}/{jd['elem'][0]}</div></div>"""
    return textwrap.dedent(style + html + '</div>')

# --- [UI: 로그인 및 회원가입 페이지] ---
# --- [UI: 로그인 및 회원가입 페이지] ---
def login_page():
    st.title("🔮 운명의 사주 매칭")
    st.markdown("##### 당신의 운명을 확인하고, 부족한 기운을 채워줄 귀인을 만나보세요.")
    
    tab1, tab2 = st.tabs(["로그인", "회원가입"])
    
    with tab1: # 로그인
        email = st.text_input("이메일", key="login_email")
        password = st.text_input("비밀번호", type="password", key="login_pw")
        if st.button("로그인", use_container_width=True):
            try:
                res = supabase.auth.sign_in_with_password({"email": email, "password": password})
                st.session_state['user'] = res.user
                st.session_state['is_logged_in'] = True
                st.rerun()
            except Exception as e:
                st.error(f"로그인 실패: 이메일 또는 비밀번호를 확인하세요.")

    with tab2: # 회원가입
        st.info("회원가입을 위해 아래 정보를 입력해주세요.")
        new_email = st.text_input("이메일", key="signup_email")
        new_password = st.text_input("비밀번호", type="password", key="signup_pw")
        new_name = st.text_input("이름 (닉네임)", key="signup_name")
        
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            birth_date = st.date_input("생년월일", min_value=datetime.date(1900, 1, 1))
        with col_s2:
            birth_time = st.time_input("태어난 시간")
        gender = st.radio("성별", ["여성", "남성"], horizontal=True, key="signup_gender")

        # --- [약관 동의 로직 개선: 전체 동의 기능] ---
        
        # 1. 콜백 함수 정의 (상태 동기화용)
        def toggle_all():
            """전체 동의 체크박스가 변경될 때 실행"""
            val = st.session_state.agree_all
            st.session_state.agree_service = val
            st.session_state.agree_privacy = val
            st.session_state.agree_location = val
            st.session_state.agree_marketing = val

        def toggle_individual():
            """개별 체크박스가 변경될 때 실행 (하나라도 꺼지면 전체 동의 해제)"""
            if (st.session_state.agree_service and 
                st.session_state.agree_privacy and 
                st.session_state.agree_location and 
                st.session_state.agree_marketing):
                st.session_state.agree_all = True
            else:
                st.session_state.agree_all = False

        st.markdown("---")
        # 전체 동의 체크박스 (on_change로 나머지 제어)
        agree_all = st.checkbox("**약관 전체 동의** (선택 포함)", key="agree_all", on_change=toggle_all)
        st.markdown("---")

        # 개별 체크박스 (key를 할당하여 상태 관리)
        with st.expander("📝 [필수] 서비스 이용약관"):
            st.markdown(load_term_file("service.md"))
        # key와 on_change 추가
        agree_service = st.checkbox("서비스 이용약관에 동의합니다.", key="agree_service", on_change=toggle_individual)

        with st.expander("🔒 [필수] 개인정보 수집 및 이용 동의"):
            st.markdown(load_term_file("privacy.md"))
        agree_privacy = st.checkbox("개인정보 수집 및 이용에 동의합니다.", key="agree_privacy", on_change=toggle_individual)

        with st.expander("📍 [필수] 위치기반 서비스 이용약관 (매칭용)"):
            st.markdown(load_term_file("location.md"))
        agree_location = st.checkbox("위치기반 서비스 이용약관에 동의합니다.", key="agree_location", on_change=toggle_individual)

        with st.expander("📢 [선택] 마케팅 정보 수신 동의 (광고)"):
            st.markdown(load_term_file("marketing.md"))
        agree_marketing = st.checkbox("마케팅 정보 수신에 동의합니다. (선택)", key="agree_marketing", on_change=toggle_individual)

        # 가입 버튼
        if st.button("가입하기", use_container_width=True):
            if not (agree_service and agree_privacy and agree_location):
                st.error("필수 약관(서비스, 개인정보, 위치정보)에 모두 동의해야 가입할 수 있습니다.")
            else:
                try:
                    # 1. Auth 가입
                    auth_res = supabase.auth.sign_up({"email": new_email, "password": new_password})
                    if auth_res.user:
                        # 2. DB에 추가 정보 저장
                        user_data = {
                            "id": auth_res.user.id,
                            "email": new_email,
                            "name": new_name,
                            "birth_date": str(birth_date),
                            "birth_time": str(birth_time),
                            "gender": gender,
                            "agree_location": agree_location,
                            "agree_marketing": agree_marketing
                        }
                        supabase.table("users").insert(user_data).execute()
                        st.success("가입 성공! 로그인 탭에서 로그인해주세요.")
                except Exception as e:
                    st.error(f"가입 오류: {str(e)}")

# --- [UI: 메인 사주 앱] ---
def main_app_page():
    # 스타일 설정
    st.markdown("""<style>h1 { font-family: 'Serif'; } .stChatInputContainer { padding-bottom: 20px; } .stChatMessage { border-radius: 15px; margin-bottom: 10px; }</style>""", unsafe_allow_html=True)
    
    # DB에서 사용자 정보 가져오기 (최초 1회)
    if "db_user_info" not in st.session_state:
        user_id = st.session_state['user'].id
        data = supabase.table("users").select("*").eq("id", user_id).execute()
        if data.data:
            st.session_state['db_user_info'] = data.data[0]

    user_info = st.session_state.get('db_user_info', {})
    
    # 사이드바
    with st.sidebar:
        st.title(f"반갑습니다, {user_info.get('name', '회원')}님!")
        if st.button("로그아웃"):
            st.session_state.clear()
            st.rerun()
            
        st.divider()
        st.subheader("상담 설정")
        selected_persona_key = st.selectbox("상담가 선택", list(PERSONAS.keys()), index=0)
        current_persona = PERSONAS[selected_persona_key]
        st.info(f"**{current_persona['name']}**\n\n{current_persona['description']}")
        
        # 페르소나 변경 시 채팅 초기화
        if st.session_state.get("current_persona") != selected_persona_key:
            st.session_state["current_persona"] = selected_persona_key
            st.session_state["messages"] = [{"role": "assistant", "content": current_persona['welcome']}]

        # 매칭 기능 예고
        st.divider()
        st.caption("🚀 Beta Feature")
        if st.button("💘 내 귀인 찾기 (매칭)"):
            if user_info.get('agree_location'):
                st.toast("현재 회원님의 지역(위치)을 기반으로 귀인을 찾고 있습니다... (준비 중)", icon="🕵️")
            else:
                st.error("위치 정보 동의가 필요합니다.")

    # 세션 초기화
    if "saju_result" not in st.session_state:
        # 로그인 시 DB 정보로 자동 계산
        b_date = datetime.datetime.strptime(user_info['birth_date'], "%Y-%m-%d").date()
        b_time = datetime.datetime.strptime(user_info['birth_time'], "%H:%M:%S").time()
        
        saju = calculate_saju_pillars(b_date.year, b_date.month, b_date.day, b_time.hour, b_time.minute)
        st.session_state["saju_result"] = saju
        
        # 오행 계산
        cnt = {"목(木)":0, "화(火)":0, "토(土)":0, "금(金)":0, "수(水)":0}
        for p in saju.values():
            if p['gan'] in OHEANG_MAP: cnt[OHEANG_MAP[p['gan']]] += 1
            if p['ji'] in OHEANG_MAP: cnt[OHEANG_MAP[p['ji']]] += 1
        st.session_state["element_counts"] = cnt
        
        # 분석 생성
        u_info = {"name": user_info['name'], "date": b_date, "time": b_time, "gender": user_info['gender']}
        with st.spinner("AI가 사주를 분석 중입니다..."):
            ans = generate_detailed_analysis(saju, u_info, cnt, selected_persona_key)
            st.session_state["analysis_result"] = ans

    # 메인 탭 화면
    saju = st.session_state["saju_result"]
    element_counts = st.session_state["element_counts"]
    current_persona = PERSONAS[st.session_state["current_persona"]]

    tab1, tab2 = st.tabs([f"💬 {current_persona['name']} 채팅", "📜 내 사주 분석"])

    with tab2: # 분석 탭
        st.header("나의 사주팔자(四柱八字)")
        st.markdown(get_saju_card_html(saju), unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("오행 분포")
            fig = go.Figure()
            fig.add_trace(go.Scatterpolar(r=list(element_counts.values()), theta=list(element_counts.keys()), fill='toself', marker=dict(color="#FF9800"), line=dict(color="#8D6E63")))
            fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 5], showticklabels=False)), showlegend=False, height=300, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="white"))
            st.plotly_chart(fig, use_container_width=True)
        st.markdown("---")
        st.markdown(st.session_state.get("analysis_result", ""))

    with tab1: # 채팅 탭
        st.title(f"{current_persona['name']}와의 대화")
        chat_container = st.container()
        with chat_container:
            for msg in st.session_state.get("messages", []):
                avatar = current_persona['avatar'] if msg["role"] == "assistant" else "👤"
                with st.chat_message(msg["role"], avatar=avatar):
                    st.markdown(msg["content"])
        
        if prompt := st.chat_input("질문을 입력하세요..."):
            st.session_state["messages"].append({"role": "user", "content": prompt})
            with st.chat_message("user", avatar="👤"):
                st.markdown(prompt)
            
            with st.chat_message("assistant", avatar=current_persona['avatar']):
                with st.spinner("운세를 살피는 중..."):
                    try:
                        u_info = {"name": user_info['name'], "gender": user_info['gender'], "date": user_info['birth_date'], "time": user_info['birth_time']}
                        full_saju = f"년주:{saju['year']['gan']}{saju['year']['ji']}, 일주:{saju['day']['gan']}{saju['day']['ji']}"
                        sys_prompt = f"{current_persona['prompt_instruction']}\n[사용자] {u_info}, 사주:{full_saju}\n[질문] {prompt}\n[말투] {current_persona['tone']}"
                        
                        response = gemini_client.models.generate_content(model=TARGET_MODEL_NAME, contents=sys_prompt)
                        st.markdown(response.text)
                        st.session_state["messages"].append({"role": "assistant", "content": response.text})
                        st.rerun()
                    except Exception as e:
                        st.error(f"에러: {e}")

# --- [앱 실행 진입점] ---
if __name__ == "__main__":
    st.set_page_config(page_title="AI 사주 매칭", page_icon="🔮", layout="wide")
    
    if 'is_logged_in' not in st.session_state:
        st.session_state['is_logged_in'] = False

    if not st.session_state['is_logged_in']:
        login_page()
    else:
        main_app_page()