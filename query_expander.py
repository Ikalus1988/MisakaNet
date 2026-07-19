import json
import argparse
from typing import List, Dict

# Load synonyms from synonyms.json
def load_synonyms(file_path: str) -> Dict[str, List[str]]:
    with open(file_path, 'r') as file:
        return json.load(file)

# Expand query terms with synonyms
def expand_query(query: str, synonyms: Dict[str, List[str]], top_n: int = 2) -> str:
    expanded_terms = []
    for term in query.split():
        if term in synonyms:
            # Add the original term and its top-n synonyms
            expanded_terms.append(term)
            expanded_terms.extend(synonyms[term][:top_n])
        else:
            expanded_terms.append(term)
    return " OR ".join(expanded_terms)

# Explain mode to show the expansion
def explain_expansion(query: str, synonyms: Dict[str, List[str]], top_n: int = 2) -> str:
    expanded_terms = []
    for term in query.split():
        if term in synonyms:
            # Add the original term and its top-n synonyms
            expanded_terms.append(f"{term} → {term}, " + ", ".join(synonyms[term][:top_n]))
        else:
            expanded_terms.append(term)
    return "\n".join(expanded_terms)

# Main function to process the query
def main():
    parser = argparse.ArgumentParser(description="Expand user queries with synonyms before BM25 search.")
    parser.add_argument("query", type=str, help="The user query to be expanded")
    parser.add_argument("--no-expand", action="store_true", help="Disable query expansion")
    parser.add_argument("--explain", action="store_true", help="Show the expansion in explain mode")
    parser.add_argument("--synonyms", type=str, default="synonyms.json", help="Path to the synonyms JSON file")
    args = parser.parse_args()

    # Load synonyms
    synonyms = load_synonyms(args.synonyms)

    if args.no_expand:
        print(f"Query (no expansion): {args.query}")
    else:
        if args.explain:
            print("Explain mode:")
            print(explain_expansion(args.query, synonyms))
        else:
            expanded_query = expand_query(args.query, synonyms)
            print(f"Expanded Query: {expanded_query}")

if __name__ == "__main__":
    main()