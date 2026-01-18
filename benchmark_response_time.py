"""
Benchmark Response Time - Đo thời gian phản hồi của chức năng cv_jd_analyze
Sử dụng 10 CV ngẫu nhiên từ các folder data trong dự án
"""

import os
import json
import time
import random
from typing import List, Tuple
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

# Thử import matplotlib
try:
    import matplotlib.pyplot as plt
    import matplotlib
    matplotlib.use('Agg')
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
    print("[WARNING] matplotlib not installed. Charts will be skipped.")

# ======================== CONFIGURATION ========================
BASE_DIR = os.path.dirname(__file__)
OUTPUT_FILE = os.path.join(BASE_DIR, "benchmark_response_time_results.json")

# Folders chứa CV
CV_FOLDERS = [
    ("data-for-txt-extract", ".txt"),
    ("data-for-pdf-extract", ".pdf"),
    ("data-for-png-extract", ".png"),
]

# JD folder
JD_FOLDER = os.path.join(BASE_DIR, "data-for-cv-jd-analyze")

# ======================== HELPER FUNCTIONS ========================

def get_all_cv_files() -> List[Tuple[str, str]]:
    """Lấy danh sách tất cả CV files từ các folder."""
    cv_files = []
    
    for folder_name, ext in CV_FOLDERS:
        folder_path = os.path.join(BASE_DIR, folder_name)
        if not os.path.exists(folder_path):
            continue
        
        for filename in os.listdir(folder_path):
            if filename.endswith(ext) and not filename.startswith("ground_truth") and not filename.startswith("extracted"):
                cv_files.append((os.path.join(folder_path, filename), ext))
    
    return cv_files


def get_random_jd_file() -> str:
    """Lấy ngẫu nhiên một JD file."""
    jd_files = [f for f in os.listdir(JD_FOLDER) if f.endswith(".txt")]
    if not jd_files:
        return None
    return os.path.join(JD_FOLDER, random.choice(jd_files))


def extract_text_from_file(file_path: str, file_type: str) -> str:
    """Trích xuất text từ file CV."""
    import base64
    from openai import OpenAI
    
    if file_type == ".txt":
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    
    elif file_type == ".pdf":
        import fitz
        doc = fitz.open(file_path)
        text = ""
        for page in doc:
            text += page.get_text() + "\n"
        doc.close()
        
        if text.strip():
            return text.strip()
        
        # OCR nếu không có text layer
        doc = fitz.open(file_path)
        page = doc.load_page(0)
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
        img_bytes = pix.tobytes("png")
        doc.close()
        
        base64_img = base64.b64encode(img_bytes).decode('utf-8')
        client = OpenAI()
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": "Trích xuất TOÀN BỘ văn bản trong CV này. Chỉ trả về text."},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_img}"}}
                ]
            }],
            max_tokens=4096
        )
        return response.choices[0].message.content
    
    elif file_type == ".png":
        with open(file_path, "rb") as f:
            img_bytes = f.read()
        base64_img = base64.b64encode(img_bytes).decode('utf-8')
        
        client = OpenAI()
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": "Trích xuất TOÀN BỘ văn bản trong CV này. Chỉ trả về text."},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_img}"}}
                ]
            }],
            max_tokens=4096
        )
        return response.choices[0].message.content
    
    return ""


def analyze_cv_jd(cv_text: str, jd_text: str) -> dict:
    """Phân tích CV so với JD."""
    llm = ChatOpenAI(model="gpt-4o", temperature=0)
    
    prompt = (
        "Bạn là chuyên gia tuyển dụng. Hãy phân tích CV của ứng viên so với mô tả "
        "công việc (JD) để trích xuất kỹ năng.\n"
        "Trả về JSON với 4 mảng: cv_skills, jd_skills, matched_skills, missing_skills. "
        "Mỗi mảng liệt kê tối đa 20 kỹ năng.\n"
        "CHỈ trả JSON, không thêm mô tả hay markdown.\n\n"
        f"CV TEXT:\n{cv_text[:6000]}\n\n"
        f"JOB DESCRIPTION:\n{jd_text[:3000]}"
    )
    
    response = llm.invoke([HumanMessage(content=prompt)])
    content = response.content.strip()
    
    # Parse JSON
    if content.startswith("```"):
        content = content.strip("`")
        if "\n" in content:
            content = content.split("\n", 1)[1]
        if content.startswith("json"):
            content = content[4:].strip()
    
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {"cv_skills": [], "jd_skills": [], "matched_skills": [], "missing_skills": []}


# ======================== BENCHMARK FUNCTION ========================

def benchmark_single_cv(cv_path: str, cv_type: str, jd_path: str) -> dict:
    """Benchmark một CV với một JD."""
    cv_filename = os.path.basename(cv_path)
    jd_filename = os.path.basename(jd_path)
    
    print(f"\n  CV: {cv_filename} ({cv_type})")
    print(f"  JD: {jd_filename}")
    
    result = {
        "cv_file": cv_filename,
        "cv_type": cv_type,
        "jd_file": jd_filename,
        "status": "PENDING"
    }
    
    try:
        # Bước 1: Đo thời gian trích xuất CV
        start_extract = time.time()
        cv_text = extract_text_from_file(cv_path, cv_type)
        extract_time = time.time() - start_extract
        
        if not cv_text or len(cv_text) < 50:
            result["status"] = "FAILED"
            result["error"] = "CV text extraction failed"
            return result
        
        # Đọc JD
        with open(jd_path, "r", encoding="utf-8") as f:
            jd_text = f.read()
        
        # Bước 2: Đo thời gian phân tích CV-JD
        start_analyze = time.time()
        analysis_result = analyze_cv_jd(cv_text, jd_text)
        analyze_time = time.time() - start_analyze
        
        # Tổng thời gian
        total_time = extract_time + analyze_time
        
        result.update({
            "status": "SUCCESS",
            "cv_text_length": len(cv_text),
            "timings": {
                "extract_time": round(extract_time, 3),
                "analyze_time": round(analyze_time, 3),
                "total_time": round(total_time, 3)
            },
            "result_summary": {
                "cv_skills_count": len(analysis_result.get("cv_skills", [])),
                "jd_skills_count": len(analysis_result.get("jd_skills", [])),
                "matched_skills_count": len(analysis_result.get("matched_skills", [])),
                "missing_skills_count": len(analysis_result.get("missing_skills", []))
            }
        })
        
        print(f"      Extract: {extract_time:.2f}s | Analyze: {analyze_time:.2f}s | Total: {total_time:.2f}s")
        print(f"      CV Skills: {result['result_summary']['cv_skills_count']} | Matched: {result['result_summary']['matched_skills_count']}")
        
    except Exception as e:
        result["status"] = "FAILED"
        result["error"] = str(e)[:200]
        print(f"      [ERROR] {str(e)[:100]}")
    
    return result


def calculate_statistics(results: list) -> dict:
    """Tính thống kê thời gian phản hồi."""
    successful = [r for r in results if r["status"] == "SUCCESS"]
    
    if not successful:
        return {"total": len(results), "success": 0}
    
    extract_times = [r["timings"]["extract_time"] for r in successful]
    analyze_times = [r["timings"]["analyze_time"] for r in successful]
    total_times = [r["timings"]["total_time"] for r in successful]
    
    def calc_stats(times):
        return {
            "min": round(min(times), 3),
            "max": round(max(times), 3),
            "avg": round(sum(times) / len(times), 3),
            "median": round(sorted(times)[len(times) // 2], 3)
        }
    
    # Phân theo loại file
    by_type = {}
    for r in successful:
        cv_type = r["cv_type"]
        if cv_type not in by_type:
            by_type[cv_type] = []
        by_type[cv_type].append(r["timings"]["total_time"])
    
    type_stats = {}
    for cv_type, times in by_type.items():
        type_stats[cv_type] = calc_stats(times)
    
    return {
        "total": len(results),
        "success": len(successful),
        "failed": len(results) - len(successful),
        "extract_time": calc_stats(extract_times),
        "analyze_time": calc_stats(analyze_times),
        "total_time": calc_stats(total_times),
        "by_file_type": type_stats
    }


# ======================== VISUALIZATION ========================

def create_charts(results: list, stats: dict, output_dir: str):
    """Tạo biểu đồ thời gian phản hồi."""
    if not HAS_MATPLOTLIB:
        print("[SKIP] Charts not created (matplotlib not installed)")
        return
    
    successful = [r for r in results if r["status"] == "SUCCESS"]
    if not successful:
        return
    
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    
    # Chart 1: Response Time per CV
    ax1 = axes[0]
    cv_names = [r["cv_file"][:15] for r in successful]
    extract_times = [r["timings"]["extract_time"] for r in successful]
    analyze_times = [r["timings"]["analyze_time"] for r in successful]
    
    x = range(len(cv_names))
    width = 0.35
    
    ax1.bar([i - width/2 for i in x], extract_times, width, label='Extract', color='#3498db')
    ax1.bar([i + width/2 for i in x], analyze_times, width, label='Analyze', color='#e74c3c')
    
    ax1.set_ylabel('Time (seconds)')
    ax1.set_title('Response Time per CV', fontweight='bold')
    ax1.set_xticks(x)
    ax1.set_xticklabels(cv_names, rotation=45, ha='right', fontsize=8)
    ax1.legend()
    ax1.grid(axis='y', alpha=0.3)
    
    # Chart 2: Time Distribution by File Type
    ax2 = axes[1]
    type_stats = stats.get("by_file_type", {})
    
    if type_stats:
        types = list(type_stats.keys())
        avgs = [type_stats[t]["avg"] for t in types]
        colors = {'txt': '#3498db', 'pdf': '#e74c3c', 'png': '#2ecc71'}
        bar_colors = [colors.get(t.replace(".", ""), '#95a5a6') for t in types]
        
        ax2.bar(types, avgs, color=bar_colors, edgecolor='black')
        ax2.set_ylabel('Avg Time (seconds)')
        ax2.set_title('Avg Response Time by File Type', fontweight='bold')
        ax2.grid(axis='y', alpha=0.3)
        
        for i, (t, v) in enumerate(zip(types, avgs)):
            ax2.annotate(f'{v:.2f}s', xy=(i, v), xytext=(0, 3),
                        textcoords="offset points", ha='center', fontsize=10, fontweight='bold')
    
    plt.tight_layout()
    
    chart_path = os.path.join(output_dir, "benchmark_response_time_chart.png")
    plt.savefig(chart_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"\n[CHART] Saved: {chart_path}")


# ======================== MAIN ========================

def main():
    """Main function - Benchmark response time với 10 CV ngẫu nhiên."""
    print("=" * 70)
    print("  CV-JD ANALYZE RESPONSE TIME BENCHMARK")
    print("  Testing with 10 Random CVs")
    print("=" * 70)
    
    # Lấy danh sách tất cả CV
    all_cvs = get_all_cv_files()
    print(f"\nFound {len(all_cvs)} CV files total")
    
    if len(all_cvs) < 10:
        print(f"[WARNING] Only {len(all_cvs)} CVs available, using all")
        selected_cvs = all_cvs
    else:
        # Chọn ngẫu nhiên 10 CV
        selected_cvs = random.sample(all_cvs, 10)
    
    print(f"Selected {len(selected_cvs)} CVs for benchmark")
    
    # Hiển thị danh sách CV được chọn
    print("\nSelected CVs:")
    for i, (cv_path, cv_type) in enumerate(selected_cvs, 1):
        print(f"  {i}. {os.path.basename(cv_path)} ({cv_type})")
    
    print(f"\n{'='*60}")
    print(f"  RUNNING BENCHMARK")
    print(f"{'='*60}")
    
    results = []
    for cv_path, cv_type in selected_cvs:
        # Lấy ngẫu nhiên một JD
        jd_path = get_random_jd_file()
        if not jd_path:
            print(f"\n  [ERROR] No JD files found!")
            continue
        
        result = benchmark_single_cv(cv_path, cv_type, jd_path)
        results.append(result)
        
        # Delay ngắn giữa các request
        time.sleep(0.5)
    
    # Tính thống kê
    stats = calculate_statistics(results)
    
    # In summary
    print(f"\n{'='*60}")
    print(f"  SUMMARY")
    print(f"{'='*60}")
    print(f"  Total Tests: {stats['total']}")
    print(f"  Successful: {stats['success']}")
    print(f"  Failed: {stats.get('failed', 0)}")
    
    if stats.get('success', 0) > 0:
        print(f"\n  RESPONSE TIME STATISTICS:")
        print(f"    Extract Time:")
        print(f"      Avg: {stats['extract_time']['avg']:.2f}s | Min: {stats['extract_time']['min']:.2f}s | Max: {stats['extract_time']['max']:.2f}s")
        print(f"    Analyze Time:")
        print(f"      Avg: {stats['analyze_time']['avg']:.2f}s | Min: {stats['analyze_time']['min']:.2f}s | Max: {stats['analyze_time']['max']:.2f}s")
        print(f"    Total Time:")
        print(f"      Avg: {stats['total_time']['avg']:.2f}s | Min: {stats['total_time']['min']:.2f}s | Max: {stats['total_time']['max']:.2f}s")
        print(f"      Median: {stats['total_time']['median']:.2f}s")
        
        print(f"\n  BY FILE TYPE:")
        for cv_type, type_stat in stats.get('by_file_type', {}).items():
            print(f"    {cv_type}: Avg {type_stat['avg']:.2f}s | Min {type_stat['min']:.2f}s | Max {type_stat['max']:.2f}s")
    
    print(f"{'='*60}")
    
    # Lưu kết quả
    output_data = {
        "results": results,
        "statistics": stats
    }
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    print(f"\n[DONE] Results saved to: {OUTPUT_FILE}")
    
    # Tạo biểu đồ
    create_charts(results, stats, BASE_DIR)


if __name__ == "__main__":
    main()
