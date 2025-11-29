"""
Interview API - Endpoints cho Phỏng Vấn Ảo
"""

import os
import sys
from typing import Optional, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# Add parent directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from interview_agent import (
    InterviewSession,
    create_interview_session,
    generate_interview_questions,
    analyze_video_frame,
    transcribe_audio,
    evaluate_answer
)

router = APIRouter(prefix="/api/interview", tags=["Interview"])

# Store active sessions (in production, use Redis or DB)
active_sessions = {}


# ===== MODELS =====

class StartInterviewRequest(BaseModel):
    cv_text: str = ""
    jd_text: str = ""
    num_questions: int = 5

class SubmitAnswerRequest(BaseModel):
    session_id: str
    video_frames: Optional[List[str]] = []  # base64 frames
    audio_base64: Optional[str] = ""
    text_answer: Optional[str] = ""  # Direct text answer
    
    class Config:
        extra = "allow"  # Allow extra fields

class AnalyzeFrameRequest(BaseModel):
    frame_base64: str

class TranscribeRequest(BaseModel):
    audio_base64: str
    format: str = "webm"


# ===== ENDPOINTS =====

@router.post("/start")
async def start_interview(request: StartInterviewRequest):
    """
    Bắt đầu phiên phỏng vấn mới.
    
    Returns:
        - session_id
        - questions list
    """
    try:
        # Create session
        session = create_interview_session(request.cv_text, request.jd_text)
        questions = session.start_interview(request.num_questions)
        
        # Generate session ID
        import uuid
        session_id = str(uuid.uuid4())[:8]
        active_sessions[session_id] = session
        
        return {
            "success": True,
            "session_id": session_id,
            "questions": questions,
            "total_questions": len(questions)
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/question/{session_id}")
async def get_current_question(session_id: str):
    """Lấy câu hỏi hiện tại."""
    session = active_sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    question = session.get_current_question()
    if not question:
        return {
            "success": True,
            "finished": True,
            "message": "Đã hoàn thành tất cả câu hỏi"
        }
    
    return {
        "success": True,
        "finished": False,
        "current_index": session.current_question_idx,
        "total": len(session.questions),
        "question": question
    }


@router.post("/submit-answer")
async def submit_answer(request: SubmitAnswerRequest):
    """
    Submit câu trả lời (video + audio hoặc text).
    """
    print(f"\n{'='*50}")
    print(f"=== SUBMIT ANSWER API ===")
    print(f"{'='*50}")
    print(f"Session ID: {request.session_id}")
    print(f"Text Answer (raw): '{request.text_answer}'")
    print(f"Text Answer type: {type(request.text_answer)}")
    print(f"Text Answer length: {len(request.text_answer) if request.text_answer else 0}")
    print(f"Video Frames count: {len(request.video_frames) if request.video_frames else 0}")
    print(f"Audio length: {len(request.audio_base64) if request.audio_base64 else 0} chars")
    
    session = active_sessions.get(request.session_id)
    if not session:
        print(f"ERROR: Session not found! Active sessions: {list(active_sessions.keys())}")
        raise HTTPException(status_code=404, detail="Session not found")
    
    print(f"Current question index: {session.current_question_idx}")
    print(f"Total questions: {len(session.questions)}")
    
    try:
        result = session.submit_answer(
            video_frames=request.video_frames,
            audio_base64=request.audio_base64,
            text_answer=request.text_answer
        )
        
        print(f"Result transcript: {result.get('transcript', 'NO TRANSCRIPT')[:100]}...")
        print(f"Result evaluation: {result.get('answer_evaluation', {}).get('overall_score', 'N/A')}")
        
        # Check if more questions
        has_more = session.current_question_idx < len(session.questions)
        
        return {
            "success": True,
            "result": result,
            "has_more_questions": has_more,
            "next_question_index": session.current_question_idx if has_more else None
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}


@router.post("/finish/{session_id}")
async def finish_interview(session_id: str):
    """
    Kết thúc phỏng vấn và lấy báo cáo.
    """
    session = active_sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    try:
        report = session.finish_interview()
        
        # Cleanup session (optional)
        # del active_sessions[session_id]
        
        return {
            "success": True,
            "report": report
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/analyze-frame")
async def analyze_frame(request: AnalyzeFrameRequest):
    """
    Phân tích một frame video (realtime feedback).
    """
    try:
        result = analyze_video_frame(request.frame_base64)
        return {"success": True, "analysis": result}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/transcribe")
async def transcribe(request: TranscribeRequest):
    """
    Chuyển audio thành text.
    """
    try:
        text = transcribe_audio(request.audio_base64, request.format)
        return {"success": True, "transcript": text}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/sessions")
async def list_sessions():
    """List all active sessions (for debugging)."""
    session_details = {}
    for sid, session in active_sessions.items():
        session_details[sid] = {
            "current_question": session.current_question_idx,
            "total_questions": len(session.questions),
            "answers_count": len(session.answers),
            "has_cv": bool(session.cv_text),
            "has_jd": bool(session.jd_text)
        }
    return {
        "active_sessions": list(active_sessions.keys()),
        "count": len(active_sessions),
        "details": session_details
    }


@router.get("/debug/{session_id}")
async def debug_session(session_id: str):
    """Debug a specific session."""
    session = active_sessions.get(session_id)
    if not session:
        return {"error": "Session not found", "active": list(active_sessions.keys())}
    
    return {
        "session_id": session_id,
        "current_question_idx": session.current_question_idx,
        "total_questions": len(session.questions),
        "questions": [q.get("question", "")[:50] for q in session.questions],
        "answers": [
            {
                "q_id": a.get("question_id"),
                "transcript": a.get("transcript", "")[:100] if a.get("transcript") else "NO TRANSCRIPT"
            }
            for a in session.answers
        ],
        "answer_evaluations_count": len(session.answer_evaluations),
        "cv_text_length": len(session.cv_text) if session.cv_text else 0,
        "jd_text_length": len(session.jd_text) if session.jd_text else 0
    }


@router.delete("/session/{session_id}")
async def delete_session(session_id: str):
    """Delete a session."""
    if session_id in active_sessions:
        del active_sessions[session_id]
        return {"success": True, "message": "Session deleted"}
    raise HTTPException(status_code=404, detail="Session not found")

