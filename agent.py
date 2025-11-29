import os
import streamlit as st
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage 
from dotenv import load_dotenv
import base64
from langchain_community.tools.tavily_search import TavilySearchResults

# Load environment variables
load_dotenv(".env")

# Import tools
try:
    from tools_ocr import process_raw_text
    from tools_skills import compare_skills_tool
except ImportError as e:
    print(f"IMPORT ERROR: {e}")
    def process_raw_text(text):
        return text.strip() if text else ""
    from tools_skills import compare_skills_tool

# Use OpenAI for similarity calculation
def calculate_similarity(cv_text, jd_text):
    """Tính điểm phù hợp CV-JD bằng GPT-4o"""
    try:
        import re
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
        
        match = re.search(r'(\d+\.?\d*)', score_text)
        if match:
            score = float(match.group(1))
            return round(min(max(score, 0.0), 1.0), 4)
        return 0.5
    except Exception as e:
        print(f"Similarity error: {e}")
        return 0.5

print("✅ calculate_similarity using OpenAI GPT-4o")


# ===== KHỞI TẠO SESSION STATE (QUAN TRỌNG CHO STREAMLIT) =====
# Giúp dữ liệu không bị mất khi reload hoặc chuyển tab
if "stored_cv_text" not in st.session_state:
    st.session_state["stored_cv_text"] = ""
if "stored_jd_text" not in st.session_state:
    st.session_state["stored_jd_text"] = ""
if "chat_history" not in st.session_state:
    st.session_state["chat_history"] = []

# Global variables (giữ lại để fallback, nhưng ưu tiên dùng session_state)
CV_TEXT_STORAGE = ""
JD_TEXT_STORAGE = ""


# ===== SIMPLE TOOLS - NO JSON =====
@tool
def tool_extract_text_from_file(file_path: str) -> str:
    """
    Trích xuất văn bản từ file (PDF hoặc ảnh).
    - PDF: Dùng PyMuPDF để extract text
    - Ảnh: Dùng GPT-4o Vision
    
    Input: đường dẫn file (PDF/PNG/JPG/JPEG)
    Output: nội dung văn bản được trích xuất
    """
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
                    # If no text extracted, try OCR fallback
                    return "PDF không có text layer. Vui lòng upload ảnh hoặc paste text trực tiếp."
            except ImportError:
                return "ERROR: PyMuPDF chưa được cài đặt. Chạy: pip install PyMuPDF"
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
    """
    Làm sạch văn bản.
    Input: văn bản thô
    Output: văn bản đã làm sạch
    """
    try:
        return process_raw_text(raw_text)
    except Exception as e:
        return f"ERROR: {str(e)}"


@tool
def tool_store_cv_text(cv_text: str) -> str:
    """
    Lưu CV text đã trích xuất vào bộ nhớ phiên làm việc (Session State).
    """
    # Lưu vào biến global
    global CV_TEXT_STORAGE
    CV_TEXT_STORAGE = cv_text
    
    # [QUAN TRỌNG] Lưu vào Session State
    st.session_state["stored_cv_text"] = cv_text
    
    return f"SUCCESS: Đã lưu CV text ({len(cv_text)} ký tự)"


@tool
def tool_store_jd_text(jd_text: str) -> str:
    """
    Lưu JD text đã trích xuất vào bộ nhớ.
    """
    global JD_TEXT_STORAGE
    JD_TEXT_STORAGE = jd_text
    
    # [QUAN TRỌNG] Lưu vào Session State
    st.session_state["stored_jd_text"] = jd_text
    
    return f"SUCCESS: Đã lưu JD text ({len(jd_text)} ký tự)"


@tool
def tool_calculate_match_score(dummy: str = "run") -> str:
    """
    Tính điểm phù hợp giữa CV và JD đã lưu trong bộ nhớ.
    Input: bất kỳ string nào (không quan trọng)
    Output: điểm phù hợp dạng số
    """
    # Ưu tiên lấy từ Session State
    cv_text = st.session_state.get("stored_cv_text", "")
    jd_text = st.session_state.get("stored_jd_text", "")
    
    try:
        if not cv_text or not jd_text:
            return "ERROR: Chưa có CV hoặc JD text. Hãy lưu chúng trước."
        score = calculate_similarity(cv_text, jd_text)
        return str(score)
    except Exception as e:
        return f"ERROR: {str(e)}"

@tool
def tool_find_jobs_online(search_query: str) -> str:
    """
    Tìm kiếm việc làm thực tế trên mạng bằng Tavily (Google Search tối ưu cho AI).
    Input: Câu truy vấn tìm kiếm (Ví dụ: "Python Developer tuyển dụng hcm")
    Output: Danh sách các kết quả tìm kiếm (Tiêu đề + Link + Nội dung tóm tắt)
    """
    try:
        # Tavily tự động tối ưu tìm kiếm, không cần cấu hình phức tạp
        # k=5 là số lượng kết quả muốn lấy
        tool = TavilySearchResults(max_results=5)
        
        results = tool.invoke({"query": search_query})
        
        # Format lại kết quả cho đẹp để LLM dễ đọc
        formatted_results = ""
        for item in results:
            formatted_results += f"- Tiêu đề: {item.get('content', 'No content')[:100]}...\n"
            formatted_results += f"  Link: {item.get('url')}\n\n"
            
        return formatted_results
    except Exception as e:
        print(f"DEBUG - TAVILY ERROR: {str(e)}")
        return f"ERROR searching jobs: {str(e)}"

@tool
def tool_analyze_skills(dummy: str = "run") -> str:
    """
    Phân tích kỹ năng trong CV so với JD đã lưu.
    """
    # Ưu tiên lấy từ Session State
    cv_text = st.session_state.get("stored_cv_text", "")
    jd_text = st.session_state.get("stored_jd_text", "")
    
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
    """
    Gợi ý các vị trí việc làm phù hợp dựa trên CV đã lưu (Internal Knowledge).
    """
    cv_text = st.session_state.get("stored_cv_text", "")
    
    if not cv_text:
        return "ERROR: Chưa có CV. Vui lòng phân tích CV trước."
    
    # Trả về CV để agent tự phân tích
    return f"CV_CONTENT_FOR_ANALYSIS:\n{cv_text[:2000]}"


@tool
def tool_suggest_cv_improvements(dummy: str = "run") -> str:
    """
    Đề xuất chỉnh sửa CV dựa trên nội dung CV và JD đã lưu.
    Output: Bản CV đã được chỉnh sửa/cải thiện dạng TEXT với format rõ ràng.
    Agent sẽ phân tích và đưa ra CV mới tối ưu hơn.
    """
    cv_text = st.session_state.get("stored_cv_text", "")
    jd_text = st.session_state.get("stored_jd_text", "")
    
    if not cv_text:
        return "ERROR: Chưa có CV. Vui lòng phân tích CV trước."
    
    # Sử dụng GPT-4o để phân tích và đề xuất chỉnh sửa
    vision_llm = ChatOpenAI(model="gpt-4o", temperature=0.3)
    
    jd_context = f"\n\nJD MỤC TIÊU:\n{jd_text[:2000]}" if jd_text else ""
    
    prompt = f"""Bạn là chuyên gia tư vấn CV chuyên nghiệp. Hãy phân tích CV sau và ĐỀ XUẤT BẢN CV MỚI ĐÃ ĐƯỢC CHỈNH SỬA.

CV HIỆN TẠI:
{cv_text[:3500]}
{jd_context}

YÊU CẦU:
1. Phân tích điểm mạnh/yếu của CV hiện tại
2. Đề xuất CỤ THỂ những gì cần thay đổi
3. VIẾT LẠI HOÀN CHỈNH bản CV mới với format chuẩn:

OUTPUT FORMAT:
## 📋 PHÂN TÍCH CV HIỆN TẠI
[Điểm mạnh và điểm yếu]

## ✏️ ĐỀ XUẤT CHỈNH SỬA
[Liệt kê cụ thể những thay đổi]

## 📄 CV MỚI ĐÃ CHỈNH SỬA
```
[Nội dung CV đã được viết lại hoàn chỉnh với format đẹp]
```

## 💡 GHI CHÚ QUAN TRỌNG
[Lời khuyên thêm]
"""
    
    try:
        response = vision_llm.invoke([HumanMessage(content=prompt)])
        return response.content
    except Exception as e:
        return f"ERROR: Không thể phân tích CV - {str(e)}"


@tool  
def tool_analyze_cv_layout(file_path: str) -> str:
    """
    Phân tích và đánh giá LAYOUT/BỐ CỤC của CV từ file ảnh hoặc PDF.
    Kiểm tra: format, spacing, font, màu sắc, cấu trúc sections, tính chuyên nghiệp.
    
    Input: đường dẫn file ảnh (PNG/JPG) hoặc PDF
    Output: Đánh giá chi tiết về layout và đề xuất cải thiện
    """
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
        
        analysis_prompt = """Bạn là chuyên gia đánh giá CV với kinh nghiệm 15 năm trong ngành tuyển dụng.
Hãy PHÂN TÍCH CHI TIẾT LAYOUT/BỐ CỤC của CV này.

TIÊU CHÍ ĐÁNH GIÁ (Chấm điểm 1-10 cho mỗi mục):

1. 📐 BỐ CỤC TỔNG THỂ (Layout Structure)
   - Cân đối không gian trắng
   - Phân chia sections rõ ràng
   - Dễ đọc, scan nhanh được

2. 🔤 TYPOGRAPHY (Font chữ)
   - Font có chuyên nghiệp không
   - Size chữ phù hợp không
   - Hierarchy rõ ràng (tiêu đề, nội dung)

3. 🎨 THIẾT KẾ & MÀU SẮC
   - Màu sắc hài hòa, chuyên nghiệp
   - Có quá nhiều màu không
   - Phù hợp ngành nghề không

4. 📋 CẤU TRÚC SECTIONS
   - Thứ tự sections hợp lý không
   - Có đủ sections quan trọng không
   - Spacing giữa sections

5. 📊 TÍNH CHUYÊN NGHIỆP
   - Ấn tượng đầu tiên
   - ATS-friendly (máy đọc được)
   - Phù hợp tiêu chuẩn quốc tế

OUTPUT FORMAT:
## 🎯 ĐÁNH GIÁ LAYOUT CV

### Điểm Tổng: X/10

### Chi Tiết Đánh Giá:

| Tiêu Chí | Điểm | Nhận Xét |
|----------|------|----------|
| Bố cục tổng thể | X/10 | ... |
| Typography | X/10 | ... |
| Thiết kế & Màu sắc | X/10 | ... |
| Cấu trúc Sections | X/10 | ... |
| Tính chuyên nghiệp | X/10 | ... |

### ✅ ĐIỂM TỐT
[Liệt kê những gì làm đúng]

### ⚠️ CẦN CẢI THIỆN
[Liệt kê vấn đề cụ thể]

### 💡 ĐỀ XUẤT CHỈNH SỬA LAYOUT
[Hướng dẫn cụ thể cách sửa]

### 🎨 MẪU LAYOUT GỢI Ý
[Mô tả layout tối ưu cho CV này]
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
        return f"ERROR: Không thể phân tích layout - {str(e)}"


@tool
def tool_generate_improved_cv_image(dummy: str = "run") -> str:
    """
    Tạo mô tả chi tiết về CV mới với layout được cải thiện.
    Output: Mô tả visual chi tiết để người dùng có thể tự thiết kế hoặc dùng tool thiết kế.
    """
    cv_text = st.session_state.get("stored_cv_text", "")
    
    if not cv_text:
        return "ERROR: Chưa có CV. Vui lòng phân tích CV trước."
    
    vision_llm = ChatOpenAI(model="gpt-4o", temperature=0.3)
    
    prompt = f"""Dựa trên nội dung CV bên dưới, hãy tạo MÔ TẢ CHI TIẾT về một bản CV mới với LAYOUT CHUYÊN NGHIỆP.

NỘI DUNG CV:
{cv_text[:3000]}

TẠO MÔ TẢ VISUAL LAYOUT MỚI:

## 🖼️ MÔ TẢ LAYOUT CV MỚI

### Cấu trúc tổng thể:
- Kích thước: A4 (210 x 297mm)
- Margins: [cụ thể]
- Columns: [1 cột / 2 cột / layout khác]

### Header Section:
- Vị trí tên: [mô tả]
- Font tên: [gợi ý font + size]
- Thông tin liên hệ: [cách bố trí]

### Main Sections (theo thứ tự):
1. [Section 1] - Position: ... , Style: ...
2. [Section 2] - Position: ... , Style: ...
...

### Color Scheme:
- Primary: [màu chính]
- Secondary: [màu phụ]
- Text: [màu chữ]
- Background: [màu nền]

### Typography Guide:
- Heading font: [font + size]
- Body font: [font + size]
- Accent font: [nếu có]

### Visual Elements:
- Icons: [có/không, style]
- Lines/Dividers: [mô tả]
- Progress bars: [nếu có]

## 📝 NỘI DUNG CV ĐÃ TỐI ƯU
[Viết lại nội dung CV với format sẵn sàng để paste vào template]

## 🔗 TEMPLATE GỢI Ý
[Gợi ý các template Canva/Word/Google Docs phù hợp]
"""
    
    try:
        response = vision_llm.invoke([HumanMessage(content=prompt)])
        return response.content
    except Exception as e:
        return f"ERROR: Không thể tạo mô tả CV - {str(e)}"

def initialize_agent():
    """Khởi tạo Agent."""
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
        tool_generate_improved_cv_image
    ]
    
    system_message = """Bạn là AI Recruitment Expert chuyên nghiệp.

NHIỆM VỤ:
- Phân tích CV/JD, tính điểm, so sánh kỹ năng.
- Gợi ý việc làm:
  1. Gợi ý dựa trên kiến thức nội tại (Phân tích chung).
  2. TÌM VIỆC THỰC TẾ ONLINE: Nếu người dùng yêu cầu tìm việc đang tuyển hoặc tìm link thực tế, hãy dùng 'tool_find_jobs_online'.

QUY TRÌNH TÌM VIỆC ONLINE:
1. Đọc nội dung CV trong bộ nhớ để xác định: Vị trí (Title), Kỹ năng chính (Skills) và Địa điểm (nếu có).
2. Tạo câu truy vấn tìm kiếm tối ưu. Ví dụ: "Tuyển dụng [Vị trí] [Kỹ năng] tại [Địa điểm]".
3. Gọi 'tool_find_jobs_online' với câu truy vấn đó.
4. Trả về kết quả kèm Link cho người dùng.
5. ĐÁNH GIÁ TRẠNG THÁI PHỎNG VẤN: Với mỗi job, đánh giá khả năng được gọi phỏng vấn (Cao/Trung bình/Thấp).

TOOLS MỚI:
- tool_suggest_cv_improvements: Đề xuất chỉnh sửa CV và viết lại CV mới tối ưu hơn.
- tool_analyze_cv_layout: Phân tích layout/bố cục CV từ file ảnh, đánh giá tính chuyên nghiệp.
- tool_generate_improved_cv_image: Tạo mô tả visual chi tiết cho CV mới với layout đẹp.

QUAN TRỌNG:
- Với file: Dùng tool_extract_text_from_file.
- Luôn lưu CV/JD sau khi trích xuất.
- Khi đề xuất chỉnh sửa CV: Dùng tool_suggest_cv_improvements.
- Khi cần đánh giá layout CV: Dùng tool_analyze_cv_layout với đường dẫn file.
- Trả lời tiếng Việt, trình bày đẹp, rõ ràng."""
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_message),
        MessagesPlaceholder(variable_name="chat_history"),
        ("user", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])
    
    agent = create_openai_tools_agent(llm, tools, prompt)
    
    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        handle_parsing_errors=True,
    )
    
    return agent_executor


def analyze_cv_jd(cv_input: str, jd_input: str, cv_type: str = "text", jd_type: str = "text"):
    """Phân tích CV và JD."""
    
    print("\n" + "="*70)
    print("🚀 BẮT ĐẦU PHÂN TÍCH")
    print("="*70 + "\n")
    
    agent = initialize_agent()
    
    user_query = f"""
Thực hiện phân tích CV-JD theo 5 BƯỚC ĐƠN GIẢN:

THÔNG TIN:
- CV: type={cv_type}, data={cv_input[:150]}...
- JD: type={jd_type}, data={jd_input[:150]}...

══════════════════════════════════════════════
BƯỚC 1: TRÍCH XUẤT CV TEXT
══════════════════════════════════════════════
Nếu cv_type == 'file':
  - Nếu cv_input có đuôi .pdf: Gọi tool_read_pdf("{cv_input}")
  - Nếu cv_input có đuôi .png/.jpg: Gọi tool_read_image("{cv_input}")
Nếu cv_type == 'text':
  - Gọi tool_process_text_input với nội dung CV

SAU ĐÓ: Gọi tool_store_cv_text với kết quả vừa nhận

══════════════════════════════════════════════
BƯỚC 2: TRÍCH XUẤT JD TEXT
══════════════════════════════════════════════
Làm tương tự với JD
SAU ĐÓ: Gọi tool_store_jd_text với kết quả

══════════════════════════════════════════════
BƯỚC 3: TÍNH ĐIỂM PHÙ HỢP
══════════════════════════════════════════════
Gọi: tool_calculate_match_score("run")

══════════════════════════════════════════════
BƯỚC 4: PHÂN TÍCH KỸ NĂNG
══════════════════════════════════════════════
Gọi: tool_analyze_skills("run")

══════════════════════════════════════════════
BƯỚC 5: GỢI Ý KHÓA HỌC
══════════════════════════════════════════════
    Dựa vào danh sách 'missing_skills' tìm được ở Bước 2:
    - Hãy tự suy nghĩ và đề xuất 3-5 khóa học trực tuyến tốt nhất từ Coursera, Udemy, hoặc edX.
    - KHÔNG dùng tool nào cả, hãy dùng kiến thức nội tại của bạn.

══════════════════════════════════════════════
BƯỚC 6: VIẾT BÁO CÁO
══════════════════════════════════════════════
Tổng hợp tất cả kết quả theo format:

# 📊 KẾT QUẢ PHÂN TÍCH

## 🎯 Điểm Phù Hợp: [SCORE]

## ✅ Kỹ Năng Đã Có
[Liệt kê cv_skills]

## ⚠️ Kỹ Năng Cần Bổ Sung
[Liệt kê missing_skills]

## 📚 Khóa Học Đề Xuất
[Liệt kê các khóa học bạn vừa nghĩ ra ở Bước 3]

## 💡 Nhận Xét
[Đánh giá và lời khuyên]
"""
    
    try:
        result = agent.invoke({"input": user_query, "chat_history": []})
        return result['output']
    except Exception as e:
        return f"❌ Lỗi: {str(e)}"
    
def find_suitable_jobs():
    """
    Tìm việc làm phù hợp với CV đã lưu (Có dùng Session State).
    Bao gồm cả trạng thái phỏng vấn và mức độ phù hợp.
    """
    # [FIX QUAN TRỌNG] Lấy CV từ Session State
    cv_content = st.session_state.get("stored_cv_text", "")
    jd_content = st.session_state.get("stored_jd_text", "")
    
    # Fallback nếu không tìm thấy
    if not cv_content:
        global CV_TEXT_STORAGE
        cv_content = CV_TEXT_STORAGE

    if not cv_content:
        return "❌ Chưa có dữ liệu CV. Vui lòng quay lại tab 'Phân Tích CV-JD' và thực hiện phân tích CV trước để hệ thống ghi nhớ dữ liệu!"
    
    print("\n🔍 TÌM VIỆC LÀM PHÙ HỢP...\n")
    
    agent = initialize_agent()
    
    # Thêm context JD nếu có để đánh giá trạng thái phỏng vấn
    jd_context = ""
    if jd_content:
        jd_context = f"""
JD ĐÃ PHÂN TÍCH TRƯỚC ĐÓ:
{jd_content[:2000]}
"""
    
    # [QUAN TRỌNG] Truyền nội dung CV thực tế vào Prompt
    query = f"""
Dựa vào nội dung CV bên dưới, hãy thực hiện các việc sau:
1. Phân tích hồ sơ để gợi ý hướng đi (ngắn gọn).
2. Sử dụng 'tool_find_jobs_online' để tìm kiếm và LIỆT KÊ ít nhất 5 công việc thực tế đang tuyển dụng trên mạng (LinkedIn, TopCV, VietnamWorks, CareerBuilder...).
3. QUAN TRỌNG: Đánh giá TRẠNG THÁI PHỎNG VẤN cho mỗi vị trí dựa trên mức độ phù hợp của CV với JD.

NỘI DUNG CV:
{cv_content[:4000]}
{jd_context}

YÊU CẦU OUTPUT:
# 💼 GỢI Ý VIỆC LÀM

## 🔍 Phân Tích Nhanh
[Nhận xét ngắn về thế mạnh của ứng viên]

## 🎯 ĐÁNH GIÁ KHẢ NĂNG PHỎNG VẤN
Dựa trên CV và các yêu cầu thị trường, đánh giá:
- **Khả năng được gọi phỏng vấn:** [Cao/Trung bình/Thấp] - [Lý do]
- **Điểm mạnh khi phỏng vấn:** [Liệt kê 2-3 điểm]
- **Cần chuẩn bị thêm:** [Liệt kê những gì cần chuẩn bị]

## 🌐 Các Công Việc Đang Tuyển (Tìm từ Internet)
Với mỗi công việc, đánh giá chi tiết:

### 1. [Tên Vị Trí] - [Tên Công Ty/Nguồn]
   - 🔗 **Link:** [URL]
   - 📊 **Mức độ phù hợp:** [XX%]
   - 📞 **TRẠNG THÁI PHỎNG VẤN:** 
     - 🟢 **Khả năng được gọi PV:** [Cao/Trung bình/Thấp]
     - 📝 **Yêu cầu khớp:** [Liệt kê skills/kinh nghiệm khớp]
     - ⚠️ **Yêu cầu thiếu:** [Liệt kê những gì còn thiếu]
     - 💡 **Tips chuẩn bị PV:** [Gợi ý ngắn gọn]

### 2. [Tên Vị Trí] ...
...

## 📋 TỔNG KẾT TRẠNG THÁI ỨNG TUYỂN
| Vị Trí | Công Ty | Khả Năng PV | Ưu Tiên |
|--------|---------|-------------|---------|
| ... | ... | 🟢/🟡/🔴 | 1/2/3 |

## 💡 LỜI KHUYÊN CHUẨN BỊ PHỎNG VẤN
[Các bước chuẩn bị cụ thể cho ứng viên]
"""
    
    try:
        # Truyền chat_history rỗng
        result = agent.invoke({"input": query, "chat_history": []})
        return result['output']
    except Exception as e:
        return f"❌ Lỗi: {str(e)}"

def chat_with_agent(user_message: str):
    """
    Chat với agent với ngữ cảnh đầy đủ (CV & JD content) và Lịch sử chat.
    """
    agent = initialize_agent()
    
    # Lấy dữ liệu từ Session State
    cv_text = st.session_state.get("stored_cv_text", "")
    jd_text = st.session_state.get("stored_jd_text", "")
    chat_history = st.session_state.get("chat_history", [])

    context_data = ""
    if cv_text:
        context_data += f"\n=== NỘI DUNG CV CỦA USER ===\n{cv_text[:3000]}\n============================\n"
    else:
        context_data += "\n[Hệ thống: Chưa có dữ liệu CV.]\n"

    if jd_text:
        context_data += f"\n=== NỘI DUNG JD ===\n{jd_text[:3000]}\n============================\n"

    # Format lại lịch sử chat để đưa vào prompt (dạng text dễ hiểu cho model)
    history_text = "\n".join(chat_history[-6:]) # Chỉ lấy 6 tin nhắn gần nhất

    full_query = f"""
THÔNG TIN NGỮ CẢNH:
{context_data}

LỊCH SỬ TRÒ CHUYỆN GẦN ĐÂY:
{history_text}

CÂU HỎI MỚI CỦA USER:
{user_message}

YÊU CẦU:
- Trả lời user dựa trên ngữ cảnh CV/JD (nếu có).
- Nếu user yêu cầu tìm việc, nhắc user dùng tab "Tìm Việc Làm" hoặc dùng tool_find_jobs_online nếu bạn muốn.
"""

    try:
        result = agent.invoke({
            "input": full_query,
            "chat_history": [] # Ta đã tự handle history ở trên
        })
        
        output_text = result['output']
        
        # [FIX QUAN TRỌNG] Lưu lịch sử vào Session State
        st.session_state["chat_history"].append(f"User: {user_message}")
        st.session_state["chat_history"].append(f"AI: {output_text}")
        
        return output_text
    except Exception as e:
        return f"❌ Lỗi: {str(e)}"
