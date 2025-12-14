"""
Agent API - Version không dùng Streamlit
Dành cho FastAPI Backend
"""

import os
import sys
import base64
import re
from typing import Any, Dict, List, Union

# Add parent directory to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from langchain_openai import ChatOpenAI
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.tools import tool
from dotenv import load_dotenv
from langchain_community.tools.tavily_search import TavilySearchResults

load_dotenv(os.path.join(os.path.dirname(current_dir), ".env"))


class ToolCallingAgentRunner:
    """Minimal agent runner supporting OpenAI tool-calling for backend usage."""

    def __init__(
        self,
        llm: ChatOpenAI,
        tools: List[Any],
        system_message: str = "",
        verbose: bool = False,
    ) -> None:
        self.llm = llm
        self.llm_with_tools = llm.bind_tools(tools)
        self.tool_map = {tool.name: tool for tool in tools}
        self.system_message = system_message
        self.verbose = verbose

    def _format_history(
        self, history: Union[List[BaseMessage], None, List[Any]]
    ) -> List[BaseMessage]:
        if not history:
            return []

        formatted: List[BaseMessage] = []
        for item in history:
            if isinstance(item, BaseMessage):
                formatted.append(item)
                continue

            if isinstance(item, dict):
                role = item.get("role") or item.get("type")
                content = item.get("content", "")
                if role in ("human", "user"):
                    formatted.append(HumanMessage(content=str(content)))
                elif role in ("ai", "assistant"):
                    formatted.append(AIMessage(content=str(content)))
                elif role == "system":
                    formatted.append(SystemMessage(content=str(content)))
                elif role == "tool":
                    formatted.append(
                        ToolMessage(
                            content=str(content),
                            tool_call_id=item.get("tool_call_id", ""),
                        )
                    )
                continue

            if isinstance(item, str):
                formatted.append(HumanMessage(content=item))

        return formatted

    def invoke(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        user_input = inputs.get("input", "")
        history = self._format_history(inputs.get("chat_history"))

        messages: List[BaseMessage] = []
        if self.system_message:
            messages.append(SystemMessage(content=self.system_message))

        messages.extend(history or [])
        messages.append(HumanMessage(content=user_input))

        while True:
            response: AIMessage = self.llm_with_tools.invoke(messages)
            messages.append(response)

            tool_calls = getattr(response, "tool_calls", None) or []
            if not tool_calls:
                return {"output": response.content, "messages": messages}

            for tool_call in tool_calls:
                tool_name = getattr(tool_call, "name", None) or getattr(
                    tool_call, "tool_name", None
                )
                tool_args = getattr(tool_call, "args", None) or getattr(
                    tool_call, "arguments", None
                )
                tool_call_id = getattr(tool_call, "id", None)

                if isinstance(tool_call, dict):
                    tool_name = tool_name or tool_call.get("name")
                    tool_args = tool_args or tool_call.get("args") or tool_call.get(
                        "arguments"
                    )
                    tool_call_id = tool_call_id or tool_call.get("id") or tool_call.get(
                        "tool_call_id"
                    )

                tool_instance = self.tool_map.get(tool_name)

                if not tool_instance:
                    tool_output = f"ERROR: Tool '{tool_name}' không tồn tại."
                else:
                    tool_params = tool_args or {}
                    if not isinstance(tool_params, dict):
                        args_schema = getattr(tool_instance, "args_schema", None)
                        if args_schema and hasattr(args_schema, "__fields__"):
                            fields = list(args_schema.__fields__.keys())
                            if len(fields) == 1:
                                tool_params = {fields[0]: tool_params}
                            else:
                                tool_params = {}
                        else:
                            tool_params = {}

                    try:
                        tool_output = tool_instance.invoke(tool_params)
                    except Exception as exc:
                        tool_output = f"ERROR: {exc}"

                if not isinstance(tool_output, str):
                    tool_output = str(tool_output)

                messages.append(
                    ToolMessage(content=tool_output, tool_call_id=tool_call_id or "")
                )

# Import tools with fallback
calculate_similarity = None
compare_skills_tool = None
process_raw_text = None

try:
    from .tools_ocr import process_raw_text  # type: ignore
except ImportError:
    try:
        from tools_ocr import process_raw_text  # type: ignore
    except ImportError as e:
        print(f"⚠️ tools_ocr import error: {e}")

        def process_raw_text(text):
            return text.strip() if text else ""
    else:
        print("✅ tools_ocr imported")
else:
    print("✅ tools_ocr imported (package relative)")

# Use OpenAI for similarity calculation
def calculate_similarity(cv_text, jd_text):
    """Tính điểm phù hợp CV-JD bằng GPT-4o"""
    try:
        llm = ChatOpenAI(model="gpt-4o", temperature=0)
        prompt = f"""Bạn là chuyên gia tuyển dụng. Hãy đánh giá mức độ phù hợp giữa CV và JD sau.

CV:
{cv_text[:3000]}

JD:
{jd_text[:2000]}

Hãy CHỈ trả về MỘT SỐ từ 0.0 đến 1.0 (ví dụ: 0.75) thể hiện mức độ phù hợp.
- 0.0-0.3: Không phù hợp
- 0.3-0.5: Ít phù hợp
- 0.5-0.7: Phù hợp trung bình
- 0.7-0.85: Phù hợp tốt
- 0.85-1.0: Rất phù hợp

CHỈ TRẢ VỀ SỐ, KHÔNG THÊM GÌ KHÁC."""
        
        response = llm.invoke([HumanMessage(content=prompt)])
        score_text = response.content.strip()
        
        # Parse score
        import re
        match = re.search(r'(\d+\.?\d*)', score_text)
        if match:
            score = float(match.group(1))
            return round(min(max(score, 0.0), 1.0), 4)
        return 0.5
    except Exception as e:
        print(f"Similarity error: {e}")
        return 0.5

print("✅ calculate_similarity using OpenAI GPT-4o")

try:
    from .tools_skills import compare_skills_tool  # type: ignore
except ImportError:
    try:
        from tools_skills import compare_skills_tool  # type: ignore
    except ImportError as e:
        print(f"⚠️ tools_skills import error: {e}")

        COMMON_SKILLS_DB = {
            "python", "java", "c++", "javascript", "typescript", "react", "angular", "vue",
            "django", "flask", "spring boot", "node.js", "tensorflow", "pytorch", "pandas",
            "numpy", "scikit-learn", "git", "docker", "kubernetes", "aws", "azure", "mysql",
            "postgresql", "mongodb", "machine learning", "deep learning", "nlp", "ai"
        }

        def compare_skills_tool(cv_text, jd_text):
            cv_lower = cv_text.lower()
            jd_lower = jd_text.lower()
            cv_skills = set()
            jd_skills = set()

            for skill in COMMON_SKILLS_DB:
                if re.search(r'\b' + re.escape(skill) + r'\b', cv_lower):
                    cv_skills.add(skill)
                if re.search(r'\b' + re.escape(skill) + r'\b', jd_lower):
                    jd_skills.add(skill)

            return {
                "cv_skills": list(cv_skills),
                "jd_skills": list(jd_skills),
                "matched_skills": list(cv_skills.intersection(jd_skills)),
                "missing_skills": list(jd_skills.difference(cv_skills))
            }
    else:
        print("✅ tools_skills imported")
else:
    print("✅ tools_skills imported (package relative)")

# Global storage reference (will be set by API)
_session_storage = {}

def set_session_storage(storage):
    global _session_storage
    _session_storage = storage

# ===== TOOLS =====
@tool
def tool_extract_text_from_file(file_path: str) -> str:
    """Trích xuất văn bản từ file (PDF hoặc ảnh)."""
    try:
        ext = file_path.lower().split('.')[-1]
        
        # Handle PDF with PyMuPDF
        if ext == 'pdf':
            try:
                import fitz  # PyMuPDF
                doc = fitz.open(file_path)
                text_output = ""
                for page in doc:
                    text_output += page.get_text() + "\n"
                doc.close()
                
                if text_output.strip():
                    return text_output.strip()
                else:
                    return "PDF không có text layer."
            except ImportError:
                return "ERROR: PyMuPDF chưa được cài đặt."
            except Exception as e:
                return f"ERROR: Không thể đọc PDF - {str(e)}"
        
        # Handle images with GPT-4o Vision
        else:
            with open(file_path, "rb") as f:
                file_bytes = f.read()
                base64_data = base64.b64encode(file_bytes).decode('utf-8')
            
            mime_type = f"image/{ext}" if ext != 'jpg' else "image/jpeg"
            
            vision_llm = ChatOpenAI(model="gpt-4o", temperature=0)
            message = HumanMessage(
                content=[
                    {
                        "type": "text",
                        "text": "Trích xuất TOÀN BỘ văn bản trong hình ảnh này. Giữ nguyên format và cấu trúc. Chỉ trả về text, không thêm giải thích."
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime_type};base64,{base64_data}"}
                    }
                ]
            )
            response = vision_llm.invoke([message])
            return response.content
            
    except Exception as e:
        return f"ERROR: Không thể đọc file - {str(e)}"


@tool
def tool_process_text_input(raw_text: str) -> str:
    """Làm sạch văn bản."""
    try:
        return process_raw_text(raw_text)
    except Exception as e:
        return f"ERROR: {str(e)}"


@tool
def tool_store_cv_text(cv_text: str) -> str:
    """Lưu CV text vào bộ nhớ."""
    global _session_storage
    _session_storage["cv_text"] = cv_text
    return f"SUCCESS: Đã lưu CV text ({len(cv_text)} ký tự)"


@tool
def tool_store_jd_text(jd_text: str) -> str:
    """Lưu JD text vào bộ nhớ."""
    global _session_storage
    _session_storage["jd_text"] = jd_text
    return f"SUCCESS: Đã lưu JD text ({len(jd_text)} ký tự)"


@tool
def tool_calculate_match_score(dummy: str = "run") -> str:
    """Tính điểm phù hợp giữa CV và JD."""
    global _session_storage
    cv_text = _session_storage.get("cv_text", "")
    jd_text = _session_storage.get("jd_text", "")
    
    try:
        if not cv_text or not jd_text:
            return "ERROR: Chưa có CV hoặc JD text."
        score = calculate_similarity(cv_text, jd_text)
        return str(score)
    except Exception as e:
        return f"ERROR: {str(e)}"


@tool
def tool_find_jobs_online(search_query: str) -> str:
    """Tìm kiếm việc làm trên mạng."""
    try:
        search_tool = TavilySearchResults(max_results=5)
        results = search_tool.invoke({"query": search_query})
        
        formatted_results = ""
        for item in results:
            formatted_results += f"- Tiêu đề: {item.get('content', 'No content')[:100]}...\n"
            formatted_results += f"  Link: {item.get('url')}\n\n"
            
        return formatted_results
    except Exception as e:
        return f"ERROR searching jobs: {str(e)}"


@tool
def tool_analyze_skills(dummy: str = "run") -> str:
    """Phân tích kỹ năng trong CV so với JD."""
    global _session_storage
    cv_text = _session_storage.get("cv_text", "")
    jd_text = _session_storage.get("jd_text", "")
    
    try:
        if not cv_text or not jd_text:
            return "ERROR: Chưa có CV hoặc JD text."
        
        result = compare_skills_tool(cv_text, jd_text)
        cv_skills = ", ".join(result.get('cv_skills', []))
        missing_skills = ", ".join(result.get('missing_skills', []))
        
        return f"cv_skills: {cv_skills} ||| missing_skills: {missing_skills}"
    except Exception as e:
        return f"ERROR: {str(e)}"


@tool
def tool_suggest_jobs(dummy: str = "run") -> str:
    """Gợi ý việc làm phù hợp."""
    global _session_storage
    cv_text = _session_storage.get("cv_text", "")
    
    if not cv_text:
        return "ERROR: Chưa có CV."
    
    return f"CV_CONTENT_FOR_ANALYSIS:\n{cv_text[:2000]}"


@tool
def tool_suggest_cv_improvements(dummy: str = "run") -> str:
    """Đề xuất chỉnh sửa CV."""
    global _session_storage
    cv_text = _session_storage.get("cv_text", "")
    jd_text = _session_storage.get("jd_text", "")
    
    if not cv_text:
        return "ERROR: Chưa có CV."
    
    vision_llm = ChatOpenAI(model="gpt-4o", temperature=0.3)
    jd_context = f"\n\nJD MỤC TIÊU:\n{jd_text[:2000]}" if jd_text else ""
    
    prompt = f"""Bạn là chuyên gia tư vấn CV. Hãy phân tích CV sau và ĐỀ XUẤT BẢN CV MỚI ĐÃ ĐƯỢC CHỈNH SỬA.

CV HIỆN TẠI:
{cv_text[:3500]}
{jd_context}

OUTPUT FORMAT:
## 📋 PHÂN TÍCH CV HIỆN TẠI
[Điểm mạnh và điểm yếu]

## ✏️ ĐỀ XUẤT CHỈNH SỬA
[Liệt kê cụ thể những thay đổi]

## 📄 CV MỚI ĐÃ CHỈNH SỬA
```
[Nội dung CV đã được viết lại hoàn chỉnh]
```

## 💡 GHI CHÚ QUAN TRỌNG
[Lời khuyên thêm]
"""
    
    try:
        response = vision_llm.invoke([HumanMessage(content=prompt)])
        return response.content
    except Exception as e:
        return f"ERROR: {str(e)}"


@tool  
def tool_analyze_cv_layout(file_path: str) -> str:
    """Phân tích layout CV từ file ảnh."""
    try:
        with open(file_path, "rb") as f:
            file_bytes = f.read()
            base64_data = base64.b64encode(file_bytes).decode('utf-8')
        
        ext = file_path.lower().split('.')[-1]
        if ext == 'pdf':
            mime_type = "application/pdf"
        else:
            mime_type = f"image/{ext}" if ext != 'jpg' else "image/jpeg"
        
        vision_llm = ChatOpenAI(model="gpt-4o", temperature=0)
        
        analysis_prompt = """Bạn là chuyên gia đánh giá CV. Hãy PHÂN TÍCH CHI TIẾT LAYOUT/BỐ CỤC của CV này.

TIÊU CHÍ ĐÁNH GIÁ (1-10 điểm):
1. 📐 BỐ CỤC TỔNG THỂ
2. 🔤 TYPOGRAPHY
3. 🎨 THIẾT KẾ & MÀU SẮC
4. 📋 CẤU TRÚC SECTIONS
5. 📊 TÍNH CHUYÊN NGHIỆP

OUTPUT FORMAT:
## 🎯 ĐÁNH GIÁ LAYOUT CV
### Điểm Tổng: X/10
| Tiêu Chí | Điểm | Nhận Xét |
|----------|------|----------|
| ... | X/10 | ... |

### ✅ ĐIỂM TỐT
### ⚠️ CẦN CẢI THIỆN
### 💡 ĐỀ XUẤT CHỈNH SỬA LAYOUT
"""
        
        message = HumanMessage(
            content=[
                {"type": "text", "text": analysis_prompt},
                {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{base64_data}"}}
            ]
        )
        
        response = vision_llm.invoke([message])
        return response.content
        
    except Exception as e:
        return f"ERROR: {str(e)}"


@tool
def tool_generate_improved_cv_image(dummy: str = "run") -> str:
    """Tạo mô tả layout CV mới."""
    global _session_storage
    cv_text = _session_storage.get("cv_text", "")
    
    if not cv_text:
        return "ERROR: Chưa có CV."
    
    vision_llm = ChatOpenAI(model="gpt-4o", temperature=0.3)
    
    prompt = f"""Dựa trên nội dung CV bên dưới, hãy tạo MÔ TẢ CHI TIẾT về một bản CV mới với LAYOUT CHUYÊN NGHIỆP.

NỘI DUNG CV:
{cv_text[:3000]}

TẠO MÔ TẢ VISUAL LAYOUT MỚI:
## 🖼️ MÔ TẢ LAYOUT CV MỚI
### Cấu trúc tổng thể
### Header Section
### Main Sections
### Color Scheme
### Typography Guide
### Visual Elements
## 📝 NỘI DUNG CV ĐÃ TỐI ƯU
## 🔗 TEMPLATE GỢI Ý
"""
    
    try:
        response = vision_llm.invoke([HumanMessage(content=prompt)])
        return response.content
    except Exception as e:
        return f"ERROR: {str(e)}"


def initialize_agent_api(verbose: bool = False) -> ToolCallingAgentRunner:
    """Khởi tạo Agent cho API."""
    llm = ChatOpenAI(model="gpt-4o", temperature=0)

    tools = [
        tool_extract_text_from_file,
        tool_process_text_input,
        tool_store_cv_text,
        tool_store_jd_text,
        tool_calculate_match_score,
        tool_analyze_skills,
        tool_suggest_jobs,
        tool_find_jobs_online,
        tool_suggest_cv_improvements,
        tool_analyze_cv_layout,
        tool_generate_improved_cv_image,
    ]

    system_message = (
        "Bạn là AI Recruitment Expert chuyên nghiệp.\n\n"
        "NHIỆM VỤ:\n"
        "- Phân tích CV/JD, tính điểm, so sánh kỹ năng.\n"
        "- Gợi ý việc làm và đánh giá trạng thái phỏng vấn.\n"
        "- Đề xuất chỉnh sửa CV bằng tiếng Anh.\n"
        "- Phân tích layout CV khi được yêu cầu.\n\n"
        "QUAN TRỌNG:\n"
        "- Với file: Dùng tool_extract_text_from_file.\n"
        "- Luôn lưu CV/JD sau khi trích xuất.\n"
        "- Trả lời rõ ràng, dễ đọc."
    )

    return ToolCallingAgentRunner(
        llm=llm,
        tools=tools,
        system_message=system_message,
        verbose=verbose,
    )


# ===== API FUNCTIONS =====

def analyze_cv_jd_api(cv_input: str, jd_input: str, cv_type: str, jd_type: str, storage: dict) -> str:
    """API version of analyze_cv_jd"""
    global _session_storage
    _session_storage = storage
    
    agent = initialize_agent_api()
    
    user_query = f"""
Thực hiện phân tích CV-JD:

THÔNG TIN:
- CV: type={cv_type}, data={cv_input[:150]}...
- JD: type={jd_type}, data={jd_input[:150]}...

BƯỚC 1: TRÍCH XUẤT CV TEXT
Nếu cv_type == 'file': Gọi tool_extract_text_from_file("{cv_input}")
Nếu cv_type == 'text': Gọi tool_process_text_input với nội dung CV
SAU ĐÓ: Gọi tool_store_cv_text với kết quả

BƯỚC 2: TRÍCH XUẤT JD TEXT
Làm tương tự với JD, SAU ĐÓ: Gọi tool_store_jd_text

BƯỚC 3: TÍNH ĐIỂM PHÙ HỢP
Gọi: tool_calculate_match_score("run")

BƯỚC 4: PHÂN TÍCH KỸ NĂNG
Gọi: tool_analyze_skills("run")

BƯỚC 5: GỢI Ý KHÓA HỌC
Dựa vào missing_skills, đề xuất 3-5 khóa học từ Coursera, Udemy, edX.

BƯỚC 6: VIẾT BÁO CÁO
# 📊 KẾT QUẢ PHÂN TÍCH
## 🎯 Điểm Phù Hợp: [SCORE]
## ✅ Kỹ Năng Đã Có
## ⚠️ Kỹ Năng Cần Bổ Sung
## 📚 Khóa Học Đề Xuất
## 💡 Nhận Xét
"""
    
    try:
        result = agent.invoke({"input": user_query, "chat_history": []})
        return result['output']
    except Exception as e:
        return f"❌ Lỗi: {str(e)}"


def find_suitable_jobs_api(storage: dict) -> str:
    """API version of find_suitable_jobs"""
    global _session_storage
    _session_storage = storage
    
    cv_content = storage.get("cv_text", "")
    jd_content = storage.get("jd_text", "")
    
    if not cv_content:
        return "❌ Chưa có dữ liệu CV. Vui lòng phân tích CV trước!"
    
    agent = initialize_agent_api()
    
    jd_context = f"\nJD ĐÃ PHÂN TÍCH:\n{jd_content[:2000]}" if jd_content else ""
    
    query = f"""
Dựa vào CV bên dưới, thực hiện:
1. Phân tích hồ sơ
2. Sử dụng tool_find_jobs_online để tìm 5+ công việc đang tuyển
3. Đánh giá TRẠNG THÁI PHỎNG VẤN cho mỗi vị trí

NỘI DUNG CV:
{cv_content[:4000]}
{jd_context}

YÊU CẦU OUTPUT:
# 💼 GỢI Ý VIỆC LÀM

## 🔍 Phân Tích Nhanh
## 🎯 ĐÁNH GIÁ KHẢ NĂNG PHỎNG VẤN
- **Khả năng được gọi phỏng vấn:** [Cao/Trung bình/Thấp]
- **Điểm mạnh khi phỏng vấn:**
- **Cần chuẩn bị thêm:**

## 🌐 Các Công Việc Đang Tuyển
### 1. [Tên Vị Trí] - [Công Ty]
   - 🔗 **Link:**
   - 📊 **Mức độ phù hợp:**
   - 📞 **TRẠNG THÁI PHỎNG VẤN:** 🟢/🟡/🔴

## 📋 TỔNG KẾT TRẠNG THÁI ỨNG TUYỂN
| Vị Trí | Công Ty | Khả Năng PV | Ưu Tiên |
|--------|---------|-------------|---------|

## 💡 LỜI KHUYÊN CHUẨN BỊ PHỎNG VẤN
"""
    
    try:
        result = agent.invoke({"input": query, "chat_history": []})
        return result['output']
    except Exception as e:
        return f"❌ Lỗi: {str(e)}"


def chat_with_agent_api(user_message: str, storage: dict) -> str:
    """API version of chat_with_agent"""
    global _session_storage
    _session_storage = storage
    
    agent = initialize_agent_api()
    
    cv_text = storage.get("cv_text", "")
    jd_text = storage.get("jd_text", "")
    chat_history = storage.get("chat_history", [])

    context_data = ""
    if cv_text:
        context_data += f"\n=== NỘI DUNG CV ===\n{cv_text[:3000]}\n"
    if jd_text:
        context_data += f"\n=== NỘI DUNG JD ===\n{jd_text[:3000]}\n"

    history_text = "\n".join(chat_history[-6:])

    full_query = f"""
THÔNG TIN NGỮ CẢNH:
{context_data}

LỊCH SỬ TRÒ CHUYỆN:
{history_text}

CÂU HỎI MỚI:
{user_message}
"""

    try:
        result = agent.invoke({"input": full_query, "chat_history": []})
        output_text = result['output']
        
        # Save to history
        storage["chat_history"].append(f"User: {user_message}")
        storage["chat_history"].append(f"AI: {output_text}")
        
        return output_text
    except Exception as e:
        return f"❌ Lỗi: {str(e)}"


def suggest_cv_improvements_api(storage: dict) -> dict:
    """API version of suggest_cv_improvements"""
    global _session_storage
    _session_storage = storage
    
    if not storage.get("cv_text"):
        return {"success": False, "output": "❌ Chưa có CV. Vui lòng phân tích CV trước!"}
    
    agent = initialize_agent_api()
    
    try:
        result = agent.invoke(
            {
                "input": (
                    "Please call tool_suggest_cv_improvements and deliver the rewritten CV entirely in English. "
                    "Do not include Vietnamese explanations."
                ),
                "chat_history": [],
            }
        )
        output_text = result["output"]
        response_payload = {"success": True, "output": output_text}

        return response_payload
    except Exception as e:
        return {"success": False, "output": f"❌ Lỗi: {str(e)}"}


def analyze_cv_layout_api(file_path: str) -> str:
    """API version of analyze_cv_layout"""
    agent = initialize_agent_api()
    
    try:
        result = agent.invoke({
            "input": f"Hãy sử dụng tool_analyze_cv_layout với file '{file_path}' để phân tích layout CV.",
            "chat_history": []
        })
        return result['output']
    except Exception as e:
        return f"❌ Lỗi: {str(e)}"


def generate_improved_cv_api(storage: dict) -> str:
    """API version of generate_improved_cv"""
    global _session_storage
    _session_storage = storage
    
    if not storage.get("cv_text"):
        return "❌ Chưa có CV. Vui lòng phân tích CV trước!"
    
    agent = initialize_agent_api()
    
    try:
        result = agent.invoke({
            "input": "Hãy sử dụng tool_generate_improved_cv_image để tạo mô tả layout CV mới.",
            "chat_history": []
        })
        return result['output']
    except Exception as e:
        return f"❌ Lỗi: {str(e)}"

