import os
import re
import tempfile
from typing import Optional, Tuple

import streamlit as st
from dotenv import load_dotenv

load_dotenv()
from agent import (
    analyze_cv_jd,
    find_suitable_jobs,
    chat_with_agent,
    initialize_agent,
    tool_extract_text_from_file,
    tool_process_text_input,
    tool_store_cv_text,
)
from services.docx_generator import create_docx_from_text, extract_rewritten_cv_text

st.set_page_config(page_title="AI Resume Analyzer", page_icon="🕵️‍♂️", layout="wide")

st.markdown("""
<style>
    .main { background-color: #f0f2f6; }
    h1 { color: #2e86c1; }
    .stButton>button {
        width: 100%; background-color: #2e86c1; color: white; font-weight: bold; padding: 10px;
    }
    .stButton>button:hover { background-color: #1a5276; color: white; }
    .error-box { background-color: #ffebee; border-left: 5px solid #f44336; padding: 15px; margin: 10px 0; border-radius: 5px; }
    .warning-box { background-color: #fff3e0; border-left: 5px solid #ff9800; padding: 15px; margin: 10px 0; border-radius: 5px; }
    .info-box { background-color: #e3f2fd; border-left: 5px solid #2196f3; padding: 15px; margin: 10px 0; border-radius: 5px; }
    .success-box { background-color: #e8f5e9; border-left: 5px solid #4caf50; padding: 15px; margin: 10px 0; border-radius: 5px; }
</style>
""", unsafe_allow_html=True)

def save_uploaded_file(uploaded_file, session_key=None):
    try:
        suffix = "." + uploaded_file.name.split('.')[-1]
        if session_key:
            old_path = st.session_state.get(session_key)
            if old_path and os.path.exists(old_path):
                try:
                    os.unlink(old_path)
                except Exception:
                    pass
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            path = tmp_file.name
        if session_key:
            st.session_state[session_key] = path
            st.session_state[f"{session_key}_name"] = uploaded_file.name
            st.session_state[f"{session_key}_type"] = uploaded_file.type
        return path
    except Exception as e:
        st.error(f"Lỗi khi lưu file: {e}")
        return None


def store_cv_from_file(file_path: str) -> bool:
    """Trích xuất & lưu nội dung CV từ file đã upload."""
    if not file_path or not os.path.exists(file_path):
        return False

    try:
        raw_output = tool_extract_text_from_file.invoke({"file_path": file_path})
        if not raw_output or (
            isinstance(raw_output, str) and raw_output.startswith("ERROR")
        ):
            st.warning("⚠️ Không thể trích xuất nội dung từ file CV. Vui lòng thử lại.")
            return False

        processed_output = tool_process_text_input.invoke({"raw_text": raw_output})
        cv_text_result = (
            processed_output if isinstance(processed_output, str) else str(processed_output)
        )
        st.session_state["stored_cv_text"] = cv_text_result
        st.session_state["last_cv_text"] = cv_text_result
        try:
            tool_store_cv_text.invoke({"cv_text": cv_text_result})
        except Exception:
            pass
        return True
    except Exception as exc:
        st.warning(f"⚠️ Lỗi khi xử lý file CV: {exc}")
        return False


def ensure_cv_text_in_session() -> str:
    """Đảm bảo session_state đã có CV text, ưu tiên dùng file đã upload trước đó."""
    cv_text = st.session_state.get("stored_cv_text", "")
    if cv_text:
        return cv_text

    cv_file_path = st.session_state.get("last_cv_file_path")
    if cv_file_path and store_cv_from_file(cv_file_path):
        return st.session_state.get("stored_cv_text", "")

    return ""


def extract_rewritten_cv_text(agent_output: str) -> str:
    """Lấy phần CV đã viết lại từ phản hồi của agent."""
    if not agent_output:
        return ""

    code_block = re.search(r"```(?:[\w-]+)?\n(.*?)```", agent_output, re.DOTALL)
    if code_block:
        return code_block.group(1).strip()

    new_cv_section = re.search(
        r"##\s*[^\n]*CV[^\n]*\n```?\s*(.*?)\s*```?",
        agent_output,
        re.DOTALL | re.IGNORECASE,
    )
    if new_cv_section:
        return new_cv_section.group(1).strip()

    return agent_output.strip()


FONT_PAIR_CANDIDATES = [
    ("arial.ttf", "arialbd.ttf"),
    ("segoeui.ttf", "segoeuib.ttf"),
    ("tahoma.ttf", "tahomabd.ttf"),
    ("calibri.ttf", "calibrib.ttf"),
    ("times.ttf", "timesbd.ttf"),
    ("DejaVuSans.ttf", "DejaVuSans-Bold.ttf"),
]

FONT_SEARCH_DIRS = [
    os.getenv("CV_PDF_FONT_DIR"),
    "C:\\Windows\\Fonts",
    "C:\\Windows\\fonts",
    "/usr/share/fonts/truetype/dejavu",
    "/usr/share/fonts/truetype",
    "/usr/share/fonts",
    "/Library/Fonts",
]


def _locate_font_file(filename: str) -> Optional[str]:
    for directory in filter(None, FONT_SEARCH_DIRS):
        candidate = os.path.join(directory, filename)
        if os.path.exists(candidate):
            return candidate
    return None


def _get_font_paths() -> Tuple[Optional[str], Optional[str]]:
    env_regular = os.getenv("CV_PDF_FONT_PATH")
    env_bold = os.getenv("CV_PDF_FONT_BOLD_PATH")

    if env_regular and os.path.exists(env_regular):
        regular = env_regular
        if env_bold and os.path.exists(env_bold):
            bold = env_bold
        else:
            bold = None
        return regular, bold

    for regular_name, bold_name in FONT_PAIR_CANDIDATES:
        regular_path = _locate_font_file(regular_name)
        if not regular_path:
            continue
        bold_path = _locate_font_file(bold_name) or regular_path
        return regular_path, bold_path

    return None, None


def create_docx_from_text(text: str) -> bytes:
    """Tạo DOCX CV đẹp mắt từ chuỗi văn bản."""
    sanitized = (text or "").strip()
    if not sanitized:
        raise ValueError("Không có nội dung để xuất ra DOCX.")

    removal_phrases = [
        "Dưới đây là bản CV đã được chỉnh sửa và tối ưu hóa cho bạn:",
        "Dưới đây là bản CV đã được chỉnh sửa và tối ưu hóa bằng tiếng Anh:",
        "Dưới đây là bản CV đã được chỉnh sửa và tối ưu hóa bằng tiếng Anh.",
        "• **Ghi chú quan trọng**:",
        "• Định dạng CV chuyên nghiệp với font chữ và kích thước thống nhất.",
        "• Cập nhật thường xuyên với các kỹ năng và kinh nghiệm mới nhất.",
        "• Tùy chỉnh nội dung CV để phù hợp với yêu cầu của từng công việc cụ thể.",
        "• Hy vọng bản CV mới này sẽ giúp bạn nổi bật hơn trong mắt nhà tuyển dụng!",
        "**Ghi chú quan trọng**:",
        "**Ghi chú:**",
        "Ghi chú:",
        "• Ghi chú:",
        "## 💡 Important Notes",
        "## Important Notes",
        "### Important Notes",
        "**Important Notes:**",
        "Important Notes:",
    ]

    for phrase in removal_phrases:
        sanitized = sanitized.replace(phrase, "")

    sanitized_lines = []
    skip_section = False
    for line in sanitized.splitlines():
        stripped_line = line.strip()
        if not stripped_line:
            continue
        lowered = stripped_line.lower()
        if "important note" in lowered or "ghi chú" in lowered:
            skip_section = True
            continue
        if skip_section:
            if lowered.startswith("##") or lowered.startswith("###"):
                skip_section = False
            else:
                continue
        sanitized_lines.append(stripped_line)

    sanitized = "\n".join(sanitized_lines)

    # Parse basic formatting from markdown-like text
    lines = sanitized.splitlines()
    sections = []
    current_section = {"title": "", "items": []}
    bullet_pattern = re.compile(r"^\s*[-•]\s+")

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        if stripped in {"---", "***"}:
            continue

        if stripped.startswith("### "):
            if current_section["title"] or current_section["items"]:
                sections.append(current_section)
            current_section = {"title": stripped[4:].strip(), "items": []}
        elif stripped.startswith("## "):
            if current_section["title"] or current_section["items"]:
                sections.append(current_section)
            current_section = {"title": stripped[3:].strip(), "items": []}
        elif stripped.startswith("**") and stripped.endswith("**") and len(stripped) <= 80:
            if current_section["title"] or current_section["items"]:
                sections.append(current_section)
            current_section = {"title": stripped.strip("* "), "items": []}
        elif bullet_pattern.match(stripped):
            current_section["items"].append(bullet_pattern.sub("", stripped))
        else:
            current_section["items"].append(stripped)

    if current_section["title"] or current_section["items"]:
        sections.append(current_section)

    def _shade_cell(cell, color_hex: str):
        tc_pr = cell._tc.get_or_add_tcPr()
        shd = OxmlElement("w:shd")
        shd.set(qn("w:fill"), color_hex)
        shd.set(qn("w:color"), "auto")
        shd.set(qn("w:val"), "clear")
        tc_pr.append(shd)

    def _add_divider(document: Document, color_hex: str = "CBD3E3"):
        p = document.add_paragraph()
        p_format = p.paragraph_format
        p_format.space_before = Pt(6)
        p_format.space_after = Pt(6)
        pPr = p._p.get_or_add_pPr()
        pBdr = OxmlElement("w:pBdr")
        bottom = OxmlElement("w:bottom")
        bottom.set(qn("w:val"), "single")
        bottom.set(qn("w:sz"), "12")
        bottom.set(qn("w:space"), "1")
        bottom.set(qn("w:color"), color_hex)
        pBdr.append(bottom)
        pPr.append(pBdr)

    doc = Document()
    section = doc.sections[0]
    section.top_margin = Inches(0.7)
    section.bottom_margin = Inches(0.7)
    section.left_margin = Inches(0.8)
    section.right_margin = Inches(0.6)

    style_normal = doc.styles["Normal"]
    style_normal.font.name = "Arial"
    style_normal.font.size = Pt(11)
    style_normal._element.rPr.rFonts.set(qn("w:eastAsia"), "Arial")

    heading_style = doc.styles["Heading 1"]
    heading_style.font.name = "Arial"
    heading_style._element.rPr.rFonts.set(qn("w:eastAsia"), "Arial")
    heading_style.font.size = Pt(16)
    heading_style.font.bold = True

    subheading_style = doc.styles["Heading 2"]
    subheading_style.font.name = "Arial"
    subheading_style._element.rPr.rFonts.set(qn("w:eastAsia"), "Arial")
    subheading_style.font.size = Pt(13)
    subheading_style.font.bold = True

    primary_color = RGBColor(28, 58, 112)
    accent_color = RGBColor(255, 255, 255)

    header_info = sections.pop(0) if sections else {"title": "YOUR NAME", "items": []}

    contacts = header_info.get("items", [])
    primary_contacts = [line for line in contacts if any(key in line.lower() for key in ["phone", "mail", "email", "linkedin", "address", "địa", "số"])]
    if not primary_contacts:
        primary_contacts = contacts[:4]

    header_table = doc.add_table(rows=1 + max(len(primary_contacts), 1), cols=1)
    header_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    header_table.autofit = False
    header_table.columns[0].width = Inches(7.3)

    name_cell = header_table.cell(0, 0)
    _shade_cell(name_cell, "1C3A70")
    name_cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER

    name_para = name_cell.paragraphs[0]
    name_para.alignment = WD_PARAGRAPH_ALIGNMENT.LEFT
    name_para.paragraph_format.space_before = Pt(10)
    name_para.paragraph_format.space_after = Pt(4)
    name_run = name_para.add_run(header_info["title"].upper())
    name_run.font.size = Pt(26)
    name_run.font.bold = True
    name_run.font.color.rgb = accent_color

    if primary_contacts:
        for idx, contact_line in enumerate(primary_contacts, start=1):
            contact_cell = header_table.cell(idx, 0)
            _shade_cell(contact_cell, "26477F")
            contact_cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            contact_para = contact_cell.paragraphs[0]
            contact_para.alignment = WD_PARAGRAPH_ALIGNMENT.LEFT
            contact_para.paragraph_format.space_before = Pt(4)
            contact_para.paragraph_format.space_after = Pt(4)
            contact_run = contact_para.add_run(contact_line)
            contact_run.font.size = Pt(11.5)
            contact_run.font.bold = True
            contact_run.font.color.rgb = accent_color

    doc.add_paragraph()

    if sections:
        summary_section = sections[0]
        if summary_section["title"].lower().startswith("mục tiêu") or "summary" in summary_section["title"].lower():
            sections.pop(0)
            summary_para = doc.add_paragraph(summary_section["title"])
            summary_para.style = doc.styles["Heading 2"]
            summary_para.runs[0].font.color.rgb = primary_color
            for item in summary_section["items"]:
                para = doc.add_paragraph(item)
                para.paragraph_format.space_after = Pt(6)

            doc.add_paragraph()

    for index, section_data in enumerate(sections):
        _add_divider(doc)
        if section_data["title"]:
            if "ghi chú" in section_data["title"].lower():
                continue
            if "important note" in section_data["title"].lower():
                continue
            heading_para = doc.add_heading(section_data["title"], level=1)
            heading_para.alignment = WD_PARAGRAPH_ALIGNMENT.LEFT
            for run in heading_para.runs:
                run.font.color.rgb = primary_color
                run.font.size = Pt(14)

        for item in section_data["items"]:
            para = doc.add_paragraph(style="List Bullet")
            para_format = para.paragraph_format
            para_format.space_after = Pt(2)
            para_format.left_indent = Inches(0.25)

            if ":" in item:
                label, remainder = item.split(":", 1)
                label_run = para.add_run(f"{label.strip()}: ")
                label_run.font.bold = True
                label_run.font.color.rgb = primary_color
                label_run.font.name = "Arial"
                label_run._element.rPr.rFonts.set(qn("w:eastAsia"), "Arial")
                label_run.font.size = Pt(11)

                text_run = para.add_run(remainder.strip())
                text_run.font.name = "Arial"
                text_run._element.rPr.rFonts.set(qn("w:eastAsia"), "Arial")
                text_run.font.size = Pt(11)
            else:
                run = para.add_run(item)
                run.font.name = "Arial"
                run._element.rPr.rFonts.set(qn("w:eastAsia"), "Arial")
                run.font.size = Pt(11)

        doc.add_paragraph()

    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()


# Session state cho chatbox
if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []

st.title("🕵️‍♂️ AI Resume & Career Analyzer")
st.caption("Phát triển bởi Võ Phước Thịnh, Liên Phúc Thịnh và Lê Ngọc Thanh Toàn - The Unwithering Trio")
st.markdown("---")

if not os.getenv("OPENAI_API_KEY"):
    st.error("⚠️ Chưa tìm thấy OPENAI_API_KEY trong file .env.")
    st.stop()

# TABS
tab1, tab2, tab3, tab4 = st.tabs(["📊 Phân Tích CV-JD", "💼 Tìm Việc Làm", "✏️ Cải Thiện CV", "💬 Chat với AI"])

with tab1:
    st.header("📊 Phân Tích CV và JD")
    
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📄 CV")
        cv_option = st.radio("Nguồn CV:", ["Nhập văn bản (Text)", "Upload File (PDF/Ảnh)"], key="cv_opt")
        cv_input = None
        cv_type = "text"
        
        if cv_option == "Upload File (PDF/Ảnh)":
            cv_type = "file"
            uploaded_cv = st.file_uploader("Tải lên CV", type=["pdf", "png", "jpg", "jpeg"], key="cv_file")
            if uploaded_cv:
                cv_input = save_uploaded_file(uploaded_cv, session_key="last_cv_file_path")
                st.success(f"✅ Đã tải: {uploaded_cv.name}")
                if uploaded_cv.type.startswith('image'):
                    st.image(uploaded_cv, caption="Preview CV", use_column_width=True)
                elif uploaded_cv.type == "application/pdf":
                    st.info("📄 File PDF đã sẵn sàng để phân tích")
                if cv_input:
                    store_cv_from_file(cv_input)
        else:
            cv_input = st.text_area("Nội dung CV:", height=300, 
                                    placeholder="Paste nội dung CV vào đây...")
            if cv_input:
                st.session_state["stored_cv_text"] = cv_input
                st.session_state["last_cv_text"] = cv_input
                try:
                    tool_store_cv_text.invoke({"cv_text": cv_input})
                except Exception:
                    pass
                st.session_state["last_cv_text"] = cv_input
    
    with col2:
        st.subheader("💼 JD")
        jd_option = st.radio("Nguồn JD:", ["Nhập văn bản (Text)", "Upload File (PDF/Ảnh)"], key="jd_opt")
        jd_input = None
        jd_type = "text"
        
        if jd_option == "Upload File (PDF/Ảnh)":
            jd_type = "file"
            uploaded_jd = st.file_uploader("Tải lên JD", type=["pdf", "png", "jpg", "jpeg"], key="jd_file")
            if uploaded_jd:
                jd_input = save_uploaded_file(uploaded_jd, session_key="last_jd_file_path")
                st.success(f"✅ Đã tải: {uploaded_jd.name}")
                if uploaded_jd.type.startswith('image'):
                    st.image(uploaded_jd, caption="Preview JD", use_column_width=True)
                elif uploaded_jd.type == "application/pdf":
                    st.info("📄 File PDF đã sẵn sàng")
        else:
            jd_input = st.text_area("Nội dung JD:", height=300,
                                    placeholder="Paste nội dung JD vào đây...")
            if jd_input:
                st.session_state["stored_jd_text"] = jd_input
    
    st.markdown("---")
    analyze_btn = st.button("🚀 PHÂN TÍCH", type="primary", use_container_width=True)
    
    if analyze_btn:
        if not cv_input or not jd_input:
            st.error("⚠️ Vui lòng cung cấp đầy đủ CV và JD!")
        else:
            try:
                with st.spinner("🤖 AI đang phân tích... Vui lòng đợi..."):
                    result = analyze_cv_jd(cv_input=cv_input, jd_input=jd_input, 
                                          cv_type=cv_type, jd_type=jd_type)
                    
                    if "ERROR:" in result or "❌" in result:
                        st.markdown(f"""
                        <div class="error-box">
                        <h3>❌ Lỗi khi xử lý</h3>
                        <p>{result}</p>
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.success("✅ Phân tích hoàn tất!")
                        st.markdown("---")
                        st.markdown(result)
            except Exception as e:
                st.error(f"❌ Lỗi: {e}")
            finally:
                if cv_type == "file" and cv_input and os.path.exists(cv_input):
                    if st.session_state.get("last_cv_file_path") != cv_input:
                        try:
                            os.unlink(cv_input)
                        except Exception:
                            pass
                if jd_type == "file" and jd_input and os.path.exists(jd_input):
                    if st.session_state.get("last_jd_file_path") != jd_input:
                        try:
                            os.unlink(jd_input)
                        except Exception:
                            pass

# ==================== TAB 2: TÌM VIỆC ====================
with tab2:
    st.header("💼 Tìm Việc Làm Phù Hợp")
    

    
    st.markdown("---")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        if st.button("🔍 TÌM VIỆC PHÙ HỢP NGAY", type="primary", use_container_width=True):
            with st.spinner("🤖 AI đang phân tích CV và tìm việc phù hợp..."):
                try:
                    result = find_suitable_jobs()
                    
                    if "❌" in result:
                        st.markdown(f"""
                        <div class="warning-box">
                        <h4>⚠️ Chưa thể tìm việc</h4>
                        <p>{result}</p>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        st.info("💡 **Hướng dẫn:** Hãy chuyển sang tab 'Phân Tích CV-JD' và phân tích CV trước!")
                    else:
                        st.markdown(result)
                        
                except Exception as e:
                    st.error(f"❌ Lỗi: {str(e)}")
    
    with col2:
        st.markdown("""
        <div class="success-box" style = "color: black;">
        <strong>📋 Bước thực hiện:</strong><br>
        1. Tab 1: Phân tích CV<br>
        2. Tab 2: Tìm việc<br>
        3. Tab 3: Hỏi đáp
        </div>
        """, unsafe_allow_html=True)
    
    # Thêm section tips
    st.markdown("---")
    st.markdown("### 💡 Mẹo Tìm Việc Hiệu Quả")
    
    tips_col1, tips_col2 = st.columns(2)
    
    with tips_col1:
        st.markdown("""
        **🎯 Chuẩn bị CV tốt:**
        - Liệt kê đầy đủ kỹ năng kỹ thuật
        - Ghi rõ số năm kinh nghiệm
        - Mô tả dự án cụ thể
        - Cập nhật công nghệ mới nhất
        """)
    
    with tips_col2:
        st.markdown("""
        **🚀 Sau khi có gợi ý:**
        - Tìm hiểu chi tiết về vị trí
        - Chuẩn bị kỹ năng còn thiếu
        - Networking trên LinkedIn
        - Cập nhật CV theo xu hướng
        """)

# ==================== TAB 3: CẢI THIỆN CV ====================
with tab3:
    st.header("✏️ Cải Thiện CV của Bạn")
    
    st.markdown("""
    <div class="info-box">
    <strong>🎯 Tính năng:</strong><br>
    • <strong>Đề xuất chỉnh sửa CV:</strong> AI phân tích và viết lại CV tối ưu hơn<br>
    • <strong>Kiểm tra Layout:</strong> Đánh giá bố cục, font, màu sắc của CV<br>
    • <strong>Tạo mô tả CV mới:</strong> Hướng dẫn thiết kế CV chuyên nghiệp
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Kiểm tra CV đã có chưa
    cv_available = bool(
        st.session_state.get("stored_cv_text")
        or st.session_state.get("last_cv_file_path")
    )
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📝 Đề Xuất Chỉnh Sửa CV")
        
        if cv_available:
            st.success("✅ Đã có CV trong hệ thống")
        else:
            st.warning("⚠️ Chưa có CV. Vui lòng phân tích CV ở Tab 1 trước.")
        
        if st.button("🚀 ĐỀ XUẤT CHỈNH SỬA CV", type="primary", use_container_width=True, disabled=not cv_available):
            cv_text_ready = ensure_cv_text_in_session()
            if not cv_text_ready:
                st.error("⚠️ Không tìm thấy CV đã upload. Vui lòng quay lại Tab 1 để tải hoặc phân tích CV.")
            else:
                with st.spinner("🤖 AI đang phân tích và viết lại CV..."):
                    try:
                        agent = initialize_agent()
                        cv_excerpt = cv_text_ready[:2000]
                        result = agent.invoke({
                            "input": (
                                "CV hiện tại của người dùng đã được lưu trong Session State với key 'stored_cv_text'. "
                                "Không yêu cầu người dùng upload lại file. "
                                "Dưới đây là nội dung CV (có thể đã được rút gọn):\n"
                                f"{cv_excerpt}\n\n"
                                "Hãy sử dụng trực tiếp tool_suggest_cv_improvements để phân tích và viết lại CV hoàn chỉnh. "
                                "Toàn bộ bản CV mới phải được trình bày bằng tiếng Anh."
                            ),
                            "chat_history": []
                        })
                        result_text = result.get("output", "")
                        st.markdown(result_text)

                        rewritten_cv_text = extract_rewritten_cv_text(result_text)
                        if rewritten_cv_text:
                            try:
                                docx_bytes = create_docx_from_text(rewritten_cv_text)
                            except Exception as docx_err:
                                st.warning(f"⚠️ Không thể tạo file DOCX tự động: {docx_err}")
                            else:
                                st.download_button(
                                    "⬇️ Tải CV đã chỉnh sửa (DOCX)",
                                    data=docx_bytes,
                                    file_name="cv_da_chinh_sua.docx",
                                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                    type="primary",
                                    key="download_rewritten_cv",
                                )
                        else:
                            st.info("ℹ️ Không tìm thấy nội dung CV mới trong phản hồi để tạo DOCX.")
                    except Exception as e:
                        st.error(f"❌ Lỗi: {str(e)}")
    
    with col2:
        st.subheader("🖼️ Tạo Mô Tả Layout CV Mới")
        
        if st.button("🎨 TẠO MÔ TẢ CV MỚI", type="secondary", use_container_width=True, disabled=not cv_available):
            cv_text_ready = ensure_cv_text_in_session()
            if not cv_text_ready:
                st.error("⚠️ Không tìm thấy CV đã upload. Vui lòng quay lại Tab 1 để tải hoặc phân tích CV.")
            else:
                with st.spinner("🤖 AI đang thiết kế layout CV mới..."):
                    try:
                        agent = initialize_agent()
                        cv_excerpt = cv_text_ready[:2000]
                        result = agent.invoke({
                            "input": (
                                "CV hiện tại của người dùng đã được lưu trong Session State với key 'stored_cv_text'. "
                                "Không yêu cầu người dùng upload lại file. "
                                "Dưới đây là nội dung CV (có thể đã được rút gọn):\n"
                                f"{cv_excerpt}\n\n"
                                "Hãy sử dụng trực tiếp tool_generate_improved_cv_image để tạo mô tả chi tiết về layout CV mới chuyên nghiệp."
                            ),
                            "chat_history": []
                        })
                        st.markdown(result['output'])
                    except Exception as e:
                        st.error(f"❌ Lỗi: {str(e)}")
    
    st.markdown("---")
    st.subheader("🔍 Kiểm Tra Layout CV (Từ File Ảnh)")
    
    st.markdown("""
    Upload ảnh CV của bạn để AI đánh giá:
    - Bố cục tổng thể
    - Typography (font chữ)
    - Thiết kế & Màu sắc
    - Cấu trúc sections
    - Tính chuyên nghiệp
    """)
    
    uploaded_cv_image = st.file_uploader(
        "📤 Upload ảnh CV (PNG/JPG/PDF)", 
        type=["png", "jpg", "jpeg", "pdf"], 
        key="cv_layout_file"
    )
    
    if uploaded_cv_image:
        # Hiển thị preview nếu là ảnh
        if uploaded_cv_image.type.startswith('image'):
            st.image(uploaded_cv_image, caption="Preview CV", width=400)
        else:
            st.info("📄 File PDF đã sẵn sàng để phân tích layout")
        
        if st.button("🔍 KIỂM TRA LAYOUT", type="primary", use_container_width=True):
            with st.spinner("🤖 AI đang đánh giá layout CV..."):
                try:
                    # Lưu file tạm
                    cv_file_path = save_uploaded_file(uploaded_cv_image)
                    
                    if cv_file_path:
                        agent = initialize_agent()
                        result = agent.invoke({
                            "input": f"Hãy sử dụng tool_analyze_cv_layout với file '{cv_file_path}' để phân tích và đánh giá layout CV này.",
                            "chat_history": []
                        })
                        st.markdown(result['output'])
                        
                        # Xóa file tạm
                        try:
                            os.unlink(cv_file_path)
                        except:
                            pass
                except Exception as e:
                    st.error(f"❌ Lỗi: {str(e)}")
    
    # Tips section
    st.markdown("---")
    st.markdown("### 💡 Mẹo Tạo CV Chuyên Nghiệp")
    
    tips_col1, tips_col2, tips_col3 = st.columns(3)
    
    with tips_col1:
        st.markdown("""
        **📐 Layout:**
        - Sử dụng 1-2 cột
        - Margins đều 1 inch
        - Khoảng trắng hợp lý
        - Độ dài 1-2 trang
        """)
    
    with tips_col2:
        st.markdown("""
        **🔤 Typography:**
        - Font: Arial, Calibri, Garamond
        - Size: 10-12pt cho body
        - Heading: 14-16pt, bold
        - Consistency là key
        """)
    
    with tips_col3:
        st.markdown("""
        **🎨 Design:**
        - Tối đa 2-3 màu
        - Màu trung tính + 1 accent
        - ATS-friendly format
        - Tránh graphics phức tạp
        """)

# ==================== TAB 4: CHATBOX ====================
with tab4:
    st.header("💬 Chat với AI Assistant")
    
    
    # Hiển thị lịch sử chat
    chat_container = st.container()
    
    with chat_container:
        for msg in st.session_state.chat_messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
    
    # Chat input
    user_input = st.chat_input("Nhập câu hỏi của bạn...")
    
    if user_input:
        # Thêm tin nhắn người dùng
        st.session_state.chat_messages.append({"role": "user", "content": user_input})
        
        # Hiển thị tin nhắn người dùng
        with st.chat_message("user"):
            st.markdown(user_input)
        
        # Gọi agent
        with st.chat_message("assistant"):
            with st.spinner("Đang suy nghĩ..."):
                try:
                    response = chat_with_agent(user_input)
                    st.markdown(response)
                    
                    # Lưu phản hồi
                    st.session_state.chat_messages.append({"role": "assistant", "content": response})
                    
                except Exception as e:
                    error_msg = f"❌ Lỗi: {str(e)}"
                    st.error(error_msg)
                    st.session_state.chat_messages.append({"role": "assistant", "content": error_msg})
        
        # Rerun để cập nhật UI
        st.rerun()
    
    # Quick actions
    st.markdown("---")
    st.markdown("#### 🎯 Câu Hỏi Gợi Ý")
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        if st.button("📊 Phân tích CV", use_container_width=True):
            user_input = "Hãy phân tích CV của tôi một cách chi tiết"
            st.session_state.chat_messages.append({"role": "user", "content": user_input})
            st.rerun()
    
    with col2:
        if st.button("✏️ Cải thiện CV", use_container_width=True):
            user_input = "Hãy đề xuất chỉnh sửa và viết lại CV của tôi"
            st.session_state.chat_messages.append({"role": "user", "content": user_input})
            st.rerun()
    
    with col3:
        if st.button("📚 Gợi ý học tập", use_container_width=True):
            user_input = "Đề xuất lộ trình học tập và khóa học phù hợp"
            st.session_state.chat_messages.append({"role": "user", "content": user_input})
            st.rerun()
    
    with col4:
        if st.button("💼 Tư vấn nghề nghiệp", use_container_width=True):
            user_input = "Cho tôi lời khuyên về sự nghiệp và phát triển"
            st.session_state.chat_messages.append({"role": "user", "content": user_input})
            st.rerun()
    
    with col5:
        if st.button("🔄 Xóa chat", type="secondary", use_container_width=True):
            st.session_state.chat_messages = []
            st.rerun()

st.markdown("---")
st.caption("Phát triển bởi Võ Phước Thịnh, Liên Phúc Thịnh và Lê Ngọc Thanh Toàn - Powered by LangChain & GPT-4o")
st.caption("Version 3.0 - GPT-4o Vision OCR • Job Search • CV Improvement • Layout Analysis • Interview Status • AI Chat Assistant")