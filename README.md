# 🕵️‍♂️ AI Resume Analyzer v3.0

**Phân tích CV thông minh với AI | Tìm việc làm | Cải thiện CV**

Phát triển bởi: **Võ Phước Thịnh, Liên Phúc Thịnh & Lê Ngọc Thanh Toàn** - The Unwithering Trio

---

## 📋 Tổng Quan

AI Resume Analyzer là công cụ phân tích CV và tìm việc làm sử dụng GPT-4o. Hệ thống có 2 phiên bản:

### 🎯 Streamlit Version (Simple)
- Giao diện đơn giản, dễ sử dụng
- Chạy bằng 1 command

### ⚡ React + FastAPI Version (Advanced)  
- Giao diện hiện đại, animation mượt
- Backend API riêng biệt
- Hiệu suất cao hơn

---

## 🚀 Cài Đặt

### Prerequisites
- Python 3.10+
- Node.js 18+ (cho React frontend)
- OpenAI API Key
- Tavily API Key (optional, cho tìm kiếm việc làm)

### 1. Clone và cài đặt dependencies

```bash
cd "D:\CS311 Project - Copy\data"
pip install -r requirements.txt
```

### 2. Tạo file `.env`

```env
OPENAI_API_KEY=sk-your-key-here
TAVILY_API_KEY=tvly-your-key-here
```

---

## 🎮 Chạy Ứng Dụng

### Option 1: Streamlit (Simple)

```bash
streamlit run main.py
```

Truy cập: http://localhost:8501

### Option 2: React + FastAPI (Advanced)

**Cách 1: Chạy tự động**
```bash
# Double-click file:
start_all.bat
```

**Cách 2: Chạy thủ công**

Terminal 1 - Backend:
```bash
cd backend
uvicorn api:app --reload --port 8000
```

Terminal 2 - Frontend:
```bash
cd frontend
npm install
npm run dev
```

Truy cập:
- Frontend: http://localhost:3000
- API Docs: http://localhost:8000/docs

---

## 🛠️ Tính Năng

### 📊 Tab 1: Phân Tích CV-JD
- Upload CV/JD (PDF, PNG, JPG) hoặc paste text
- Tính điểm phù hợp (Match Score)
- Phân tích kỹ năng khớp/thiếu
- Gợi ý khóa học bổ sung

### 💼 Tab 2: Tìm Việc Làm
- Tìm kiếm việc làm online (LinkedIn, TopCV, VietnamWorks...)
- **MỚI**: Đánh giá trạng thái phỏng vấn
  - 🟢 Khả năng cao
  - 🟡 Trung bình
  - 🔴 Thấp
- Tips chuẩn bị phỏng vấn

### ✏️ Tab 3: Cải Thiện CV
- **Đề xuất chỉnh sửa CV**: AI viết lại CV tối ưu
- **Kiểm tra Layout**: Phân tích bố cục, font, màu sắc
- **Tạo mô tả CV mới**: Hướng dẫn thiết kế CV chuyên nghiệp

### 💬 Tab 4: Chat AI
- Chat trực tiếp với AI Assistant
- Quick actions: Phân tích CV, Gợi ý học tập, Tư vấn nghề nghiệp

---

## 📁 Cấu Trúc Dự Án

```
data/
├── agent.py           # Agent chính (Streamlit)
├── agent_api.py       # Agent cho FastAPI
├── main.py            # Streamlit app
├── requirements.txt   # Python dependencies
├── .env               # API keys
│
├── backend/
│   └── api.py         # FastAPI server
│
├── frontend/
│   ├── package.json   # Node dependencies
│   ├── src/
│   │   ├── App.jsx    # Main React component
│   │   ├── main.jsx   # Entry point
│   │   └── index.css  # Styles (Tailwind)
│   └── ...
│
├── tools_ocr.py       # OCR tools
├── tools_skills.py    # Skills comparison
├── tools_similarity.py # Similarity calculation
│
└── start_all.bat      # Quick start script
```

---

## 🎨 Tech Stack

### Backend
- **Python 3.10+**
- **LangChain** - AI Agent framework
- **OpenAI GPT-4o** - Language model + Vision
- **FastAPI** - REST API
- **Tavily** - Web search

### Frontend
- **React 18** - UI library
- **Vite** - Build tool
- **Tailwind CSS** - Styling
- **Framer Motion** - Animations
- **Lucide Icons** - Icons

---

## 📝 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/analyze` | POST | Phân tích CV-JD |
| `/api/find-jobs` | POST | Tìm việc làm |
| `/api/chat` | POST | Chat với AI |
| `/api/suggest-cv-improvements` | POST | Đề xuất chỉnh sửa CV |
| `/api/analyze-cv-layout` | POST | Phân tích layout CV |
| `/api/generate-improved-cv` | POST | Tạo mô tả CV mới |
| `/api/session-status` | GET | Trạng thái session |
| `/api/clear-session` | POST | Xóa session |

---

## 🔧 Troubleshooting

### Lỗi: "OPENAI_API_KEY not found"
→ Kiểm tra file `.env` đã được tạo và có key hợp lệ

### Lỗi: "Cannot connect to backend"
→ Đảm bảo backend đang chạy trên port 8000

### Lỗi: "Module not found"
→ Chạy `pip install -r requirements.txt`

### Frontend không load
→ Chạy `npm install` trong thư mục `frontend/`

---

## 📄 License

MIT License - Free to use and modify

---

## 🙏 Credits

- **OpenAI** - GPT-4o API
- **LangChain** - Agent Framework
- **Tavily** - Search API
- **The Unwithering Trio** - Development Team

---

**Version 3.0** | November 2025

