import re
from typing import Dict, List, Any

class IntakeClassifier:
    def __init__(self):
        self.patterns = {
            'lesson': [
                r'how to', r'explain', r'what is', r'tutorial', r'guide', r'step by step', r'knowledge'
            ],
            'escue': [
                r'fix', r'patch', r'remedy', r'solution', r'actionable', r'resolve', r'reproduce'
            ],
            'bug': [
                r'error', r'crash', r'fail', r'broken', r'not working', r'issue', r'unexpected', r'bug'
            ],
            'noise': [
                r'test', r'dummy', r'spam', r'random', r'asdf', r'test123'
            ]
        }

    def classify(self, text: str) -> Dict[str, Any]:
        text = text.lower()
        scores = {category: 0 for category in self.patterns.keys()}
        
        for category, keywords in self.patterns.items():
            for pattern in keywords:
                if re.search(pattern, text):
                    scores[category] += 1

        # Find max score
        max_score = max(scores.values())
        if max_score == 0:
            return {"category": "noise", "confidence": 0.0}

        best_category = max(scores, key=scores.get)
        confidence = max_score / len(self.patterns[best_category]) if self.patterns[best_category] else 0.0
        
        return {
            "category": best_category,
            "confidence": round(min(confidence, 1.0), 2),
            "scores": scores
        }

if __name__ == "__main__":
    import sys
    import json

    classifier = IntakeClassifier()
    input_text = sys.stdin.read()
    print(json.dumps(classifier.classify(input_text), indent=2))
