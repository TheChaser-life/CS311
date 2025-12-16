"""
FastAPI Backend for AI Resume Analyzer.
Đảm nhiệm việc kết nối React frontend với tầng AI agent và Redis session store.
"""

import os
import sys
import tempfile
import base64
import json
from typing import Optional
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
import redis
from redis.exceptions import RedisError

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# --- Redis cấu hình & session store ---
# Ưu tiên REDIS_URL nếu tồn tại; fallback sang host/port rời rạc.
REDIS_URL = os.getenv("REDIS_URL","redis://127.0.0.1:6379/0")
REDIS_HOST = os.getenv("REDIS_HOST", "127.0.0.1") # tên host/IP Redis nội bộ, khi deploy cần override để trỏ đúng container/máy
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379")) # port Redis nội bộ, khi deploy cần override để trỏ đúng container/máy
REDIS_DB = int(os.getenv("REDIS_DB", "0")) # database Redis nội bộ, khi deploy cần override để trỏ đúng container/máy
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD") # password Redis nội bộ, khi deploy cần override để trỏ đúng container/máy
SESSION_KEY_PREFIX = os.getenv("SESSION_KEY_PREFIX", "resume:session:") # prefix Redis key nhất quán cho từng session ID.
SESSION_TTL_SECONDS = int(os.getenv("SESSION_TTL_SECONDS", "3600")) # TTL session (3600s = 1 giờ).

if REDIS_URL:
    # Kết nối theo URL (thường dùng cho dịch vụ managed như Upstash).
    redis_client = redis.Redis.from_url(
        REDIS_URL, decode_responses=True, health_check_interval=30
    )
else:
    # Kết nối thủ công tới Redis nội bộ / docker compose.
    redis_client = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=REDIS_DB,
        password=REDIS_PASSWORD,
        decode_responses=True,
        health_check_interval=30,
    )

try:
    # Kiểm tra kết nối ngay khi khởi động để fail fast nếu Redis không chạy.
    redis_client.ping()
except RedisError as exc:
    raise RuntimeError(f"Không thể kết nối Redis: {exc}") from exc


def _new_session_state() -> dict:
    """Khởi tạo template session mặc định cho mỗi người dùng."""
    return {"cv_text": "", "jd_text": "", "chat_history": []}


def _session_key(session_id: str) -> str:
    """Tạo Redis key nhất quán cho từng session ID."""
    return f"{SESSION_KEY_PREFIX}{session_id}"


def load_session_state(session_id: str) -> dict:
    """Đọc session từ Redis và đảm bảo luôn trả về cấu trúc hợp lệ."""
    try:
        raw = redis_client.get(_session_key(session_id))
    except RedisError as exc:
        raise HTTPException(status_code=500, detail="Session store unavailable") from exc

    if not raw:
        return _new_session_state()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return _new_session_state()

    if not isinstance(data, dict):
        return _new_session_state()

    session = _new_session_state()
    session.update({k: v for k, v in data.items() if k in session})

    if not isinstance(session["chat_history"], list):
        session["chat_history"] = []

    return session


def persist_session_state(session_id: str, session: dict) -> bool:
    """
    Ghi session về Redis với TTL.
    Đồng thời ép kiểu dữ liệu để tránh lỗi serialize khi agent trả kiểu lạ.
    """
    payload = {
        "cv_text": session.get("cv_text", "") or "",
        "jd_text": session.get("jd_text", "") or "",
        "chat_history": session.get("chat_history", []) or [],
    }

    if not isinstance(payload["chat_history"], list):
        payload["chat_history"] = []

    try:
        redis_client.setex(
            _session_key(session_id),
            SESSION_TTL_SECONDS,
            json.dumps(payload),
        )
        return True
    except RedisError as exc:
        print(f"[Redis] Failed to persist session {session_id}: {exc}")
        return False


def clear_session_state(session_id: str) -> None:
    """Xóa hẳn session khỏi Redis (dùng khi người dùng thoát hoặc yêu cầu)."""
    try:
        redis_client.delete(_session_key(session_id))
    except RedisError as exc:
        print(f"[Redis] Failed to clear session {session_id}: {exc}")

# --- Agent layer (LangChain + OpenAI) ---
# Import relative trước; fallback sang absolute khi chạy trực tiếp.
try:
    from agent_api import (
        analyze_cv_jd_api,
        find_suitable_jobs_api,
        chat_with_agent_api,
        suggest_cv_improvements_api,
        analyze_cv_layout_api,
        generate_improved_cv_api,
    )
except ImportError:
    from agent_api import (
    analyze_cv_jd_api, 
    find_suitable_jobs_api, 
    chat_with_agent_api,
    suggest_cv_improvements_api,
    analyze_cv_layout_api,
    generate_improved_cv_api
    )

# (Module phỏng vấn ảo đã bị loại khỏi frontend nên không include router nào ở đây.)


# Khởi tạo ứng dụng FastAPI chính.
app = FastAPI(
    title="AI Resume Analyzer API",
    description="API cho hệ thống phân tích CV và tìm việc làm",
    version="3.0"
)

# Cho phép frontend (Vite dev server, build, v.v.) gọi API mà không bị chặn CORS.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ========== MODELS ==========
# Pydantic schema phục vụ validate payload cho các endpoint JSON.
class TextInput(BaseModel):
    cv_text: Optional[str] = ""
    jd_text: Optional[str] = ""

class ChatInput(BaseModel):
    message: str

class AnalysisResponse(BaseModel):
    success: bool
    result: str
    score: Optional[float] = None

# ========== ENDPOINTS ==========

@app.get("/")
async def root():
    return {"message": "AI Resume Analyzer API v3.0", "status": "running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "openai_key": bool(os.getenv("OPENAI_API_KEY"))}


@app.post("/api/analyze")
async def analyze_cv_jd(
    cv_file: Optional[UploadFile] = File(None),
    jd_file: Optional[UploadFile] = File(None),
    cv_text: Optional[str] = Form(None),
    jd_text: Optional[str] = Form(None),
    session_id: str = Header(..., alias="X-Session-Id"),
):
    """Phân tích CV và JD."""
    session_storage = load_session_state(session_id)
    temp_files: list[str] = []
    try:
        cv_input = ""
        jd_input = ""
        cv_type = "text"
        jd_type = "text"
        
        # --- Đọc CV ---
        if cv_file and cv_file.filename:
            cv_type = "file"
            suffix = "." + cv_file.filename.split('.')[-1]
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                content = await cv_file.read()
                tmp.write(content)
                cv_input = tmp.name
                temp_files.append(tmp.name)
        elif cv_text:
            cv_input = cv_text
        else:
            raise HTTPException(status_code=400, detail="CV is required")
        
        # --- Đọc JD ---
        if jd_file and jd_file.filename:
            jd_type = "file"
            suffix = "." + jd_file.filename.split('.')[-1]
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                content = await jd_file.read()
                tmp.write(content)
                jd_input = tmp.name
                temp_files.append(tmp.name)
        elif jd_text:
            jd_input = jd_text
        else:
            raise HTTPException(status_code=400, detail="JD is required")
        
        # Lưu text trực tiếp ngay lập tức để đảm bảo session có dữ liệu.
        if cv_type == "text" and cv_input:
            session_storage["cv_text"] = cv_input
        if jd_type == "text" and jd_input:
            session_storage["jd_text"] = jd_input
        
        # Gọi tầng agent để thực hiện các bước phân tích.
        result = analyze_cv_jd_api(cv_input, jd_input, cv_type, jd_type, session_storage)
        response = {
            "success": True, 
            "result": result,
            "cv_stored": bool(session_storage.get("cv_text")),
            "jd_stored": bool(session_storage.get("jd_text"))
        }
        
    except Exception as e:
        response = {"success": False, "result": f"Error: {str(e)}"}
    finally:
        for f in temp_files:
            try:
                os.unlink(f)
            except Exception:
                pass

    if response.get("success"):
        if not persist_session_state(session_id, session_storage):
            response = {
                "success": False,
                "result": "Error: Unable to persist session data.",
            }
    else:
        # Vẫn cập nhật TTL cho session ngay cả khi thất bại để tránh timeout đột ngột.
        persist_session_state(session_id, session_storage)

    return response


@app.post("/api/find-jobs")
async def find_jobs(session_id: str = Header(..., alias="X-Session-Id")):
    """Tìm việc làm phù hợp với CV đã lưu."""
    session_storage = load_session_state(session_id)
    try:
        result = find_suitable_jobs_api(session_storage)
        response = {"success": True, "result": result}
    except Exception as e:
        response = {"success": False, "result": f"Error: {str(e)}"}

    if response.get("success"):
        if not persist_session_state(session_id, session_storage):
            response = {
                "success": False,
                "result": "Error: Unable to persist session data.",
            }
    else:
        persist_session_state(session_id, session_storage)

    return response


@app.post("/api/chat")
async def chat(
    input_data: ChatInput,
    session_id: str = Header(..., alias="X-Session-Id"),
):
    """Chat với AI Assistant."""
    session_storage = load_session_state(session_id)
    try:
        result = chat_with_agent_api(input_data.message, session_storage)
        response = {"success": True, "result": result}
    except Exception as e:
        response = {"success": False, "result": f"Error: {str(e)}"}

    if response.get("success"):
        if not persist_session_state(session_id, session_storage):
            response = {
                "success": False,
                "result": "Error: Unable to persist session data.",
            }
    else:
        persist_session_state(session_id, session_storage)

    return response


@app.post("/api/suggest-cv-improvements")
async def suggest_cv_improvements(
    session_id: str = Header(..., alias="X-Session-Id"),
):
    """Đề xuất chỉnh sửa CV."""
    session_storage = load_session_state(session_id)
    try:
        result = suggest_cv_improvements_api(session_storage)

        if not isinstance(result, dict):
            response_payload = {"success": True, "result": result}
        else:
            if not result.get("success"):
                response_payload = {
                    "success": False,
                    "result": result.get("output", "Unknown error"),
                }
            else:
                response_payload = {
                    "success": True,
                    "result": result.get("output", ""),
                }

                docx_bytes = result.get("docx_bytes")
                if docx_bytes:
                    response_payload["docx_file"] = base64.b64encode(docx_bytes).decode(
                        "utf-8"
                    )
                    response_payload["docx_filename"] = "optimized_cv.docx"

                if result.get("docx_warning"):
                    response_payload["warning"] = result["docx_warning"]

        response = response_payload
    except Exception as e:
        response = {"success": False, "result": f"Error: {str(e)}"}

    if response.get("success"):
        if not persist_session_state(session_id, session_storage):
            response = {
                "success": False,
                "result": "Error: Unable to persist session data.",
            }
    else:
        persist_session_state(session_id, session_storage)

    return response


@app.post("/api/analyze-cv-layout")
async def analyze_cv_layout(
    file: UploadFile = File(...),
    session_id: str = Header(..., alias="X-Session-Id"),
):
    """Phân tích layout CV từ file ảnh."""
    session_storage = load_session_state(session_id)
    temp_path: Optional[str] = None
    try:
        suffix = "." + file.filename.split('.')[-1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await file.read()
            tmp.write(content)
            temp_path = tmp.name
        
        result = analyze_cv_layout_api(temp_path)
        response = {"success": True, "result": result}
    except Exception as e:
        response = {"success": False, "result": f"Error: {str(e)}"}
    finally:
        if temp_path:
            try:
                os.unlink(temp_path)
            except Exception:
                pass

    # TTL refresh
    persist_session_state(session_id, session_storage)

    return response


@app.post("/api/generate-improved-cv")
async def generate_improved_cv(session_id: str = Header(..., alias="X-Session-Id")):
    """Tạo mô tả layout CV mới."""
    session_storage = load_session_state(session_id)
    try:
        result = generate_improved_cv_api(session_storage)
        response = {"success": True, "result": result}
    except Exception as e:
        response = {"success": False, "result": f"Error: {str(e)}"}

    if response.get("success"):
        if not persist_session_state(session_id, session_storage):
            response = {
                "success": False,
                "result": "Error: Unable to persist session data.",
            }
    else:
        persist_session_state(session_id, session_storage)

    return response


@app.get("/api/session-status")
async def get_session_status(session_id: str = Header(..., alias="X-Session-Id")):
    """Lấy trạng thái session hiện tại."""
    session_storage = load_session_state(session_id)
    persist_session_state(session_id, session_storage)

    return {
        "has_cv": bool(session_storage.get("cv_text")),
        "has_jd": bool(session_storage.get("jd_text")),
        "chat_history_count": len(session_storage.get("chat_history", []))
    }


@app.get("/api/get-cv-jd")
async def get_cv_jd(session_id: str = Header(..., alias="X-Session-Id")):
    """Lấy nội dung CV và JD đã lưu."""
    session_storage = load_session_state(session_id)
    persist_session_state(session_id, session_storage)

    return {
        "success": True,
        "cv_text": session_storage.get("cv_text", ""),
        "jd_text": session_storage.get("jd_text", "")
    }


@app.post("/api/clear-session")
async def clear_session(session_id: str = Header(..., alias="X-Session-Id")):
    """Xóa session khi người dùng thoát hẳn."""
    clear_session_state(session_id)
    return {"success": True, "message": "Session cleared"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.api:app", host="0.0.0.0", port=8000, reload=True)

