from flask import Flask, request, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

app = Flask(__name__)

# Rate limiting: 60 requests per minute for unauthenticated users
limiter = Limiter(
    app,
    key_func=get_remote_address,
    default_limits=["60 per minute"]
)

# Mock data for demonstration purposes
data = [
    {"id": 1, "title": "DevOps Best Practices", "domain": "devops"},
    {"id": 2, "title": "Kubernetes in Action", "domain": "devops"},
    {"id": 3, "title": "Python for Data Science", "domain": "data-science"},
    {"id": 4, "title": "Flask Web Development", "domain": "web-development"},
    {"id": 5, "title": "Docker Containerization", "domain": "devops"},
    {"id": 6, "title": "Machine Learning with Python", "domain": "data-science"},
    {"id": 7, "title": "RESTful API Design", "domain": "web-development"},
    {"id": 8, "title": "Continuous Integration and Deployment", "domain": "devops"},
]

@app.route('/api/search', methods=['GET'])
@limiter.limit("60/minute")
def search():
    query = request.args.get('q')
    domain = request.args.get('domain')
    limit = int(request.args.get('limit', 10))
    offset = int(request.args.get('offset', 0))

    # Filter data based on query and domain
    filtered_data = [item for item in data if (query is None or query.lower() in item['title'].lower()) and (domain is None or domain.lower() == item['domain'].lower())]

    # Apply pagination
    paginated_data = filtered_data[offset:offset + limit]

    return jsonify(paginated_data)

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({"status": "OK"})

if __name__ == '__main__':
    app.run(debug=True)