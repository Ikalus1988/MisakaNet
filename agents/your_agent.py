class YourAgent:
    def __init__(self, name):
        self.name = name
        self.lessons = {}

    def run(self, task, lesson=None):
        # Simulate running the task
        if lesson:
            # Use the provided lesson to improve performance
            print(f"Running {task} with lesson: {lesson}")
            return "success"
        else:
            # Run the task without any prior knowledge
            print(f"Running {task} without any prior knowledge")
            return "failure"

    def get_lesson(self, result):
        # Simulate extracting a lesson from the result
        if result == "success":
            return f"Lesson learned from {result}"
        else:
            return None

if __name__ == "__main__":
    agent = YourAgent("YourAgent")
    result = agent.run("Task A")
    lesson = agent.get_lesson(result)
    result = agent.run("Task B", lesson=lesson)
    print(f"Final result: {result}")
