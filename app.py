
import streamlit as st
from datetime import datetime

# ============================================================
# 중학교 15~17차시 독서 포트폴리오 수행평가 시스템
# Streamlit UI prototype
# - AI Studio 화면을 최대한 비슷하게 재현
# - 실제 Google Sheets 연결 전에도 UI/기능을 테스트할 수 있도록 샘플 데이터 포함
# ============================================================

st.set_page_config(
    page_title="독서 포트폴리오 수행평가 시스템",
    page_icon="📖",
    layout="wide",
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
            "도서": ["아몬드 (손원평)"],
            "완료차시": 0,
            "총독서": 0,
            "점수": None,
            "채점": False,
        },
        {
            "학번": "20308",
            "반": "2-3",
            "이름": "박도윤",
            "도서": ["페인트 (이희영)", "체험하지 않는 마음 (김민정)"],
            "완료차시": 0,
            "총독서": 0,
            "점수": None,
            "채점": False,
        },
        {
            "학번": "30112",
            "반": "3-1",
            "이름": "김서윤",
            "도서": ["완득이 (김려령)"],
            "완료차시": 0,
            "총독서": 0,
            "점수": None,
            "채점": False,
        },
    ]

if "records" not in st.session_state:
    st.session_state.records = {}

if "screen" not in st.session_state:
    st.session_state.screen = "student"

if "selected_student" not in st.session_state:
    st.session_state.selected_student = "10101"

if "show_add_record" not in st.session_state:
    st.session_state.show_add_record = False

# ------------------------------------------------------------
# 디자인 CSS
# ------------------------------------------------------------
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Noto Sans KR', sans-serif;
}

.stApp {
    background: #f7f9fc;
    color: #172033;
}

.block-container {
    max-width: 1220px;
    padding-top: 0.5rem;
    padding-bottom: 2rem;
}

header[data-testid="stHeader"] {
    background: transparent;
}

section[data-testid="stSidebar"] {
    display: none;
}

/* 상단 바 */
.topbar {
    background: #0f172a;
    color: white;
    padding: 8px 18px;
    border-radius: 0 0 8px 8px;
    margin: -8px -10px 16px -10px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-size: 12px;
}

.topbar-left {
    display:flex;
    align-items:center;
    gap:10px;
    font-weight:700;
}

.db-pill {
    color:#00d99a;
    border:1px solid #007e63;
    background:#062c28;
    padding:4px 10px;
    border-radius:999px;
    font-size:11px;
    font-weight:700;
}

.title-row {
    background:white;
    border-bottom:1px solid #e5eaf2;
    padding: 10px 0 14px 0;
    margin: -4px -10px 14px -10px;
}

.brand {
    display:flex;
    align-items:center;
    gap:12px;
}

.brand-icon {
    width:42px;
    height:42px;
    background:#5141f5;
    border-radius:12px;
    display:flex;
    align-items:center;
    justify-content:center;
    color:white;
    font-size:22px;
}

.brand-name {
    font-size:18px;
    font-weight:800;
    color:#172033;
}

.brand-sub {
    font-size:12px;
    color:#718096;
    margin-top:2px;
}

.badge {
    display:inline-block;
    background:#eef0ff;
    color:#4b42e9;
    border-radius:6px;
    padding:3px 7px;
    font-size:11px;
    margin-left:4px;
    font-weight:700;
}

/* 카드 */
.card {
    background:white;
    border:1px solid #dfe6f1;
    border-radius:16px;
    padding:18px 22px;
    box-shadow:0 1px 2px rgba(20,35,70,.03);
    margin-bottom:14px;
}

.book-card {
    background:white;
    border:1px solid #dfe6f1;
    border-radius:16px;
    padding:18px 22px;
    margin-bottom:12px;
}

.section-title {
    color:#4b3df5;
    font-size:13px;
    font-weight:800;
    margin-bottom:10px;
}

.big-number {
    font-size:24px;
    font-weight:800;
    color:#141b2d;
}

.muted {
    color:#7c8799;
    font-size:12px;
}

.blue {
    color:#4938ff;
}

.green {
    color:#00a878;
}

.orange {
    color:#e58b00;
}

.progress-bg {
    height:8px;
    background:#edf1f7;
    border-radius:999px;
    overflow:hidden;
    margin-top:8px;
}

.progress-fill {
    height:100%;
    background:#4b3df5;
    border-radius:999px;
}

.record-empty {
    border:1px dashed #cdd7e7;
    background:#fff;
    border-radius:14px;
    padding:18px;
    margin:10px 0;
}

.record-number {
    width:32px;
    height:32px;
    border-radius:10px;
    background:#edf1ff;
    color:#4b3df5;
    display:flex;
    align-items:center;
    justify-content:center;
    font-weight:800;
}

.stat-box {
    background:white;
    border:1px solid #e0e6ef;
    border-radius:15px;
    padding:18px 20px;
    min-height:105px;
}

.admin-card {
    background:white;
    border:1px solid #dfe6f1;
    border-radius:15px;
    padding:17px 20px;
}

.small-label {
    color:#6d7788;
    font-size:12px;
    font-weight:600;
}

.table-head {
    background:#f8fafc;
    border-top:1px solid #e3e8f1;
    border-bottom:1px solid #e3e8f1;
    padding:12px 10px;
    color:#607087;
    font-size:12px;
    font-weight:700;
}

.student-row {
    background:white;
    border-bottom:1px solid #edf0f5;
    padding:13px 10px;
}

.status {
    display:inline-block;
    padding:4px 10px;
    border-radius:999px;
    font-size:11px;
    font-weight:700;
}

.status-wait {
    color:#e09a00;
    border:1px solid #f2ce69;
    background:#fffaf0;
}

.status-done {
    color:#008d67;
    border:1px solid #80d8bd;
    background:#effcf7;
}

.notice {
    border:1px solid #d9e2ff;
    background:#f7f8ff;
    color:#4b3df5;
    border-radius:12px;
    padding:11px 14px;
    font-size:12px;
}

hr {
    border:none;
    border-top:1px solid #edf0f5;
    margin:14px 0;
}

/* Streamlit 기본 버튼 */
.stButton > button {
    border-radius:10px;
    border:1px solid #dbe2ed;
    font-weight:700;
    color:#39455c;
    background:white;
    min-height:38px;
}

.stButton > button:hover {
    border-color:#5141f5;
    color:#5141f5;
}

.primary-btn .stButton > button {
    background:#4b3df5;
    color:white;
    border-color:#4b3df5;
}

div[data-testid="stForm"] {
    border:1px solid #dfe6f1;
    border-radius:15px;
    background:white;
    padding:20px;
}

label[data-testid="stWidgetLabel"] p {
    font-size:12px !important;
    font-weight:700 !important;
    color:#4a5568 !important;
}

div[data-baseweb="select"] > div {
    border-radius:9px;
}

textarea, input {
    border-radius:9px !important;
}

[data-testid="stMetric"] {
    background:transparent;
}

@media (max-width: 800px) {
    .block-container {
        padding-left: 10px;
        padding-right: 10px;
    }
}
</style>
""",
    unsafe_allow_html=True,
)

# ------------------------------------------------------------
# 공통 상단
# ------------------------------------------------------------
def topbar():
    st.markdown(
        """
        <div class="topbar">
            <div class="topbar-left">
                <span>▣</span>
                <span>중학교 15~17차시 독서 포트폴리오 수행평가 시스템</span>
                <span class="db-pill">●　클라우드 DB: Google Sheets (GAS 검증 모드)</span>
            </div>
            <div style="font-size:11px;color:#c7cfdd;">화면 전환:　독서 포트폴리오</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def page_title(title, subtitle, teacher=False):
    icon = "▣"
    st.markdown(
        f"""
        <div class="title-row">
            <div class="brand">
                <div class="brand-icon" style="background:{'#111a31' if teacher else '#5141f5'}">{icon}</div>
                <div>
                    <div class="brand-name">{title}
                        <span class="badge">중학교 독서수행평가</span>
                    </div>
                    <div class="brand-sub">{subtitle}</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def switch_buttons():
    c1, c2, c3 = st.columns([1, 1, 6])
    with c1:
        if st.button("학생 화면", use_container_width=True):
            st.session_state.screen = "student"
            st.rerun()
    with c2:
        if st.button("교사 관리자", use_container_width=True):
            st.session_state.screen = "teacher"
            st.rerun()


# ------------------------------------------------------------
# 학생 화면
# ------------------------------------------------------------
def student_screen():
    topbar()

    student = next(
        (x for x in st.session_state.students if x["학번"] == st.session_state.selected_student),
        st.session_state.students[0],
    )

    page_title(
        "독서포트폴리오",
        f"{student['반']} {student['학번']}번 · {student['이름']} 학생",
    )

    c1, c2, c3 = st.columns([6, 1.4, 1])
    with c1:
        st.markdown(
            f"""
            <div class="card" style="padding:20px 24px 16px 24px;">
                <div style="display:flex;justify-content:space-between;align-items:flex-start;">
                    <div>
                        <div class="section-title">▣ 나의 이번 학기 선택 도서 (1~2권)</div>
                        <div style="display:flex;align-items:center;gap:12px;">
                            <div style="width:30px;height:30px;border-radius:9px;background:#e7edff;color:#4b3df5;
                                display:flex;align-items:center;justify-content:center;font-weight:800;">1</div>
                            <div>
                                <b style="font-size:14px;">{student['도서'][0].split(' (')[0]}</b>
                                <div class="muted">{student['도서'][0].split('(')[-1].replace(')','')} · 청소년 소설</div>
                            </div>
                        </div>
                    </div>
                    <div class="muted">✎ 도서 변경 / 등록</div>
                </div>
                <hr>
                <div class="section-title">⌁ 1학기 독서 포트폴리오 달성도 (15~17차시 기준)</div>
                <div style="display:flex;justify-content:space-between;">
                    <span class="muted">시작 (1차시)</span>
                    <span style="font-size:11px;color:#f08b00;">10차시 (반환점)</span>
                    <span style="font-size:11px;color:#4b3df5;">15~17차시 (수행평가 만점 구간)</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with c2:
        st.markdown(
            f"""
            <div class="stat-box">
                <div class="small-label">작성 차시</div>
                <div class="big-number blue">{student['완료차시']} <span class="muted">/16차시</span></div>
                <div class="muted">15차시 남음</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with c3:
        st.markdown(
            f"""
            <div class="stat-box">
                <div class="small-label">총 읽은 쪽수</div>
                <div class="big-number green">{student['총독서']} <span class="muted">쪽</span></div>
                <div class="muted">평균 0쪽/차시</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown(
        f"""
        <div class="card" style="padding:12px 22px;">
            <div style="display:flex;justify-content:space-between;align-items:center;">
                <b style="font-size:13px;color:#4b3df5;">⌑ 차시별 독서 포트폴리오 ({student['완료차시']}개)</b>
                <span style="font-size:12px;color:#4b3df5;">▥ 독서 통계 그래프 & 성취 배지　　♙ 수행평가 채점 결과 확인</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="card" style="background:#f7f8ff;border-color:#dce2ff;">
            <div style="display:flex;justify-content:space-between;align-items:center;">
                <div>
                    <b style="font-size:13px;">매 차시 (30~35분) 독서 후 배운 점을 누적 기록하세요</b>
                    <div class="muted" style="color:#5141f5;margin-top:3px;">
                        요약, 인상 깊은 문장, 질문과 답변, 나의 생각과 느낌이 누적되어 한 권의 포트폴리오가 됩니다.
                    </div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns([7, 1.6, 1.5])
    with c2:
        if st.button("＋ 새 차시 독서 기록 작성", use_container_width=True):
            st.session_state.show_add_record = True
    with c3:
        st.empty()

    # 기록 작성 폼
    if st.session_state.show_add_record:
        st.markdown("### 새 차시 독서 기록")
        with st.form("new_record_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                session_no = st.number_input(
                    "차시",
                    min_value=1,
                    max_value=17,
                    value=min(student["완료차시"] + 1, 17),
                )
                pages = st.number_input("읽은 쪽수", min_value=0, max_value=1000, value=0)
                summary = st.text_area("요약", height=110, placeholder="오늘 읽은 내용을 자신의 말로 정리해 보세요.")
            with col2:
                memorable = st.text_area("인상 깊은 내용", height=110)
                question = st.text_area("질문과 답변", height=110)
                feeling = st.text_area("느낀점", height=110)

            b1, b2 = st.columns(2)
            with b1:
                submitted = st.form_submit_button("기록 저장", use_container_width=True)
            with b2:
                cancelled = st.form_submit_button("취소", use_container_width=True)

            if submitted:
                if not summary.strip():
                    st.warning("요약을 입력해 주세요.")
                else:
                    key = student["학번"]
                    st.session_state.records.setdefault(key, [])
                    st.session_state.records[key].append(
                        {
                            "차시": int(session_no),
                            "쪽수": int(pages),
                            "요약": summary,
                            "인상": memorable,
                            "질문": question,
                            "느낀점": feeling,
                            "작성일": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        }
                    )
                    student["완료차시"] = len(st.session_state.records[key])
                    student["총독서"] = sum(x["쪽수"] for x in st.session_state.records[key])
                    st.session_state.show_add_record = False
                    st.success("독서 기록이 저장되었습니다.")
                    st.rerun()

            if cancelled:
                st.session_state.show_add_record = False
                st.rerun()

    # 차시 목록
    records = st.session_state.records.get(student["학번"], [])
    for n in range(1, 17):
        rec = next((r for r in records if r["차시"] == n), None)

        if rec:
            st.markdown(
                f"""
                <div class="book-card">
                    <div style="display:flex;gap:14px;align-items:flex-start;">
                        <div class="record-number">{n}</div>
                        <div style="flex:1;">
                            <div style="font-weight:800;font-size:13px;">{n}차시 독서 기록</div>
                            <div class="muted" style="margin-top:4px;">
                                {rec['작성일']} · {rec['쪽수']}쪽
                            </div>
                            <div style="margin-top:9px;font-size:12px;line-height:1.6;">
                                <b>요약</b>　{rec['요약'][:180]}
                            </div>
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f"""
                <div class="record-empty">
                    <div style="display:flex;align-items:center;gap:12px;">
                        <div class="record-number" style="background:#f1f4f8;color:#7c8799;">{n}</div>
                        <div>
                            <b style="font-size:13px;color:#56647a;">{n}차시 독서 기록</b>
                            <div class="muted">아직 작성되지 않았습니다. 클릭하여 오늘 읽은 내용을 기록하세요.</div>
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # 학생 선택
    st.markdown("---")
    st.markdown("#### 학생 화면 테스트")
    options = {f"{s['반']} {s['학번']} {s['이름']}": s["학번"] for s in st.session_state.students}
    selected_label = next(k for k, v in options.items() if v == st.session_state.selected_student)
    new_label = st.selectbox("학생 선택", list(options.keys()), index=list(options.keys()).index(selected_label))
    new_id = options[new_label]
    if new_id != st.session_state.selected_student:
        st.session_state.selected_student = new_id
        st.rerun()


# ------------------------------------------------------------
# 교사 관리자 화면
# ------------------------------------------------------------
def teacher_screen():
    topbar()

    page_title(
        "교사용 수행평가 관리 대시보드",
        "중학교 15~17차시 독서 포트폴리오 누적 진도 관리 & 학기말 성적 연계",
        teacher=True,
    )

    # 관리자 버튼
    c1, c2, c3, c4, c5 = st.columns([1.3, 1.3, 1.3, 1.3, 1.1])
    with c1:
        st.button("ⓘ 채점 기준표(루브릭)", use_container_width=True)
    with c2:
        st.button("🔑 비밀번호 변경", use_container_width=True)
    with c3:
        st.button("⚙ 반영비율 (20%)", use_container_width=True)
    with c4:
        if st.button("학생 화면 →", use_container_width=True):
            st.session_state.screen = "student"
            st.rerun()
    with c5:
        st.empty()

    # 탭 느낌의 버튼
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    t1, t2, t3, t4 = st.columns([1.5, 1.7, 1.7, 5])
    with t1:
        st.markdown("<div style='background:#4b3df5;color:white;border-radius:10px;padding:9px;text-align:center;font-size:12px;font-weight:700;'>♧ 학생별 명단 및 채점</div>", unsafe_allow_html=True)
    with t2:
        st.markdown("<div style='background:white;border:1px solid #dce3ee;border-radius:10px;padding:9px;text-align:center;font-size:12px;font-weight:700;'>▥ 학급별 통계 및 비교 (3개 반)</div>", unsafe_allow_html=True)
    with t3:
        st.markdown("<div style='background:white;border:1px solid #dce3ee;border-radius:10px;padding:9px;text-align:center;font-size:12px;font-weight:700;'>▣ 데이터 저장소 & 백업 안내</div>", unsafe_allow_html=True)
    with t4:
        st.empty()

    # 통계 카드
    students = st.session_state.students
    total = len(students)
    avg_sessions = sum(s["완료차시"] for s in students) / total if total else 0
    graded = sum(1 for s in students if s["채점"])
    scores = [s["점수"] for s in students if s["점수"] is not None]
    avg_score = sum(scores) / len(scores) if scores else None

    cols = st.columns(4)
    card_data = [
        ("♧", "조회 학생 수", f"{total}명", "전체 학년 전체 반"),
        ("◷", "평균 작성 차시", f"{avg_sessions:.1f}", "차시당 30~35분 독서"),
        ("✓", "수행 채점 완료율", f"{graded} / {total}명", f"{(graded/total*100 if total else 0):.0f}%"),
        ("♙", "평가자 평균 총점", f"{avg_score:.1f}점" if avg_score is not None else "–점", "학기말 20% 환산 반영"),
    ]
    for col, (ico, label, value, sub) in zip(cols, card_data):
        with col:
            st.markdown(
                f"""
                <div class="stat-box">
                    <div style="font-size:22px;color:#4b3df5;">{ico}</div>
                    <div class="small-label">{label}</div>
                    <div class="big-number">{value}</div>
                    <div class="muted">{sub}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    # 필터
    st.markdown('<div class="card">', unsafe_allow_html=True)
    f1, f2, f3, f4 = st.columns([1.4, 1.4, 2.5, 2.5])
    with f1:
        grade = st.selectbox("학년", ["전체 학년", "1학년", "2학년", "3학년"])
    with f2:
        class_no = st.selectbox("반", ["전체 반", "1반", "2반", "3반"])
    with f3:
        state = st.radio("상태", ["전체", "채점완료", "미채점", "15차시+"], horizontal=True)
    with f4:
        search = st.text_input("검색", placeholder="학생 이름, 학번, 도서명 검색...")
    st.markdown("</div>", unsafe_allow_html=True)

    # 필터링
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
            target = " ".join([s["이름"], s["학번"], *s["도서"]])
            if search.lower() not in target.lower():
                continue
        filtered.append(s)

    st.markdown(
        f"""
        <div class="card" style="padding:14px 20px 8px 20px;">
            <div style="display:flex;justify-content:space-between;align-items:center;">
                <b style="color:#1c3edb;font-size:13px;">♧ 학생 독서 포트폴리오 진도 및 수행평가 성적 명단 ({len(filtered)}명)</b>
                <span style="color:#65738a;font-size:11px;">* [AI 자동 채점 / 수기 채점]을 통해 수행평가 점수와 세특을 완성하세요.</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 테이블 헤더
    st.markdown(
        """
        <div class="table-head">
            <div style="display:grid;grid-template-columns:0.8fr 0.8fr 0.9fr 2.0fr 1.2fr 0.9fr 0.9fr 0.9fr 0.9fr 1fr 1fr;gap:8px;">
                <div>학적</div><div>학번</div><div>성명</div><div>선택 도서 (1~2권)</div>
                <div>진도 (16차시 기준)</div><div>총 읽은 쪽수</div><div>수행 총점</div>
                <div>성취도</div><div>학기말 반영</div><div>채점 상태</div><div>관리</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    for s in filtered:
        score_text = f"{s['점수']}점" if s["점수"] is not None else "–"
        status_class = "status-done" if s["채점"] else "status-wait"
        status_text = "채점완료" if s["채점"] else "미채점"
        books = "<br>".join(s["도서"])

        st.markdown(
            f"""
            <div class="student-row">
                <div style="display:grid;grid-template-columns:0.8fr 0.8fr 0.9fr 2.0fr 1.2fr 0.9fr 0.9fr 0.9fr 0.9fr 1fr 1fr;gap:8px;align-items:center;font-size:12px;">
                    <div><span style="background:#eef2f7;border-radius:6px;padding:4px 6px;">{s['반']}<br>({s['반'][0]}반)</span></div>
                    <div><b>{s['학번']}</b></div>
                    <div><b>{s['이름']}</b>　◉</div>
                    <div>{books}</div>
                    <div>
                        <b style="color:#4b3df5;">{s['완료차시']} / 16차시</b>
                        <div class="progress-bg"><div class="progress-fill" style="width:{min(s['완료차시']/16*100,100)}%;"></div></div>
                    </div>
                    <div><b>{s['총독서']}</b> 쪽</div>
                    <div>{score_text}</div>
                    <div>–</div>
                    <div>–</div>
                    <div><span class="status {status_class}">{status_text}</span></div>
                    <div style="display:flex;gap:5px;"></div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # 행별 관리 버튼
        a, b, c, d, e = st.columns([1, 1, 1, 1, 6])
        with a:
            if st.button("채점", key=f"grade_{s['학번']}"):
                st.session_state.grade_student = s["학번"]
        with b:
            if st.button("학생", key=f"view_{s['학번']}"):
                st.session_state.selected_student = s["학번"]
                st.session_state.screen = "student"
                st.rerun()

    # 채점 영역
    if "grade_student" in st.session_state:
        target = next((x for x in students if x["학번"] == st.session_state.grade_student), None)
        if target:
            st.markdown("---")
            st.markdown(f"### 📝 {target['이름']} 학생 수행평가 채점")
            with st.form(f"grading_{target['학번']}"):
                st.markdown(
                    """
                    <div class="notice">
                    루브릭에 따라 AI 자동 채점 또는 수기 채점을 선택할 수 있습니다.
                    AI 점수는 교사가 수정한 뒤 최종 저장할 수 있도록 구성했습니다.
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                gc1, gc2 = st.columns(2)
                with gc1:
                    level = st.radio(
                        "평가 수준",
                        ["탁월함", "우수함", "보통", "노력 요함"],
                        horizontal=True,
                    )
                with gc2:
                    score = st.number_input(
                        "수행평가 총점 (100점)",
                        min_value=0,
                        max_value=100,
                        value=int(target["점수"] or 0),
                        step=1,
                    )
                feedback = st.text_area("교사 피드백 / 세특 메모", height=100)
                save_grade = st.form_submit_button("최종 채점 저장", use_container_width=True)

                if save_grade:
                    target["점수"] = int(score)
                    target["채점"] = True
                    st.session_state.pop("grade_student", None)
                    st.success("채점 결과가 저장되었습니다.")
                    st.rerun()


# ------------------------------------------------------------
# 실행
# ------------------------------------------------------------
switch_buttons()

if st.session_state.screen == "student":
    student_screen()
else:
    teacher_screen()
