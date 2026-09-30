import base64
import hashlib
import json
import re
from datetime import date, datetime
from zoneinfo import ZoneInfo
from typing import Any, Dict, Iterable, List, Optional

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from streamlit_gsheets import GSheetsConnection

try:
    from google import genai
    from google.genai import types
except ImportError:  # Gemini OCR 기능을 사용하지 않는 환경에서도 앱이 기동되도록 처리
    genai = None
    types = None


# =========================================================
# 기본 설정
# =========================================================
APP_TITLE = "중학교 독서 포트폴리오"
APP_SUBTITLE = "15~17차시 한 학기 독서 누적 기록 & 수행평가 관리 시스템"

# Google Sheet 주소는 코드에 고정합니다.
# 서비스 계정 인증정보(private_key 등)만 secrets.toml에 보관하세요.
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
    "Schedules": ["학반", "차시", "작성일"],
}

DEFAULT_TOTAL_SESSIONS = 16
MIN_SESSIONS = 15
MAX_SESSIONS = 17

DEMO_ACCOUNTS = [
    {"학번": "20315", "이름": "김예시", "PIN": "1111"},
    {"학번": "20507", "이름": "이참관", "PIN": "2222"},
]

GEMINI_DEFAULT_MODEL = "gemini-3.8-flash"
KST = ZoneInfo("Asia/Seoul")

OCR_SCHEMA = {
    "type": "object",
    "properties": {
        "book_title": {"type": "string"},
        "author": {"type": "string"},
        "page_range": {"type": "string"},
        "summary": {"type": "string"},
        "quote": {"type": "string"},
        "question": {"type": "string"},
        "answer": {"type": "string"},
        "thoughts": {"type": "string"},
    },
    "required": [
        "book_title",
        "author",
        "page_range",
        "summary",
        "quote",
        "question",
        "answer",
        "thoughts",
    ],
}


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


def get_connection() -> GSheetsConnection:
    conn = st.connection("gsheets", type=GSheetsConnection)
    # GSheetsConnection은 인증정보를 secrets에서 읽되, 실제 Spreadsheet 주소는
    # 코드에서 기본값으로 지정할 수 있습니다.
    conn.set_default(GOOGLE_SHEET_URL)
    return conn


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
    return datetime.now(KST).strftime("%Y-%m-%d %H:%M")


def today_kst() -> date:
    return datetime.now(KST).date()


def student_to_class_code(student_id: str) -> str:
    """20315 -> 2-03 (2학년 3반)."""
    sid = normalize_student_id(student_id)
    if len(sid) == 5 and sid[0].isdigit() and sid[1:3].isdigit():
        return f"{sid[0]}-{int(sid[1:3]):02d}"
    return ""


def format_class_code(class_code: str) -> str:
    if "-" in class_code:
        grade, cls = class_code.split("-", 1)
        return f"{grade}학년 {int(cls)}반"
    return class_code


def get_gemini_api_key() -> str:
    try:
        value = st.secrets.get("gemini_api_key", "")
        if value:
            return normalize_text(value)
    except Exception:
        pass

    try:
        gemini_secrets = st.secrets.get("gemini", {})
        if isinstance(gemini_secrets, dict):
            return normalize_text(gemini_secrets.get("api_key", ""))
    except Exception:
        pass
    return ""


def get_gemini_model() -> str:
    try:
        gemini_secrets = st.secrets.get("gemini", {})
        if isinstance(gemini_secrets, dict):
            return normalize_text(
                gemini_secrets.get("model", GEMINI_DEFAULT_MODEL)
            ) or GEMINI_DEFAULT_MODEL
    except Exception:
        pass
    return GEMINI_DEFAULT_MODEL


def get_app_secret(name: str, default: Any = None) -> Any:
    """
    App 설정을 최대한 폭넓게 읽는다.

    우선순위:
    1) [app] 섹션
    2) 최상위 teacher_password / enable_demo_accounts
    3) [connections.gsheets] 안에 잘못 넣은 경우도 호환
       (향후에는 [app] 사용을 권장)
    """
    # 1. [app]
    try:
        app_secrets = st.secrets["app"]
        try:
            value = app_secrets[name]
            if value is not None and normalize_text(value) != "":
                return value
        except (KeyError, TypeError):
            pass
    except Exception:
        pass

    # 2. top-level
    try:
        value = st.secrets[name]
        if value is not None and normalize_text(value) != "":
            return value
    except (KeyError, TypeError):
        pass
    except Exception:
        pass

    # 3. [connections.gsheets] (호환용)
    try:
        gsheets = st.secrets["connections"]["gsheets"]
        try:
            value = gsheets[name]
            if value is not None and normalize_text(value) != "":
                return value
        except (KeyError, TypeError):
            pass
    except Exception:
        pass

    return default


def get_teacher_password() -> str:
    value = get_app_secret("teacher_password", "")
    return normalize_text(value)


def demo_enabled() -> bool:
    value = get_app_secret("enable_demo_accounts", True)
    if isinstance(value, bool):
        return value
    return normalize_text(value).lower() in {"1", "true", "yes", "on"}


# =========================================================
# Google Sheets 데이터 계층
# =========================================================
def make_empty_df(columns: Iterable[str]) -> pd.DataFrame:
    return pd.DataFrame(columns=list(columns))


@st.cache_data(ttl=60, show_spinner=False)
def read_sheet(worksheet: str) -> pd.DataFrame:
    """Google Sheet 데이터를 60초 동안 캐시합니다.

    학생 화면은 한 번의 rerun에서 여러 탭의 코드를 모두 실행할 수 있기 때문에
    매번 Google API를 호출하면 로딩이 매우 느려집니다. 저장/수정 후에는
    st.cache_data.clear()로 캐시를 비워 최신 데이터가 바로 반영되게 합니다.
    """
    if worksheet not in SHEET_CONFIG:
        raise ValueError(f"지원하지 않는 worksheet: {worksheet}")

    conn = get_connection()
    try:
        df = conn.read(worksheet=worksheet, ttl=60, evaluate_formulas=False)
    except Exception as error:
        raise RuntimeError(
            f"Google Sheets의 '{worksheet}' 탭을 읽을 수 없습니다. "
            "서비스 계정 인증([connections.gsheets]), Google Sheet 공유(Editor), "
            "worksheet 이름을 확인하세요. "
            f"원본 오류: {error}"
        ) from error
    if df is None:
        return make_empty_df(SHEET_CONFIG[worksheet])

    df = df.copy()
    expected = SHEET_CONFIG[worksheet]
    for col in expected:
        if col not in df.columns:
            df[col] = ""
    return df[expected]

def update_sheet(worksheet: str, df: pd.DataFrame) -> None:
    conn = get_connection()
    expected = SHEET_CONFIG[worksheet]
    output = df.copy()

    for col in expected:
        if col not in output.columns:
            output[col] = ""

    output = output[expected]
    conn.update(worksheet=worksheet, data=output)
    st.cache_data.clear()


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
# 학반별 작성일 / Gemini OCR
# =========================================================
def ensure_schedule_sheet() -> None:
    """교사가 일정 설정 메뉴를 열었을 때만 Schedules 탭을 필요 시 생성합니다."""
    conn = get_connection()
    try:
        conn.read(worksheet="Schedules", ttl=1, nrows=1)
    except Exception:
        conn.create(
            worksheet="Schedules",
            data=make_empty_df(SHEET_CONFIG["Schedules"]),
        )


def get_schedules(class_code: Optional[str] = None) -> pd.DataFrame:
    try:
        df = read_sheet("Schedules").copy()
    except Exception:
        return make_empty_df(SHEET_CONFIG["Schedules"])

    if df.empty:
        return df

    df["학반"] = df["학반"].map(normalize_text)
    df["차시"] = df["차시"].map(safe_int)
    df["작성일"] = df["작성일"].map(normalize_text)

    if class_code:
        df = df[df["학반"] == class_code].copy()
    return df


def get_allowed_date(class_code: str, session_no: int) -> Optional[date]:
    schedules = get_schedules(class_code)
    if schedules.empty:
        return None

    rows = schedules[schedules["차시"] == int(session_no)]
    if rows.empty:
        return None

    raw = normalize_text(rows.iloc[-1]["작성일"])
    if not raw:
        return None

    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def class_schedule_map(class_code: str, total_sessions: int) -> Dict[int, Optional[date]]:
    return {
        session_no: get_allowed_date(class_code, session_no)
        for session_no in range(1, total_sessions + 1)
    }


def render_schedule_summary(class_code: str, total_sessions: int) -> None:
    mapping = class_schedule_map(class_code, total_sessions)
    rows = []
    for session_no in range(1, total_sessions + 1):
        scheduled = mapping.get(session_no)
        rows.append(
            {
                "차시": f"{session_no}차시",
                "작성 가능일": scheduled.strftime("%Y-%m-%d") if scheduled else "미지정",
                "상태": "📅 지정" if scheduled else "🔒 잠금",
            }
        )
    st.dataframe(
        pd.DataFrame(rows),
        use_container_width=True,
        hide_index=True,
    )


def extract_page_range(page_range: str) -> tuple[int, int] | None:
    match = re.fullmatch(
        r"\s*(\d+)\s*[~\-–—]\s*(\d+)\s*p?\s*",
        normalize_text(page_range),
        re.IGNORECASE,
    )
    if not match:
        return None

    start_page = int(match.group(1))
    end_page = int(match.group(2))
    if start_page < 1 or end_page < start_page:
        return None
    return start_page, end_page


def run_gemini_ocr(image_bytes: bytes, mime_type: str) -> Dict[str, str]:
    """
    Gemini 멀티모달 모델로 종이 독서활동지의 손글씨/인쇄 문항을 읽어
    앱 입력 필드에 대응되는 JSON으로 추출합니다.
    """
    if genai is None or types is None:
        raise RuntimeError(
            "google-genai 패키지가 설치되어 있지 않습니다. requirements.txt를 확인하세요."
        )

    api_key = get_gemini_api_key()
    if not api_key:
        raise RuntimeError(
            "Gemini API 키가 없습니다. Streamlit Secrets에 "
            "[gemini] api_key를 설정하세요."
        )

    if len(image_bytes) > 18 * 1024 * 1024:
        raise RuntimeError("사진 파일이 너무 큽니다. 18MB 이하의 JPG/PNG 사진을 사용하세요.")

    client = genai.Client(api_key=api_key)
    prompt = """
당신은 중학교 독서활동지 OCR 도우미입니다.
첨부된 종이 독서활동지 사진에서 학생이 실제로 작성한 내용을 읽어
아래 JSON 필드에 정확히 옮겨 적으세요.

중요 규칙:
1. 학생의 글을 요약하거나 새로 작성하지 말고, 읽을 수 있는 범위에서 가능한 한 원문 그대로 전사하세요.
2. 손글씨가 불명확하면 추측하지 말고 해당 필드를 빈 문자열로 두세요.
3. 인쇄된 안내문/문항 제목은 결과에 포함하지 마세요.
4. 책 제목, 작가, 페이지 범위도 학생이 적은 값을 그대로 전사하세요.
5. 페이지 범위는 예: "12~35p"처럼 문자열로 반환하세요.
6. 결과는 반드시 지정한 JSON 스키마에 맞춰 반환하세요.
"""
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")

    response = client.models.generate_content(
        model=get_gemini_model(),
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
            prompt,
        ],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=OCR_SCHEMA,
            temperature=0,
        ),
    )

    raw = getattr(response, "text", None)
    if not raw:
        raise RuntimeError("Gemini에서 OCR 결과를 받지 못했습니다.")

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as error:
        raise RuntimeError("Gemini OCR 결과를 JSON으로 해석하지 못했습니다.") from error

    return {
        "book_title": normalize_text(parsed.get("book_title", "")),
        "author": normalize_text(parsed.get("author", "")),
        "page_range": normalize_text(parsed.get("page_range", "")),
        "summary": normalize_text(parsed.get("summary", "")),
        "quote": normalize_text(parsed.get("quote", "")),
        "question": normalize_text(parsed.get("question", "")),
        "answer": normalize_text(parsed.get("answer", "")),
        "thoughts": normalize_text(parsed.get("thoughts", "")),
    }


def render_ocr_panel(
    student_id: str,
    selected_session: int,
) -> None:
    st.markdown("### ✨ 종이 활동지 자동 입력 (Gemini OCR)")
    st.caption(
        "종이에 직접 작성한 독서활동지를 사진으로 찍어 올리면 "
        "Gemini가 책 제목·페이지·요약·질문·느낀점을 읽어 입력칸에 넣어 줍니다. "
        "AI가 읽은 결과는 반드시 확인·수정한 뒤 저장하세요."
    )
    st.info(
        "주의: 사진은 Gemini API로 전송됩니다. 학생 이름·연락처 등 불필요한 개인정보가 "
        "사진에 함께 들어가지 않도록 주의하세요."
    )

    upload_col, camera_col = st.columns(2)
    with upload_col:
        uploaded = st.file_uploader(
            "활동지 사진 업로드",
            type=["jpg", "jpeg", "png", "webp"],
            key=f"ocr_upload_{student_id}_{selected_session}",
        )
    with camera_col:
        camera_image = st.camera_input(
            "또는 카메라로 촬영",
            key=f"ocr_camera_{student_id}_{selected_session}",
        )

    image_file = camera_image or uploaded

    if image_file is None:
        return

    st.image(image_file, caption="OCR에 사용할 활동지", use_container_width=True)

    if st.button(
        "Gemini로 읽어서 입력칸 채우기 ✨",
        use_container_width=True,
        key=f"ocr_button_{student_id}_{selected_session}",
    ):
        try:
            with st.spinner("활동지의 글씨를 읽는 중입니다…"):
                result = run_gemini_ocr(
                    image_file.getvalue(),
                    image_file.type or "image/jpeg",
                )
            st.session_state["ocr_result"] = result
            st.session_state["ocr_session"] = selected_session
            st.success("OCR이 완료되었습니다. 아래 입력칸의 내용을 확인해 주세요.")
            st.rerun()
        except Exception as error:
            st.error(f"Gemini OCR 처리 중 오류가 발생했습니다: {error}")


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


def get_student_books_cached(student_id: str) -> pd.DataFrame:
    cached = st.session_state.get("student_books_cache")
    cached_sid = st.session_state.get("student_books_cache_sid")
    if cached is not None and cached_sid == student_id:
        return cached.copy()
    df = get_books(student_id)
    st.session_state["student_books_cache"] = df.copy()
    st.session_state["student_books_cache_sid"] = student_id
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


def parse_reflection(raw: Any) -> Dict[str, str]:
    """기존 Logs의 한 칸짜리 요약및느낀점을 5개 항목으로 복원합니다."""
    text = normalize_text(raw)
    result = {
        "book_title": "",
        "author": "",
        "summary": "",
        "quote": "",
        "question": "",
        "answer": "",
        "thoughts": "",
    }
    if not text:
        return result

    labels = {
        "[도서명]": "book_title",
        "[저자]": "author",
        "[오늘 읽은 내용 짧은 요약]": "summary",
        "[가장 인상 깊은 문장과 이유]": "quote",
        "[나의 질문]": "question",
        "[질문에 대한 나의 생각/답변]": "answer",
        "[나의 생각과 느낌]": "thoughts",
    }

    current_key = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped in labels:
            current_key = labels[stripped]
            continue
        if current_key:
            if result[current_key]:
                result[current_key] += "\n" + line
            else:
                result[current_key] = line

    # 이전 버전에서 저장된 자유 형식 텍스트는 요약으로 보여 줍니다.
    if not any(result.values()):
        result["summary"] = text

    return result


def build_reflection(
    book_title: str,
    author: str,
    summary: str,
    quote: str,
    question: str,
    answer: str,
    thoughts: str,
) -> str:
    """Logs의 기존 '요약및느낀점' 한 칸에 구조화된 내용을 저장합니다."""
    sections = [
        ("[도서명]", book_title.strip()),
        ("[저자]", author.strip()),
        ("[오늘 읽은 내용 짧은 요약]", summary.strip()),
        ("[가장 인상 깊은 문장과 이유]", quote.strip()),
        ("[나의 질문]", question.strip()),
        ("[질문에 대한 나의 생각/답변]", answer.strip()),
        ("[나의 생각과 느낌]", thoughts.strip()),
    ]
    return "\n\n".join(
        f"{label}\n{value}" for label, value in sections if value
    )


def reflection_html(raw: Any) -> str:
    """교사 화면에서 구조화된 독서 기록을 보기 좋게 렌더링합니다."""
    data = parse_reflection(raw)
    labels = [
        ("오늘 읽은 내용 짧은 요약", "summary"),
        ("가장 인상 깊은 문장과 이유", "quote"),
        ("나의 질문", "question"),
        ("질문에 대한 나의 생각/답변", "answer"),
        ("나의 생각과 느낌", "thoughts"),
    ]
    chunks = []
    for title, key in labels:
        value = data.get(key, "").strip()
        if value:
            safe = value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
            chunks.append(
                f'<div style="margin-bottom:.9rem;">'
                f'<div style="font-weight:800;color:#4834D4;margin-bottom:.25rem;">{title}</div>'
                f'<div>{safe}</div></div>'
            )
    return "".join(chunks) if chunks else '<div class="help-text">작성 내용 없음</div>'


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

    # 예시 계정은 Google Sheets 조회 없이 즉시 로그인합니다.
    if demo_enabled():
        for demo in DEMO_ACCOUNTS:
            if (demo["학번"] == student_id and demo["이름"] == name and demo["PIN"] == pin):
                st.session_state.update({
                    "role": "student",
                    "student_id": student_id,
                    "student_name": name,
                    "page": "student",
                    "student_section": "선택 도서 등록",
                    "student_books_cache": None,
                })
                return True

    # 실제 학생 로그인 시점에만 Students를 조회합니다.
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


def render_student_profile(student_id: str, student_name: str) -> None:
    class_code = student_to_class_code(student_id)
    class_text = format_class_code(class_code) if class_code else "학반 미확인"
    st.markdown(
        f"""
        <div class="profile-card">
            <div class="profile-name">👋 {student_name} 학생</div>
            <div class="profile-sub">학번 {student_id} · {class_text} · 중학교 독서 포트폴리오</div>
            <div class="profile-sub" style="margin-top:.35rem;">차시별 작성 가능일은 학반별로 교사가 지정합니다.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_books_tab(student_id: str) -> None:
    st.markdown('<div class="section-title">이번 학기 선택 도서</div>', unsafe_allow_html=True)
    st.caption("최대 2권까지 등록할 수 있습니다. 같은 도서는 도서 1 또는 도서 2로 수정할 수 있습니다.")

    books = get_student_books_cached(student_id)
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
            st.session_state["student_books_cache"] = None
            st.session_state["student_books_cache_sid"] = None
            st.cache_data.clear()
            st.success(f"도서 {book_no}가 저장되었습니다.")
            st.rerun()


def render_log_readonly(row: Optional[pd.Series]) -> None:
    if row is None:
        st.info("아직 이 차시의 기록이 없습니다.")
        return

    reflection = parse_reflection(row["요약및느낀점"])
    st.markdown(
        f"""
        <div class="card">
            <div class="section-title">기록된 내용</div>
            <div><b>책 제목:</b> {normalize_text(reflection.get("book_title", ""))}</div>
            <div><b>작가:</b> {normalize_text(reflection.get("author", ""))}</div>
            <div><b>페이지:</b> {safe_int(row["시작페이지"])}~{safe_int(row["끝페이지"])}p</div>
            <div><b>독서 시간:</b> {safe_int(row["독서시간(분)"])}분</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="card" style="margin-top:.7rem;">{reflection_html(row["요약및느낀점"])}</div>',
        unsafe_allow_html=True,
    )


def render_log_tab(student_id: str, total_sessions: int) -> None:
    st.markdown('<div class="section-title">차시별 독서 누가기록</div>', unsafe_allow_html=True)

    books = get_student_books_cached(student_id)
    if books.empty:
        st.warning("먼저 '선택 도서 등록'에서 이번 학기 책을 등록해 주세요.")
        return

    class_code = student_to_class_code(student_id)
    if not class_code:
        st.error("학번에서 학반 정보를 확인할 수 없습니다.")
        return

    schedule_map = class_schedule_map(class_code, total_sessions)
    logs = get_logs(student_id)
    existing_by_session = {}
    if not logs.empty:
        for _, row in logs.iterrows():
            existing_by_session[safe_int(row["차시"])] = row

    def session_label(session_no: int) -> str:
        allowed = schedule_map.get(session_no)
        existing = existing_by_session.get(session_no)
        if allowed:
            if allowed == today_kst():
                state = "🟢 오늘 작성 가능"
            elif allowed > today_kst():
                state = f"🟡 {allowed.strftime('%m/%d')} 예정"
            else:
                state = f"🔒 {allowed.strftime('%m/%d')} 종료"
        else:
            state = "⚪ 날짜 미지정"
        if existing is not None:
            state += " · 기록 있음"
        return f"{session_no}차시 · {state}"

    today_sessions = [
        s for s in range(1, total_sessions + 1)
        if schedule_map.get(s) == today_kst()
    ]
    default_index = (
        today_sessions[0] - 1
        if today_sessions
        else 0
    )

    selected_session = st.selectbox(
        "작성할 차시",
        list(range(1, total_sessions + 1)),
        index=default_index,
        format_func=session_label,
        key="log_session_selector",
    )

    allowed_date = schedule_map.get(selected_session)
    row = existing_by_session.get(selected_session)

    if allowed_date is None:
        st.error(
            f"{class_code}반의 {selected_session}차시 작성일이 아직 지정되지 않았습니다. "
            "교사가 작성 가능일을 먼저 설정해야 합니다."
        )
        render_log_readonly(row)
        return

    if allowed_date != today_kst():
        if allowed_date > today_kst():
            st.warning(
                f"{selected_session}차시는 **{allowed_date.strftime('%Y년 %m월 %d일')}**에만 작성·수정할 수 있습니다. "
                "오늘은 아직 작성할 수 없습니다."
            )
        else:
            st.warning(
                f"{selected_session}차시의 작성일은 **{allowed_date.strftime('%Y년 %m월 %d일')}**이었습니다. "
                "작성·수정은 잠금 상태입니다."
            )
        render_log_readonly(row)
        return

    if row is not None:
        st.info(
            f"{selected_session}차시는 오늘이 작성 가능일입니다. "
            "기존 기록을 불러와 수정할 수 있습니다."
        )

    # 오늘 작성 가능한 차시에서만 OCR과 입력폼을 노출합니다.
    ocr_state = st.session_state.get("ocr_result")
    ocr_session = st.session_state.get("ocr_session")
    if ocr_session != selected_session:
        ocr_state = None

    render_ocr_panel(student_id, selected_session)

    # OCR 결과가 방금 생성된 경우 새로 만든 결과를 사용합니다.
    ocr_state = st.session_state.get("ocr_result") if st.session_state.get("ocr_session") == selected_session else None

    reflection = parse_reflection(row["요약및느낀점"]) if row is not None else {}

    book_records = books.sort_values("도서번호").to_dict("records")
    if len(book_records) == 1:
        selected_book = book_records[0]
    else:
        book_labels = [
            f"도서 {safe_int(b['도서번호'])} · {normalize_text(b['도서명'])} — {normalize_text(b['저자'])}"
            for b in book_records
        ]
        selected_book_index = st.selectbox(
            "이번 기록의 도서",
            list(range(len(book_records))),
            format_func=lambda i: book_labels[i],
            key=f"log_book_selector_{student_id}_{selected_session}",
        )
        selected_book = book_records[selected_book_index]

    default_title = (
        (ocr_state or {}).get("book_title")
        or reflection.get("book_title")
        or normalize_text(selected_book["도서명"])
    )
    default_author = (
        (ocr_state or {}).get("author")
        or reflection.get("author")
        or normalize_text(selected_book["저자"])
    )

    if ocr_state and not row:
        st.success("✨ Gemini OCR 결과가 입력칸에 반영되었습니다. 내용을 검토한 후 저장하세요.")

    with st.form(f"reading_log_form_{student_id}_{selected_session}"):
        c1, c2 = st.columns(2)
        with c1:
            book_title = st.text_input(
                "책 제목 *",
                value=default_title,
                placeholder="예: 아몬드",
                key=f"log_title_{student_id}_{selected_session}",
            )
        with c2:
            c_start = safe_int(row["시작페이지"], 1) if row is not None else 1
            c_end = safe_int(row["끝페이지"], 1) if row is not None else 1
            default_page_range = (
                (ocr_state or {}).get("page_range")
                or (f"{c_start}~{c_end}p" if row is not None else "")
            )
            page_range = st.text_input(
                "오늘 읽은 페이지 범위 (예: 12~35p) *",
                value=default_page_range,
                placeholder="예: 12~35p",
                key=f"log_range_{student_id}_{selected_session}",
            )

        author = st.text_input(
            "작가 이름 *",
            value=default_author,
            placeholder="예: 손원평",
            key=f"log_author_{student_id}_{selected_session}",
        )

        st.markdown("### 1. 오늘 읽은 내용 짧은 요약 (핵심 줄거리) *")
        summary = st.text_area(
            "요약",
            value=(ocr_state or {}).get("summary") or reflection.get("summary", ""),
            height=120,
            placeholder="오늘 읽은 부분에서 어떤 일이 있었는지 핵심 내용만 짧게 정리해 보세요.",
            label_visibility="collapsed",
            key=f"log_summary_{student_id}_{selected_session}",
        )

        st.markdown("### 2. 가장 인상 깊은 문장과 이유")
        quote = st.text_area(
            "인상 깊은 문장과 이유",
            value=(ocr_state or {}).get("quote") or reflection.get("quote", ""),
            height=105,
            placeholder="기억에 남은 문장이나 장면을 적고, 왜 인상 깊었는지 써 보세요.",
            label_visibility="collapsed",
            key=f"log_quote_{student_id}_{selected_session}",
        )

        st.markdown("### 3. 읽은 내용을 바탕으로 만든 질문과 답변")
        q1, q2 = st.columns(2)
        with q1:
            st.markdown("**3-1. 나의 질문**")
            question = st.text_area(
                "나의 질문",
                value=(ocr_state or {}).get("question") or reflection.get("question", ""),
                height=110,
                placeholder="예: 주인공은 왜 그런 선택을 했을까?",
                label_visibility="collapsed",
                key=f"log_question_{student_id}_{selected_session}",
            )
        with q2:
            st.markdown("**3-2. 질문에 대한 나의 생각/답변**")
            answer = st.text_area(
                "질문에 대한 나의 생각/답변",
                value=(ocr_state or {}).get("answer") or reflection.get("answer", ""),
                height=110,
                placeholder="예: 자신이 중요하게 생각하는 가치를 지키기 위해서였을 것이다.",
                label_visibility="collapsed",
                key=f"log_answer_{student_id}_{selected_session}",
            )

        st.markdown("### 4. 나의 생각과 느낌 (느낀점/깨달은점) *")
        thoughts = st.text_area(
            "나의 생각과 느낌",
            value=(ocr_state or {}).get("thoughts") or reflection.get("thoughts", ""),
            height=140,
            placeholder="책을 읽고 새롭게 생각하게 된 점, 느낀 점, 깨달은 점 등을 자유롭게 써 보세요.",
            label_visibility="collapsed",
            key=f"log_thoughts_{student_id}_{selected_session}",
        )

        st.markdown("###")
        st.info(
            f"오늘의 작성 가능일: **{allowed_date.strftime('%Y-%m-%d')}** · "
            "날짜는 교사가 지정한 날로 자동 기록됩니다."
        )

        minutes = st.number_input(
            "독서 시간(분)",
            min_value=0,
            max_value=1440,
            value=max(0, safe_int(row["독서시간(분)"])) if row is not None else 0,
            step=5,
            key=f"log_minutes_{student_id}_{selected_session}",
        )

        submitted = st.form_submit_button(
            "독서 기록 저장하기",
            use_container_width=True,
        )

    if submitted:
        # UI 잠금과 별개로 서버측에서도 작성 가능일을 재검증합니다.
        if allowed_date != today_kst():
            st.error("오늘은 이 차시의 기록 작성/수정 가능일이 아닙니다.")
            return

        page_pair = extract_page_range(page_range)
        if not page_pair:
            st.error("페이지 범위를 `12~35p`와 같은 형식으로 입력해 주세요.")
            return

        start_page, end_page = page_pair
        if not book_title.strip() or not author.strip():
            st.error("책 제목과 작가 이름을 입력해 주세요.")
            return
        if not summary.strip():
            st.error("1번 '오늘 읽은 내용 짧은 요약'을 작성해 주세요.")
            return
        if not thoughts.strip():
            st.error("4번 '나의 생각과 느낌'을 작성해 주세요.")
            return

        pages_read = int(end_page - start_page + 1)
        structured_text = build_reflection(
            book_title,
            author,
            summary,
            quote,
            question,
            answer,
            thoughts,
        )

        upsert_row(
            "Logs",
            {
                "학번": student_id,
                "차시": selected_session,
                "날짜": allowed_date.strftime("%Y-%m-%d"),
                "시작페이지": start_page,
                "끝페이지": end_page,
                "읽은페이지수": pages_read,
                "독서시간(분)": int(minutes),
                "요약및느낀점": structured_text,
            },
            ["학번", "차시"],
        )
        st.session_state["ocr_result"] = None
        st.session_state["ocr_session"] = None
        st.success(
            f"{selected_session}차시 기록이 저장되었습니다. 읽은 페이지 {pages_read}쪽"
        )
        st.rerun()

    st.markdown("### 차시 진행 상태")
    rows = []
    for session_no in range(1, total_sessions + 1):
        allowed = schedule_map.get(session_no)
        existing = existing_by_session.get(session_no)
        status = "미지정"
        if allowed:
            if allowed == today_kst():
                status = "🟢 오늘 작성 가능"
            elif allowed > today_kst():
                status = f"🟡 {allowed.strftime('%m/%d')} 예정"
            else:
                status = "🔒 작성 종료"
        rows.append(
            {
                "차시": f"{session_no}차시",
                "작성 가능일": allowed.strftime("%Y-%m-%d") if allowed else "미지정",
                "상태": status,
                "기록": "✅ 작성됨" if existing is not None else "⬜ 미작성",
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
    student_id = st.session_state.student_id
    student_name = st.session_state.student_name

    render_student_profile(student_id, student_name)

    _, top_right = st.columns([6, 1])
    with top_right:
        if st.button("로그아웃", use_container_width=True):
            logout()

    sections = [
        "선택 도서 등록",
        "차시별 독서 누가기록",
        "독서 통계 그래프",
        "수행평가 채점 결과 확인",
    ]
    current = st.session_state.get("student_section", sections[0])
    if current not in sections:
        current = sections[0]

    selected = st.radio(
        "학생 메뉴",
        sections,
        index=sections.index(current),
        horizontal=True,
        key="student_section_radio",
    )
    st.session_state["student_section"] = selected

    # 선택한 메뉴만 실행합니다. st.tabs()와 달리 다른 탭의 Google API 조회가
    # 페이지 로드 때 동시에 실행되지 않습니다.
    if selected == "선택 도서 등록":
        render_books_tab(student_id)
    elif selected == "차시별 독서 누가기록":
        total_sessions = get_total_sessions()
        render_log_tab(student_id, total_sessions)
    elif selected == "독서 통계 그래프":
        total_sessions = get_total_sessions()
        render_stats_tab(student_id, total_sessions)
    else:
        total_sessions = get_total_sessions()
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
                "Streamlit Cloud의 Secrets에 teacher_password가 없습니다. "
                "[app] 아래 teacher_password = \"1234\"를 넣거나, "
                "최상위에 teacher_password = \"1234\"를 넣어 주세요."
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

    st.markdown("###")
    st.markdown('<div class="section-title">📅 학반별 차시 작성 날짜 설정</div>', unsafe_allow_html=True)
    st.caption(
        "학생은 자기 학반에 설정된 날짜와 오늘 날짜가 일치할 때만 해당 차시를 작성하거나 수정할 수 있습니다. "
        "미래 날짜·지난 날짜·미지정 차시는 잠금됩니다."
    )

    try:
        ensure_schedule_sheet()
    except Exception as error:
        st.error(
            "Schedules 탭을 생성하지 못했습니다. 서비스 계정이 해당 Google Sheet에 "
            "편집자(Editor) 권한인지 확인하세요."
        )
        st.code(str(error))
        return

    g1, g2 = st.columns(2)
    with g1:
        grade = st.selectbox("학년", [1, 2, 3], index=1, key="schedule_grade")
    with g2:
        class_no = st.selectbox("반", list(range(1, 13)), index=2, key="schedule_class")

    class_code = f"{grade}-{class_no:02d}"
    st.info(f"현재 설정 대상: **{format_class_code(class_code)}**")

    schedules = get_schedules(class_code)
    existing_map: Dict[int, date] = {}
    if not schedules.empty:
        for _, row in schedules.iterrows():
            d = normalize_text(row["작성일"])
            try:
                parsed = datetime.strptime(d, "%Y-%m-%d").date()
                existing_map[safe_int(row["차시"])] = parsed
            except ValueError:
                pass

    with st.form(f"schedule_form_{class_code}_{current}"):
        schedule_rows = []
        for session_no in range(1, current + 1):
            c1, c2 = st.columns([1, 2])
            existing_date = existing_map.get(session_no)
            with c1:
                enabled = st.checkbox(
                    f"{session_no}차시 지정",
                    value=existing_date is not None,
                    key=f"schedule_enabled_{class_code}_{session_no}",
                )
            with c2:
                selected_date = st.date_input(
                    f"{session_no}차시 작성일",
                    value=existing_date or today_kst(),
                    disabled=not enabled,
                    key=f"schedule_date_{class_code}_{session_no}",
                )
            schedule_rows.append((session_no, enabled, selected_date))

        submitted = st.form_submit_button(
            f"{format_class_code(class_code)} 작성 날짜 저장",
            use_container_width=True,
        )

    if submitted:
        all_schedules = get_schedules()
        if not all_schedules.empty:
            all_schedules = all_schedules[
                all_schedules["학반"] != class_code
            ].copy()

        new_rows = []
        for session_no, enabled, selected_date in schedule_rows:
            if enabled:
                new_rows.append(
                    {
                        "학반": class_code,
                        "차시": session_no,
                        "작성일": selected_date.strftime("%Y-%m-%d"),
                    }
                )

        if new_rows:
            all_schedules = pd.concat(
                [all_schedules, pd.DataFrame(new_rows)],
                ignore_index=True,
            )

        update_sheet("Schedules", all_schedules)
        st.success(f"{format_class_code(class_code)}의 차시 작성 날짜가 저장되었습니다.")
        st.rerun()

    st.markdown("### 현재 설정 요약")
    render_schedule_summary(class_code, current)



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
        for _, log_row in logs.sort_values("차시").iterrows():
            session_no = safe_int(log_row["차시"])
            title = parse_reflection(log_row["요약및느낀점"]).get("book_title", "")
            with st.expander(
                f"{session_no}차시 · {normalize_text(log_row['날짜'])} · "
                f"{safe_int(log_row['시작페이지'])}~{safe_int(log_row['끝페이지'])}p · "
                f"{safe_int(log_row['읽은페이지수'])}쪽 · {safe_int(log_row['독서시간(분)'])}분"
            ):
                if title:
                    author = parse_reflection(log_row["요약및느낀점"]).get("author", "")
                    st.markdown(f"**책 제목:** {title}  \n**작가:** {author}")
                st.markdown(
                    f'<div class="card">{reflection_html(log_row["요약및느낀점"])}</div>',
                    unsafe_allow_html=True,
                )

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
    render_hero()

    header_left, header_right = st.columns([6, 1])
    with header_left:
        st.markdown(
            """
            <div class="card">
                <div class="section-title">교사 관리 콘솔</div>
                <div class="help-text">필요한 메뉴의 데이터만 Google Sheets에서 불러옵니다.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with header_right:
        if st.button("로그아웃", use_container_width=True):
            logout()

    sections = ["학기·작성일 설정", "학생 목록", "누가기록·채점"]
    current = st.session_state.get("teacher_section", sections[0])
    if current not in sections:
        current = sections[0]

    selected = st.radio(
        "교사 메뉴",
        sections,
        index=sections.index(current),
        horizontal=True,
        key="teacher_section_radio",
    )
    st.session_state["teacher_section"] = selected

    if selected == "학기·작성일 설정":
        render_teacher_settings()
        return

    total_sessions = get_total_sessions()

    if selected == "학생 목록":
        selected_id = render_teacher_student_list(total_sessions)
        if selected_id:
            st.session_state["teacher_selected_student"] = selected_id
        return

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

    # 연결은 실제로 데이터가 필요할 때 지연해서 읽습니다.
    # 앱 시작 시 5개 worksheet를 전부 읽지 않아 초기 로딩을 줄입니다.

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
