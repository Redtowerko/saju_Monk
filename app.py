import streamlit as st
from google import genai
from google.genai import types
from supabase import create_client, Client
import pandas as pd
import plotly.graph_objects as go
import datetime
import os
import textwrap
import re # 정규식
from dotenv import load_dotenv
from korean_lunar_calendar import KoreanLunarCalendar
from personas import PERSONAS

# 1. 환경 변수 및 Secrets 로드 (순서 중요!)
load_dotenv()

def get_secret(key_name):
    # 1순위: 내 컴퓨터 환경변수 (.env)
    value = os.getenv(key_name)
    # 2순위: Streamlit Cloud Secrets
    if not value and key_name in st.secrets:
        value = st.secrets[key_name]
    return value

# API 키 설정
GEMINI_API_KEY = get_secret("GEMINI_API_KEY")
SUPABASE_URL = get_secret("SUPABASE_URL")
SUPABASE_KEY = get_secret("SUPABASE_KEY")
TARGET_MODEL_NAME = "gemini-2.0-flash"

# 2. 클라이언트 초기화
gemini_client = None
if GEMINI_API_KEY:
    try:
        gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        st.error(f"Gemini 연결 실패: {e}")
else:
    st.error("🚨 API 키를 찾을 수 없습니다. Streamlit Secrets 설정을 확인해주세요.")

supabase: Client = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        st.error(f"Supabase 연결 실패: {e}")

# --- [헬퍼 함수: 약관 파일 읽기] ---
def load_term_file(filename):
    try:
        file_path = os.path.join("terms", filename)
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "약관 내용을 불러올 수 없습니다."

# --- [상수 데이터] ---
# (코드 길이상 오행 데이터 등은 유지되었다고 가정합니다. 기존 코드의 상수 부분을 그대로 두세요.)
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

# --- [계산 로직 함수들] ---
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

# =======================================================
# [인증 화면 UI 분리 - 라우터 적용]
# =======================================================

def login_page():
    # 세션 상태로 화면 전환 관리 ('login', 'signup', 'reset')
    if 'auth_mode' not in st.session_state:
        st.session_state.auth_mode = 'login'

    # 화면 라우팅
    if st.session_state.auth_mode == 'login':
        render_login_view()
    elif st.session_state.auth_mode == 'signup':
        render_signup_view()
    elif st.session_state.auth_mode == 'reset':
        render_reset_view()

def render_login_view():
    st.title("🔮 운명의 사주 매칭")
    st.subheader("로그인")
    
    with st.form("login_form"):
        username = st.text_input("아이디") # 이메일 아님! ID 입력
        password = st.text_input("비밀번호", type="password")
        login_submitted = st.form_submit_button("로그인", use_container_width=True)

        if login_submitted:
            if not username or not password:
                st.error("아이디와 비밀번호를 입력해주세요.")
            else:
                try:
                    # [핵심] 아이디로 이메일 찾기 (ID 로그인 구현)
                    user_query = supabase.table("users").select("email").eq("username", username).execute()
                    
                    if not user_query.data:
                        st.error("존재하지 않는 아이디입니다.")
                    else:
                        target_email = user_query.data[0]['email']
                        # 찾은 이메일로 로그인 시도
                        res = supabase.auth.sign_in_with_password({"email": target_email, "password": password})
                        st.session_state['user'] = res.user
                        st.session_state['is_logged_in'] = True
                        st.rerun()
                except Exception as e:
                    msg = str(e)
                    if "Email not confirmed" in msg:
                        st.warning("이메일 인증이 완료되지 않았습니다. 메일함을 확인해주세요.")
                    elif "Invalid login credentials" in msg:
                        st.error("비밀번호가 일치하지 않습니다.")
                    else:
                        st.error(f"로그인 오류: {msg}")

    # 하단 링크 버튼들 (회원가입 / 비밀번호 찾기)
    col1, col2 = st.columns(2)
    with col1:
        if st.button("회원가입", use_container_width=True):
            st.session_state.auth_mode = 'signup'
            st.rerun()
    with col2:
        if st.button("비밀번호 찾기", use_container_width=True):
            st.session_state.auth_mode = 'reset'
            st.rerun()

def render_reset_view():
    st.title("🔐 비밀번호 찾기")
    st.info("가입 시 등록한 이메일 주소를 입력하시면, 비밀번호 재설정 링크를 보내드립니다.")
    
    email = st.text_input("이메일 주소")
    
    if st.button("재설정 메일 전송", use_container_width=True):
        if not email:
            st.error("이메일을 입력해주세요.")
        else:
            try:
                # Supabase 비밀번호 리셋 요청
                supabase.auth.reset_password_for_email(email, options={"redirect_to": "https://sajumonk.streamlit.app/"})
                st.success("✅ 메일이 발송되었습니다. 메일함을 확인해주세요.")
            except Exception as e:
                st.error(f"전송 실패: {str(e)}")
    
    st.markdown("---")
    if st.button("로그인 화면으로 돌아가기"):
        st.session_state.auth_mode = 'login'
        st.rerun()

def render_signup_view():
    st.title("📝 회원가입")
    st.caption("운명의 상대를 만나기 위한 첫 걸음입니다. (* 표시는 필수 항목)")
    
    # [1] 아이디 중복 확인 로직
    col_id1, col_id2 = st.columns([3, 1], vertical_alignment="bottom")
    with col_id1:
        # 아이디 입력값이 바뀌면 중복확인 상태 초기화 (on_change)
        def reset_id_check():
            st.session_state.id_checked = False
        new_username = st.text_input("아이디 *", key="signup_username", on_change=reset_id_check)
    
    with col_id2:
        if st.button("중복 확인", key="btn_check_id", use_container_width=True):
            if not new_username:
                st.error("입력 필요")
            else:
                try:
                    res = supabase.table("users").select("username").eq("username", new_username).execute()
                    if res.data:
                        st.error("사용 불가")
                        st.session_state.id_checked = False
                    else:
                        st.success("사용 가능")
                        st.session_state.id_checked = True
                except Exception as e:
                    st.error("오류 발생")
    
    # 상태 메시지 유지 (리런 되어도 메시지 보이게)
    if st.session_state.get('id_checked') is True:
        st.caption("✅ 사용 가능한 아이디입니다.")
    elif st.session_state.get('id_checked') is False and new_username:
        st.caption("❌ 중복 확인이 필요하거나 이미 사용 중입니다.")

    # [2] 이메일 중복 확인 로직
    col_em1, col_em2 = st.columns([3, 1], vertical_alignment="bottom")
    with col_em1:
        def reset_email_check():
            st.session_state.email_checked = False
        new_email = st.text_input("이메일 (본인인증용) *", key="signup_email", help="실제 사용 중인 이메일을 입력하세요.", on_change=reset_email_check)
    
    with col_em2:
        if st.button("중복 확인", key="btn_check_email", use_container_width=True):
            if not new_email:
                st.error("입력 필요")
            elif not re.match(r"[^@]+@[^@]+\.[^@]+", new_email):
                st.error("형식 오류")
            else:
                try:
                    res = supabase.table("users").select("email").eq("email", new_email).execute()
                    if res.data:
                        st.error("사용 불가")
                        st.session_state.email_checked = False
                    else:
                        st.success("사용 가능")
                        st.session_state.email_checked = True
                except:
                    st.error("오류")

    if st.session_state.get('email_checked') is True:
        st.caption("✅ 사용 가능한 이메일입니다.")
    elif st.session_state.get('email_checked') is False and new_email:
        st.caption("❌ 중복 확인이 필요하거나 이미 사용 중입니다.")

    # [3] 비밀번호
    c1, c2 = st.columns(2)
    with c1:
        new_pw = st.text_input("비밀번호 *", type="password", key="signup_pw")
    with c2:
        new_pw_chk = st.text_input("비밀번호 확인 *", type="password", key="signup_pw_chk")
        
    if new_pw and new_pw_chk:
        if new_pw == new_pw_chk:
            st.success("비밀번호가 일치합니다.")
        else:
            st.error("비밀번호가 일치하지 않습니다.")
            
    # [4] 이름 (필수로 변경됨)
    new_name = st.text_input("이름 *", key="signup_name")
    
    # [5] 휴대전화
    new_phone = st.text_input("휴대전화 번호 *", placeholder="010-0000-0000", key="signup_phone")
    
    # [6] 생년월일/성별
    cc1, cc2 = st.columns(2)
    with cc1:
        b_date = st.date_input("생년월일", min_value=datetime.date(1900, 1, 1))
    with cc2:
        b_time = st.time_input("태어난 시간")
    gender = st.radio("성별 *", ["여성", "남성", "선택 안 함"], horizontal=True)

    # [7] 약관 동의
    def toggle_all():
        val = st.session_state.agree_all
        st.session_state.agree_service = val
        st.session_state.agree_privacy = val
        st.session_state.agree_location = val
        st.session_state.agree_marketing = val

    def toggle_individual():
        if (st.session_state.get('agree_service') and st.session_state.get('agree_privacy') and 
            st.session_state.get('agree_location') and st.session_state.get('agree_marketing')):
            st.session_state.agree_all = True
        else:
            st.session_state.agree_all = False

    st.markdown("---")
    st.checkbox("약관 전체 동의", key="agree_all", on_change=toggle_all)
    
    with st.expander("📝 [필수] 서비스 이용약관"):
        st.markdown(load_term_file("service.md"))
    st.checkbox("서비스 이용약관 동의", key="agree_service", on_change=toggle_individual)

    with st.expander("🔒 [필수] 개인정보 수집 및 이용 동의"):
        st.markdown(load_term_file("privacy.md"))
    st.checkbox("개인정보 수집 및 이용 동의", key="agree_privacy", on_change=toggle_individual)

    with st.expander("📍 [필수] 위치기반 서비스 이용약관"):
        st.markdown(load_term_file("location.md"))
    st.checkbox("위치기반 서비스 이용약관 동의", key="agree_location", on_change=toggle_individual)

    with st.expander("📢 [선택] 마케팅 정보 수신 동의"):
        st.markdown(load_term_file("marketing.md"))
    st.checkbox("마케팅 정보 수신 동의 (선택)", key="agree_marketing", on_change=toggle_individual)

    # [8] 최종 가입 버튼
    if st.button("가입하기", use_container_width=True):
        # 유효성 검사
        if not (new_username and new_email and new_pw and new_pw_chk and new_phone and new_name):
            st.error("필수 항목(*)을 모두 입력해주세요.")
            return
        
        # 중복 확인 여부 검사 (핵심!)
        if not st.session_state.get('id_checked'):
            st.error("아이디 중복 확인을 해주세요.")
            return
        if not st.session_state.get('email_checked'):
            st.error("이메일 중복 확인을 해주세요.")
            return
            
        if new_pw != new_pw_chk:
            st.error("비밀번호가 일치하지 않습니다.")
            return
            
        if not (st.session_state.get('agree_service') and st.session_state.get('agree_privacy') and st.session_state.get('agree_location')):
            st.error("필수 약관에 동의해야 합니다.")
            return
            
        # 가입 로직 수행
        try:
            # 1. Auth 가입
            auth = supabase.auth.sign_up({
                "email": new_email, "password": new_pw,
                "options": {"data": {"username": new_username}}
            })
            
            if auth.user and auth.user.identities:
                # 2. DB 저장
                user_data = {
                    "id": auth.user.id,
                    "email": new_email,
                    "username": new_username,
                    "name": new_name,
                    "phone": new_phone,
                    "birth_date": str(b_date),
                    "birth_time": str(b_time),
                    "gender": gender,
                    "agree_location": st.session_state.agree_location,
                    "agree_marketing": st.session_state.agree_marketing
                }
                supabase.table("users").insert(user_data).execute()
                st.success(f"가입 요청 완료! {new_email}로 발송된 인증 메일을 확인해주세요.")
            else:
                st.warning("이미 가입된 이메일이거나 요청을 처리할 수 없습니다.")
        except Exception as e:
            st.error(f"가입 중 오류 발생: {e}")

    st.markdown("---")
    if st.button("로그인 화면으로 돌아가기"):
        st.session_state.auth_mode = 'login'
        st.rerun()

# --- [메인 앱 페이지: 매칭 기능 강화 버전] ---
def main_app_page():
    # 스타일 설정
    st.markdown("""
    <style>
        .stButton>button { width: 100%; border-radius: 12px; height: 3em; font-weight: bold; }
        .match-card { background-color: #f8f9fa; padding: 15px; border-radius: 10px; margin-bottom: 10px; border: 1px solid #ddd; }
        .match-score { color: #e91e63; font-weight: bold; font-size: 1.2rem; }
        .match-tag { display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 0.8rem; margin-right: 5px; color: white; }
    </style>
    """, unsafe_allow_html=True)
    
    # 사용자 정보 로드
    user_id = st.session_state['user'].id
    if "db_user_info" not in st.session_state:
        try:
            data = supabase.table("users").select("*").eq("id", user_id).execute()
            if data.data:
                st.session_state['db_user_info'] = data.data[0]
        except:
            pass
            
    user_info = st.session_state.get('db_user_info', {})
    subscription_plan = user_info.get('subscription_plan', 'free')

    # 탭 네비게이션
    tab_home, tab_analysis, tab_match, tab_my = st.tabs(["🏠 홈", "🔮 사주분석", "💞 매칭", "👤 내 정보"])

    # ----------------------------------------------------------------
    # 1. [홈 탭]
    # ----------------------------------------------------------------
    with tab_home:
        st.markdown(f"### 👋 반가워요, **{user_info.get('name', '회원')}**님!")
        
        with st.container(border=True):
            st.markdown("##### 📅 오늘의 한 줄 운세")
            today_str = datetime.date.today().strftime("%Y-%m-%d")
            
            if "today_fortune" not in st.session_state or st.session_state.get("fortune_date") != today_str:
                try:
                    short_prompt = f"사용자({user_info.get('name')})를 위해 오늘({today_str})의 운세를 희망찬 이모지와 함께 30자 이내로 작성해."
                    resp = gemini_client.models.generate_content(model=TARGET_MODEL_NAME, contents=short_prompt)
                    st.session_state["today_fortune"] = resp.text
                    st.session_state["fortune_date"] = today_str
                except:
                    st.session_state["today_fortune"] = "🍀 오늘은 작은 행운이 깃든 하루가 될 거예요!"
            
            st.info(st.session_state["today_fortune"])

        st.markdown("---")
        st.markdown("#### 🔥 인기 콘텐츠")
        c1, c2 = st.columns(2)
        with c1: st.button("💰 재물운 보기")
        with c2: st.button("💘 연애운 보기")

    # ----------------------------------------------------------------
    # 2. [사주분석 탭] + 저장 기능 추가
    # ----------------------------------------------------------------
    with tab_analysis:
        st.header("🔍 정통 사주 분석")
        
        if "analysis_result" not in st.session_state:
            # [입력 모드]
            st.info("정확한 분석을 위해 정보를 확인해주세요.")
            
            # 기본값 로딩
            def_date = datetime.date.today()
            def_time = datetime.time(12, 0)
            def_idx = 0
            if user_info.get('birth_date'):
                def_date = datetime.datetime.strptime(user_info['birth_date'], "%Y-%m-%d").date()
            if user_info.get('birth_time'):
                t_str = user_info['birth_time']
                if len(t_str) > 5: def_time = datetime.datetime.strptime(t_str, "%H:%M:%S").time()
                else: def_time = datetime.datetime.strptime(t_str, "%H:%M").time()
            if user_info.get('gender') == '남성': def_idx = 1

            with st.container(border=True):
                input_date = st.date_input("생년월일", value=def_date, min_value=datetime.date(1900, 1, 1))
                input_time = st.time_input("태어난 시간", value=def_time)
                input_gender = st.radio("성별", ["여성", "남성"], index=def_idx, horizontal=True)
                
            st.markdown("<br>", unsafe_allow_html=True)
            
            if st.button("🔮 사주 분석 시작하기", type="primary"):
                # 계산
                saju = calculate_saju_pillars(input_date.year, input_date.month, input_date.day, input_time.hour, input_time.minute)
                cnt = {"목":0, "화":0, "토":0, "금":0, "수":0} # 한글 키로 통일
                for p in saju.values():
                    if p['gan'] in OHEANG_MAP: cnt[OHEANG_MAP[p['gan']][0]] += 1 # '목(木)' -> '목'
                    if p['ji'] in OHEANG_MAP: cnt[OHEANG_MAP[p['ji']][0]] += 1
                
                st.session_state["saju_result"] = saju
                st.session_state["element_counts"] = cnt
                
                # AI 호출
                with st.spinner("운명을 분석 중입니다..."):
                    try:
                        u_ctx = {"name": user_info.get('name'), "gender": input_gender, "date": input_date, "time": input_time}
                        full_saju = f"년주:{saju['year']['gan']}{saju['year']['ji']}, 일주:{saju['day']['gan']}{saju['day']['ji']}"
                        
                        prompt_sys = f"너는 사주 전문가야. {u_ctx['name']}님의 사주를 분석해줘. (무료회원용 요약)" if subscription_plan == 'free' else f"너는 사주 전문가야. {u_ctx['name']}님의 사주를 상세히 분석해줘."
                        prompt_sys += f"\n사주: {full_saju}, 오행: {cnt}"
                        
                        resp = gemini_client.models.generate_content(model=TARGET_MODEL_NAME, contents=prompt_sys)
                        st.session_state["analysis_result"] = resp.text
                        st.rerun()
                    except Exception as e:
                        st.error(f"분석 중 오류: {e}")

        else:
            # [결과 모드]
            st.success("분석이 완료되었습니다!")
            
            with st.expander("내 사주 명식표 보기", expanded=False):
                st.markdown(get_saju_card_html(st.session_state["saju_result"]), unsafe_allow_html=True)
            
            st.markdown("### 📜 분석 결과")
            st.write(st.session_state["analysis_result"])
            
            # [핵심] 매칭 정보 저장 버튼
            st.markdown("---")
            if st.button("💾 이 사주 결과를 '내 매칭 정보'로 저장하기"):
                try:
                    # DB 업데이트 (오행 정보 저장)
                    supabase.table("users").update({
                        "saju_elements": st.session_state["element_counts"]
                    }).eq("id", user_id).execute()
                    
                    # 세션 갱신
                    st.session_state['db_user_info']['saju_elements'] = st.session_state["element_counts"]
                    st.toast("✅ 저장 완료! 이제 '매칭' 탭에서 귀인을 찾을 수 있습니다.")
                except Exception as e:
                    st.error(f"저장 실패: {e}")

            if subscription_plan == 'free':
                if st.button("💎 구독하고 전체 풀이 보기"):
                    st.toast("결제 페이지로 이동합니다. (준비 중)")
            
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("🔄 다시 분석하기"):
                del st.session_state["analysis_result"]
                st.rerun()

    # ----------------------------------------------------------------
    # 3. [매칭 탭] 알고리즘 구현
    # ----------------------------------------------------------------
    with tab_match:
        st.header("💞 운명의 상대 매칭")
        
        # 1. 내 정보가 있는지 확인
        my_elements = user_info.get('saju_elements')
        
        if not my_elements:
            st.warning("⚠️ 아직 내 사주 정보가 저장되지 않았습니다.")
            st.info("👉 **[사주분석]** 탭에서 분석 후 **'내 매칭 정보로 저장하기'**를 눌러주세요.")
        else:
            # 2. 매칭 로직 실행
            st.write(f"**{user_info.get('name')}**님에게 부족한 기운을 채워줄 귀인을 찾습니다...")
            
            try:
                # 나를 제외한 유저 불러오기 (실무에선 페이지네이션 필요)
                candidates_query = supabase.table("users").select("*").neq("id", user_id).execute()
                candidates = candidates_query.data
                
                if not candidates:
                    st.info("아직 매칭할 다른 회원이 없습니다. 친구를 초대해보세요!")
                else:
                    # [매칭 알고리즘]
                    matches = []
                    my_lacks = [k for k, v in my_elements.items() if v == 0] # 내가 없는 오행
                    
                    for cand in candidates:
                        cand_elements = cand.get('saju_elements')
                        if not cand_elements: continue # 정보 없는 유저 패스
                        
                        score = 50 # 기본 점수
                        
                        # 1) 성별 매칭 (이성에게 가산점)
                        if user_info.get('gender') != cand.get('gender'):
                            score += 20
                            
                        # 2) 오행 보완 (내가 없는 걸 상대가 3개 이상 가졌으면 대박)
                        bonus_txt = []
                        for lack in my_lacks:
                            if cand_elements.get(lack, 0) >= 3:
                                score += 30
                                bonus_txt.append(f"부족한 '{lack}' 기운 가득!")
                            elif cand_elements.get(lack, 0) >= 1:
                                score += 10
                        
                        # 3) 과다 조심 (나도 많고 쟤도 많으면 감점)
                        for k, v in my_elements.items():
                            if v >= 3 and cand_elements.get(k, 0) >= 3:
                                score -= 10
                        
                        matches.append({
                            "name": cand.get('name', '익명'),
                            "gender": cand.get('gender', '-'),
                            "score": min(score, 100), # 100점 만점
                            "bonus": ", ".join(bonus_txt),
                            "birth_year": cand.get('birth_date', '????')[:4]
                        })
                    
                    # 점수순 정렬
                    matches.sort(key=lambda x: x['score'], reverse=True)
                    
                    # 리스트 출력
                    for m in matches[:5]: # 상위 5명만
                        with st.container():
                            col_av, col_info, col_score = st.columns([1, 3, 1])
                            with col_av:
                                st.markdown("👤")
                            with col_info:
                                st.markdown(f"**{m['name']}** ({m['gender']}, {m['birth_year']}년생)")
                                if m['bonus']:
                                    st.caption(f"✨ {m['bonus']}")
                            with col_score:
                                st.markdown(f"<div style='color:#e91e63; font-weight:bold;'>{m['score']}점</div>", unsafe_allow_html=True)
                            st.divider()
                            
            except Exception as e:
                st.error(f"매칭 중 오류 발생: {e}")

    # ----------------------------------------------------------------
    # 4. [내 정보 탭]
    # ----------------------------------------------------------------
    with tab_my:
        st.header("내 정보")
        st.write(f"**이름:** {user_info.get('name')}")
        st.write(f"**등급:** {'💎 PRO' if subscription_plan == 'pro' else '🌱 FREE'}")
        
        # 내 오행 정보 보여주기
        if user_info.get('saju_elements'):
            st.caption("저장된 내 오행 정보:")
            st.json(user_info.get('saju_elements'))
        
        st.divider()
        if st.button("로그아웃"):
            supabase.auth.sign_out()
            st.session_state.clear()
            st.rerun()

# --- [앱 실행 진입점] ---
if __name__ == "__main__":
    st.set_page_config(page_title="AI 사주 매칭", page_icon="🔮", layout="wide")
    
    if 'is_logged_in' not in st.session_state:
        st.session_state['is_logged_in'] = False

    if not st.session_state['is_logged_in']:
        login_page()
    else:
        main_app_page()