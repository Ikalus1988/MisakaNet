import argparse
from whoosh import scoring
from whoosh.qparser import QueryParser

def main():
    parser = argparse.ArgumentParser(description='Search knowledge base')
    parser.add_argument('query', type=str, help='search query')
    parser.add_argument('--explain', action='store_true', help='explain the scoring')
    args = parser.parse_args()

    # Assuming the search index is already opened and available as 'ix'
    ix = open_dir('indexdir')

    qp = QueryParser("content", schema=ix.schema)
    q = qp.parse(args.query)

    with ix.searcher(weighting=scoring.BM25F) as s:
        results = s.search(q, terms=True, limit=None)
        for result in results:
            print(result['title'])
            if args.explain:
                # Calculate and print the breakdown of the score
                score = result.score
                bm25_score = scoring.BM25F().score(result, s)
                domain_boost = 1.0  # Replace with actual domain boost logic
                quality_score = 1.0  # Replace with actual quality score logic
                reuse_count = 0  # Replace with actual reuse count logic
                print(f"Score: {score:.4f} = BM25({bm25_score:.4f}) * Domain Boost({domain_boost:.4f}) + Quality Score({quality_score:.4f}) + Reuse Count({reuse_count})")

if __name__ == "__main__":
    main()