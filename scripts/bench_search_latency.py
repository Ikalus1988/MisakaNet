import asyncio
import time
import json
import statistics
import numpy as np
from misakanet.search.engine import SearchEngine

# Mock queries for benchmarking
QUERIES = [
    "GitHub Actions Code Injection",
    "Docker container crash",
    "Python syntax error",
    "MisakaNet installation guide",
    "RAG latency issues",
    "BM25 vs SAG-Lite",
    "How to use MisakaNet",
    "troubleshooting node2",
    "credential rotation",
    "CI self-heal workflow"
] * 10  # 100 queries

async def benchmark_engine(engine_name, engine_instance, queries):
    latencies = []
    for query in queries:
        start = time.perf_counter()
        # Assuming search is an async method in SearchEngine
        await engine_instance.search(query, top_k=5)
        end = time.perf_counter()
        latencies.append((end - start) * 1000)  # ms
    
    return {
        "engine": engine_name,
        "p50": statistics.median(latencies),
        "p95": np.percentile(latencies, 95),
        "p99": np.percentile(latencies, 99),
        "avg": statistics.mean(latencies)
    }

async def main():
    print("Starting search latency benchmark...")
    engine = SearchEngine()
    
    # In a real scenario, we'd iterate through different engine configurations
    # For this implementation, we benchmark the default engine behavior
    results = []
    
    # Benchmark default engine
    print("Benchmarking default engine...")
    results.append(await benchmark_engine("default", engine, QUERIES))
    
    # Output results
    output_file = "data/search-latency.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"Benchmark complete. Results saved to {output_file}")
    for res in results:
        print(f"Engine: {res['engine']} | p50: {res['p50']:.2f}ms | p95: {res['p95']:.2f}ms")

if __name__ == "__main__":
    asyncio.run(main())