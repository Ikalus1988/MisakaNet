#!/usr/bin/env python3
import sys, requests, textwrap

API = "https://api.stackexchange.com/2.3"

def get(qid):
    q = requests.get(f"{API}/questions/{qid}",
                     params={"site":"stackoverflow","filter":"!-*f(6rc.lF)"}).json()
    a = requests.get(f"{API}/questions/{qid}/answers",
                     params={"site":"stackoverflow","filter":"!-*f(6rc.lF)","sort":"votes"}).json()
    title = q["items"][0]["title"]
    ans_body = a["items"][0]["body_markdown"] if a["items"] else "No answer"
    return title, ans_body

def main():
    if len(sys.argv) != 3:
        print("Usage: script.py <question_id_1> <question_id_2>")
        return
    lessons = []
    for qid in sys.argv[1:]:
        title, ans = get(qid)
        lesson = f"### {title}\n\n{ans}"
        lessons.append(textwrap.dedent(lesson))
    print("\n---\n".join(lessons))

if __name__ == "__main__":
    main()