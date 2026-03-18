"""CLI for examforge."""
import sys, json, argparse
from .core import Examforge

def main():
    parser = argparse.ArgumentParser(description="ExamForge — AI Exam Generator. Creates MCQs, short answer, essays with auto-grading from any textbook or PDF.")
    parser.add_argument("command", nargs="?", default="status", choices=["status", "run", "info"])
    parser.add_argument("--input", "-i", default="")
    args = parser.parse_args()
    instance = Examforge()
    if args.command == "status":
        print(json.dumps(instance.get_stats(), indent=2))
    elif args.command == "run":
        print(json.dumps(instance.generate(input=args.input or "test"), indent=2, default=str))
    elif args.command == "info":
        print(f"examforge v0.1.0 — ExamForge — AI Exam Generator. Creates MCQs, short answer, essays with auto-grading from any textbook or PDF.")

if __name__ == "__main__":
    main()
