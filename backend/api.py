"""
FastAPI Backend for AI Resume Analyzer
Kết nối với React Frontend
"""

import os
import sys
import tempfile
import base64
from typing import Optional
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

# Import agent functions
from agent_api import (
    analyze_cv_jd_api, 
    find_suitable_jobs_api, 
    chat_with_agent_api,
    suggest_cv_improvements_api,
    analyze_cv_layout_api,
    generate_improved_cv_api
)

# Import interview router
from interview_api import router as interview_router

app = FastAPI(
    title="AI Resume Analyzer API",
    description="API cho hệ thống phân tích CV và tìm việc làm",
    version="3.0"
)

# CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include interview router
app.include_router(interview_router)

# In-memory storage for session data
session_storage = {
    "cv_text": "",
    "jd_text": "",
    "chat_history": []
}

# ========== MODELS ==========
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
    jd_text: Optional[str] = Form(None)
):
    """Phân tích CV và JD"""
    try:
        cv_input = ""
        jd_input = ""
        cv_type = "text"
        jd_type = "text"
        temp_files = []
        
        # Process CV
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
        
        # Process JD
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
        
        # Store text inputs directly (in case agent doesn't)
        if cv_type == "text" and cv_input:
            session_storage["cv_text"] = cv_input
        if jd_type == "text" and jd_input:
            session_storage["jd_text"] = jd_input
        
        # Call agent
        result = analyze_cv_jd_api(cv_input, jd_input, cv_type, jd_type, session_storage)
        
        # Cleanup temp files
        for f in temp_files:
            try:
                os.unlink(f)
            except:
                pass
        
        return {
            "success": True, 
            "result": result,
            "cv_stored": bool(session_storage.get("cv_text")),
            "jd_stored": bool(session_storage.get("jd_text"))
        }
        
    except Exception as e:
        return {"success": False, "result": f"Error: {str(e)}"}


@app.post("/api/find-jobs")
async def find_jobs():
    """Tìm việc làm phù hợp với CV đã lưu"""
    try:
        result = find_suitable_jobs_api(session_storage)
        return {"success": True, "result": result}
    except Exception as e:
        return {"success": False, "result": f"Error: {str(e)}"}


@app.post("/api/chat")
async def chat(input_data: ChatInput):
    """Chat với AI Assistant"""
    try:
        result = chat_with_agent_api(input_data.message, session_storage)
        return {"success": True, "result": result}
    except Exception as e:
        return {"success": False, "result": f"Error: {str(e)}"}


@app.post("/api/suggest-cv-improvements")
async def suggest_cv_improvements():
    """Đề xuất chỉnh sửa CV"""
    try:
        result = suggest_cv_improvements_api(session_storage)
        return {"success": True, "result": result}
    except Exception as e:
        return {"success": False, "result": f"Error: {str(e)}"}


@app.post("/api/analyze-cv-layout")
async def analyze_cv_layout(file: UploadFile = File(...)):
    """Phân tích layout CV từ file ảnh"""
    try:
        suffix = "." + file.filename.split('.')[-1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await file.read()
            tmp.write(content)
            file_path = tmp.name
        
        result = analyze_cv_layout_api(file_path)
        
        # Cleanup
        try:
            os.unlink(file_path)
        except:
            pass
        
        return {"success": True, "result": result}
    except Exception as e:
        return {"success": False, "result": f"Error: {str(e)}"}


@app.post("/api/generate-improved-cv")
async def generate_improved_cv():
    """Tạo mô tả layout CV mới"""
    try:
        result = generate_improved_cv_api(session_storage)
        return {"success": True, "result": result}
    except Exception as e:
        return {"success": False, "result": f"Error: {str(e)}"}


@app.get("/api/session-status")
async def get_session_status():
    """Lấy trạng thái session hiện tại"""
    return {
        "has_cv": bool(session_storage.get("cv_text")),
        "has_jd": bool(session_storage.get("jd_text")),
        "chat_history_count": len(session_storage.get("chat_history", []))
    }


@app.get("/api/get-cv-jd")
async def get_cv_jd():
    """Lấy nội dung CV và JD đã lưu"""
    return {
        "success": True,
        "cv_text": session_storage.get("cv_text", ""),
        "jd_text": session_storage.get("jd_text", "")
    }


@app.post("/api/clear-session")
async def clear_session():
    """Xóa session"""
    session_storage["cv_text"] = ""
    session_storage["jd_text"] = ""
    session_storage["chat_history"] = []
    return {"success": True, "message": "Session cleared"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)

