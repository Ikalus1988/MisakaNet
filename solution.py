import os
import shutil
import subprocess

def compare_lessons(lesson1, lesson2):
    with open(lesson1, 'r') as f1, open(lesson2, 'r') as f2:
        content1 = f1.read()
        content2 = f2.read()
        return content1 == content2

def archive_lesson(lesson):
    archive_dir = 'lessons/_archive/'
    if not os.path.exists(archive_dir):
        os.makedirs(archive_dir)
    filename = os.path.basename(lesson)
    shutil.move(lesson, os.path.join(archive_dir, filename))

def add_cross_link(lesson, target):
    with open(lesson, 'r+') as f:
        content = f.read()
        f.seek(0)
        f.write(f'[See also]({target})\n' + content)
        f.truncate()

def run_duplicate_check(threshold):
    subprocess.run(['python3', 'scripts/find_duplicate_lessons.py', '--threshold', str(threshold)])

def main():
    lesson1 = 'lessons/contrib/cc-connect-feishu-setup-complete.md'
    lesson2 = 'lessons/contrib/feishu-bot-setup-complete.md'
    threshold = 0.6
    if compare_lessons(lesson1, lesson2):
        # Keep the more complete one and archive the other
        archive_lesson(lesson2)
    else:
        # Add a cross-link to the other lesson
        add_cross_link(lesson1, lesson2)
    run_duplicate_check(threshold)

if __name__ == '__main__':
    main()