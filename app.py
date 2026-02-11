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

# --- [메인 앱 페이지: 모바일 앱 스타일] ---
def main_app_page():
    # 모바일 친화적 스타일 (버튼 꽉 차게, 폰트 조정)
    st.markdown("""
    <style>
        .stButton>button { width: 100%; border-radius: 12px; height: 3em; font-weight: bold; }
        .stTabs [data-baseweb="tab-list"] { gap: 8px; }
        .stTabs [data-baseweb="tab"] { height: 50px; white-space: pre-wrap; background-color: #f0f2f6; border-radius: 8px; padding: 0 10px; }
        .stTabs [aria-selected="true"] { background-color: #ff4b4b; color: white; }
        h1 { font-size: 1.8rem; } h2 { font-size: 1.5rem; } h3 { font-size: 1.2rem; }
    </style>
    """, unsafe_allow_html=True)
    
    # DB에서 최신 사용자 정보 가져오기 (구독 정보 포함)
    user_id = st.session_state['user'].id
    if "db_user_info" not in st.session_state:
        try:
            data = supabase.table("users").select("*").eq("id", user_id).execute()
            if data.data:
                st.session_state['db_user_info'] = data.data[0]
        except:
            pass
            
    user_info = st.session_state.get('db_user_info', {})
    subscription_plan = user_info.get('subscription_plan', 'free') # free 또는 pro

    # --- [네비게이션: 모바일 탭 구조] ---
    # 실제 앱의 하단 바 역할을 합니다.
    tab_home, tab_analysis, tab_match, tab_my = st.tabs(["🏠 홈", "🔮 사주분석", "💞 매칭", "👤 내 정보"])

    # ----------------------------------------------------------------
    # 1. [홈 탭] 오늘의 운세 (짧고 강렬하게)
    # ----------------------------------------------------------------
    with tab_home:
        st.markdown(f"### 👋 반가워요, **{user_info.get('name', '회원')}**님!")
        
        # 오늘의 운세 카드
        with st.container(border=True):
            st.markdown("##### 📅 오늘의 한 줄 운세")
            
            # [비용 절감] 매번 API 쓰지 말고, 날짜가 같으면 기존 거 보여주기 (세션 활용)
            today_str = datetime.date.today().strftime("%Y-%m-%d")
            
            if "today_fortune" not in st.session_state or st.session_state.get("fortune_date") != today_str:
                # 간단한 AI 요청 (30자 제한)
                try:
                    # 간단한 로직으로 대체하거나(비용0), 매우 짧은 프롬프트 사용
                    short_prompt = f"사용자({user_info.get('name')})를 위해 오늘({today_str})의 운세를 희망찬 이모지 1개와 함께 30자 이내로 한 문장으로 작성해."
                    resp = gemini_client.models.generate_content(model=TARGET_MODEL_NAME, contents=short_prompt)
                    st.session_state["today_fortune"] = resp.text
                    st.session_state["fortune_date"] = today_str
                except:
                    st.session_state["today_fortune"] = "🍀 오늘은 작은 행운이 깃든 하루가 될 거예요!"
            
            st.info(st.session_state["today_fortune"])
            st.caption(f"기준: {today_str}")

        st.markdown("---")
        st.markdown("#### 🔥 인기 콘텐츠")
        c1, c2 = st.columns(2)
        with c1: st.button("💰 재물운 보기")
        with c2: st.button("💘 연애운 보기")

    # ----------------------------------------------------------------
    # 2. [사주분석 탭] 핵심 기능
    # ----------------------------------------------------------------
    with tab_analysis:
        st.header("🔍 정통 사주 분석")
        
        # 분석 결과가 없으면 -> 입력창 보여줌
        # 분석 결과가 있으면 -> 결과창 보여줌
        
        if "analysis_result" not in st.session_state:
            # [입력 모드]
            st.info("정확한 분석을 위해 정보를 확인해주세요.")
            
            # 기본값 설정
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
                # 1. 만세력 계산
                saju = calculate_saju_pillars(input_date.year, input_date.month, input_date.day, input_time.hour, input_time.minute)
                cnt = {"목(木)":0, "화(火)":0, "토(土)":0, "금(金)":0, "수(水)":0}
                for p in saju.values():
                    if p['gan'] in OHEANG_MAP: cnt[OHEANG_MAP[p['gan']]] += 1
                    if p['ji'] in OHEANG_MAP: cnt[OHEANG_MAP[p['ji']]] += 1
                
                # 세션 저장
                st.session_state["saju_result"] = saju
                st.session_state["element_counts"] = cnt
                
                # [cite_start]2. AI 분석 요청 (무료/유료 분기) [cite: 7]
                with st.spinner("운명을 분석 중입니다..."):
                    try:
                        u_ctx = {"name": user_info.get('name'), "gender": input_gender, "date": input_date, "time": input_time}
                        full_saju = f"년주:{saju['year']['gan']}{saju['year']['ji']}, 일주:{saju['day']['gan']}{saju['day']['ji']}"
                        
                        if subscription_plan == 'free':
                            # [무료] 글자수 제한, 맛보기 요약
                            sys_prompt = f"""
                            너는 사주 전문가야. 아래 사람의 사주를 분석해줘.
                            단, 무료 회원이므로 **핵심 내용만 150자 이내로** 매우 짧게 요약해서 말해줘.
                            마지막에 "더 자세한 내용은 구독을 통해 확인하세요."라고 덧붙여.
                            [정보] {u_ctx}, 사주: {full_saju}, 오행: {cnt}
                            """
                        else:
                            # [유료] 제한 없는 상세 분석
                            sys_prompt = f"""
                            너는 사주 전문가야. 아래 사람의 사주를 아주 상세하고 친절하게 분석해줘.
                            전체 형국, 성격, 재물운, 직업운, 조언을 포함해서 1000자 내외로 풍부하게 작성해줘.
                            [정보] {u_ctx}, 사주: {full_saju}, 오행: {cnt}
                            """
                        
                        resp = gemini_client.models.generate_content(model=TARGET_MODEL_NAME, contents=sys_prompt)
                        st.session_state["analysis_result"] = resp.text
                        st.rerun() # 화면 갱신
                        
                    except Exception as e:
                        st.error(f"분석 중 오류: {e}")

        else:
            # [결과 모드]
            st.success("분석이 완료되었습니다!")
            
            # 사주 카드 표시 (접었다 폈다 가능하게)
            with st.expander("내 사주 명식표 보기", expanded=False):
                st.markdown(get_saju_card_html(st.session_state["saju_result"]), unsafe_allow_html=True)
            
            # 분석 결과 텍스트
            st.markdown("### 📜 분석 결과")
            st.write(st.session_state["analysis_result"])
            
            # 무료 회원일 경우 블러 처리 효과(느낌) 및 구독 유도
            if subscription_plan == 'free':
                st.markdown("---")
                st.warning("🔒 여기까지는 무료 요약본입니다.")
                st.info("지금 구독하면 **재물운, 직업운, 10년 대운**까지 무제한으로 볼 수 있습니다!")
                if st.button("💎 3초만에 구독하고 전체 풀이 보기"):
                    # 실제 결제 연동 전이므로 DB 업데이트 시늉
                    st.toast("테스트: 'pro' 등급으로 업그레이드합니다. (DB수정 필요)")
                    # 여기서 supabase update 로직을 넣거나, 결제창 띄움
            
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("🔄 다른 사주 다시 보기"):
                del st.session_state["analysis_result"]
                st.rerun()

    # ----------------------------------------------------------------
    # 3. [매칭 탭]
    # ----------------------------------------------------------------
    with tab_match:
        st.header("💞 운명의 상대 매칭")
        st.info("준비 중인 기능입니다.")
        if user_info.get('agree_location'):
            st.map() # 위치 동의했으면 지도 보여주기 (간지)
        else:
            st.error("위치 정보 이용에 동의해야 내 주변 귀인을 찾을 수 있습니다.")

    # ----------------------------------------------------------------
    # 4. [내 정보 탭]
    # ----------------------------------------------------------------
    with tab_my:
        st.header("내 정보")
        st.write(f"**이름:** {user_info.get('name')}")
        st.write(f"**등급:** {'💎 PRO' if subscription_plan == 'pro' else '🌱 FREE'}")
        
        if subscription_plan == 'free':
            st.button("💎 프리미엄 구독하기")
        
        st.divider()
        st.caption("고객센터 | 이용약관 | 개인정보처리방침")
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