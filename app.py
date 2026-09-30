import hashlib
from datetime import date, datetime
from typing import Any, Dict, Iterable, List, Optional

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import gspread
from gspread.exceptions import SpreadsheetNotFound, WorksheetNotFound


# =========================================================
# 기본 설정
# =========================================================
APP_TITLE = "중학교 독서 포트폴리오"
APP_SUBTITLE = "15~17차시 한 학기 독서 누적 기록 & 수행평가 관리 시스템"

# Google Sheet 문서 주소는 코드에 고정합니다.
# 서비스 계정 인증정보(private_key 등)는 반드시 secrets.toml에 보관하세요.
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/1fB5c_VQequRNY7PsJ9dUwt3_jzsIJlhACPNRu5IkIEU/edit"

SHEET_CONFIG = {
    "Students": ["학번", "이름", "PIN", "등록일"],
    "Books": ["학번", "도서번호", "도서명", "저자", "총페이지수"],
    "Logs": [
        "학번",
        "차시",
        "날짜",
        "시작페이지",
        "끝페이지",
        "읽은페이지수",
        "독서시간(분)",
        "요약및느낀점",
    ],
    "Evaluations": ["학번", "차시", "점수", "교사피드백", "최종평어"],
    "Settings": ["총차시수"],
}

DEFAULT_TOTAL_SESSIONS = 16
MIN_SESSIONS = 15
MAX_SESSIONS = 17

DEMO_ACCOUNTS = [
    {"학번": "20315", "이름": "김예시", "PIN": "1111"},
    {"학번": "20507", "이름": "이참관", "PIN": "2222"},
]


# =========================================================
# 유틸리티
# =========================================================
def init_session_state() -> None:
    defaults = {
        "role": "guest",
        "student_id": None,
        "student_name": None,
        "page": "home",
        "teacher_authenticated": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _get_secret_mapping() -> dict:
    """서비스 계정 설정을 여러 Secrets 입력 형태에서 읽습니다.

    지원 형태:
    1) [connections.gsheets] 아래에 credential 값을 넣은 형태
    2) 최상위에 credential 값을 넣은 형태
    3) [gsheets] 아래에 credential 값을 넣은 형태
    """
    required_keys = [
        "type",
        "project_id",
        "private_key_id",
        "private_key",
        "client_email",
        "client_id",
        "auth_uri",
        "token_uri",
        "auth_provider_x509_cert_url",
        "client_x509_cert_url",
    ]

    # Streamlit Cloud / 로컬의 st.secrets는 mapping처럼 접근할 수 있습니다.
    try:
        secrets_dict = st.secrets.to_dict()
    except Exception:
        secrets_dict = dict(st.secrets)

    candidates = []

    connections = secrets_dict.get("connections")
    if isinstance(connections, dict):
        gsheets = connections.get("gsheets")
        if isinstance(gsheets, dict):
            candidates.append(gsheets)

    gsheets_top = secrets_dict.get("gsheets")
    if isinstance(gsheets_top, dict):
        candidates.append(gsheets_top)

    # 마지막으로 최상위에 직접 넣은 경우.
    candidates.append(secrets_dict)

    for candidate in candidates:
        config = {
            key: candidate.get(key)
            for key in required_keys
            if key in candidate
        }
        if config:
            # 최소 한 개 이상의 인증 키를 찾은 후보를 반환
            return config

    return {}


def get_gspread_client():
    """secrets.toml의 서비스 계정 인증정보로 gspread 클라이언트를 생성합니다."""
    config = _get_secret_mapping()

    required_keys = [
        "type",
        "project_id",
        "private_key_id",
        "private_key",
        "client_email",
        "client_id",
        "auth_uri",
        "token_uri",
        "auth_provider_x509_cert_url",
        "client_x509_cert_url",
    ]

    missing = [key for key in required_keys if not normalize_text(config.get(key, ""))]
    if missing:
        raise RuntimeError(
            "서비스 계정 인증정보가 부족합니다. 누락된 항목: " + ", ".join(missing)
            + "\n\n"
            "secrets.toml 형식은 [connections.gsheets] 아래에 넣거나 "
            "최상위에 직접 넣을 수 있습니다."
        )

    if normalize_text(config.get("type")) != "service_account":
        raise RuntimeError(
            "서비스 계정 JSON의 type 값은 'service_account'여야 합니다."
        )

    credentials_info = {
        key: config[key]
        for key in required_keys
        if key != "type"
    }
    credentials_info["type"] = "service_account"

    # gspread의 service_account_from_dict보다 명시적인 google-auth 방식을 사용합니다.
    # Google Sheets / Drive API 모두 사용할 수 있도록 scope을 지정합니다.
    from google.oauth2.service_account import Credentials

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    credentials = Credentials.from_service_account_info(
        credentials_info,
        scopes=scopes,
    )
    return gspread.authorize(credentials)


def get_spreadsheet():
    """Python 코드에 고정한 Google Sheet URL로 스프레드시트를 엽니다."""
    try:
        return get_gspread_client().open_by_url(GOOGLE_SHEET_URL)
    except SpreadsheetNotFound as error:
        raise RuntimeError(
            "Google Sheet를 찾을 수 없습니다. 서비스 계정 client_email이 "
            "'독서 포트폴리오 테스트' 시트의 편집자로 공유되어 있는지 확인하세요."
        ) from error
    except Exception as error:
        raise RuntimeError(f"Google Sheet 연결 실패: {error}") from error


def get_worksheet(worksheet: str):
    try:
        return get_spreadsheet().worksheet(worksheet)
    except WorksheetNotFound:
        try:
            return get_spreadsheet().add_worksheet(
                title=worksheet,
                rows=1000,
                cols=max(8, len(SHEET_CONFIG[worksheet])),
            )
        except Exception as error:
            raise RuntimeError(
                f"'{worksheet}' worksheet를 생성할 수 없습니다: {error}"
            ) from error


def normalize_text(value: Any) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def normalize_student_id(value: Any) -> str:
    text = normalize_text(value)
    if text.endswith(".0") and text[:-2].isdigit():
        text = text[:-2]
    return text


def safe_int(value: Any, default: int = 0) -> int:
    try:
        if pd.isna(value) or normalize_text(value) == "":
            return default
        return int(float(value))
    except (ValueError, TypeError):
        return default


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if pd.isna(value) or normalize_text(value) == "":
            return default
        return float(value)
    except (ValueError, TypeError):
        return default


def hash_pin(pin: str) -> str:
    return hashlib.sha256(pin.encode("utf-8")).hexdigest()


def verify_pin(input_pin: str, stored_value: Any) -> bool:
    stored = normalize_text(stored_value)
    if not stored:
        return False

    # 신규 저장값은 SHA-256 해시를 사용.
    # 기존 시트에 평문 4자리 PIN이 들어 있어도 마이그레이션 전까지 로그인 가능하게 처리.
    if len(stored) == 64:
        return hashlib.sha256(input_pin.encode("utf-8")).hexdigest() == stored

    return stored == input_pin


def now_string() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def get_teacher_password() -> str:
    try:
        if "app" in st.secrets:
            return normalize_text(st.secrets["app"].get("teacher_password", ""))
        return normalize_text(st.secrets.get("teacher_password", ""))
    except Exception:
        return ""


def demo_enabled() -> bool:
    try:
        if "app" in st.secrets:
            value = st.secrets["app"].get("enable_demo_accounts", True)
        else:
            value = st.secrets.get("enable_demo_accounts", True)
        if isinstance(value, bool):
            return value
        return normalize_text(value).lower() in {"1", "true", "yes", "on"}
    except Exception:
        return True


# =========================================================
# Google Sheets 데이터 계층
# =========================================================
def make_empty_df(columns: Iterable[str]) -> pd.DataFrame:
    return pd.DataFrame(columns=list(columns))


def read_sheet(worksheet: str) -> pd.DataFrame:
    ws = get_worksheet(worksheet)
    try:
        records = ws.get_all_records(default_blank="")
    except TypeError:
        records = ws.get_all_records()

    if not records:
        return make_empty_df(SHEET_CONFIG[worksheet])

    df = pd.DataFrame(records)
    expected = SHEET_CONFIG[worksheet]
    for col in expected:
        if col not in df.columns:
            df[col] = ""
    return df[expected]


def ensure_worksheets() -> None:
    """
    CRUD를 위해 각 worksheet가 없으면 생성하고, 첫 행에 표준 헤더를 준비합니다.
    이미 헤더가 있으면 데이터를 건드리지 않습니다.
    """
    spreadsheet = get_spreadsheet()

    for worksheet, columns in SHEET_CONFIG.items():
        try:
            ws = spreadsheet.worksheet(worksheet)
        except WorksheetNotFound:
            ws = spreadsheet.add_worksheet(
                title=worksheet,
                rows=1000,
                cols=max(8, len(columns)),
            )

        first_row = ws.row_values(1)
        if not first_row:
            ws.update("A1", [columns], raw=True)
        else:
            existing = [normalize_text(v) for v in first_row[: len(columns)]]
            if existing != columns:
                # 사용자가 이미 만든 탭의 헤더가 요구사항과 다를 때는 자동 덮어쓰지 않습니다.
                # read_sheet()가 필요한 열을 보완할 수 있도록 그대로 둡니다.
                pass


def update_sheet(worksheet: str, df: pd.DataFrame) -> None:
    ws = get_worksheet(worksheet)
    expected = SHEET_CONFIG[worksheet]
    output = df.copy()

    for col in expected:
        if col not in output.columns:
            output[col] = ""

    output = output[expected].copy()
    output = output.where(pd.notna(output), "")

    values = [expected]
    if not output.empty:
        values.extend(output.astype(object).values.tolist())

    # 사용자가 원하는 시트 구조를 유지하면서 전체 데이터를 최신 상태로 갱신합니다.
    ws.clear()
    ws.update("A1", values, raw=True)
    st.cache_resource.clear()


def append_row(worksheet: str, row: Dict[str, Any]) -> None:
    df = read_sheet(worksheet)
    row_data = {col: row.get(col, "") for col in SHEET_CONFIG[worksheet]}
    df = pd.concat([df, pd.DataFrame([row_data])], ignore_index=True)
    update_sheet(worksheet, df)


def upsert_row(
    worksheet: str,
    row: Dict[str, Any],
    key_columns: List[str],
) -> None:
    df = read_sheet(worksheet)
    row_data = {col: row.get(col, "") for col in SHEET_CONFIG[worksheet]}

    if df.empty:
        update_sheet(worksheet, pd.DataFrame([row_data]))
        return

    mask = pd.Series(True, index=df.index)
    for key in key_columns:
        target = normalize_text(row_data.get(key, ""))
        mask = mask & df[key].map(normalize_text).eq(target)

    if mask.any():
        first_index = df[mask].index[0]
        for key, value in row_data.items():
            df.at[first_index, key] = value
    else:
        df = pd.concat([df, pd.DataFrame([row_data])], ignore_index=True)

    update_sheet(worksheet, df)


def delete_matching_rows(
    worksheet: str,
    key_columns: List[str],
    key_values: Dict[str, Any],
) -> None:
    df = read_sheet(worksheet)
    if df.empty:
        return

    mask = pd.Series(True, index=df.index)
    for key in key_columns:
        target = normalize_text(key_values.get(key, ""))
        mask = mask & df[key].map(normalize_text).eq(target)

    if mask.any():
        update_sheet(worksheet, df.loc[~mask].reset_index(drop=True))


# =========================================================
# 데이터 정제 / 계산
# =========================================================
def get_total_sessions() -> int:
    try:
        settings = read_sheet("Settings")
        if not settings.empty:
            value = safe_int(settings.iloc[0]["총차시수"], DEFAULT_TOTAL_SESSIONS)
            return max(MIN_SESSIONS, min(MAX_SESSIONS, value))
    except Exception:
        pass
    return DEFAULT_TOTAL_SESSIONS


def save_total_sessions(total_sessions: int) -> None:
    total_sessions = max(MIN_SESSIONS, min(MAX_SESSIONS, int(total_sessions)))
    df = pd.DataFrame([{"총차시수": total_sessions}])
    update_sheet("Settings", df)


def get_students() -> pd.DataFrame:
    df = read_sheet("Students").copy()
    if df.empty:
        return df
    df["학번"] = df["학번"].map(normalize_student_id)
    df["이름"] = df["이름"].map(normalize_text)
    df["PIN"] = df["PIN"].map(normalize_text)
    return df


def get_books(student_id: Optional[str] = None) -> pd.DataFrame:
    df = read_sheet("Books").copy()
    if df.empty:
        return df

    df["학번"] = df["학번"].map(normalize_student_id)
    df["도서번호"] = df["도서번호"].map(safe_int)
    df["총페이지수"] = df["총페이지수"].map(safe_int)
    df["도서명"] = df["도서명"].map(normalize_text)
    df["저자"] = df["저자"].map(normalize_text)

    if student_id:
        df = df[df["학번"] == normalize_student_id(student_id)].copy()
    return df


def get_logs(student_id: Optional[str] = None) -> pd.DataFrame:
    df = read_sheet("Logs").copy()
    if df.empty:
        return df

    df["학번"] = df["학번"].map(normalize_student_id)
    df["차시"] = df["차시"].map(safe_int)
    df["시작페이지"] = df["시작페이지"].map(safe_int)
    df["끝페이지"] = df["끝페이지"].map(safe_int)
    df["읽은페이지수"] = df["읽은페이지수"].map(safe_int)
    df["독서시간(분)"] = df["독서시간(분)"].map(safe_int)
    df["날짜"] = df["날짜"].map(normalize_text)
    df["요약및느낀점"] = df["요약및느낀점"].map(normalize_text)

    if student_id:
        df = df[df["학번"] == normalize_student_id(student_id)].copy()
    return df


def get_evaluations(student_id: Optional[str] = None) -> pd.DataFrame:
    df = read_sheet("Evaluations").copy()
    if df.empty:
        return df

    df["학번"] = df["학번"].map(normalize_student_id)
    df["차시"] = df["차시"].map(normalize_text)
    df["점수"] = df["점수"].map(normalize_text)
    df["교사피드백"] = df["교사피드백"].map(normalize_text)
    df["최종평어"] = df["최종평어"].map(normalize_text)

    if student_id:
        df = df[df["학번"] == normalize_student_id(student_id)].copy()
    return df


def get_student_by_id(student_id: str) -> Optional[Dict[str, str]]:
    students = get_students()
    student_id = normalize_student_id(student_id)
    if not students.empty:
        row = students[students["학번"] == student_id]
        if not row.empty:
            return {
                "학번": student_id,
                "이름": normalize_text(row.iloc[0]["이름"]),
                "PIN": normalize_text(row.iloc[0]["PIN"]),
                "등록일": normalize_text(row.iloc[0]["등록일"]),
            }

    if demo_enabled():
        for demo in DEMO_ACCOUNTS:
            if demo["학번"] == student_id:
                return demo
    return None


def calculate_progress(student_id: str, total_sessions: int) -> Dict[str, float]:
    logs = get_logs(student_id)
    completed = 0 if logs.empty else int(logs["차시"].nunique())
    progress = (completed / total_sessions * 100) if total_sessions else 0.0
    return {
        "completed": completed,
        "total": total_sessions,
        "percent": min(progress, 100.0),
    }


def calculate_statistics(student_id: str) -> Dict[str, float]:
    logs = get_logs(student_id)

    if logs.empty:
        return {
            "total_pages": 0,
            "total_minutes": 0,
            "avg_speed": 0.0,
            "sessions": 0,
        }

    total_pages = int(logs["읽은페이지수"].sum())
    total_minutes = int(logs["독서시간(분)"].sum())
    avg_speed = total_pages / total_minutes * 60 if total_minutes > 0 else 0.0

    return {
        "total_pages": total_pages,
        "total_minutes": total_minutes,
        "avg_speed": avg_speed,
        "sessions": int(logs["차시"].nunique()),
    }


def sessions_status(student_id: str, total_sessions: int) -> List[Dict[str, Any]]:
    logs = get_logs(student_id)
    by_session = {}
    if not logs.empty:
        by_session = logs.set_index("차시").to_dict(orient="index")

    result = []
    for session in range(1, total_sessions + 1):
        row = by_session.get(session)
        result.append(
            {
                "차시": session,
                "작성": row is not None,
                "읽은페이지수": safe_int(row["읽은페이지수"]) if row else 0,
                "독서시간": safe_int(row["독서시간(분)"]) if row else 0,
            }
        )
    return result


# =========================================================
# 스타일
# =========================================================
def inject_css() -> None:
    st.markdown(
        """
        <style>
        :root {
            --primary: #6C5CE7;
            --primary-dark: #4834D4;
            --soft: #F4F1FF;
            --ink: #241F3D;
            --muted: #716C82;
            --border: #E8E3FA;
        }

        .stApp {
            background: linear-gradient(180deg, #FAF9FF 0%, #FFFFFF 34%);
        }

        .block-container {
            max-width: 1180px;
            padding-top: 2.1rem;
            padding-bottom: 4rem;
        }

        .hero {
            text-align: center;
            padding: 1.0rem 0 1.7rem 0;
        }

        .hero h1 {
            color: var(--ink);
            font-size: 2.25rem;
            margin-bottom: .45rem;
            letter-spacing: -0.04em;
        }

        .hero p {
            color: var(--muted);
            font-size: 1rem;
            margin: 0 auto;
        }

        .pill {
            display: inline-block;
            background: var(--soft);
            color: var(--primary-dark);
            padding: .35rem .72rem;
            border-radius: 999px;
            font-size: .82rem;
            font-weight: 700;
            margin-bottom: .7rem;
        }

        .card {
            background: #FFFFFF;
            border: 1px solid var(--border);
            border-radius: 22px;
            padding: 1.2rem 1.3rem;
            box-shadow: 0 10px 28px rgba(72, 52, 212, 0.07);
        }

        .kpi {
            text-align: center;
            background: #FFFFFF;
            border: 1px solid var(--border);
            border-radius: 18px;
            padding: 1.1rem .7rem;
            box-shadow: 0 8px 24px rgba(72, 52, 212, 0.06);
        }

        .kpi-label {
            font-size: .82rem;
            color: var(--muted);
            margin-bottom: .35rem;
        }

        .kpi-value {
            font-size: 1.55rem;
            font-weight: 800;
            color: var(--primary-dark);
        }

        .profile-card {
            background: linear-gradient(135deg, #6C5CE7 0%, #4834D4 100%);
            color: #FFFFFF;
            border-radius: 24px;
            padding: 1.25rem 1.35rem;
            margin-bottom: 1rem;
            box-shadow: 0 14px 30px rgba(72, 52, 212, 0.18);
        }

        .profile-name {
            font-size: 1.35rem;
            font-weight: 800;
            margin-bottom: .18rem;
        }

        .profile-sub {
            opacity: .88;
            font-size: .9rem;
        }

        .status-chip {
            border: 1px solid var(--border);
            background: #FFFFFF;
            border-radius: 999px;
            padding: .28rem .62rem;
            font-size: .78rem;
            display: inline-block;
        }

        div[data-testid="stButton"] > button,
        div[data-testid="stFormSubmitButton"] > button {
            border-radius: 12px;
            font-weight: 700;
            min-height: 2.65rem;
        }

        .section-title {
            font-size: 1.08rem;
            font-weight: 800;
            color: var(--ink);
            margin: .2rem 0 .75rem 0;
        }

        .help-text {
            color: var(--muted);
            font-size: .86rem;
        }

        .login-wrap {
            max-width: 740px;
            margin: 0 auto;
        }

        .teacher-lock {
            max-width: 520px;
            margin: 0 auto;
        }

        .small-gap {
            height: .35rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_hero() -> None:
    st.markdown(
        f"""
        <div class="hero">
            <div class="pill">📚 Reading Portfolio · Streamlit</div>
            <h1>{APP_TITLE}</h1>
            <p>{APP_SUBTITLE}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_kpis(items: List[tuple]) -> None:
    cols = st.columns(len(items))
    for col, (label, value) in zip(cols, items):
        with col:
            st.markdown(
                f"""
                <div class="kpi">
                    <div class="kpi-label">{label}</div>
                    <div class="kpi-value">{value}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


# =========================================================
# 인증 / 메인
# =========================================================
def login_student(student_id: str, name: str, pin: str) -> bool:
    student_id = normalize_student_id(student_id)
    name = normalize_text(name)
    pin = normalize_text(pin)

    if len(pin) != 4 or not pin.isdigit():
        st.error("PIN은 숫자 4자리로 입력해 주세요.")
        return False

    students = get_students()
    if not students.empty:
        match = students[
            (students["학번"] == student_id) & (students["이름"] == name)
        ]
        if not match.empty and verify_pin(pin, match.iloc[0]["PIN"]):
            st.session_state.update(
                {
                    "role": "student",
                    "student_id": student_id,
                    "student_name": name,
                    "page": "student",
                }
            )
            return True

    if demo_enabled():
        for demo in DEMO_ACCOUNTS:
            if (
                demo["학번"] == student_id
                and demo["이름"] == name
                and demo["PIN"] == pin
            ):
                st.session_state.update(
                    {
                        "role": "student",
                        "student_id": student_id,
                        "student_name": name,
                        "page": "student",
                    }
                )
                return True

    st.error("학번, 이름, PIN을 다시 확인해 주세요.")
    return False


def render_login_page() -> None:
    render_hero()

    st.markdown('<div class="login-wrap">', unsafe_allow_html=True)

    tab_login, tab_register = st.tabs(["학생 로그인", "신규 학생 등록"])

    with tab_login:
        with st.form("student_login_form"):
            st.markdown('<div class="section-title">학생 포트폴리오 입장</div>', unsafe_allow_html=True)
            col1, col2 = st.columns(2)
            with col1:
                student_id = st.text_input(
                    "학번",
                    placeholder="예: 20315",
                    max_chars=5,
                )
            with col2:
                student_name = st.text_input(
                    "학생 이름",
                    placeholder="예: 김학생",
                )

            pin = st.text_input(
                "고유번호(PIN 4자리 비밀번호)",
                type="password",
                max_chars=4,
                placeholder="숫자 4자리",
            )

            submitted = st.form_submit_button(
                "포트폴리오 입장하기 ➔",
                use_container_width=True,
            )

        if submitted and login_student(student_id, student_name, pin):
            st.success("로그인되었습니다.")
            st.rerun()

        with st.expander("선생님·참관용 예시 계정 둘러보기 (2명)"):
            if demo_enabled():
                for demo in DEMO_ACCOUNTS:
                    st.write(
                        f"**{demo['이름']}** · 학번 `{demo['학번']}` · PIN `{demo['PIN']}`"
                    )
                st.caption(
                    "예시 계정은 화면 확인용입니다. 실제 수업에서는 secrets의 "
                    "`enable_demo_accounts = false`로 끄는 것을 권장합니다."
                )
            else:
                st.info("예시 계정 기능이 비활성화되어 있습니다.")

        st.markdown("###")
        if st.button(
            "교사용 관리 및 평가 페이지로 이동 (교사 전용)",
            use_container_width=True,
        ):
            st.session_state.page = "teacher_login"
            st.rerun()

    with tab_register:
        with st.form("student_register_form"):
            st.markdown('<div class="section-title">새 학생 등록</div>', unsafe_allow_html=True)
            c1, c2, c3 = st.columns(3)

            with c1:
                grade = st.selectbox("학년", [1, 2, 3], index=1)
            with c2:
                class_no = st.selectbox("반", list(range(1, 13)), index=2)
            with c3:
                number = st.number_input(
                    "번호",
                    min_value=1,
                    max_value=40,
                    value=1,
                    step=1,
                )

            generated_id = f"{grade}{class_no:02d}{int(number):02d}"
            st.info(f"생성되는 학번: **{generated_id}**")

            name = st.text_input("학생 이름", placeholder="예: 홍길동")
            pin = st.text_input(
                "PIN 4자리 비밀번호",
                type="password",
                max_chars=4,
                placeholder="숫자 4자리",
            )

            submitted = st.form_submit_button(
                "등록하고 포트폴리오 시작하기 ➔",
                use_container_width=True,
            )

        if submitted:
            if not name.strip():
                st.error("학생 이름을 입력해 주세요.")
            elif len(pin) != 4 or not pin.isdigit():
                st.error("PIN은 숫자 4자리로 입력해 주세요.")
            else:
                students = get_students()
                exists = (
                    not students.empty
                    and (students["학번"] == generated_id).any()
                )

                if exists:
                    st.error("이미 등록된 학번입니다. 학생 정보를 확인해 주세요.")
                else:
                    append_row(
                        "Students",
                        {
                            "학번": generated_id,
                            "이름": name.strip(),
                            "PIN": hash_pin(pin),
                            "등록일": now_string(),
                        },
                    )
                    st.session_state.update(
                        {
                            "role": "student",
                            "student_id": generated_id,
                            "student_name": name.strip(),
                            "page": "student",
                        }
                    )
                    st.success("등록이 완료되었습니다.")
                    st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)


# =========================================================
# 학생 페이지
# =========================================================
def logout() -> None:
    st.session_state.update(
        {
            "role": "guest",
            "student_id": None,
            "student_name": None,
            "teacher_authenticated": False,
            "page": "home",
        }
    )
    st.rerun()


def render_student_profile(student_id: str, student_name: str, total_sessions: int) -> None:
    books = get_books(student_id)
    book_text = "등록 도서 없음"
    if not books.empty:
        names = [
            normalize_text(v)
            for v in books["도서명"].tolist()
            if normalize_text(v)
        ]
        if names:
            book_text = " / ".join(names[:2])

    progress = calculate_progress(student_id, total_sessions)

    st.markdown(
        f"""
        <div class="profile-card">
            <div class="profile-name">👋 {student_name} 학생</div>
            <div class="profile-sub">학번 {student_id} · 선택 도서: {book_text}</div>
            <div class="profile-sub" style="margin-top:.35rem;">
                독서 진행률: {progress['completed']}/{progress['total']}차시 ({progress['percent']:.0f}%)
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_books_tab(student_id: str) -> None:
    st.markdown('<div class="section-title">이번 학기 선택 도서</div>', unsafe_allow_html=True)
    st.caption("최대 2권까지 등록할 수 있습니다. 같은 도서는 도서 1 또는 도서 2로 수정할 수 있습니다.")

    books = get_books(student_id)
    current = {}
    if not books.empty:
        for _, row in books.iterrows():
            current[safe_int(row["도서번호"])] = row

    for book_no in [1, 2]:
        row = current.get(book_no)
        with st.form(f"book_form_{book_no}"):
            st.subheader(f"도서 {book_no}")
            c1, c2 = st.columns([2, 1])
            with c1:
                title = st.text_input(
                    "도서명",
                    value=normalize_text(row["도서명"]) if row is not None else "",
                    key=f"book_title_{book_no}",
                )
            with c2:
                total_pages = st.number_input(
                    "총 페이지 수",
                    min_value=0,
                    max_value=10000,
                    value=safe_int(row["총페이지수"]) if row is not None else 0,
                    step=1,
                    key=f"book_pages_{book_no}",
                )

            author = st.text_input(
                "저자",
                value=normalize_text(row["저자"]) if row is not None else "",
                key=f"book_author_{book_no}",
            )

            submitted = st.form_submit_button(
                f"도서 {book_no} 저장",
                use_container_width=True,
            )

        if submitted:
            if not title.strip() or not author.strip():
                st.error("도서명과 저자를 입력해 주세요.")
                continue

            upsert_row(
                "Books",
                {
                    "학번": student_id,
                    "도서번호": book_no,
                    "도서명": title.strip(),
                    "저자": author.strip(),
                    "총페이지수": int(total_pages),
                },
                ["학번", "도서번호"],
            )
            st.success(f"도서 {book_no}가 저장되었습니다.")
            st.rerun()


def render_log_tab(student_id: str, total_sessions: int) -> None:
    st.markdown('<div class="section-title">차시별 독서 누가기록</div>', unsafe_allow_html=True)

    books = get_books(student_id)
    if books.empty:
        st.warning("먼저 '선택 도서 등록' 탭에서 이번 학기 책을 등록해 주세요.")
        return

    logs = get_logs(student_id)
    existing_by_session = {}
    if not logs.empty:
        for _, row in logs.iterrows():
            existing_by_session[safe_int(row["차시"])] = row

    selected_session = st.selectbox(
        "기록할 차시",
        list(range(1, total_sessions + 1)),
        format_func=lambda x: f"{x}차시",
        key="log_session_selector",
    )
    row = existing_by_session.get(selected_session)

    if row is not None:
        st.info(f"{selected_session}차시 기존 기록을 불러왔습니다. 저장하면 업데이트됩니다.")

    with st.form("reading_log_form"):
        log_date = st.date_input(
            "읽은 날짜",
            value=(
                pd.to_datetime(row["날짜"]).date()
                if row is not None and normalize_text(row["날짜"])
                else date.today()
            ),
        )

        c1, c2, c3 = st.columns(3)
        with c1:
            start_page = st.number_input(
                "오늘 읽은 시작 페이지",
                min_value=1,
                max_value=10000,
                value=max(1, safe_int(row["시작페이지"], 1)) if row is not None else 1,
                step=1,
            )
        with c2:
            end_page = st.number_input(
                "오늘 읽은 끝 페이지",
                min_value=1,
                max_value=10000,
                value=max(1, safe_int(row["끝페이지"], 1)) if row is not None else 1,
                step=1,
            )
        with c3:
            minutes = st.number_input(
                "독서 시간(분)",
                min_value=0,
                max_value=1440,
                value=max(0, safe_int(row["독서시간(분)"])) if row is not None else 0,
                step=5,
            )

        summary = st.text_area(
            "차시별 핵심 요약 및 느낀 점",
            value=normalize_text(row["요약및느낀점"]) if row is not None else "",
            height=170,
            placeholder="오늘 읽은 내용의 핵심, 인상 깊은 부분, 생각의 변화 등을 적어 주세요.",
        )

        submitted = st.form_submit_button(
            "독서 기록 저장하기",
            use_container_width=True,
        )

    if submitted:
        if end_page < start_page:
            st.error("끝 페이지는 시작 페이지보다 크거나 같아야 합니다.")
            return

        pages_read = int(end_page - start_page + 1)

        upsert_row(
            "Logs",
            {
                "학번": student_id,
                "차시": selected_session,
                "날짜": log_date.strftime("%Y-%m-%d"),
                "시작페이지": int(start_page),
                "끝페이지": int(end_page),
                "읽은페이지수": pages_read,
                "독서시간(분)": int(minutes),
                "요약및느낀점": summary.strip(),
            },
            ["학번", "차시"],
        )
        st.success(
            f"{selected_session}차시 기록이 저장되었습니다. "
            f"읽은 페이지 {pages_read}쪽"
        )
        st.rerun()

    st.markdown("### 차시 진행 상태")
    statuses = sessions_status(student_id, total_sessions)
    rows = []
    for item in statuses:
        rows.append(
            {
                "차시": f"{item['차시']}차시",
                "기록상태": "✅ 작성" if item["작성"] else "⬜ 미작성",
                "읽은 페이지": item["읽은페이지수"],
                "독서 시간(분)": item["독서시간"],
            }
        )
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def render_stats_tab(student_id: str, total_sessions: int) -> None:
    st.markdown('<div class="section-title">독서 통계 그래프</div>', unsafe_allow_html=True)

    stats = calculate_statistics(student_id)
    render_kpis(
        [
            ("총 읽은 페이지", f"{stats['total_pages']}쪽"),
            ("총 독서 시간", f"{stats['total_minutes']}분"),
            ("평균 독서 속도", f"{stats['avg_speed']:.1f}쪽/시간"),
            ("기록 차시", f"{stats['sessions']}/{total_sessions}"),
        ]
    )

    st.markdown("###")

    logs = get_logs(student_id)
    if logs.empty:
        st.info("독서 누가기록을 1건 이상 저장하면 그래프가 표시됩니다.")
        return

    by_session = (
        logs.groupby("차시", as_index=False)
        .agg(
            {
                "읽은페이지수": "sum",
                "독서시간(분)": "sum",
            }
        )
        .sort_values("차시")
    )

    all_sessions = pd.DataFrame({"차시": list(range(1, total_sessions + 1))})
    by_session = all_sessions.merge(by_session, on="차시", how="left").fillna(0)
    by_session["누적페이지"] = by_session["읽은페이지수"].cumsum()

    fig1 = go.Figure()
    fig1.add_trace(
        go.Scatter(
            x=by_session["차시"],
            y=by_session["누적페이지"],
            mode="lines+markers",
            name="누적 읽은 페이지",
        )
    )
    fig1.update_layout(
        title="차시별 누적 읽은 페이지 추이",
        xaxis_title="차시",
        yaxis_title="누적 페이지",
        margin=dict(l=30, r=20, t=60, b=30),
        height=360,
    )
    st.plotly_chart(fig1, use_container_width=True)

    fig2 = go.Figure()
    fig2.add_trace(
        go.Bar(
            x=by_session["차시"],
            y=by_session["읽은페이지수"],
            name="읽은 페이지 수",
        )
    )
    fig2.add_trace(
        go.Bar(
            x=by_session["차시"],
            y=by_session["독서시간(분)"],
            name="독서 시간(분)",
        )
    )
    fig2.update_layout(
        title="차시별 독서량 & 독서 시간",
        xaxis_title="차시",
        yaxis_title="값",
        barmode="group",
        margin=dict(l=30, r=20, t=60, b=30),
        height=360,
    )
    st.plotly_chart(fig2, use_container_width=True)

    st.caption(
        "평균 독서 속도는 총 읽은 페이지 ÷ 총 독서시간 × 60으로 계산한 값입니다."
    )


def evaluation_total(evals: pd.DataFrame) -> float:
    if evals.empty:
        return 0.0
    numeric = pd.to_numeric(evals["점수"], errors="coerce")
    return float(numeric.fillna(0).sum())


def render_evaluation_result_tab(student_id: str, total_sessions: int) -> None:
    st.markdown('<div class="section-title">수행평가 채점 결과 확인</div>', unsafe_allow_html=True)

    evals = get_evaluations(student_id)
    if evals.empty:
        st.info("아직 교사가 등록한 평가 결과가 없습니다.")
        return

    total_score = evaluation_total(evals)

    final_rows = evals[evals["차시"].str.strip() == "학기말"]
    final_comment = ""
    final_score = ""
    if not final_rows.empty:
        final_score = normalize_text(final_rows.iloc[-1]["점수"])
        final_comment = normalize_text(final_rows.iloc[-1]["최종평어"])

    session_evals = evals[evals["차시"].str.strip() != "학기말"].copy()
    completed_eval = 0 if session_evals.empty else int(session_evals["차시"].nunique())

    render_kpis(
        [
            ("누적 평가 점수", f"{total_score:g}점"),
            ("차시 평가 등록", f"{completed_eval}/{total_sessions}"),
            ("학기말 점수", final_score if final_score else "미입력"),
        ]
    )

    st.markdown("###")
    display_cols = ["차시", "점수", "교사피드백"]
    if not session_evals.empty:
        display_df = session_evals[display_cols].sort_values(
            "차시",
            key=lambda s: pd.to_numeric(s, errors="coerce"),
        )
        st.dataframe(
            display_df.rename(
                columns={
                    "차시": "차시",
                    "점수": "점수",
                    "교사피드백": "교사 피드백",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )

    if final_comment:
        st.markdown("### 종합 총평")
        st.markdown(
            f"""
            <div class="card">
                {final_comment.replace(chr(10), "<br>")}
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_student_page() -> None:
    total_sessions = get_total_sessions()
    student_id = st.session_state.student_id
    student_name = st.session_state.student_name

    render_student_profile(student_id, student_name, total_sessions)

    top_left, top_right = st.columns([6, 1])
    with top_right:
        if st.button("로그아웃", use_container_width=True):
            logout()

    tab_book, tab_log, tab_stats, tab_eval = st.tabs(
        [
            "선택 도서 등록",
            "차시별 독서 누가기록",
            "독서 통계 그래프",
            "수행평가 채점 결과 확인",
        ]
    )

    with tab_book:
        render_books_tab(student_id)

    with tab_log:
        render_log_tab(student_id, total_sessions)

    with tab_stats:
        render_stats_tab(student_id, total_sessions)

    with tab_eval:
        render_evaluation_result_tab(student_id, total_sessions)


# =========================================================
# 교사 페이지
# =========================================================
def render_teacher_login() -> None:
    render_hero()
    st.markdown('<div class="teacher-lock">', unsafe_allow_html=True)

    st.markdown(
        """
        <div class="card">
            <div class="section-title">🔐 교사용 관리 및 평가</div>
            <div class="help-text">
                교사 전용 비밀번호를 입력하면 학기 설정, 학생 누가기록 조회,
                수행평가 채점 기능을 사용할 수 있습니다.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.form("teacher_login_form"):
        password = st.text_input(
            "교사 전용 비밀번호",
            type="password",
            max_chars=64,
        )
        c1, c2 = st.columns(2)
        with c1:
            submitted = st.form_submit_button(
                "교사 페이지 입장",
                use_container_width=True,
            )
        with c2:
            go_back = st.form_submit_button(
                "학생 로그인으로 돌아가기",
                use_container_width=True,
            )

    if go_back:
        st.session_state.page = "home"
        st.rerun()

    if submitted:
        configured_password = get_teacher_password()
        if not configured_password:
            st.error(
                "교사 비밀번호가 설정되지 않았습니다. "
                ".streamlit/secrets.toml의 teacher_password를 설정해 주세요."
            )
        elif password == configured_password:
            st.session_state.update(
                {
                    "role": "teacher",
                    "teacher_authenticated": True,
                    "page": "teacher",
                }
            )
            st.success("교사 인증이 완료되었습니다.")
            st.rerun()
        else:
            st.error("교사 전용 비밀번호가 올바르지 않습니다.")

    st.markdown("</div>", unsafe_allow_html=True)


def render_teacher_settings() -> None:
    st.markdown('<div class="section-title">⚙️ 시스템 설정</div>', unsafe_allow_html=True)

    current = get_total_sessions()
    with st.form("settings_form"):
        new_total = st.slider(
            "이번 학기 전체 차시 수",
            min_value=MIN_SESSIONS,
            max_value=MAX_SESSIONS,
            value=current,
            step=1,
            help="15~17차시 범위에서 설정할 수 있습니다.",
        )
        submitted = st.form_submit_button(
            "학기 차시 설정 저장",
            use_container_width=True,
        )

    if submitted:
        save_total_sessions(new_total)
        st.success(f"총 차시 수가 {new_total}차시로 저장되었습니다.")
        st.rerun()


def render_teacher_student_list(total_sessions: int) -> Optional[str]:
    st.markdown('<div class="section-title">👥 학생 목록 조회</div>', unsafe_allow_html=True)

    students = get_students()
    logs = get_logs()

    if students.empty:
        st.info("등록된 학생이 없습니다.")
        return None

    search = st.text_input(
        "학생 검색",
        placeholder="학번 또는 이름으로 검색",
    ).strip()

    filtered = students.copy()
    if search:
        filtered = filtered[
            filtered["학번"].str.contains(search, na=False)
            | filtered["이름"].str.contains(search, na=False)
        ].copy()

    if filtered.empty:
        st.warning("검색 조건에 맞는 학생이 없습니다.")
        return None

    records = []
    log_counts = {}
    if not logs.empty:
        log_counts = logs.groupby("학번")["차시"].nunique().to_dict()

    for _, row in filtered.sort_values(["학번"]).iterrows():
        sid = normalize_student_id(row["학번"])
        count = int(log_counts.get(sid, 0))
        percent = count / total_sessions * 100 if total_sessions else 0
        records.append(
            {
                "학번": sid,
                "이름": normalize_text(row["이름"]),
                "독서기록": f"{count}/{total_sessions}차시",
                "진행률": f"{percent:.0f}%",
                "등록일": normalize_text(row["등록일"]),
            }
        )

    view = pd.DataFrame(records)
    st.dataframe(view, use_container_width=True, hide_index=True)

    selected_id = st.selectbox(
        "조회할 학생",
        view["학번"].tolist(),
        format_func=lambda x: (
            f"{x} · {view.loc[view['학번'] == x, '이름'].iloc[0]}"
        ),
    )
    return selected_id


def render_teacher_logs(student_id: str, total_sessions: int) -> None:
    st.markdown('<div class="section-title">📝 학생 누가기록 상세</div>', unsafe_allow_html=True)

    students = get_students()
    student_rows = students[students["학번"] == student_id]
    student_name = (
        normalize_text(student_rows.iloc[0]["이름"])
        if not student_rows.empty
        else ""
    )

    books = get_books(student_id)
    logs = get_logs(student_id)
    evals = get_evaluations(student_id)

    if not books.empty:
        st.markdown("**선택 도서**")
        book_view = books[["도서번호", "도서명", "저자", "총페이지수"]].copy()
        book_view.columns = ["도서번호", "도서명", "저자", "총페이지수"]
        st.dataframe(book_view, use_container_width=True, hide_index=True)

    st.markdown(
        f"**{student_name} ({student_id})** · {total_sessions}차시 기준"
    )

    if logs.empty:
        st.info("아직 작성된 누가기록이 없습니다.")
    else:
        display = logs[
            [
                "차시",
                "날짜",
                "시작페이지",
                "끝페이지",
                "읽은페이지수",
                "독서시간(분)",
                "요약및느낀점",
            ]
        ].sort_values("차시")
        st.dataframe(display, use_container_width=True, hide_index=True)

    st.markdown("###")
    st.markdown('<div class="section-title">✏️ 수행평가 채점 입력</div>', unsafe_allow_html=True)

    selected_session = st.selectbox(
        "평가 차시",
        ["학기말"] + [str(x) for x in range(1, total_sessions + 1)],
        key=f"teacher_eval_session_{student_id}",
    )

    existing = None
    if not evals.empty:
        matches = evals[evals["차시"] == str(selected_session)]
        if not matches.empty:
            existing = matches.iloc[-1]

    default_score = safe_float(existing["점수"]) if existing is not None else 0.0
    default_feedback = (
        normalize_text(existing["교사피드백"]) if existing is not None else ""
    )
    default_comment = (
        normalize_text(existing["최종평어"]) if existing is not None else ""
    )

    with st.form(f"teacher_eval_form_{student_id}_{selected_session}"):
        score = st.number_input(
            "점수",
            min_value=0.0,
            max_value=100.0,
            value=default_score,
            step=0.5,
            help="배점 기준에 맞춰 점수를 입력하세요. 기본 입력 범위는 0~100점입니다.",
        )
        feedback = st.text_area(
            "교사 피드백",
            value=default_feedback,
            height=130,
            placeholder="기록 내용에 근거한 구체적인 피드백을 입력하세요.",
        )
        final_comment = st.text_area(
            "최종평어",
            value=default_comment,
            height=110,
            placeholder="학기말인 경우 종합 총평을 입력하세요.",
        )

        submitted = st.form_submit_button(
            "채점 결과 저장 / 업데이트",
            use_container_width=True,
        )

    if submitted:
        upsert_row(
            "Evaluations",
            {
                "학번": student_id,
                "차시": str(selected_session),
                "점수": f"{score:g}",
                "교사피드백": feedback.strip(),
                "최종평어": final_comment.strip(),
            },
            ["학번", "차시"],
        )
        st.success(f"{selected_session} 평가 결과가 저장되었습니다.")
        st.rerun()

    if not evals.empty:
        st.markdown("### 현재 평가 요약")
        summary = evals.copy()
        summary = summary[["차시", "점수", "교사피드백", "최종평어"]]
        st.dataframe(summary, use_container_width=True, hide_index=True)


def render_teacher_page() -> None:
    total_sessions = get_total_sessions()
    render_hero()

    header_left, header_right = st.columns([6, 1])
    with header_left:
        st.markdown(
            f"""
            <div class="card">
                <div class="section-title">교사 관리 콘솔</div>
                <div class="help-text">현재 학기 총 {total_sessions}차시</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with header_right:
        if st.button("로그아웃", use_container_width=True):
            logout()

    tab_settings, tab_students, tab_evaluate = st.tabs(
        ["시스템 설정", "학생 목록", "누가기록·채점"]
    )

    with tab_settings:
        render_teacher_settings()

    with tab_students:
        selected_id = render_teacher_student_list(total_sessions)
        if selected_id:
            st.session_state["teacher_selected_student"] = selected_id

    with tab_evaluate:
        students = get_students()
        if students.empty:
            st.info("학생을 먼저 등록해 주세요.")
            return

        saved_student = st.session_state.get("teacher_selected_student")
        student_ids = students["학번"].astype(str).tolist()
        if saved_student not in student_ids:
            saved_student = student_ids[0]

        selected_id = st.selectbox(
            "채점할 학생 선택",
            student_ids,
            index=student_ids.index(saved_student),
            format_func=lambda x: (
                f"{x} · {students.loc[students['학번'].astype(str) == str(x), '이름'].iloc[0]}"
            ),
            key="teacher_eval_student_selector",
        )

        st.session_state["teacher_selected_student"] = selected_id
        render_teacher_logs(selected_id, total_sessions)


# =========================================================
# 앱 시작
# =========================================================
def main() -> None:
    st.set_page_config(
        page_title=APP_TITLE,
        page_icon="📚",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    init_session_state()
    inject_css()

    # Google Sheets 연결 실패 시 오류 원인을 사용자에게 명확히 보여준다.
    try:
        ensure_worksheets()
    except Exception as error:
        st.error("Google Sheets 연결 또는 worksheet 초기화에 실패했습니다.")
        st.code(str(error))
        st.info(
            "확인할 항목: Secrets의 서비스 계정 인증정보(type/project_id/private_key_id/private_key/client_email/client_id/auth_uri/token_uri/auth_provider_x509_cert_url/client_x509_cert_url), "
            "그리고 client_email이 Google Sheet에서 편집자(Editor)로 공유되어 있는지 확인하세요. "
            "시트 주소는 app.py에 고정되어 있습니다."
        )
        st.stop()

    page = st.session_state.get("page", "home")

    if page == "teacher_login":
        render_teacher_login()
    elif page == "teacher" and st.session_state.get("teacher_authenticated"):
        render_teacher_page()
    elif page == "student" and st.session_state.get("student_id"):
        render_student_page()
    else:
        render_login_page()


if __name__ == "__main__":
    main()
