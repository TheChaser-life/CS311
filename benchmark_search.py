"""
Benchmark Script - Đánh giá chức năng tìm kiếm khóa học và công việc
Sử dụng Tavily Search API (giống tool_find_courses_online và tool_find_jobs_online)
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

# Import Tavily
from langchain_community.tools.tavily_search import TavilySearchResults

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
QUERIES_FILE = os.path.join(BASE_DIR, "test_search_queries.json")
OUTPUT_FILE = os.path.join(BASE_DIR, "benchmark_search_results.json")

# ======================== SEARCH FUNCTIONS ========================

def search_with_tavily(query: str, max_results: int = 5) -> dict:
    """
    Thực hiện tìm kiếm với Tavily API.
    Trả về dict chứa kết quả và metadata.
    """
    start_time = time.time()
    
    try:
        search_tool = TavilySearchResults(max_results=max_results)
        results = search_tool.invoke({"query": query})
        
        elapsed_time = time.time() - start_time
        
        # Parse kết quả
        parsed_results = []
        for item in results:
            parsed_results.append({
                "title": item.get("title", "No title"),
                "url": item.get("url", ""),
                "snippet": item.get("content", "")[:200],
                "has_url": bool(item.get("url"))
            })
        
        return {
            "status": "SUCCESS",
            "query": query,
            "num_results": len(parsed_results),
            "elapsed_time": round(elapsed_time, 3),
            "results": parsed_results,
            "has_valid_urls": sum(1 for r in parsed_results if r["has_url"]),
            "avg_snippet_length": sum(len(r["snippet"]) for r in parsed_results) / max(len(parsed_results), 1)
        }
        
    except Exception as e:
        elapsed_time = time.time() - start_time
        return {
            "status": "FAILED",
            "query": query,
            "num_results": 0,
            "elapsed_time": round(elapsed_time, 3),
            "error": str(e)[:200],
            "results": []
        }


def evaluate_relevance(query: str, results: list, query_category: str) -> float:
    """
    Đánh giá độ liên quan của kết quả với query.
    Trả về điểm từ 0.0 đến 1.0
    """
    if not results:
        return 0.0
    
    # Keywords từ query
    query_words = set(query.lower().split())
    
    relevance_scores = []
    for result in results:
        title = result.get("title", "").lower()
        snippet = result.get("snippet", "").lower()
        combined_text = title + " " + snippet
        
        # Đếm số từ khóa xuất hiện
        matches = sum(1 for word in query_words if word in combined_text and len(word) > 2)
        
        # Tính tỷ lệ khớp
        score = matches / max(len(query_words), 1)
        relevance_scores.append(min(score, 1.0))
    
    return round(sum(relevance_scores) / len(relevance_scores), 4)


# ======================== BENCHMARK FUNCTIONS ========================

def benchmark_course_queries(queries: list, limit: Optional[int] = None) -> list:
    """Benchmark các query tìm kiếm khóa học."""
    results = []
    
    if limit:
        queries = queries[:limit]
    
    print(f"\n{'='*60}")
    print(f"  BENCHMARKING COURSE SEARCH ({len(queries)} queries)")
    print(f"{'='*60}")
    
    for i, q in enumerate(queries):
        query_text = q["query"]
        category = q.get("category", "Unknown")
        
        print(f"\n  [{i+1}/{len(queries)}] {query_text[:50]}...")
        
        # Thực hiện tìm kiếm
        result = search_with_tavily(query_text)
        
        # Đánh giá độ liên quan
        relevance = evaluate_relevance(query_text, result.get("results", []), category)
        result["relevance_score"] = relevance
        result["category"] = category
        result["difficulty"] = q.get("difficulty", "Unknown")
        result["query_id"] = q.get("id", i+1)
        
        print(f"       Results: {result['num_results']} | Time: {result['elapsed_time']}s | Relevance: {relevance:.2%}")
        
        results.append(result)
        
        # Delay để tránh rate limit
        time.sleep(0.5)
    
    return results


def benchmark_job_queries(queries: list, limit: Optional[int] = None) -> list:
    """Benchmark các query tìm kiếm công việc."""
    results = []
    
    if limit:
        queries = queries[:limit]
    
    print(f"\n{'='*60}")
    print(f"  BENCHMARKING JOB SEARCH ({len(queries)} queries)")
    print(f"{'='*60}")
    
    for i, q in enumerate(queries):
        query_text = q["query"]
        category = q.get("category", "Unknown")
        
        print(f"\n  [{i+1}/{len(queries)}] {query_text[:50]}...")
        
        # Thực hiện tìm kiếm
        result = search_with_tavily(query_text)
        
        # Đánh giá độ liên quan
        relevance = evaluate_relevance(query_text, result.get("results", []), category)
        result["relevance_score"] = relevance
        result["category"] = category
        result["seniority"] = q.get("seniority", "Unknown")
        result["location"] = q.get("location", "Any")
        result["query_id"] = q.get("id", i+1)
        
        print(f"       Results: {result['num_results']} | Time: {result['elapsed_time']}s | Relevance: {relevance:.2%}")
        
        results.append(result)
        
        # Delay để tránh rate limit
        time.sleep(0.5)
    
    return results


def calculate_aggregate_stats(results: list) -> dict:
    """Tính thống kê tổng hợp."""
    if not results:
        return {}
    
    successful = [r for r in results if r["status"] == "SUCCESS"]
    
    if not successful:
        return {
            "total_queries": len(results),
            "success_rate": 0,
            "avg_response_time": 0,
            "avg_num_results": 0,
            "avg_relevance": 0
        }
    
    return {
        "total_queries": len(results),
        "successful_queries": len(successful),
        "failed_queries": len(results) - len(successful),
        "success_rate": round(len(successful) / len(results), 4),
        "avg_response_time": round(sum(r["elapsed_time"] for r in successful) / len(successful), 3),
        "min_response_time": round(min(r["elapsed_time"] for r in successful), 3),
        "max_response_time": round(max(r["elapsed_time"] for r in successful), 3),
        "avg_num_results": round(sum(r["num_results"] for r in successful) / len(successful), 2),
        "avg_relevance": round(sum(r.get("relevance_score", 0) for r in successful) / len(successful), 4),
        "total_urls_found": sum(r.get("has_valid_urls", 0) for r in successful)
    }


# ======================== VISUALIZATION ========================

def create_charts(course_results: list, job_results: list, output_dir: str):
    """Tạo biểu đồ trực quan hóa kết quả."""
    if not HAS_MATPLOTLIB:
        print("[SKIP] Charts not created (matplotlib not installed)")
        return
    
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    
    # Chart 1: Response Time Distribution
    ax1 = axes[0, 0]
    course_times = [r["elapsed_time"] for r in course_results if r["status"] == "SUCCESS"]
    job_times = [r["elapsed_time"] for r in job_results if r["status"] == "SUCCESS"]
    
    x = range(max(len(course_times), len(job_times)))
    if course_times:
        ax1.plot(range(len(course_times)), course_times, 'o-', label='Course Search', color='#3498db')
    if job_times:
        ax1.plot(range(len(job_times)), job_times, 's-', label='Job Search', color='#e74c3c')
    
    ax1.set_xlabel('Query Index')
    ax1.set_ylabel('Response Time (seconds)')
    ax1.set_title('Response Time per Query', fontweight='bold')
    ax1.legend()
    ax1.grid(alpha=0.3)
    
    # Chart 2: Relevance Score Distribution
    ax2 = axes[0, 1]
    course_relevance = [r.get("relevance_score", 0) * 100 for r in course_results if r["status"] == "SUCCESS"]
    job_relevance = [r.get("relevance_score", 0) * 100 for r in job_results if r["status"] == "SUCCESS"]
    
    categories = ['Course Search', 'Job Search']
    avg_relevance = [
        sum(course_relevance)/max(len(course_relevance), 1),
        sum(job_relevance)/max(len(job_relevance), 1)
    ]
    colors = ['#3498db', '#e74c3c']
    
    bars = ax2.bar(categories, avg_relevance, color=colors, edgecolor='black')
    ax2.set_ylabel('Relevance Score (%)')
    ax2.set_title('Average Relevance Score', fontweight='bold')
    ax2.set_ylim(0, 100)
    ax2.grid(axis='y', alpha=0.3)
    
    for bar, val in zip(bars, avg_relevance):
        ax2.annotate(f'{val:.1f}%',
                    xy=(bar.get_x() + bar.get_width() / 2, val),
                    xytext=(0, 3),
                    textcoords="offset points",
                    ha='center', va='bottom', fontsize=11, fontweight='bold')
    
    # Chart 3: Number of Results per Query
    ax3 = axes[1, 0]
    course_nums = [r["num_results"] for r in course_results if r["status"] == "SUCCESS"]
    job_nums = [r["num_results"] for r in job_results if r["status"] == "SUCCESS"]
    
    if course_nums:
        ax3.bar([i - 0.2 for i in range(len(course_nums))], course_nums, 0.4, 
                label='Course', color='#3498db', alpha=0.8)
    if job_nums:
        ax3.bar([i + 0.2 for i in range(len(job_nums))], job_nums, 0.4, 
                label='Job', color='#e74c3c', alpha=0.8)
    
    ax3.set_xlabel('Query Index')
    ax3.set_ylabel('Number of Results')
    ax3.set_title('Results Count per Query', fontweight='bold')
    ax3.legend()
    ax3.grid(axis='y', alpha=0.3)
    
    # Chart 4: Summary Statistics
    ax4 = axes[1, 1]
    
    course_stats = calculate_aggregate_stats(course_results)
    job_stats = calculate_aggregate_stats(job_results)
    
    metrics = ['Avg Response\nTime (s)', 'Avg Results', 'Relevance\nScore (%)']
    course_values = [
        course_stats.get('avg_response_time', 0),
        course_stats.get('avg_num_results', 0),
        course_stats.get('avg_relevance', 0) * 100
    ]
    job_values = [
        job_stats.get('avg_response_time', 0),
        job_stats.get('avg_num_results', 0),
        job_stats.get('avg_relevance', 0) * 100
    ]
    
    x = range(len(metrics))
    width = 0.35
    
    ax4.bar([i - width/2 for i in x], course_values, width, label='Course Search', color='#3498db')
    ax4.bar([i + width/2 for i in x], job_values, width, label='Job Search', color='#e74c3c')
    
    ax4.set_ylabel('Value')
    ax4.set_title('Summary Comparison', fontweight='bold')
    ax4.set_xticks(x)
    ax4.set_xticklabels(metrics)
    ax4.legend()
    ax4.grid(axis='y', alpha=0.3)
    
    plt.tight_layout()
    
    chart_path = os.path.join(output_dir, "benchmark_search_chart.png")
    plt.savefig(chart_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"\n[CHART] Saved: {chart_path}")


# ======================== MAIN ========================

def main():
    """Main function - Chạy benchmark cho cả 2 loại tìm kiếm."""
    print("=" * 70)
    print("  SEARCH FUNCTIONALITY BENCHMARK")
    print("  Testing tool_find_courses_online & tool_find_jobs_online")
    print("=" * 70)
    
    # Load queries
    if not os.path.exists(QUERIES_FILE):
        print(f"[ERROR] Queries file not found: {QUERIES_FILE}")
        return
    
    with open(QUERIES_FILE, "r", encoding="utf-8") as f:
        queries_data = json.load(f)
    
    course_queries = queries_data.get("course_search_queries", [])
    job_queries = queries_data.get("job_search_queries", [])
    
    print(f"\nLoaded {len(course_queries)} course queries and {len(job_queries)} job queries")
    
    # Giới hạn số query để tiết kiệm API (có thể thay đổi)
    LIMIT_PER_TYPE = 5
    
    # Benchmark Course Search
    course_results = benchmark_course_queries(course_queries, limit=LIMIT_PER_TYPE)
    course_stats = calculate_aggregate_stats(course_results)
    
    print(f"\n{'='*60}")
    print(f"  COURSE SEARCH SUMMARY")
    print(f"  Success Rate: {course_stats.get('success_rate', 0):.2%}")
    print(f"  Avg Response Time: {course_stats.get('avg_response_time', 0):.3f}s")
    print(f"  Avg Results: {course_stats.get('avg_num_results', 0):.1f}")
    print(f"  Avg Relevance: {course_stats.get('avg_relevance', 0):.2%}")
    print(f"{'='*60}")
    
    # Benchmark Job Search
    job_results = benchmark_job_queries(job_queries, limit=LIMIT_PER_TYPE)
    job_stats = calculate_aggregate_stats(job_results)
    
    print(f"\n{'='*60}")
    print(f"  JOB SEARCH SUMMARY")
    print(f"  Success Rate: {job_stats.get('success_rate', 0):.2%}")
    print(f"  Avg Response Time: {job_stats.get('avg_response_time', 0):.3f}s")
    print(f"  Avg Results: {job_stats.get('avg_num_results', 0):.1f}")
    print(f"  Avg Relevance: {job_stats.get('avg_relevance', 0):.2%}")
    print(f"{'='*60}")
    
    # Lưu kết quả
    all_results = {
        "course_search": {
            "results": course_results,
            "aggregate": course_stats
        },
        "job_search": {
            "results": job_results,
            "aggregate": job_stats
        }
    }
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    
    print(f"\n[DONE] Results saved to: {OUTPUT_FILE}")
    
    # Tạo biểu đồ
    create_charts(course_results, job_results, BASE_DIR)
    
    # Final Summary
    print("\n" + "=" * 70)
    print("  FINAL COMPARISON")
    print("=" * 70)
    print(f"  {'Metric':<25} {'Course Search':<20} {'Job Search':<20}")
    print(f"  {'-'*65}")
    
    # Format values separately to avoid format string errors
    course_success = f"{course_stats.get('success_rate', 0):.2%}"
    job_success = f"{job_stats.get('success_rate', 0):.2%}"
    course_time = f"{course_stats.get('avg_response_time', 0):.3f}s"
    job_time = f"{job_stats.get('avg_response_time', 0):.3f}s"
    course_results_count = f"{course_stats.get('avg_num_results', 0):.1f}"
    job_results_count = f"{job_stats.get('avg_num_results', 0):.1f}"
    course_relevance = f"{course_stats.get('avg_relevance', 0):.2%}"
    job_relevance = f"{job_stats.get('avg_relevance', 0):.2%}"
    
    print(f"  {'Success Rate':<25} {course_success:<20} {job_success:<20}")
    print(f"  {'Avg Response Time':<25} {course_time:<20} {job_time:<20}")
    print(f"  {'Avg Results Count':<25} {course_results_count:<20} {job_results_count:<20}")
    print(f"  {'Avg Relevance':<25} {course_relevance:<20} {job_relevance:<20}")
    print("=" * 70)


if __name__ == "__main__":
    main()
