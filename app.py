
import streamlit as st
from datetime import datetime

# ============================================================
# 중학교 독서 포트폴리오 수행평가 시스템
# Streamlit UI
# ============================================================

st.set_page_config(
    page_title="중학교 독서 포트폴리오",
    page_icon="📖",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ------------------------------------------------------------
# 샘플 데이터
# ------------------------------------------------------------
if "students" not in st.session_state:
    st.session_state.students = [
        {
            "학번": "10101",
            "반": "1-1",
            "이름": "박예빈",
            "PIN": "1234",
            "도서": ["아몬드 (손원평)"],
            "완료차시": 0,
            "총독서": 0,
            "점수": None,
            "채점": False,
        },
        {
            "학번": "10201",
            "반": "1-2",
            "이름": "박은혜",
            "PIN": "1234",
            "도서": ["아몬드 (손원평)"],
            "완료차시": 0,
            "총독서": 0,
            "점수": None,
            "채점": False,
        },
        {
            "학번": "20315",
            "반": "2-3",
            "이름": "김서연",
            "PIN": "1234",
            "도서": ["페인트 (이희영)"],
            "완료차시": 0,
            "총독서": 0,
            "점수": None,
            "채점": False,
        },
        {
            "학번": "20316",
            "반": "2-3",
            "이름": "최도윤",
            "PIN": "1234",
            "도서": ["체리새우: 비밀글입니다 (황영미)", "아몬드 (손원평)"],
            "완료차시": 0,
            "총독서": 0,
            "점수": None,
            "채점": False,
        },
    ]

if "records" not in st.session_state:
    st.session_state.records = {}

if "student_logged_in" not in st.session_state:
    st.session_state.student_logged_in = False

if "teacher_logged_in" not in st.session_state:
    st.session_state.teacher_logged_in = False

if "current_student_id" not in st.session_state:
    st.session_state.current_student_id = None

if "page" not in st.session_state:
    st.session_state.page = "student_login"

if "teacher_password" not in st.session_state:
    st.session_state.teacher_password = "1234"

if "show_new_record" not in st.session_state:
    st.session_state.show_new_record = False

# ------------------------------------------------------------
# 전체 CSS
# ------------------------------------------------------------
st.markdown(
    r"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;600;700;800&display=swap');

:root{
    --bg:#f6f8fc;
    --navy:#0f172a;
    --text:#172033;
    --muted:#778397;
    --line:#dce4ef;
    --purple:#5138f5;
    --purple2:#6046f5;
    --green:#00a878;
}

html, body, [class*="css"]{
    font-family:'Noto Sans KR', sans-serif !important;
}

.stApp{
    background:var(--bg);
    color:var(--text);
}

header[data-testid="stHeader"]{
    background:transparent;
}

section[data-testid="stSidebar"]{
    display:none;
}

.block-container{
    padding-top:1.1rem;
    padding-bottom:2.5rem;
    max-width:1240px;
}

div[data-testid="stForm"]{
    border:none;
    padding:0;
    background:transparent;
}

.stButton > button,
.stDownloadButton > button{
    font-family:'Noto Sans KR', sans-serif !important;
    border-radius:10px !important;
    min-height:40px !important;
    font-weight:700 !important;
    border:1px solid var(--line) !important;
    background:#fff !important;
    color:#455166 !important;
    box-shadow:none !important;
}

.stButton > button:hover{
    border-color:var(--purple) !important;
    color:var(--purple) !important;
}

.primary-button .stButton > button{
    background:var(--purple) !important;
    color:#fff !important;
    border-color:var(--purple) !important;
}

.primary-button .stButton > button:hover{
    background:#4630ed !important;
    color:#fff !important;
}

.teacher-button .stButton > button{
    background:#f0f9f6 !important;
    color:#1a7865 !important;
    border-color:#d8efe9 !important;
}

input, textarea{
    border-radius:10px !important;
}

div[data-baseweb="input"] > div,
div[data-baseweb="textarea"] > div{
    border-radius:10px !important;
    border-color:#cbd7e6 !important;
}

div[data-baseweb="select"] > div{
    border-radius:10px !important;
}

label[data-testid="stWidgetLabel"] p{
    font-size:12px !important;
    font-weight:700 !important;
    color:#4a5568 !important;
}

/* 로그인 페이지 */
.login-wrap{
    width:100%;
    max-width:500px;
    margin:0 auto;
}

.book-logo{
    width:64px;
    height:64px;
    margin:0 auto 14px auto;
    border-radius:14px 14px 18px 18px;
    background:var(--purple);
    color:#fff;
    display:flex;
    align-items:center;
    justify-content:center;
    font-size:35px;
    box-shadow:0 12px 24px rgba(81,56,245,.18);
}

.login-title{
    text-align:center;
    font-size:25px;
    font-weight:800;
    letter-spacing:-.8px;
    margin-top:2px;
}

.login-subtitle{
    text-align:center;
    color:#53617a;
    font-size:13px;
    margin-top:8px;
    margin-bottom:30px;
}

.login-card{
    background:#fff;
    border:1px solid #dfe6f0;
    border-radius:16px;
    padding:30px 40px 28px 40px;
    box-shadow:0 2px 7px rgba(23,32,51,.05);
}

.login-tabs{
    display:grid;
    grid-template-columns:1fr 1fr;
    border-bottom:1px solid #dbe2ed;
    margin-bottom:25px;
}

.login-tab{
    text-align:center;
    padding:2px 0 13px;
    font-size:14px;
    font-weight:700;
}

.login-tab.active{
    color:var(--purple);
    border-bottom:2px solid var(--purple);
}

.login-tab.inactive{
    color:#5e6b80;
}

.helper{
    color:#748197;
    font-size:12px;
    line-height:1.5;
}

.example-box{
    margin-top:20px;
    padding:15px 0;
    border-top:1px solid #dfe6ee;
    border-bottom:1px solid #dfe6ee;
    display:flex;
    align-items:center;
    justify-content:space-between;
    color:#e48b00;
    font-size:12px;
    font-weight:700;
}

.demo-link{
    color:#8290a5;
    font-size:12px;
}

.teacher-access{
    margin-top:19px;
    text-align:center;
}

.teacher-pill{
    display:inline-block;
    background:#f1f6fa;
    border:1px solid #e4edf3;
    color:#28586d;
    border-radius:9px;
    padding:9px 15px;
    font-size:12px;
    font-weight:700;
}

/* 공통 상단 */
.topbar{
    background:var(--navy);
    color:white;
    margin:-18px -12px 16px -12px;
    padding:9px 19px;
    display:flex;
    align-items:center;
    justify-content:space-between;
    font-size:11px;
    border-radius:0;
}

.topbar-left{
    display:flex;
    align-items:center;
    gap:9px;
    font-weight:700;
}

.db-pill{
    color:#00d999;
    background:#062e29;
    border:1px solid #057961;
    padding:4px 9px;
    border-radius:999px;
    font-size:10px;
}

.teacher-header{
    background:white;
    border-bottom:1px solid #e3e8f0;
    padding:10px 0 14px;
    margin:0 -12px 18px;
}

.teacher-brand{
    display:flex;
    align-items:center;
    gap:12px;
}

.teacher-brand-icon{
    width:44px;
    height:44px;
    background:#111a31;
    color:white;
    border-radius:12px;
    display:flex;
    align-items:center;
    justify-content:center;
    font-size:22px;
}

.teacher-brand-title{
    font-size:18px;
    font-weight:800;
}

.teacher-brand-sub{
    color:#78859a;
    font-size:12px;
    margin-top:3px;
}

.dashboard-card{
    background:white;
    border:1px solid #dfe6f0;
    border-radius:15px;
    padding:18px 20px;
    box-shadow:0 1px 2px rgba(20,35,70,.03);
}

.stat-card{
    background:#fff;
    border:1px solid #dfe6f0;
    border-radius:15px;
    padding:17px 19px;
    min-height:108px;
}

.stat-label{
    color:#6e7a8e;
    font-size:12px;
    font-weight:600;
}

.stat-number{
    color:#111827;
    font-size:24px;
    font-weight:800;
    margin-top:3px;
}

.stat-sub{
    color:#7d899d;
    font-size:11px;
    margin-top:3px;
}

.status{
    display:inline-block;
    border-radius:999px;
    padding:4px 9px;
    font-size:10px;
    font-weight:700;
}

.status-wait{
    background:#fff9ed;
    border:1px solid #f0cb64;
    color:#d79400;
}

.status-done{
    background:#effaf7;
    border:1px solid #8bd8c3;
    color:#008665;
}

.progress-bg{
    width:100%;
    height:7px;
    background:#edf1f7;
    border-radius:99px;
    margin-top:7px;
    overflow:hidden;
}

.progress-fill{
    height:100%;
    background:var(--purple);
    border-radius:99px;
}

.small-muted{
    color:#7e899d;
    font-size:11px;
}

@media(max-width:800px){
    .block-container{
        padding-left:10px;
        padding-right:10px;
    }
    .login-card{
        padding:24px 20px;
    }
}
</style>
""",
    unsafe_allow_html=True,
)

# ------------------------------------------------------------
# 유틸
# ------------------------------------------------------------
def set_page(name):
    st.session_state.page = name
    st.rerun()


def get_current_student():
    sid = st.session_state.current_student_id
    return next((s for s in st.session_state.students if s["학번"] == sid), None)


def topbar():
    st.markdown(
        """
        <div class="topbar">
            <div class="topbar-left">
                <span>▣</span>
                <span>중학교 15~17차시 독서 포트폴리오 수행평가 시스템</span>
                <span class="db-pill">●　클라우드 DB: Google Sheets (GAS 검증 모드)</span>
            </div>
            <div>교사 관리자 화면</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ------------------------------------------------------------
# 학생 로그인 화면
# ------------------------------------------------------------
def student_login():
    st.markdown('<div style="height:25px;"></div>', unsafe_allow_html=True)

    st.markdown('<div class="login-wrap">', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="book-logo">▤</div>
        <div class="login-title">중학교 독서 포트폴리오</div>
        <div class="login-subtitle">15~17차시 한 학기 독서 누적 기록 & 수행평가 관리 시스템</div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="login-card">', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="login-tabs">
            <div class="login-tab active">학생 로그인</div>
            <div class="login-tab inactive">신규 학생 등록</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.form("student_login_form"):
        st.markdown("**학번** <span style='color:#7a8798;font-weight:400;'> (예: 20315 - 2학년 3반 15번)</span>", unsafe_allow_html=True)
        student_id = st.text_input(
            "학번입력",
            placeholder="예: 20315",
            label_visibility="collapsed",
        )

        st.markdown("**학생 이름**", unsafe_allow_html=True)
        name = st.text_input(
            "이름입력",
            placeholder="예: 김서연",
            label_visibility="collapsed",
        )

        st.markdown("**교번번호 (PIN / 4자리 비밀번호)**", unsafe_allow_html=True)
        pin = st.text_input(
            "PIN입력",
            placeholder="4자리 숫자 (예: 1234)",
            type="password",
            label_visibility="collapsed",
        )
        st.markdown(
            '<div class="helper">개인 포트폴리오를 보호하기 위한 4자리 비밀번호입니다.</div>',
            unsafe_allow_html=True,
        )

        st.markdown('<div class="primary-button" style="margin-top:14px;">', unsafe_allow_html=True)
        login_clicked = st.form_submit_button("포트폴리오 입장하기  →", use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

        if login_clicked:
            sid = student_id.strip()
            nm = name.strip()
            pp = pin.strip()

            matched = next(
                (
                    s for s in st.session_state.students
                    if s["학번"] == sid and s["이름"] == nm and s["PIN"] == pp
                ),
                None,
            )

            if matched:
                st.session_state.current_student_id = matched["학번"]
                st.session_state.student_logged_in = True
                set_page("student_home")
            else:
                st.error("학번, 학생 이름, 교번번호(PIN)를 확인해 주세요.")

    st.markdown(
        """
        <div class="example-box">
            <span>⚙ 선생님·참관용 예시 계정 둘러보기 (2명)</span>
            <span class="demo-link">예시 보기　⌄</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 예시 계정
    if st.button("예시 계정 1 · 20315 김서연", use_container_width=True):
        st.session_state.current_student_id = "20315"
        st.session_state.student_logged_in = True
        set_page("student_home")

    if st.button("예시 계정 2 · 10101 박예빈", use_container_width=True):
        st.session_state.current_student_id = "10101"
        st.session_state.student_logged_in = True
        set_page("student_home")

    st.markdown('<div class="teacher-access">', unsafe_allow_html=True)
    st.markdown(
        '<div class="teacher-pill">♧　교사용 관리 및 평가 페이지로 이동 (교사 전용)</div>',
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)
    if st.button("교사용 관리 및 평가 페이지", use_container_width=True):
        set_page("teacher_login")

    st.markdown("</div>", unsafe_allow_html=True)


# ------------------------------------------------------------
# 교사 로그인 화면
# ------------------------------------------------------------
def teacher_login():
    st.markdown('<div style="height:35px;"></div>', unsafe_allow_html=True)

    st.markdown('<div class="login-wrap">', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="book-logo" style="background:#111a31;">▣</div>
        <div class="login-title">교사용 관리 & 평가</div>
        <div class="login-subtitle">학생 독서 포트폴리오 진도 및 수행평가 관리</div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="login-card">', unsafe_allow_html=True)

    st.markdown(
        """
        <div style="font-size:14px;font-weight:800;margin-bottom:7px;">교사 전용 페이지</div>
        <div class="helper" style="margin-bottom:20px;">
            교사 비밀번호를 입력하면 학생 명단, 독서 진도, 수행평가 채점 화면으로 이동합니다.
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.form("teacher_login_form"):
        st.markdown("**교사 비밀번호**")
        password = st.text_input(
            "교사비밀번호",
            type="password",
            placeholder="교사 비밀번호 입력",
            label_visibility="collapsed",
        )

        st.markdown('<div class="primary-button" style="margin-top:14px;">', unsafe_allow_html=True)
        entered = st.form_submit_button("교사 페이지 입장하기  →", use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

        if entered:
            if password == st.session_state.teacher_password:
                st.session_state.teacher_logged_in = True
                set_page("teacher_dashboard")
            else:
                st.error("교사 비밀번호가 올바르지 않습니다.")

    st.markdown('<div style="height:10px;"></div>', unsafe_allow_html=True)
    if st.button("← 학생 로그인 화면으로 돌아가기", use_container_width=True):
        set_page("student_login")

    st.markdown(
        """
        <div style="margin-top:18px;text-align:center;color:#8b96a7;font-size:11px;">
            초기 테스트 비밀번호: 1234
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("</div></div>", unsafe_allow_html=True)


# ------------------------------------------------------------
# 학생 홈
# ------------------------------------------------------------
def student_home():
    student = get_current_student()
    if not student:
        set_page("student_login")
        return

    topbar()

    c1, c2, c3, c4 = st.columns([5.4, 1.3, 1.4, 1.2])
    with c1:
        st.markdown(
            f"""
            <div class="teacher-brand">
                <div class="teacher-brand-icon" style="background:#5138f5;">▤</div>
                <div>
                    <div class="teacher-brand-title">독서포트폴리오</div>
                    <div class="teacher-brand-sub">{student['반']} {student['학번']}번 · {student['이름']} 학생</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c4:
        if st.button("로그아웃", use_container_width=True):
            st.session_state.student_logged_in = False
            st.session_state.current_student_id = None
            set_page("student_login")

    # 선택 도서 / 통계
    books_html = ""
    for idx, book in enumerate(student["도서"], start=1):
        title = book.split(" (")[0]
        author = book.split("(")[-1].replace(")", "") if "(" in book else ""
        books_html += f"""
        <div style="display:flex;align-items:center;gap:11px;margin-top:10px;">
            <div style="width:29px;height:29px;background:#e9eeff;color:#5138f5;border-radius:9px;
                        display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:800;">{idx}</div>
            <div>
                <b style="font-size:13px;">{title}</b>
                <div class="small-muted">{author}</div>
            </div>
        </div>
        """

    col_main, col_stat1, col_stat2 = st.columns([5.7, 1.35, 1.35])
    with col_main:
        st.markdown(
            f"""
            <div class="dashboard-card">
                <div style="color:#5138f5;font-size:13px;font-weight:800;">▣ 나의 이번 학기 선택 도서 (1~2권)</div>
                {books_html}
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col_stat1:
        st.markdown(
            f"""
            <div class="stat-card">
                <div class="stat-label">작성 차시</div>
                <div class="stat-number" style="color:#5138f5;">{student['완료차시']} <span style="font-size:12px;color:#8591a4;font-weight:500;">/16차시</span></div>
                <div class="stat-sub">15차시 남음</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col_stat2:
        st.markdown(
            f"""
            <div class="stat-card">
                <div class="stat-label">총 읽은 쪽수</div>
                <div class="stat-number" style="color:#00a878;">{student['총독서']} <span style="font-size:12px;color:#8591a4;font-weight:500;">쪽</span></div>
                <div class="stat-sub">평균 0쪽/차시</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown(
        """
        <div class="dashboard-card" style="margin-top:14px;">
            <div style="color:#5138f5;font-size:13px;font-weight:800;margin-bottom:8px;">⌁ 1학기 독서 포트폴리오 달성도 (15~17차시 기준)</div>
            <div class="progress-bg"><div class="progress-fill" style="width:0%;"></div></div>
            <div style="display:flex;justify-content:space-between;margin-top:7px;">
                <span class="small-muted">시작 (1차시)</span>
                <span style="font-size:10px;color:#e18a00;">10차시 (반환점)</span>
                <span style="font-size:10px;color:#5138f5;">15~17차시 (수행평가 만점 구간)</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
        <div class="dashboard-card" style="margin-top:14px;background:#fafaff;border-color:#dfe3ff;">
            <div style="display:flex;justify-content:space-between;align-items:center;">
                <div>
                    <b style="font-size:13px;">매 차시 (30~35분) 독서 후 배운 점을 누적 기록하세요</b>
                    <div style="color:#616fa0;font-size:11px;margin-top:4px;">
                        요약, 인상 깊은 문장, 질문과 답변, 나의 생각과 느낌이 누적되어 한 권의 포트폴리오가 됩니다.
                    </div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns([5, 1.7])
    with c2:
        st.markdown('<div class="primary-button">', unsafe_allow_html=True)
        if st.button("＋ 새 차시 독서 기록 작성", use_container_width=True):
            st.session_state.show_new_record = True
        st.markdown("</div>", unsafe_allow_html=True)

    if st.session_state.show_new_record:
        st.markdown("### 새 차시 기록")
        with st.form("new_record"):
            n1, n2 = st.columns(2)
            with n1:
                session_no = st.number_input("차시", 1, 17, max(1, min(17, student["완료차시"] + 1)))
                pages = st.number_input("읽은 쪽수", 0, 1000, 0)
                summary = st.text_area("요약", height=120, placeholder="오늘 읽은 내용을 자신의 말로 정리해 보세요.")
            with n2:
                memorable = st.text_area("인상 깊은 내용", height=120)
                question = st.text_area("질문과 답변", height=120)
                feeling = st.text_area("느낀점", height=120)

            save = st.form_submit_button("저장", use_container_width=True)
            if save:
                if not summary.strip():
                    st.warning("요약을 입력해 주세요.")
                else:
                    key = student["학번"]
                    st.session_state.records.setdefault(key, [])
                    st.session_state.records[key] = [
                        r for r in st.session_state.records[key] if r["차시"] != int(session_no)
                    ]
                    st.session_state.records[key].append({
                        "차시": int(session_no),
                        "쪽수": int(pages),
                        "요약": summary.strip(),
                        "인상": memorable.strip(),
                        "질문": question.strip(),
                        "느낀점": feeling.strip(),
                        "작성일": datetime.now().strftime("%Y-%m-%d %H:%M")
                    })
                    student["완료차시"] = len(st.session_state.records[key])
                    student["총독서"] = sum(r["쪽수"] for r in st.session_state.records[key])
                    st.session_state.show_new_record = False
                    st.success("저장되었습니다.")
                    st.rerun()

    records = st.session_state.records.get(student["학번"], [])
    st.markdown(f"#### 차시별 독서 포트폴리오 ({len(records)}개)")

    for n in range(1, 17):
        r = next((x for x in records if x["차시"] == n), None)
        if r:
            with st.expander(f"{n}차시 독서 기록 · {r['쪽수']}쪽"):
                st.write("**요약**", r["요약"])
                st.write("**인상 깊은 내용**", r["인상"])
                st.write("**질문과 답변**", r["질문"])
                st.write("**느낀점**", r["느낀점"])
        else:
            st.markdown(
                f"""
                <div class="dashboard-card" style="margin-top:10px;padding:14px 18px;border-style:dashed;">
                    <div style="display:flex;align-items:center;gap:11px;">
                        <div style="width:30px;height:30px;border-radius:9px;background:#f0f3f7;color:#7f8ba0;display:flex;align-items:center;justify-content:center;font-weight:800;font-size:12px;">{n}</div>
                        <div>
                            <b style="font-size:12px;color:#56647a;">{n}차시 독서 기록</b>
                            <div class="small-muted">아직 작성되지 않았습니다.</div>
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )


# ------------------------------------------------------------
# 교사 대시보드
# ------------------------------------------------------------
def teacher_dashboard():
    if not st.session_state.teacher_logged_in:
        set_page("teacher_login")
        return

    topbar()

    st.markdown(
        """
        <div class="teacher-header">
            <div class="teacher-brand">
                <div class="teacher-brand-icon">▣</div>
                <div>
                    <div class="teacher-brand-title">교사용 수행평가 관리 대시보드</div>
                    <div class="teacher-brand-sub">중학교 15~17차시 독서 포트폴리오 누적 진도 관리 & 학기말 성적 연계</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    b1, b2, b3, b4, b5 = st.columns([1.5, 1.3, 1.2, 1.3, 1.4])
    with b1:
        st.button("ⓘ 채점 기준표(루브릭)", use_container_width=True)
    with b2:
        st.button("🔑 비밀번호 변경", use_container_width=True)
    with b3:
        st.button("⚙ 반영비율 (20%)", use_container_width=True)
    with b4:
        if st.button("학생 화면 →", use_container_width=True):
            st.session_state.teacher_logged_in = False
            set_page("student_login")
    with b5:
        if st.button("교사 로그아웃", use_container_width=True):
            st.session_state.teacher_logged_in = False
            set_page("teacher_login")

    st.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)

    t1, t2, t3 = st.columns([1.5, 1.8, 1.8])
    with t1:
        st.markdown(
            "<div style='background:#5138f5;color:#fff;border-radius:10px;padding:10px;text-align:center;font-size:12px;font-weight:700;'>♧ 학생별 명단 및 채점</div>",
            unsafe_allow_html=True,
        )
    with t2:
        st.markdown(
            "<div style='background:#fff;border:1px solid #dfe6f0;border-radius:10px;padding:10px;text-align:center;font-size:12px;font-weight:700;'>▥ 학급별 통계 및 비교</div>",
            unsafe_allow_html=True,
        )
    with t3:
        st.markdown(
            "<div style='background:#fff;border:1px solid #dfe6f0;border-radius:10px;padding:10px;text-align:center;font-size:12px;font-weight:700;'>▣ 데이터 저장소 & 백업 안내</div>",
            unsafe_allow_html=True,
        )

    students = st.session_state.students
    total = len(students)
    avg_sessions = sum(s["완료차시"] for s in students) / total if total else 0
    graded = sum(1 for s in students if s["채점"])
    scores = [s["점수"] for s in students if s["점수"] is not None]
    avg_score = sum(scores) / len(scores) if scores else None

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    stats = [
        ("♧", "조회 학생 수", f"{total}명", "전체 학생"),
        ("◷", "평균 작성 차시", f"{avg_sessions:.1f}", "차시당 30~35분 독서"),
        ("✓", "수행 채점 완료율", f"{graded} / {total}명", f"{graded / total * 100:.0f}%"),
        ("♙", "평가자 평균 총점", f"{avg_score:.1f}점" if avg_score is not None else "–점", "학기말 20% 환산 반영"),
    ]

    sc = st.columns(4)
    for col, (icon, label, value, sub) in zip(sc, stats):
        with col:
            st.markdown(
                f"""
                <div class="stat-card">
                    <div style="font-size:19px;color:#5138f5;">{icon}</div>
                    <div class="stat-label">{label}</div>
                    <div class="stat-number">{value}</div>
                    <div class="stat-sub">{sub}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown("<div style='height:11px'></div>", unsafe_allow_html=True)

    st.markdown('<div class="dashboard-card">', unsafe_allow_html=True)
    f1, f2, f3, f4 = st.columns([1.3, 1.3, 2.7, 2.3])
    with f1:
        grade = st.selectbox("학년", ["전체 학년", "1학년", "2학년", "3학년"])
    with f2:
        class_no = st.selectbox("반", ["전체 반", "1반", "2반", "3반"])
    with f3:
        state = st.radio("상태", ["전체", "채점완료", "미채점", "15차시+"], horizontal=True)
    with f4:
        search = st.text_input("검색", placeholder="학생 이름, 학번, 도서명 검색...")
    st.markdown("</div>", unsafe_allow_html=True)

    filtered = []
    for s in students:
        if grade != "전체 학년" and not s["반"].startswith(grade[0]):
            continue
        if class_no != "전체 반" and s["반"].split("-")[1] != class_no[0]:
            continue
        if state == "채점완료" and not s["채점"]:
            continue
        if state == "미채점" and s["채점"]:
            continue
        if state == "15차시+" and s["완료차시"] < 15:
            continue

        if search:
            target = " ".join([s["학번"], s["이름"], *s["도서"]])
            if search.lower() not in target.lower():
                continue

        filtered.append(s)

    st.markdown(
        f"""
        <div class="dashboard-card" style="margin-top:10px;padding:15px 18px 0;">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
                <b style="font-size:13px;color:#1d3bd3;">♧ 학생 독서 포트폴리오 진도 및 수행평가 성적 명단 ({len(filtered)}명)</b>
                <span class="small-muted">* AI 자동 채점 / 수기 채점으로 수행평가 점수를 완성하세요.</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 표는 작은 화면에서도 유지되도록 HTML grid로 표시
    st.markdown(
        """
        <div class="dashboard-card" style="padding:0;overflow:hidden;">
            <div style="display:grid;grid-template-columns:0.8fr 0.8fr 0.8fr 1.9fr 1.2fr 0.8fr 0.8fr 0.8fr 0.9fr 0.9fr 0.9fr;
                        gap:6px;padding:12px 10px;background:#f8fafc;border-top:1px solid #e5ebf2;border-bottom:1px solid #e5ebf2;
                        color:#67758a;font-size:10px;font-weight:800;">
                <div>학적</div><div>학번</div><div>성명</div><div>선택 도서 (1~2권)</div>
                <div>진도 (16차시)</div><div>총 쪽수</div><div>수행 총점</div><div>성취도</div>
                <div>학기말 반영</div><div>채점 상태</div><div>관리</div>
            </div>
        """,
        unsafe_allow_html=True,
    )

    for s in filtered:
        score = f"{s['점수']}점" if s["점수"] is not None else "–"
        status = "채점완료" if s["채점"] else "미채점"
        books = "<br>".join(s["도서"])
        progress = min(100, s["완료차시"] / 16 * 100)

        st.markdown(
            f"""
            <div style="display:grid;grid-template-columns:0.8fr 0.8fr 0.8fr 1.9fr 1.2fr 0.8fr 0.8fr 0.8fr 0.9fr 0.9fr 0.9fr;
                        gap:6px;padding:14px 10px;border-bottom:1px solid #edf0f5;align-items:center;font-size:10px;background:#fff;">
                <div><span style="background:#eef2f7;border-radius:6px;padding:4px 5px;">{s['반']}</span></div>
                <div><b>{s['학번']}</b></div>
                <div><b>{s['이름']}</b></div>
                <div>{books}</div>
                <div>
                    <b style="color:#5138f5;">{s['완료차시']} / 16차시</b>
                    <div class="progress-bg"><div class="progress-fill" style="width:{progress}%;"></div></div>
                </div>
                <div><b>{s['총독서']}</b>쪽</div>
                <div>{score}</div>
                <div>–</div>
                <div>–</div>
                <div><span class="status {'status-done' if s['채점'] else 'status-wait'}">{status}</span></div>
                <div></div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        a1, a2 = st.columns([1, 8])
        with a1:
            if st.button("채점" if not s["채점"] else "수정", key=f"grade_{s['학번']}", use_container_width=True):
                st.session_state.grade_student = s["학번"]

    st.markdown("</div>", unsafe_allow_html=True)

    if "grade_student" in st.session_state:
        target = next(
            (s for s in students if s["학번"] == st.session_state.grade_student),
            None
        )
        if target:
            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
            st.markdown(f"### 📝 {target['이름']} 학생 수행평가 채점")

            with st.form(f"grade_form_{target['학번']}"):
                st.markdown(
                    """
                    <div style="padding:11px 13px;border-radius:10px;background:#f6f7ff;border:1px solid #dfe3ff;color:#525d86;font-size:11px;">
                        루브릭에 따라 채점 수준과 점수를 입력하세요. AI 자동 채점 결과를 사용한다면 교사가 최종 점수를 수정할 수 있습니다.
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                g1, g2 = st.columns(2)
                with g1:
                    level = st.radio("평가 수준", ["탁월함", "우수함", "보통", "노력 요함"], horizontal=True)
                with g2:
                    score_value = st.number_input("수행평가 총점 (100점)", 0, 100, int(target["점수"] or 0))

                feedback = st.text_area("교사 피드백 / 세특 메모", height=100)
                save = st.form_submit_button("최종 채점 저장", use_container_width=True)

                if save:
                    target["점수"] = int(score_value)
                    target["채점"] = True
                    st.session_state.pop("grade_student", None)
                    st.success("채점 결과가 저장되었습니다.")
                    st.rerun()


# ------------------------------------------------------------
# 페이지 실행
# ------------------------------------------------------------
if st.session_state.page == "student_login":
    student_login()

elif st.session_state.page == "teacher_login":
    teacher_login()

elif st.session_state.page == "student_home":
    if not st.session_state.student_logged_in:
        set_page("student_login")
    student_home()

elif st.session_state.page == "teacher_dashboard":
    teacher_dashboard()
