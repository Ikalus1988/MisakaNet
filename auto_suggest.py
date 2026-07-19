import requests

def auto_suggest(query):
    response = requests.post("http://localhost:8080/search", json={"query": query})
    if response.status_code == 200:
        results = response.json()
        if results:
            print("Suggested Lessons:")
            for result in results:
                print(f"- {result['title']}: {result['description']}")
        else:
            print("No relevant lessons found.")
    else:
        print("Failed to fetch suggestions.")

# Example usage
auto_suggest("python")