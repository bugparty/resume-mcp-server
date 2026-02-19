#!/usr/bin/env python3
"""
Tool script for viewing and analyzing Markdown parsing logs
"""
import sys
from pathlib import Path

# Log file path
LOG_FILE = Path(__file__).resolve().parents[1] / "logs" / "markdown_parsing.log"


def view_all_logs():
    """Display all log content"""
    if not LOG_FILE.exists():
        print(f"Log file does not exist: {LOG_FILE}")
        return
    
    print(f"Reading log file: {LOG_FILE}")
    print("=" * 80)
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        print(f.read())


def view_recent_logs(lines=50):
    """Display recent log entries"""
    if not LOG_FILE.exists():
        print(f"Log file does not exist: {LOG_FILE}")
        return
    
    print(f"Displaying recent {lines} log lines:")
    print("=" * 80)
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        all_lines = f.readlines()
        recent = all_lines[-lines:]
        print("".join(recent))


def filter_logs_by_function(function_name):
    """Filter logs by function name"""
    if not LOG_FILE.exists():
        print(f"Log file does not exist: {LOG_FILE}")
        return
    
    print(f"Filtering function: {function_name}")
    print("=" * 80)
    
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        in_section = False
        for line in f:
            if f"=== {function_name} START ===" in line:
                in_section = True
            
            if in_section:
                print(line, end="")
            
            if f"=== {function_name} END ===" in line:
                in_section = False
                print()


def get_statistics():
    """Get log statistics"""
    if not LOG_FILE.exists():
        print(f"Log file does not exist: {LOG_FILE}")
        return
    
    stats = {
        "_parse_summary_markdown": 0,
        "_parse_skills_markdown": 0,
        "_parse_entries_markdown": 0,
        "_parse_experience_markdown": 0,
        "_parse_projects_markdown": 0,
        "_parse_raw_markdown": 0,
    }
    
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            for func_name in stats.keys():
                if f"=== {func_name} START ===" in line:
                    stats[func_name] += 1
    
    print("Log Statistics:")
    print("=" * 80)
    for func_name, count in stats.items():
        print(f"{func_name:30s}: {count:3d} calls")
    print("=" * 80)
    total = sum(stats.values())
    print(f"Total: {total} parse operations")


def clear_logs():
    """Clear log file"""
    if not LOG_FILE.exists():
        print(f"Log file does not exist: {LOG_FILE}")
        return
    
    confirm = input(f"Are you sure you want to clear log file {LOG_FILE}? (yes/no): ")
    if confirm.lower() == "yes":
        LOG_FILE.write_text("")
        print("Log file cleared")
    else:
        print("Operation cancelled")


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print(f"  {sys.argv[0]} all              - Show all logs")
        print(f"  {sys.argv[0]} recent [N]       - Show recent N lines (default 50)")
        print(f"  {sys.argv[0]} filter FUNC_NAME - Filter logs by function name")
        print(f"  {sys.argv[0]} stats            - Show statistics")
        print(f"  {sys.argv[0]} clear            - Clear log file")
        print()
        print("Examples:")
        print(f"  {sys.argv[0]} all")
        print(f"  {sys.argv[0]} recent 100")
        print(f"  {sys.argv[0]} filter _parse_summary_markdown")
        print(f"  {sys.argv[0]} stats")
        return
    
    command = sys.argv[1]
    
    if command == "all":
        view_all_logs()
    elif command == "recent":
        lines = int(sys.argv[2]) if len(sys.argv) > 2 else 50
        view_recent_logs(lines)
    elif command == "filter":
        if len(sys.argv) < 3:
            print("Error: Please specify function name")
            return
        filter_logs_by_function(sys.argv[2])
    elif command == "stats":
        get_statistics()
    elif command == "clear":
        clear_logs()
    else:
        print(f"Unknown command: {command}")


if __name__ == "__main__":
    main()
