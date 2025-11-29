"""
Interview Agent - Phỏng Vấn Ảo với AI
=====================================
- Tạo câu hỏi phỏng vấn dựa trên CV và JD
- Phân tích video trả lời (khuôn mặt, giọng nói)
- Đánh giá câu trả lời
- Đánh giá behavioral/communication skills
"""

import os
import sys
import base64
import json
import tempfile
from typing import Optional, List, Dict
from datetime import datetime

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from dotenv import load_dotenv

# Add current directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

load_dotenv(os.path.join(current_dir, ".env"))

# ===== INTERVIEW QUESTION GENERATOR =====

def generate_interview_questions(cv_text: str, jd_text: str, num_questions: int = 5) -> List[Dict]:
    """
    Tạo câu hỏi phỏng vấn dựa trên CV và JD.
    
    Returns:
        List of questions with metadata:
        [
            {
                "id": 1,
                "question": "...",
                "type": "technical" | "behavioral" | "situational",
                "difficulty": "easy" | "medium" | "hard",
                "expected_keywords": ["keyword1", "keyword2"],
                "time_limit": 120  # seconds
            }
        ]
    """
    llm = ChatOpenAI(model="gpt-4o", temperature=0.3)
    
    prompt = f"""Bạn là chuyên gia phỏng vấn tuyển dụng. Dựa trên CV và JD dưới đây, hãy tạo {num_questions} câu hỏi phỏng vấn.

CV:
{cv_text[:3000]}

JD:
{jd_text[:2000]}

Yêu cầu:
- Tạo mix câu hỏi: Technical (60%), Behavioral (30%), Situational (10%)
- Độ khó: 2 Easy, 2 Medium, 1 Hard
- Mỗi câu hỏi phải relevant với CV và JD

Trả về JSON array với format:
[
    {{
        "id": 1,
        "question": "Câu hỏi tiếng Việt",
        "question_en": "English version for TTS",
        "type": "technical",
        "difficulty": "easy",
        "expected_keywords": ["keyword1", "keyword2", "keyword3"],
        "ideal_answer_points": ["Điểm 1 cần đề cập", "Điểm 2 cần đề cập"],
        "time_limit": 120
    }}
]

CHỈ TRẢ VỀ JSON, KHÔNG THÊM GÌ KHÁC."""

    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        content = response.content.strip()
        
        # Clean JSON
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        
        questions = json.loads(content)
        return questions
    except Exception as e:
        print(f"Error generating questions: {e}")
        # Return default questions
        return [
            {
                "id": 1,
                "question": "Hãy giới thiệu về bản thân bạn.",
                "question_en": "Please introduce yourself.",
                "type": "behavioral",
                "difficulty": "easy",
                "expected_keywords": ["kinh nghiệm", "kỹ năng", "mục tiêu"],
                "ideal_answer_points": ["Tên và background", "Kinh nghiệm liên quan", "Mục tiêu nghề nghiệp"],
                "time_limit": 120
            },
            {
                "id": 2,
                "question": "Điểm mạnh lớn nhất của bạn là gì?",
                "question_en": "What is your greatest strength?",
                "type": "behavioral",
                "difficulty": "easy",
                "expected_keywords": ["kỹ năng", "thành tích", "ví dụ"],
                "ideal_answer_points": ["Nêu điểm mạnh cụ thể", "Ví dụ minh họa", "Liên quan đến công việc"],
                "time_limit": 90
            }
        ]


# ===== VIDEO/AUDIO ANALYSIS =====

def analyze_video_frame(frame_base64: str) -> Dict:
    """
    Phân tích frame video để đánh giá:
    - Biểu cảm khuôn mặt
    - Ánh mắt (eye contact)
    - Tư thế
    - Độ tự tin
    """
    # Validate input
    if not frame_base64 or len(frame_base64) < 100:
        return {
            "facial_expression": {"score": 5, "note": "Frame không hợp lệ"},
            "eye_contact": {"score": 5, "note": "Frame không hợp lệ"},
            "posture": {"score": 5, "note": "Frame không hợp lệ"},
            "confidence": {"score": 5, "note": "Frame không hợp lệ"},
            "overall_note": "Frame không hợp lệ"
        }
    
    try:
        llm = ChatOpenAI(model="gpt-4o", temperature=0)
        
        prompt = """Phân tích hình ảnh người đang phỏng vấn. Đánh giá điểm từ 1-10:

1. facial_expression (biểu cảm): tự tin hay căng thẳng?
2. eye_contact (ánh mắt): nhìn camera hay nhìn chỗ khác?
3. posture (tư thế): ngồi thẳng, chuyên nghiệp?
4. confidence (tự tin): tổng thể tự tin?

Trả về ĐÚNG format JSON sau (không thêm gì khác):
{"facial_expression":{"score":7,"note":"nhan xet"},"eye_contact":{"score":7,"note":"nhan xet"},"posture":{"score":7,"note":"nhan xet"},"confidence":{"score":7,"note":"nhan xet"},"overall_note":"nhan xet chung"}"""

        message = HumanMessage(
            content=[
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{frame_base64}"}}
            ]
        )
        
        response = llm.invoke([message])
        content = response.content.strip()
        
        # Clean JSON
        if "```" in content:
            # Extract content between ```
            parts = content.split("```")
            for part in parts:
                part = part.strip()
                if part.startswith("json"):
                    part = part[4:].strip()
                if part.startswith("{"):
                    content = part
                    break
        
        # Find JSON object
        start = content.find("{")
        end = content.rfind("}") + 1
        if start >= 0 and end > start:
            content = content[start:end]
        
        return json.loads(content)
    except json.JSONDecodeError as e:
        print(f"Video analysis JSON error: {e}")
        # Return default scores
        return {
            "facial_expression": {"score": 6, "note": "Bình thường"},
            "eye_contact": {"score": 6, "note": "Bình thường"},
            "posture": {"score": 6, "note": "Bình thường"},
            "confidence": {"score": 6, "note": "Bình thường"},
            "overall_note": "Đánh giá mặc định"
        }
    except Exception as e:
        print(f"Video analysis error: {e}")
        return {
            "facial_expression": {"score": 5, "note": "Lỗi phân tích"},
            "eye_contact": {"score": 5, "note": "Lỗi phân tích"},
            "posture": {"score": 5, "note": "Lỗi phân tích"},
            "confidence": {"score": 5, "note": "Lỗi phân tích"},
            "overall_note": f"Lỗi: {str(e)[:50]}"
        }


def transcribe_audio(audio_base64: str, audio_format: str = "webm") -> str:
    """
    Chuyển audio thành text sử dụng OpenAI Whisper API.
    Hỗ trợ: flac, m4a, mp3, mp4, mpeg, mpga, oga, ogg, wav, webm
    """
    print(f"\n=== TRANSCRIBE AUDIO ===")
    print(f"Audio base64 length: {len(audio_base64) if audio_base64 else 0}")
    
    if not audio_base64 or len(audio_base64) < 1000:
        print("Audio data too short or empty")
        return ""
    
    try:
        import openai
        client = openai.OpenAI()
        
        # Decode base64
        try:
            audio_bytes = base64.b64decode(audio_base64)
            print(f"Decoded audio bytes: {len(audio_bytes)}")
        except Exception as e:
            print(f"Base64 decode error: {e}")
            return ""
        
        if len(audio_bytes) < 1000:
            print(f"Audio file too small: {len(audio_bytes)} bytes")
            return ""
        
        # Try webm format (most common from browser)
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as tmp:
                tmp.write(audio_bytes)
                tmp_path = tmp.name
            
            print(f"Saved temp file: {tmp_path}")
            
            # Transcribe with Whisper
            with open(tmp_path, "rb") as audio_file:
                print("Calling Whisper API...")
                transcript = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language="vi"
                )
            
            print(f"Whisper result: {transcript.text[:100] if transcript.text else 'EMPTY'}...")
            
            # Cleanup
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except:
                    pass
            
            return transcript.text if transcript.text else ""
                
        except Exception as e:
            print(f"Whisper transcription error: {e}")
            # Cleanup
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except:
                    pass
            return ""
        
    except Exception as e:
        print(f"Transcription error: {e}")
        import traceback
        traceback.print_exc()
        return ""


def analyze_voice_quality(audio_base64: str) -> Dict:
    """
    Phân tích chất lượng giọng nói.
    Sử dụng GPT để đánh giá từ transcript.
    """
    # First transcribe
    transcript = transcribe_audio(audio_base64)
    
    if not transcript:
        print("No transcript available, using default voice analysis")
        return {
            "clarity": {"score": 6, "note": "Không thể phân tích audio"},
            "pace": {"score": 6, "note": "Không thể phân tích audio"},
            "filler_words": {"score": 6, "note": "Không thể phân tích audio"},
            "content_quality": {"score": 6, "note": "Không thể phân tích audio"},
            "transcript": "[Không thể chuyển đổi audio thành text]"
        }
    
    llm = ChatOpenAI(model="gpt-4o", temperature=0)
    
    prompt = f"""Phân tích transcript sau từ một buổi phỏng vấn:

TRANSCRIPT:
"{transcript}"

Đánh giá:
1. **Độ rõ ràng** (1-10): Câu trả lời có mạch lạc không?
2. **Tốc độ nói** (1-10): Quá nhanh, quá chậm, hay vừa phải?
3. **Từ đệm** (1-10): Có nhiều "ờ", "à", "ừm" không? (10 = ít từ đệm)
4. **Chất lượng nội dung** (1-10): Trả lời có đúng trọng tâm không?

Trả về JSON:
{{
    "clarity": {{"score": 8, "note": "Mạch lạc, rõ ràng"}},
    "pace": {{"score": 7, "note": "Tốc độ vừa phải"}},
    "filler_words": {{"score": 6, "note": "Có một số từ đệm"}},
    "content_quality": {{"score": 7, "note": "Trả lời đúng trọng tâm"}},
    "transcript": "{transcript[:500]}"
}}

CHỈ TRẢ VỀ JSON."""

    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        content = response.content.strip()
        
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        
        result = json.loads(content)
        result["transcript"] = transcript
        return result
    except Exception as e:
        print(f"Voice analysis error: {e}")
        return {
            "clarity": {"score": 5, "note": "Lỗi phân tích"},
            "pace": {"score": 5, "note": "Lỗi phân tích"},
            "filler_words": {"score": 5, "note": "Lỗi phân tích"},
            "content_quality": {"score": 5, "note": "Lỗi phân tích"},
            "transcript": transcript
        }


# ===== ANSWER EVALUATION =====

def evaluate_answer(
    question: Dict,
    transcript: str,
    cv_text: str = "",
    jd_text: str = ""
) -> Dict:
    """
    Đánh giá câu trả lời phỏng vấn.
    
    Returns:
        {
            "relevance_score": 8,  # Độ liên quan với câu hỏi
            "completeness_score": 7,  # Độ đầy đủ
            "accuracy_score": 8,  # Độ chính xác (nếu là technical)
            "keywords_found": ["keyword1", "keyword2"],
            "keywords_missing": ["keyword3"],
            "strengths": ["Điểm mạnh 1", "Điểm mạnh 2"],
            "improvements": ["Cần cải thiện 1"],
            "ideal_answer": "Câu trả lời mẫu",
            "overall_score": 7.5,
            "feedback": "Nhận xét chi tiết"
        }
    """
    llm = ChatOpenAI(model="gpt-4o", temperature=0)
    
    expected_keywords = question.get("expected_keywords", [])
    ideal_points = question.get("ideal_answer_points", [])
    question_type = question.get("type", "behavioral")
    
    prompt = f"""Bạn là chuyên gia phỏng vấn. Đánh giá câu trả lời sau:

CÂU HỎI: {question.get('question', '')}
LOẠI: {question_type}
CÁC ĐIỂM CẦN ĐỀ CẬP: {', '.join(ideal_points)}
TỪ KHÓA MONG ĐỢI: {', '.join(expected_keywords)}

CÂU TRẢ LỜI CỦA ỨNG VIÊN:
"{transcript}"

{f"THÔNG TIN CV: {cv_text[:1000]}" if cv_text else ""}
{f"YÊU CẦU JD: {jd_text[:1000]}" if jd_text else ""}

Hãy đánh giá và trả về JSON:
{{
    "relevance_score": 8,
    "completeness_score": 7,
    "accuracy_score": 8,
    "keywords_found": ["từ khóa tìm thấy"],
    "keywords_missing": ["từ khóa thiếu"],
    "strengths": ["Điểm mạnh của câu trả lời"],
    "improvements": ["Cần cải thiện"],
    "ideal_answer": "Câu trả lời mẫu ngắn gọn",
    "overall_score": 7.5,
    "feedback": "Nhận xét chi tiết 2-3 câu"
}}

CHỈ TRẢ VỀ JSON."""

    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        content = response.content.strip()
        
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        
        return json.loads(content)
    except Exception as e:
        print(f"Answer evaluation error: {e}")
        return {
            "relevance_score": 5,
            "completeness_score": 5,
            "accuracy_score": 5,
            "keywords_found": [],
            "keywords_missing": expected_keywords,
            "strengths": [],
            "improvements": ["Không thể đánh giá"],
            "ideal_answer": "",
            "overall_score": 5,
            "feedback": f"Lỗi đánh giá: {str(e)}"
        }


# ===== BEHAVIORAL ASSESSMENT =====

def assess_behavioral(
    video_analyses: List[Dict],
    voice_analyses: List[Dict],
    answer_evaluations: List[Dict]
) -> Dict:
    """
    Đánh giá tổng thể behavioral/soft skills của ứng viên.
    
    Returns:
        {
            "communication_score": 8,
            "confidence_score": 7,
            "professionalism_score": 8,
            "body_language_score": 7,
            "overall_behavioral_score": 7.5,
            "strengths": ["Điểm mạnh"],
            "areas_to_improve": ["Cần cải thiện"],
            "hiring_recommendation": "Recommend" | "Consider" | "Not Recommend",
            "detailed_feedback": "Nhận xét chi tiết"
        }
    """
    llm = ChatOpenAI(model="gpt-4o", temperature=0.2)
    
    # Aggregate scores
    video_summary = []
    for v in video_analyses:
        video_summary.append({
            "confidence": v.get("confidence", {}).get("score", 5),
            "eye_contact": v.get("eye_contact", {}).get("score", 5),
            "expression": v.get("facial_expression", {}).get("score", 5)
        })
    
    voice_summary = []
    for v in voice_analyses:
        voice_summary.append({
            "clarity": v.get("clarity", {}).get("score", 5),
            "pace": v.get("pace", {}).get("score", 5),
            "content": v.get("content_quality", {}).get("score", 5)
        })
    
    answer_summary = []
    for a in answer_evaluations:
        answer_summary.append({
            "relevance": a.get("relevance_score", 5),
            "completeness": a.get("completeness_score", 5),
            "overall": a.get("overall_score", 5)
        })
    
    prompt = f"""Bạn là chuyên gia đánh giá ứng viên. Dựa trên dữ liệu phỏng vấn sau, đánh giá tổng thể:

VIDEO ANALYSIS (biểu cảm, eye contact, tự tin):
{json.dumps(video_summary, indent=2)}

VOICE ANALYSIS (rõ ràng, tốc độ, nội dung):
{json.dumps(voice_summary, indent=2)}

ANSWER QUALITY (liên quan, đầy đủ, overall):
{json.dumps(answer_summary, indent=2)}

Đánh giá và trả về JSON:
{{
    "communication_score": 8,
    "confidence_score": 7,
    "professionalism_score": 8,
    "body_language_score": 7,
    "overall_behavioral_score": 7.5,
    "strengths": ["Điểm mạnh 1", "Điểm mạnh 2"],
    "areas_to_improve": ["Cần cải thiện 1", "Cần cải thiện 2"],
    "hiring_recommendation": "Recommend",
    "detailed_feedback": "Nhận xét chi tiết 3-5 câu về ứng viên"
}}

hiring_recommendation: "Recommend" (>=7.5), "Consider" (5-7.5), "Not Recommend" (<5)

CHỈ TRẢ VỀ JSON."""

    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        content = response.content.strip()
        
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        
        return json.loads(content)
    except Exception as e:
        print(f"Behavioral assessment error: {e}")
        return {
            "communication_score": 5,
            "confidence_score": 5,
            "professionalism_score": 5,
            "body_language_score": 5,
            "overall_behavioral_score": 5,
            "strengths": [],
            "areas_to_improve": ["Không thể đánh giá đầy đủ"],
            "hiring_recommendation": "Consider",
            "detailed_feedback": f"Lỗi đánh giá: {str(e)}"
        }


# ===== FULL INTERVIEW SESSION =====

class InterviewSession:
    """
    Quản lý một phiên phỏng vấn hoàn chỉnh.
    """
    
    def __init__(self, cv_text: str = "", jd_text: str = ""):
        self.cv_text = cv_text
        self.jd_text = jd_text
        self.questions = []
        self.current_question_idx = 0
        self.answers = []
        self.video_analyses = []
        self.voice_analyses = []
        self.answer_evaluations = []
        self.started_at = None
        self.ended_at = None
    
    def start_interview(self, num_questions: int = 5) -> List[Dict]:
        """Bắt đầu phỏng vấn, tạo câu hỏi."""
        self.questions = generate_interview_questions(
            self.cv_text, 
            self.jd_text, 
            num_questions
        )
        self.started_at = datetime.now().isoformat()
        self.current_question_idx = 0
        return self.questions
    
    def get_current_question(self) -> Optional[Dict]:
        """Lấy câu hỏi hiện tại."""
        if self.current_question_idx < len(self.questions):
            return self.questions[self.current_question_idx]
        return None
    
    def submit_answer(
        self,
        video_frames: List[str] = None,
        audio_base64: str = None,
        text_answer: str = None  # Direct text answer (fallback)
    ) -> Dict:
        """
        Submit câu trả lời cho câu hỏi hiện tại.
        Hỗ trợ: video + audio hoặc text trực tiếp.
        
        Returns evaluation result.
        """
        current_q = self.get_current_question()
        if not current_q:
            return {"error": "No more questions"}
        
        result = {
            "question_id": current_q["id"],
            "question": current_q["question"]
        }
        
        # Analyze video frames (only if provided and valid)
        if video_frames and len(video_frames) > 0:
            try:
                # Only analyze first frame to save time
                if video_frames[0] and len(video_frames[0]) > 100:
                    analysis = analyze_video_frame(video_frames[0])
                    self.video_analyses.append(analysis)
                    result["video_analysis"] = analysis
            except Exception as e:
                print(f"Video analysis skipped: {e}")
        
        # Determine transcript source
        transcript = ""
        
        print(f"\n--- Processing Answer ---")
        print(f"text_answer received: '{text_answer}'")
        print(f"text_answer type: {type(text_answer)}")
        print(f"audio_base64 length: {len(audio_base64) if audio_base64 else 0}")
        
        # Priority 1: Direct text answer (most reliable)
        if text_answer is not None and str(text_answer).strip():
            transcript = str(text_answer).strip()
            result["input_mode"] = "text"
            print(f"Using TEXT mode, transcript: '{transcript[:100]}...'")
        
        # Priority 2: Audio transcription
        elif audio_base64 and len(str(audio_base64)) > 1000:
            try:
                print("Using AUDIO mode...")
                voice_analysis = analyze_voice_quality(audio_base64)
                self.voice_analyses.append(voice_analysis)
                transcript = voice_analysis.get("transcript", "")
                result["voice_analysis"] = voice_analysis
                result["input_mode"] = "audio"
                print(f"Audio transcript: '{transcript[:100] if transcript else 'EMPTY'}...'")
            except Exception as e:
                print(f"Voice analysis skipped: {e}")
        else:
            print("NO INPUT RECEIVED - text_answer is empty/None and no audio")
        
        # Evaluate answer if we have transcript
        if transcript:
            answer_eval = evaluate_answer(
                current_q,
                transcript,
                self.cv_text,
                self.jd_text
            )
            self.answer_evaluations.append(answer_eval)
            result["answer_evaluation"] = answer_eval
            result["transcript"] = transcript
        else:
            # No transcript - give default evaluation
            result["answer_evaluation"] = {
                "relevance_score": 5,
                "completeness_score": 5,
                "overall_score": 5,
                "feedback": "Không nhận được câu trả lời. Vui lòng thử lại."
            }
        
        # Store answer
        self.answers.append({
            "question_id": current_q["id"],
            "transcript": transcript,
            "result": result
        })
        
        # Move to next question
        self.current_question_idx += 1
        
        return result
    
    def finish_interview(self) -> Dict:
        """
        Kết thúc phỏng vấn và tạo báo cáo tổng hợp.
        """
        self.ended_at = datetime.now().isoformat()
        
        # Behavioral assessment
        behavioral = assess_behavioral(
            self.video_analyses,
            self.voice_analyses,
            self.answer_evaluations
        )
        
        # Calculate overall scores
        avg_answer_score = sum(
            a.get("overall_score", 5) for a in self.answer_evaluations
        ) / max(len(self.answer_evaluations), 1)
        
        report = {
            "session_info": {
                "started_at": self.started_at,
                "ended_at": self.ended_at,
                "total_questions": len(self.questions),
                "questions_answered": len(self.answers)
            },
            "scores": {
                "average_answer_score": round(avg_answer_score, 2),
                "behavioral_score": behavioral.get("overall_behavioral_score", 5),
                "communication_score": behavioral.get("communication_score", 5),
                "confidence_score": behavioral.get("confidence_score", 5)
            },
            "behavioral_assessment": behavioral,
            "question_results": self.answers,
            "recommendation": behavioral.get("hiring_recommendation", "Consider"),
            "summary": self._generate_summary(behavioral, avg_answer_score)
        }
        
        return report
    
    def _generate_summary(self, behavioral: Dict, avg_score: float) -> str:
        """Tạo summary text."""
        rec = behavioral.get("hiring_recommendation", "Consider")
        
        if rec == "Recommend":
            status = "✅ ĐỀ XUẤT TUYỂN DỤNG"
        elif rec == "Consider":
            status = "🟡 CẦN CÂN NHẮC THÊM"
        else:
            status = "❌ CHƯA PHÙ HỢP"
        
        return f"""
## 📊 KẾT QUẢ PHỎNG VẤN

### {status}

**Điểm trung bình câu trả lời:** {avg_score:.1f}/10
**Điểm behavioral:** {behavioral.get('overall_behavioral_score', 5):.1f}/10

### 💪 Điểm mạnh:
{chr(10).join('- ' + s for s in behavioral.get('strengths', []))}

### 📈 Cần cải thiện:
{chr(10).join('- ' + s for s in behavioral.get('areas_to_improve', []))}

### 💬 Nhận xét:
{behavioral.get('detailed_feedback', '')}
"""


# ===== EXPORT FUNCTIONS =====

def create_interview_session(cv_text: str = "", jd_text: str = "") -> InterviewSession:
    """Factory function to create interview session."""
    return InterviewSession(cv_text, jd_text)


# For testing
if __name__ == "__main__":
    # Test question generation
    test_cv = "Python Developer với 3 năm kinh nghiệm, biết Django, Flask, Machine Learning"
    test_jd = "Tuyển Python Developer, yêu cầu 2+ năm kinh nghiệm, biết Django"
    
    questions = generate_interview_questions(test_cv, test_jd, 3)
    print("Generated Questions:")
    for q in questions:
        print(f"  {q['id']}. {q['question']}")

