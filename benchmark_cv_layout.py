"""
Benchmark Script - Đánh giá chức năng CV Layout Analysis
Kiểm tra độ chính xác của việc phân tích bố cục và thiết kế CV
"""

import os
import sys
import json
import time
import base64
from typing import Optional
from dotenv import load_dotenv

# Fix encoding cho Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Load environment variables
load_dotenv()

from openai import OpenAI
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
TEST_CASES_FILE = os.path.join(BASE_DIR, "test_cv_layout_analyze.json")
OUTPUT_FILE = os.path.join(BASE_DIR, "benchmark_cv_layout_results.json")

# OpenAI client
client = OpenAI()

# ======================== LAYOUT ANALYSIS FUNCTION ========================

def analyze_cv_layout(file_path: str) -> dict:
    """
    Phân tích layout CV từ file ảnh hoặc PDF.
    Trả về dict với các tiêu chí đánh giá và điểm số.
    """
    import fitz  # PyMuPDF
    
    ext = os.path.splitext(file_path)[1].lower()
    
    # Chuyển file thành image base64
    if ext == ".pdf":
        doc = fitz.open(file_path)
        page = doc.load_page(0)
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
        img_bytes = pix.tobytes("png")
        doc.close()
        base64_img = base64.b64encode(img_bytes).decode('utf-8')
        mime_type = "image/png"
    elif ext in [".png", ".jpg", ".jpeg"]:
        with open(file_path, "rb") as f:
            img_bytes = f.read()
        base64_img = base64.b64encode(img_bytes).decode('utf-8')
        mime_type = f"image/{ext.replace('.', '')}"
        if ext == ".jpg":
            mime_type = "image/jpeg"
    else:
        raise ValueError(f"Unsupported file type: {ext}")
    
    # Gọi GPT-4o Vision để phân tích layout
    prompt = """Bạn là chuyên gia đánh giá CV. Hãy PHÂN TÍCH CHI TIẾT LAYOUT/BỐ CỤC của CV này.

ĐÁNH GIÁ THEO 5 TIÊU CHÍ (cho điểm 1-10):

1. LAYOUT_STRUCTURE (Cấu trúc bố cục):
   - Đánh giá: single/two-column, sidebar, visual hierarchy
   - Điểm: 1-10

2. TYPOGRAPHY (Font và kiểu chữ):
   - Đánh giá: font choice, size hierarchy, readability
   - Điểm: 1-10

3. COLOR_SCHEME (Bảng màu):
   - Đánh giá: color harmony, professional look, accent colors
   - Điểm: 1-10

4. SECTION_ORGANIZATION (Tổ chức sections):
   - Đánh giá: logical flow, clear sections, information hierarchy
   - Điểm: 1-10

5. PROFESSIONALISM (Tính chuyên nghiệp):
   - Đánh giá: overall impression, suitable for job applications
   - Điểm: 1-10

TRẢ VỀ JSON với format:
{
    "layout_type": "Single Column" hoặc "Two Column",
    "has_sidebar": true/false,
    "detected_sections": ["Header", "Summary", "Experience", ...],
    "color_scheme_description": "mô tả bảng màu",
    "typography_description": "mô tả typography",
    "scores": {
        "layout_structure": 1-10,
        "typography": 1-10,
        "color_scheme": 1-10,
        "section_organization": 1-10,
        "professionalism": 1-10
    },
    "total_score": điểm trung bình,
    "strengths": ["điểm mạnh 1", "điểm mạnh 2", ...],
    "improvements": ["cần cải thiện 1", "cần cải thiện 2", ...]
}

CHỈ TRẢ VỀ JSON, KHÔNG THÊM GIẢI THÍCH."""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{base64_img}"}}
            ]
        }],
        max_tokens=2000
    )
    
    content = response.choices[0].message.content.strip()
    
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
        return {"error": "Failed to parse response", "raw": content[:500]}


def calculate_score_accuracy(predicted_scores: dict, expected_scores: dict) -> dict:
    """
    Tính độ chính xác của điểm số dự đoán so với expected.
    
    Metrics:
    - MAE (Mean Absolute Error): Sai số tuyệt đối trung bình
    - Accuracy: % điểm dự đoán nằm trong khoảng ±1 của expected
    """
    if not predicted_scores or not expected_scores:
        return {"mae": 10.0, "accuracy": 0.0, "details": {}}
    
    criteria = ["layout_structure", "typography", "color_scheme", "section_organization", "professionalism"]
    
    errors = []
    within_tolerance = 0
    details = {}
    
    for criterion in criteria:
        pred = predicted_scores.get(criterion, 5)
        exp = expected_scores.get(criterion, 5)
        
        error = abs(pred - exp)
        errors.append(error)
        
        if error <= 1:  # Tolerance of ±1
            within_tolerance += 1
        
        details[criterion] = {
            "predicted": pred,
            "expected": exp,
            "error": error,
            "within_tolerance": error <= 1
        }
    
    mae = sum(errors) / len(errors) if errors else 0
    accuracy = within_tolerance / len(criteria) if criteria else 0
    
    return {
        "mae": round(mae, 2),
        "accuracy": round(accuracy, 4),
        "within_tolerance_count": within_tolerance,
        "total_criteria": len(criteria),
        "details": details
    }


# ======================== TEST EXECUTION ========================

def run_single_test(test_case: dict) -> dict:
    """Chạy một test case."""
    test_id = test_case["id"]
    cv_file = test_case.get("cv_file", "")
    
    # Skip comparison test
    if test_case.get("cv_type") == "COMPARISON":
        print(f"\n  [{test_id}] SKIP - Comparison test")
        return {"test_id": test_id, "status": "SKIPPED", "reason": "Comparison test"}
    
    print(f"\n  [{test_id}] {cv_file}")
    
    start_time = time.time()
    
    try:
        file_path = os.path.join(BASE_DIR, cv_file)
        
        if not os.path.exists(file_path):
            print(f"      [ERROR] File not found: {file_path}")
            return {"test_id": test_id, "status": "FAILED", "error": "File not found"}
        
        # Phân tích layout
        result = analyze_cv_layout(file_path)
        
        elapsed_time = time.time() - start_time
        
        if "error" in result:
            print(f"      [ERROR] {result['error']}")
            return {"test_id": test_id, "status": "FAILED", "error": result.get("error")}
        
        # Đánh giá accuracy
        predicted_scores = result.get("scores", {})
        expected_scores = test_case.get("expected_scores", {})
        
        score_accuracy = calculate_score_accuracy(predicted_scores, expected_scores)
        
        # In kết quả
        print(f"      Layout: {result.get('layout_type', 'N/A')} | Sidebar: {result.get('has_sidebar', 'N/A')}")
        print(f"      Scores: {predicted_scores}")
        print(f"      Total: {result.get('total_score', 'N/A')}/10")
        print(f"      MAE: {score_accuracy['mae']} | Accuracy (±1): {score_accuracy['accuracy']:.2%}")
        print(f"      Time: {elapsed_time:.2f}s")
        
        return {
            "test_id": test_id,
            "cv_file": cv_file,
            "status": "SUCCESS",
            "elapsed_time": round(elapsed_time, 2),
            "predicted_result": result,
            "expected_scores": expected_scores,
            "score_accuracy": score_accuracy
        }
        
    except Exception as e:
        elapsed_time = time.time() - start_time
        print(f"      [ERROR] {str(e)[:100]}")
        return {"test_id": test_id, "status": "FAILED", "error": str(e)[:200]}


def calculate_aggregate_stats(results: list) -> dict:
    """Tính thống kê tổng hợp."""
    successful = [r for r in results if r["status"] == "SUCCESS"]
    
    if not successful:
        return {"total": len(results), "success": 0}
    
    maes = [r["score_accuracy"]["mae"] for r in successful]
    accuracies = [r["score_accuracy"]["accuracy"] for r in successful]
    
    # Tính average predicted scores
    all_predicted = {}
    for criterion in ["layout_structure", "typography", "color_scheme", "section_organization", "professionalism"]:
        scores = [r["predicted_result"]["scores"].get(criterion, 0) for r in successful]
        all_predicted[criterion] = round(sum(scores) / len(scores), 2) if scores else 0
    
    return {
        "total": len(results),
        "success": len(successful),
        "failed": len([r for r in results if r["status"] == "FAILED"]),
        "skipped": len([r for r in results if r["status"] == "SKIPPED"]),
        "avg_mae": round(sum(maes) / len(maes), 2),
        "avg_accuracy": round(sum(accuracies) / len(accuracies), 4),
        "avg_predicted_scores": all_predicted
    }


# ======================== VISUALIZATION ========================

def create_charts(results: list, output_dir: str):
    """Tạo biểu đồ trực quan hóa kết quả."""
    if not HAS_MATPLOTLIB:
        print("[SKIP] Charts not created (matplotlib not installed)")
        return
    
    successful = [r for r in results if r["status"] == "SUCCESS"]
    if not successful:
        return
    
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    
    # Chart 1: Score Distribution per Criterion
    ax1 = axes[0, 0]
    criteria = ["layout_structure", "typography", "color_scheme", "section_organization", "professionalism"]
    criteria_short = ["Layout", "Typography", "Color", "Sections", "Professional"]
    
    predicted_avgs = []
    expected_avgs = []
    
    for criterion in criteria:
        pred_scores = [r["predicted_result"]["scores"].get(criterion, 0) for r in successful]
        exp_scores = [r["expected_scores"].get(criterion, 0) for r in successful]
        predicted_avgs.append(sum(pred_scores) / len(pred_scores))
        expected_avgs.append(sum(exp_scores) / len(exp_scores))
    
    x = range(len(criteria_short))
    width = 0.35
    
    ax1.bar([i - width/2 for i in x], predicted_avgs, width, label='AI Predicted', color='#3498db')
    ax1.bar([i + width/2 for i in x], expected_avgs, width, label='Expected', color='#2ecc71')
    
    ax1.set_ylabel('Score (1-10)')
    ax1.set_title('Average Scores by Criterion', fontweight='bold')
    ax1.set_xticks(x)
    ax1.set_xticklabels(criteria_short)
    ax1.set_ylim(0, 10)
    ax1.legend()
    ax1.grid(axis='y', alpha=0.3)
    
    # Chart 2: MAE Distribution
    ax2 = axes[0, 1]
    test_names = [f"Test {r['test_id']}" for r in successful]
    maes = [r["score_accuracy"]["mae"] for r in successful]
    
    colors = ['#2ecc71' if mae <= 1 else '#f39c12' if mae <= 2 else '#e74c3c' for mae in maes]
    ax2.bar(range(len(test_names)), maes, color=colors)
    
    ax2.set_xlabel('Test Case')
    ax2.set_ylabel('Mean Absolute Error')
    ax2.set_title('Prediction Error per Test', fontweight='bold')
    ax2.set_xticks(range(len(test_names)))
    ax2.set_xticklabels(test_names, rotation=45, ha='right', fontsize=8)
    ax2.axhline(y=1, color='green', linestyle='--', label='Good (≤1)')
    ax2.axhline(y=2, color='orange', linestyle='--', label='Acceptable (≤2)')
    ax2.legend()
    ax2.grid(axis='y', alpha=0.3)
    
    # Chart 3: Total Score Distribution
    ax3 = axes[1, 0]
    total_scores = [r["predicted_result"].get("total_score", 0) for r in successful]
    
    ax3.hist(total_scores, bins=10, range=(0, 10), color='#3498db', edgecolor='black', alpha=0.7)
    ax3.set_xlabel('Total Score')
    ax3.set_ylabel('Count')
    ax3.set_title('Distribution of Total Scores', fontweight='bold')
    ax3.set_xlim(0, 10)
    ax3.grid(axis='y', alpha=0.3)
    
    # Chart 4: Accuracy Summary
    ax4 = axes[1, 1]
    stats = calculate_aggregate_stats(results)
    
    metrics = ['Success\nRate', 'Avg\nAccuracy', 'Low MAE\n(≤1)']
    values = [
        stats['success'] / max(stats['total'], 1) * 100,
        stats['avg_accuracy'] * 100,
        len([r for r in successful if r["score_accuracy"]["mae"] <= 1]) / max(len(successful), 1) * 100
    ]
    
    colors = ['#3498db', '#2ecc71', '#9b59b6']
    bars = ax4.bar(metrics, values, color=colors, edgecolor='black')
    
    ax4.set_ylabel('Percentage (%)')
    ax4.set_title('Overall Performance Summary', fontweight='bold')
    ax4.set_ylim(0, 100)
    ax4.grid(axis='y', alpha=0.3)
    
    for bar, val in zip(bars, values):
        ax4.annotate(f'{val:.1f}%',
                    xy=(bar.get_x() + bar.get_width() / 2, val),
                    xytext=(0, 3),
                    textcoords="offset points",
                    ha='center', va='bottom', fontsize=11, fontweight='bold')
    
    plt.tight_layout()
    
    chart_path = os.path.join(output_dir, "benchmark_cv_layout_chart.png")
    plt.savefig(chart_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"\n[CHART] Saved: {chart_path}")


# ======================== MAIN ========================

def main():
    """Main function - Chạy benchmark CV Layout Analysis."""
    print("=" * 70)
    print("  CV LAYOUT ANALYSIS BENCHMARK")
    print("  Testing Layout Detection Accuracy")
    print("=" * 70)
    
    # Load test cases
    if not os.path.exists(TEST_CASES_FILE):
        print(f"[ERROR] Test cases file not found: {TEST_CASES_FILE}")
        return
    
    with open(TEST_CASES_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    test_cases = data.get("test_cases", [])
    print(f"\nLoaded {len(test_cases)} test cases")
    
    # Giới hạn số test cases
    LIMIT = 5  # Set to None to run all
    if LIMIT:
        test_cases = test_cases[:LIMIT]
        print(f"Running first {LIMIT} test cases (set LIMIT=None to run all)")
    
    print(f"\n{'='*60}")
    print(f"  RUNNING TESTS")
    print(f"{'='*60}")
    
    results = []
    for test_case in test_cases:
        result = run_single_test(test_case)
        results.append(result)
        time.sleep(1)  # Avoid rate limiting
    
    # Tính aggregate stats
    stats = calculate_aggregate_stats(results)
    
    # In summary
    print(f"\n{'='*60}")
    print(f"  SUMMARY")
    print(f"{'='*60}")
    print(f"  Total Tests: {stats['total']}")
    print(f"  Successful: {stats['success']}")
    print(f"  Failed: {stats.get('failed', 0)}")
    print(f"  Skipped: {stats.get('skipped', 0)}")
    print(f"\n  SCORE PREDICTION ACCURACY:")
    print(f"    Avg MAE (Mean Absolute Error): {stats.get('avg_mae', 'N/A')}")
    print(f"    Avg Accuracy (within ±1): {stats.get('avg_accuracy', 0):.2%}")
    print(f"\n  AVG PREDICTED SCORES:")
    if 'avg_predicted_scores' in stats:
        for criterion, score in stats['avg_predicted_scores'].items():
            print(f"    {criterion}: {score}/10")
    print(f"{'='*60}")
    
    # Lưu kết quả
    output_data = {
        "results": results,
        "aggregate": stats
    }
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    print(f"\n[DONE] Results saved to: {OUTPUT_FILE}")
    
    # Tạo biểu đồ
    create_charts(results, BASE_DIR)


if __name__ == "__main__":
    main()
