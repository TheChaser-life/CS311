"""
Benchmark Script - Đánh giá chức năng trích xuất kỹ năng từ CV
Hỗ trợ 3 định dạng: TXT, PDF, PNG
Sử dụng Ground Truth từ các folder data trong dự án
Có tính năng vẽ biểu đồ để trực quan hóa kết quả
"""

import os
import sys
import json
import time
from typing import Optional
from dotenv import load_dotenv

# Fix encoding cho Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Load environment variables
load_dotenv()

# Import OpenAI
from openai import OpenAI
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

# Thử import matplotlib
try:
    import matplotlib.pyplot as plt
    import matplotlib
    matplotlib.use('Agg')  # Non-interactive backend cho server
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
    print("[WARNING] matplotlib not installed. Charts will be skipped.")

# ======================== CONFIGURATION ========================
BASE_DIR = os.path.dirname(__file__)
DATA_FOLDERS = {
    "txt": os.path.join(BASE_DIR, "data-for-txt-extract"),
    "pdf": os.path.join(BASE_DIR, "data-for-pdf-extract"),
    "png": os.path.join(BASE_DIR, "data-for-png-extract"),
}

# OpenAI client
client = OpenAI()

# ======================== SKILL EXTRACTION (STANDALONE) ========================

def extract_text_from_file_standalone(file_path: str) -> str:
    """
    Trích xuất văn bản từ file (PDF hoặc PNG).
    Sử dụng cùng logic với agent_api.py nhưng standalone.
    """
    import fitz  # PyMuPDF
    import base64
    
    ext = os.path.splitext(file_path)[1].lower()
    
    if ext == ".pdf":
        # Thử trích xuất text layer trước
        doc = fitz.open(file_path)
        text = ""
        for page in doc:
            text += page.get_text() + "\n"
        doc.close()
        
        if text.strip():
            return text.strip()
        
        # Nếu không có text layer, dùng OCR với GPT-4o Vision
        doc = fitz.open(file_path)
        page = doc.load_page(0)
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
        img_bytes = pix.tobytes("png")
        doc.close()
        
        base64_img = base64.b64encode(img_bytes).decode('utf-8')
        
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
    
    elif ext == ".png":
        # Dùng GPT-4o Vision cho ảnh
        with open(file_path, "rb") as f:
            img_bytes = f.read()
        base64_img = base64.b64encode(img_bytes).decode('utf-8')
        
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
    
    else:
        raise ValueError(f"Unsupported file type: {ext}")


def analyze_skills_standalone(cv_text: str, jd_text: str = "Any IT position") -> dict:
    """
    Phân tích kỹ năng từ CV (standalone, không cần session).
    Trả về dict với cv_skills, jd_skills, matched_skills, missing_skills.
    """
    llm = ChatOpenAI(model="gpt-4o", temperature=0)
    
    prompt = (
        "Bạn là chuyên gia tuyển dụng. Hãy phân tích CV của ứng viên.\n"
        "Trả về JSON với 4 mảng: cv_skills, jd_skills, matched_skills, missing_skills.\n"
        "Mỗi mảng liệt kê tối đa 30 kỹ năng.\n"
        "QUY TẮC:\n"
        "1. cv_skills: Trích xuất TẤT CẢ kỹ năng được đề cập trong CV (programming languages, frameworks, tools, soft skills).\n"
        "2. jd_skills: Kỹ năng yêu cầu trong JD.\n"
        "3. matched_skills: Giao của cv_skills và jd_skills.\n"
        "4. missing_skills: Có trong jd_skills nhưng không có trong cv_skills.\n"
        "- Dùng Title Case, tránh trùng lặp.\n"
        "- CHỈ trả JSON, không markdown.\n\n"
        f"CV TEXT:\n{cv_text[:8000]}\n\n"
        f"JOB DESCRIPTION:\n{jd_text[:2000]}"
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


# ======================== HELPER FUNCTIONS ========================

def normalize_skill(skill: str) -> str:
    """Chuẩn hóa tên kỹ năng để so sánh."""
    return skill.lower().strip().replace("-", " ").replace("_", " ").replace(".", "")


def load_ground_truth(folder_path: str) -> dict:
    """Load ground truth từ file JSON trong folder."""
    gt_path = os.path.join(folder_path, "ground_truth_skills.json")
    if not os.path.exists(gt_path):
        print(f"[WARNING] Ground truth not found: {gt_path}")
        return {}
    
    with open(gt_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    return {k: v for k, v in data.items() if k != "metadata"}


def calculate_metrics(predicted: list, ground_truth: list) -> dict:
    """Tính Precision, Recall, F1 Score."""
    pred_set = set(normalize_skill(s) for s in predicted)
    gt_set = set(normalize_skill(s) for s in ground_truth)
    
    if not pred_set and not gt_set:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0, "tp": 0, "fp": 0, "fn": 0}
    
    if not pred_set:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0, "tp": 0, "fp": 0, "fn": len(gt_set)}
    
    if not gt_set:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0, "tp": 0, "fp": len(pred_set), "fn": 0}
    
    tp = len(pred_set & gt_set)
    fp = len(pred_set - gt_set)
    fn = len(gt_set - pred_set)
    
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    
    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "predicted_count": len(pred_set),
        "ground_truth_count": len(gt_set),
        "hallucinated": list(pred_set - gt_set)[:10],
        "missed": list(gt_set - pred_set)[:10]
    }


# ======================== TEST FUNCTIONS ========================

def test_single_cv(file_path: str, file_type: str, ground_truth_skills: list) -> dict:
    """Test một CV đơn lẻ."""
    filename = os.path.basename(file_path)
    print(f"\n  Testing: {filename}")
    
    start_time = time.time()
    
    try:
        # Bước 1: Trích xuất văn bản
        if file_type == "txt":
            with open(file_path, "r", encoding="utf-8") as f:
                cv_text = f.read()
        else:
            cv_text = extract_text_from_file_standalone(file_path)
        
        if not cv_text or len(cv_text) < 50:
            return {"file": filename, "status": "FAILED", "error": "Text too short", "metrics": None}
        
        # Bước 2: Trích xuất kỹ năng
        result = analyze_skills_standalone(cv_text)
        predicted_skills = result.get("cv_skills", [])
        
        elapsed_time = time.time() - start_time
        
        # Bước 3: Tính metrics
        metrics = calculate_metrics(predicted_skills, ground_truth_skills)
        
        print(f"    Predicted: {len(predicted_skills)} skills | Ground Truth: {len(ground_truth_skills)} skills")
        print(f"    Precision: {metrics['precision']:.2%} | Recall: {metrics['recall']:.2%} | F1: {metrics['f1']:.2%}")
        print(f"    TP: {metrics['tp']} | FP: {metrics['fp']} | FN: {metrics['fn']} | Time: {elapsed_time:.2f}s")
        
        if metrics['hallucinated']:
            print(f"    Hallucinated (sample): {metrics['hallucinated'][:5]}")
        if metrics['missed']:
            print(f"    Missed (sample): {metrics['missed'][:5]}")
        
        return {
            "file": filename,
            "status": "SUCCESS",
            "elapsed_time": round(elapsed_time, 2),
            "metrics": metrics
        }
        
    except Exception as e:
        elapsed_time = time.time() - start_time
        print(f"    [ERROR] {str(e)[:100]}")
        return {"file": filename, "status": "FAILED", "error": str(e)[:200], "metrics": None}


def test_folder(folder_path: str, file_type: str, ground_truth: dict, limit: Optional[int] = None) -> list:
    """Test tất cả CV trong một folder."""
    results = []
    
    ext_map = {"txt": ".txt", "pdf": ".pdf", "png": ".png"}
    ext = ext_map.get(file_type, "")
    
    cv_files = [f for f in os.listdir(folder_path) 
                if f.endswith(ext) and not f.startswith("ground_truth") and not f.startswith("extracted")]
    
    if limit:
        cv_files = cv_files[:limit]
    
    print(f"\n{'='*60}")
    print(f"Testing {len(cv_files)} {file_type.upper()} files from: {folder_path}")
    print(f"{'='*60}")
    
    for cv_file in cv_files:
        gt_skills = []
        for key, value in ground_truth.items():
            if isinstance(value, dict) and value.get("file") == cv_file:
                gt_skills = value.get("all_skills_flat", [])
                break
        
        if not gt_skills:
            print(f"\n  [SKIP] No ground truth for: {cv_file}")
            continue
        
        file_path = os.path.join(folder_path, cv_file)
        result = test_single_cv(file_path, file_type, gt_skills)
        results.append(result)
    
    return results


def calculate_aggregate_metrics(results: list) -> dict:
    """Tính metrics tổng hợp."""
    successful = [r for r in results if r["status"] == "SUCCESS" and r["metrics"]]
    
    if not successful:
        return {"avg_precision": 0, "avg_recall": 0, "avg_f1": 0, "total": len(results), "success": 0}
    
    total_precision = sum(r["metrics"]["precision"] for r in successful)
    total_recall = sum(r["metrics"]["recall"] for r in successful)
    total_f1 = sum(r["metrics"]["f1"] for r in successful)
    
    return {
        "avg_precision": round(total_precision / len(successful), 4),
        "avg_recall": round(total_recall / len(successful), 4),
        "avg_f1": round(total_f1 / len(successful), 4),
        "total": len(results),
        "success": len(successful),
        "failed": len(results) - len(successful)
    }


# ======================== VISUALIZATION ========================

def create_charts(all_results: dict, output_dir: str):
    """Tạo các biểu đồ trực quan hóa kết quả."""
    if not HAS_MATPLOTLIB:
        print("[SKIP] Charts not created (matplotlib not installed)")
        return
    
    # Chuẩn bị dữ liệu
    file_types = []
    precisions = []
    recalls = []
    f1_scores = []
    
    for file_type, data in all_results.items():
        agg = data.get("aggregate", {})
        if agg.get("success", 0) > 0:
            file_types.append(file_type.upper())
            precisions.append(agg.get("avg_precision", 0) * 100)
            recalls.append(agg.get("avg_recall", 0) * 100)
            f1_scores.append(agg.get("avg_f1", 0) * 100)
    
    if not file_types:
        print("[SKIP] No data for charts")
        return
    
    # Chart 1: Bar chart so sánh Precision, Recall, F1 theo loại file
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    
    # Subplot 1: Grouped Bar Chart
    x = range(len(file_types))
    width = 0.25
    
    ax1 = axes[0]
    bars1 = ax1.bar([i - width for i in x], precisions, width, label='Precision', color='#3498db')
    bars2 = ax1.bar(x, recalls, width, label='Recall', color='#2ecc71')
    bars3 = ax1.bar([i + width for i in x], f1_scores, width, label='F1 Score', color='#e74c3c')
    
    ax1.set_xlabel('File Type', fontsize=12)
    ax1.set_ylabel('Score (%)', fontsize=12)
    ax1.set_title('Skill Extraction Performance by File Type', fontsize=14, fontweight='bold')
    ax1.set_xticks(x)
    ax1.set_xticklabels(file_types)
    ax1.set_ylim(0, 100)
    ax1.legend()
    ax1.grid(axis='y', alpha=0.3)
    
    # Thêm giá trị lên bars
    for bars in [bars1, bars2, bars3]:
        for bar in bars:
            height = bar.get_height()
            ax1.annotate(f'{height:.1f}%',
                        xy=(bar.get_x() + bar.get_width() / 2, height),
                        xytext=(0, 3),
                        textcoords="offset points",
                        ha='center', va='bottom', fontsize=8)
    
    # Subplot 2: Radar Chart
    ax2 = axes[1]
    
    # Tính average across all file types
    avg_precision = sum(precisions) / len(precisions)
    avg_recall = sum(recalls) / len(recalls)
    avg_f1 = sum(f1_scores) / len(f1_scores)
    
    categories = ['Precision', 'Recall', 'F1 Score']
    values = [avg_precision, avg_recall, avg_f1]
    
    colors = ['#3498db', '#2ecc71', '#e74c3c']
    bars = ax2.bar(categories, values, color=colors, edgecolor='black', linewidth=1.2)
    
    ax2.set_ylabel('Score (%)', fontsize=12)
    ax2.set_title('Overall Average Performance', fontsize=14, fontweight='bold')
    ax2.set_ylim(0, 100)
    ax2.grid(axis='y', alpha=0.3)
    
    for bar, val in zip(bars, values):
        ax2.annotate(f'{val:.1f}%',
                    xy=(bar.get_x() + bar.get_width() / 2, val),
                    xytext=(0, 3),
                    textcoords="offset points",
                    ha='center', va='bottom', fontsize=11, fontweight='bold')
    
    plt.tight_layout()
    
    # Lưu chart
    chart_path = os.path.join(output_dir, "benchmark_chart_summary.png")
    plt.savefig(chart_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"\n[CHART] Saved: {chart_path}")
    
    # Chart 2: Chi tiết từng file
    create_detailed_chart(all_results, output_dir)


def create_detailed_chart(all_results: dict, output_dir: str):
    """Tạo biểu đồ chi tiết cho từng file."""
    if not HAS_MATPLOTLIB:
        return
    
    all_files = []
    all_precisions = []
    all_recalls = []
    all_colors = []
    
    color_map = {"txt": "#3498db", "pdf": "#e74c3c", "png": "#2ecc71"}
    
    for file_type, data in all_results.items():
        results = data.get("results", [])
        for r in results:
            if r["status"] == "SUCCESS" and r["metrics"]:
                all_files.append(r["file"][:20])  # Truncate filename
                all_precisions.append(r["metrics"]["precision"] * 100)
                all_recalls.append(r["metrics"]["recall"] * 100)
                all_colors.append(color_map.get(file_type, "#95a5a6"))
    
    if not all_files:
        return
    
    fig, ax = plt.subplots(figsize=(12, max(6, len(all_files) * 0.4)))
    
    y = range(len(all_files))
    height = 0.35
    
    bars1 = ax.barh([i - height/2 for i in y], all_precisions, height, 
                    label='Precision', color='#3498db', alpha=0.8)
    bars2 = ax.barh([i + height/2 for i in y], all_recalls, height, 
                    label='Recall', color='#2ecc71', alpha=0.8)
    
    ax.set_xlabel('Score (%)', fontsize=12)
    ax.set_ylabel('CV File', fontsize=12)
    ax.set_title('Skill Extraction Performance per CV', fontsize=14, fontweight='bold')
    ax.set_yticks(y)
    ax.set_yticklabels(all_files, fontsize=9)
    ax.set_xlim(0, 100)
    ax.legend(loc='lower right')
    ax.grid(axis='x', alpha=0.3)
    
    # Thêm giá trị
    for bar in bars1:
        width = bar.get_width()
        ax.annotate(f'{width:.0f}%',
                    xy=(width, bar.get_y() + bar.get_height()/2),
                    xytext=(3, 0),
                    textcoords="offset points",
                    ha='left', va='center', fontsize=8)
    
    plt.tight_layout()
    
    chart_path = os.path.join(output_dir, "benchmark_chart_detailed.png")
    plt.savefig(chart_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"[CHART] Saved: {chart_path}")


# ======================== MAIN ========================

def main():
    """Main function - Chạy benchmark cho tất cả các folder."""
    print("=" * 70)
    print("  SKILL EXTRACTION BENCHMARK")
    print("  Testing skill extraction against Ground Truth")
    print("=" * 70)
    
    all_results = {}
    
    # Test từng loại file (giới hạn 3 file mỗi loại để tiết kiệm API)
    LIMIT_PER_TYPE = 3
    
    for file_type, folder_path in DATA_FOLDERS.items():
        if not os.path.exists(folder_path):
            print(f"\n[SKIP] Folder not found: {folder_path}")
            continue
        
        ground_truth = load_ground_truth(folder_path)
        if not ground_truth:
            print(f"\n[SKIP] No ground truth for: {folder_path}")
            continue
        
        results = test_folder(folder_path, file_type, ground_truth, limit=LIMIT_PER_TYPE)
        agg = calculate_aggregate_metrics(results)
        
        all_results[file_type] = {
            "results": results,
            "aggregate": agg
        }
        
        print(f"\n{'='*60}")
        print(f"  {file_type.upper()} SUMMARY")
        print(f"  Avg Precision: {agg['avg_precision']:.2%}")
        print(f"  Avg Recall: {agg['avg_recall']:.2%}")
        print(f"  Avg F1 Score: {agg['avg_f1']:.2%}")
        print(f"  Success: {agg['success']}/{agg['total']}")
        print(f"{'='*60}")
    
    # Lưu kết quả
    output_path = os.path.join(BASE_DIR, "benchmark_results.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f"\n[DONE] Results saved to: {output_path}")
    
    # Tạo biểu đồ
    create_charts(all_results, BASE_DIR)
    
    # Tổng kết
    print("\n" + "=" * 70)
    print("  FINAL SUMMARY")
    print("=" * 70)
    for file_type, data in all_results.items():
        agg = data["aggregate"]
        print(f"  {file_type.upper():6} | Precision: {agg['avg_precision']:.2%} | Recall: {agg['avg_recall']:.2%} | F1: {agg['avg_f1']:.2%}")
    print("=" * 70)


if __name__ == "__main__":
    main()
