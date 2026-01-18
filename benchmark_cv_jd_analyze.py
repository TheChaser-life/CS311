"""
Benchmark Script - Đánh giá chức năng CV-JD Analyze
Kiểm tra độ chính xác của việc so sánh missing skills giữa CV và JD
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
TEST_CASES_FILE = os.path.join(BASE_DIR, "test_cv_jd_analyze.json")
OUTPUT_FILE = os.path.join(BASE_DIR, "benchmark_cv_jd_results.json")

# ======================== CV-JD ANALYSIS FUNCTION ========================

def analyze_cv_jd(cv_text: str, jd_text: str) -> dict:
    """
    Phân tích CV so với JD để trích xuất skills.
    Trả về dict với cv_skills, jd_skills, matched_skills, missing_skills.
    Logic giống tool_analyze_skills trong agent_api.py
    """
    llm = ChatOpenAI(model="gpt-4o", temperature=0)
    
    prompt = (
        "Bạn là chuyên gia tuyển dụng. Hãy phân tích CV của ứng viên so với mô tả "
        "công việc (JD) để trích xuất kỹ năng.\n"
        "Trả về JSON với 4 mảng: cv_skills, jd_skills, matched_skills, missing_skills. "
        "Mỗi mảng liệt kê tối đa 30 kỹ năng.\n"
        "QUY TẮC QUAN TRỌNG:\n"
        "1. jd_skills: CHỈ trích xuất các kỹ năng được NHẮC ĐẾN CỤ THỂ trong JD.\n"
        "   - KHÔNG tự suy diễn thêm kỹ năng mà JD không viết.\n"
        "2. cv_skills: trích xuất kỹ năng từ CV.\n"
        "3. matched_skills: giao giữa hai danh sách (không phân biệt hoa thường).\n"
        "4. missing_skills: kỹ năng có trong jd_skills nhưng KHÔNG có trong cv_skills.\n"
        "- Dùng định dạng chữ Title Case, tránh trùng lặp.\n"
        "- CHỈ trả JSON, không thêm mô tả hay markdown.\n\n"
        f"CV TEXT:\n{cv_text[:8000]}\n\n"
        f"JOB DESCRIPTION:\n{jd_text[:4000]}"
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


def normalize_skill(skill: str) -> str:
    """Chuẩn hóa tên skill để so sánh."""
    return skill.lower().strip().replace("-", " ").replace("_", " ").replace(".", "").replace("/", " ")


def calculate_missing_skills_accuracy(predicted_missing: list, expected_missing: list) -> dict:
    """
    Tính độ chính xác của predicted missing skills so với expected.
    
    Metrics:
    - Precision: Trong số missing skills AI nói, bao nhiêu % đúng?
    - Recall: AI tìm được bao nhiêu % missing skills thực tế?
    - F1: Trung bình hài hòa
    """
    pred_set = set(normalize_skill(s) for s in predicted_missing)
    exp_set = set(normalize_skill(s) for s in expected_missing)
    
    if not pred_set and not exp_set:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0, "tp": 0, "fp": 0, "fn": 0}
    
    if not pred_set:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0, "tp": 0, "fp": 0, "fn": len(exp_set)}
    
    if not exp_set:
        # Nếu expected rỗng nhưng AI predict có, đó là false positives
        return {"precision": 0.0, "recall": 1.0, "f1": 0.0, "tp": 0, "fp": len(pred_set), "fn": 0}
    
    tp = len(pred_set & exp_set)
    fp = len(pred_set - exp_set)  # AI nói thiếu nhưng thực tế không thiếu
    fn = len(exp_set - pred_set)  # Thực tế thiếu nhưng AI không nói
    
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
        "predicted_missing": list(pred_set),
        "expected_missing": list(exp_set),
        "correct_predictions": list(pred_set & exp_set),
        "false_positives": list(pred_set - exp_set),
        "false_negatives": list(exp_set - pred_set)
    }


def calculate_matched_skills_accuracy(predicted_matched: list, expected_matched: list) -> dict:
    """Tính độ chính xác của matched skills."""
    pred_set = set(normalize_skill(s) for s in predicted_matched)
    exp_set = set(normalize_skill(s) for s in expected_matched)
    
    if not pred_set and not exp_set:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0}
    
    if not pred_set:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}
    
    if not exp_set:
        return {"precision": 0.0, "recall": 1.0, "f1": 0.0}
    
    tp = len(pred_set & exp_set)
    fp = len(pred_set - exp_set)
    fn = len(exp_set - pred_set)
    
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    
    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4)
    }


# ======================== TEST EXECUTION ========================

def run_single_test(test_case: dict) -> dict:
    """Chạy một test case."""
    test_id = test_case["id"]
    test_name = test_case["name"]
    
    print(f"\n  [{test_id}] {test_name}")
    
    start_time = time.time()
    
    try:
        # Đọc CV file
        cv_path = os.path.join(BASE_DIR, test_case["cv_file"])
        with open(cv_path, "r", encoding="utf-8") as f:
            cv_text = f.read()
        
        # Đọc JD file
        jd_path = os.path.join(BASE_DIR, test_case["jd_file"])
        with open(jd_path, "r", encoding="utf-8") as f:
            jd_text = f.read()
        
        # Phân tích CV-JD
        result = analyze_cv_jd(cv_text, jd_text)
        
        elapsed_time = time.time() - start_time
        
        # Đánh giá missing skills
        missing_accuracy = calculate_missing_skills_accuracy(
            result.get("missing_skills", []),
            test_case.get("expected_missing_skills", [])
        )
        
        # Đánh giá matched skills
        matched_accuracy = calculate_matched_skills_accuracy(
            result.get("matched_skills", []),
            test_case.get("expected_matched_skills", [])
        )
        
        print(f"      Missing Skills - Precision: {missing_accuracy['precision']:.2%} | Recall: {missing_accuracy['recall']:.2%} | F1: {missing_accuracy['f1']:.2%}")
        print(f"      Matched Skills - Precision: {matched_accuracy['precision']:.2%} | Recall: {matched_accuracy['recall']:.2%} | F1: {matched_accuracy['f1']:.2%}")
        print(f"      Time: {elapsed_time:.2f}s")
        
        if missing_accuracy.get("false_positives"):
            print(f"      False Positives (AI nói thiếu nhưng ko thiếu): {missing_accuracy['false_positives'][:5]}")
        if missing_accuracy.get("false_negatives"):
            print(f"      False Negatives (Thiếu nhưng AI ko nói): {missing_accuracy['false_negatives'][:5]}")
        
        return {
            "test_id": test_id,
            "test_name": test_name,
            "status": "SUCCESS",
            "elapsed_time": round(elapsed_time, 2),
            "predicted_result": result,
            "missing_skills_accuracy": missing_accuracy,
            "matched_skills_accuracy": matched_accuracy
        }
        
    except Exception as e:
        elapsed_time = time.time() - start_time
        print(f"      [ERROR] {str(e)[:100]}")
        return {
            "test_id": test_id,
            "test_name": test_name,
            "status": "FAILED",
            "error": str(e)[:200],
            "elapsed_time": round(elapsed_time, 2)
        }


def calculate_aggregate_stats(results: list) -> dict:
    """Tính thống kê tổng hợp."""
    successful = [r for r in results if r["status"] == "SUCCESS"]
    
    if not successful:
        return {"total": len(results), "success": 0, "avg_missing_precision": 0, "avg_missing_recall": 0, "avg_missing_f1": 0}
    
    missing_precisions = [r["missing_skills_accuracy"]["precision"] for r in successful]
    missing_recalls = [r["missing_skills_accuracy"]["recall"] for r in successful]
    missing_f1s = [r["missing_skills_accuracy"]["f1"] for r in successful]
    
    matched_precisions = [r["matched_skills_accuracy"]["precision"] for r in successful]
    matched_recalls = [r["matched_skills_accuracy"]["recall"] for r in successful]
    matched_f1s = [r["matched_skills_accuracy"]["f1"] for r in successful]
    
    return {
        "total": len(results),
        "success": len(successful),
        "failed": len(results) - len(successful),
        "avg_missing_precision": round(sum(missing_precisions) / len(successful), 4),
        "avg_missing_recall": round(sum(missing_recalls) / len(successful), 4),
        "avg_missing_f1": round(sum(missing_f1s) / len(successful), 4),
        "avg_matched_precision": round(sum(matched_precisions) / len(successful), 4),
        "avg_matched_recall": round(sum(matched_recalls) / len(successful), 4),
        "avg_matched_f1": round(sum(matched_f1s) / len(successful), 4)
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
    
    # Chart 1: Missing Skills Accuracy per Test
    ax1 = axes[0, 0]
    test_names = [r["test_name"][:25] for r in successful]
    missing_precisions = [r["missing_skills_accuracy"]["precision"] * 100 for r in successful]
    missing_recalls = [r["missing_skills_accuracy"]["recall"] * 100 for r in successful]
    
    x = range(len(test_names))
    width = 0.35
    
    ax1.bar([i - width/2 for i in x], missing_precisions, width, label='Precision', color='#3498db')
    ax1.bar([i + width/2 for i in x], missing_recalls, width, label='Recall', color='#2ecc71')
    
    ax1.set_ylabel('Score (%)')
    ax1.set_title('Missing Skills Detection Accuracy', fontweight='bold')
    ax1.set_xticks(x)
    ax1.set_xticklabels(test_names, rotation=45, ha='right', fontsize=8)
    ax1.set_ylim(0, 100)
    ax1.legend()
    ax1.grid(axis='y', alpha=0.3)
    
    # Chart 2: Matched Skills Accuracy per Test
    ax2 = axes[0, 1]
    matched_precisions = [r["matched_skills_accuracy"]["precision"] * 100 for r in successful]
    matched_recalls = [r["matched_skills_accuracy"]["recall"] * 100 for r in successful]
    
    ax2.bar([i - width/2 for i in x], matched_precisions, width, label='Precision', color='#3498db')
    ax2.bar([i + width/2 for i in x], matched_recalls, width, label='Recall', color='#2ecc71')
    
    ax2.set_ylabel('Score (%)')
    ax2.set_title('Matched Skills Detection Accuracy', fontweight='bold')
    ax2.set_xticks(x)
    ax2.set_xticklabels(test_names, rotation=45, ha='right', fontsize=8)
    ax2.set_ylim(0, 100)
    ax2.legend()
    ax2.grid(axis='y', alpha=0.3)
    
    # Chart 3: Overall Comparison (Missing vs Matched)
    ax3 = axes[1, 0]
    
    stats = calculate_aggregate_stats(results)
    categories = ['Precision', 'Recall', 'F1 Score']
    missing_values = [stats['avg_missing_precision']*100, stats['avg_missing_recall']*100, stats['avg_missing_f1']*100]
    matched_values = [stats['avg_matched_precision']*100, stats['avg_matched_recall']*100, stats['avg_matched_f1']*100]
    
    x = range(len(categories))
    ax3.bar([i - width/2 for i in x], missing_values, width, label='Missing Skills', color='#e74c3c')
    ax3.bar([i + width/2 for i in x], matched_values, width, label='Matched Skills', color='#2ecc71')
    
    ax3.set_ylabel('Score (%)')
    ax3.set_title('Overall Average Performance', fontweight='bold')
    ax3.set_xticks(x)
    ax3.set_xticklabels(categories)
    ax3.set_ylim(0, 100)
    ax3.legend()
    ax3.grid(axis='y', alpha=0.3)
    
    for i, (mv, mtv) in enumerate(zip(missing_values, matched_values)):
        ax3.annotate(f'{mv:.1f}%', xy=(i - width/2, mv), xytext=(0, 3),
                    textcoords="offset points", ha='center', va='bottom', fontsize=9)
        ax3.annotate(f'{mtv:.1f}%', xy=(i + width/2, mtv), xytext=(0, 3),
                    textcoords="offset points", ha='center', va='bottom', fontsize=9)
    
    # Chart 4: F1 Score Distribution
    ax4 = axes[1, 1]
    missing_f1s = [r["missing_skills_accuracy"]["f1"] * 100 for r in successful]
    matched_f1s = [r["matched_skills_accuracy"]["f1"] * 100 for r in successful]
    
    ax4.plot(range(len(successful)), missing_f1s, 'o-', label='Missing Skills F1', color='#e74c3c')
    ax4.plot(range(len(successful)), matched_f1s, 's-', label='Matched Skills F1', color='#2ecc71')
    
    ax4.set_xlabel('Test Case Index')
    ax4.set_ylabel('F1 Score (%)')
    ax4.set_title('F1 Score Distribution', fontweight='bold')
    ax4.set_ylim(0, 100)
    ax4.legend()
    ax4.grid(alpha=0.3)
    
    plt.tight_layout()
    
    chart_path = os.path.join(output_dir, "benchmark_cv_jd_chart.png")
    plt.savefig(chart_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"\n[CHART] Saved: {chart_path}")


# ======================== MAIN ========================

def main():
    """Main function - Chạy benchmark CV-JD Analyze."""
    print("=" * 70)
    print("  CV-JD ANALYZE BENCHMARK")
    print("  Testing Missing Skills Detection Accuracy")
    print("=" * 70)
    
    # Load test cases
    if not os.path.exists(TEST_CASES_FILE):
        print(f"[ERROR] Test cases file not found: {TEST_CASES_FILE}")
        return
    
    with open(TEST_CASES_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    test_cases = data.get("test_cases", [])
    print(f"\nLoaded {len(test_cases)} test cases")
    
    # Giới hạn số test cases (có thể thay đổi)
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
        time.sleep(0.5)  # Avoid rate limiting
    
    # Tính aggregate stats
    stats = calculate_aggregate_stats(results)
    
    # In summary
    print(f"\n{'='*60}")
    print(f"  SUMMARY")
    print(f"{'='*60}")
    print(f"  Total Tests: {stats['total']}")
    print(f"  Successful: {stats['success']}")
    print(f"  Failed: {stats.get('failed', 0)}")
    print(f"\n  MISSING SKILLS DETECTION:")
    print(f"    Avg Precision: {stats['avg_missing_precision']:.2%}")
    print(f"    Avg Recall: {stats['avg_missing_recall']:.2%}")
    print(f"    Avg F1 Score: {stats['avg_missing_f1']:.2%}")
    print(f"\n  MATCHED SKILLS DETECTION:")
    print(f"    Avg Precision: {stats['avg_matched_precision']:.2%}")
    print(f"    Avg Recall: {stats['avg_matched_recall']:.2%}")
    print(f"    Avg F1 Score: {stats['avg_matched_f1']:.2%}")
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
