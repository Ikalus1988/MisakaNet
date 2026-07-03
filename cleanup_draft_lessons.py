import os
import argparse

def cleanup_draft_lessons(directory, dry_run=False):
    """
    Cleanup draft lessons in the specified directory.

    :param directory: Path to the directory containing lessons.
    :param dry_run: If True, only print the files to be removed without actually removing them.
    """
    draft_lessons = []
    for filename in os.listdir(directory):
        if filename.startswith("draft_") or "draft" in filename.lower():
            draft_lessons.append(filename)

    if dry_run:
        print("The following draft lessons will be removed:")
        for lesson in draft_lessons:
            print(os.path.join(directory, lesson))
    else:
        print("Removing draft lessons:")
        for lesson in draft_lessons:
            filepath = os.path.join(directory, lesson)
            try:
                os.remove(filepath)
                print(f"Removed: {filepath}")
            except Exception as e:
                print(f"Failed to remove {lesson}: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cleanup draft lessons.")
    parser.add_argument("--directory", default="lessons/contrib/", help="Directory to search for draft lessons.")
    parser.add_argument("--dry-run", action="store_true", help="Dry run, print files to be removed without deleting.")
    args = parser.parse_args()

    cleanup_draft_lessons(args.directory, args.dry_run)
