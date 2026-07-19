from flask import Flask, request, jsonify

app = Flask(__name__)

# Mock data for demonstration purposes
lessons = [
    {"id": 1, "title": "Introduction to Python", "description": "Learn the basics of Python programming."},
    {"id": 2, "title": "Advanced Python Techniques", "description": "Dive into advanced Python features."},
    {"id": 3, "title": "Web Development with Flask", "description": "Build web applications using Flask."}
]

@app.route('/search', methods=['POST'])
def search():
    query = request.json.get('query', '').lower()
    results = [lesson for lesson in lessons if query in lesson['title'].lower() or query in lesson['description'].lower()]
    return jsonify(results)

if __name__ == '__main__':
    app.run(port=8080)