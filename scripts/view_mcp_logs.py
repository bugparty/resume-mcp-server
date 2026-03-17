#!/usr/bin/env python3
"""
Tool script for viewing and analyzing MCP Server logs
"""
import sys
from pathlib import Path

# Log file path
LOG_FILE = Path(__file__).resolve().parents[1] / "logs" / "mcp_server.log"


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


def filter_logs_by_tool(tool_name):
    """Filter logs by tool name"""
    if not LOG_FILE.exists():
        print(f"Log file does not exist: {LOG_FILE}")
        return
    
    print(f"Filtering tool: {tool_name}")
    print("=" * 80)
    
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        in_section = False
        for line in f:
            if f"=== MCP TOOL CALL: {tool_name} ===" in line:
                in_section = True
            
            if in_section:
                print(line, end="")
            
            if f"=== END: {tool_name} ===" in line or f"=== END (ERROR): {tool_name} ===" in line:
                in_section = False
                print()


def get_statistics():
    """Get log statistics"""
    if not LOG_FILE.exists():
        print(f"Log file does not exist: {LOG_FILE}")
        return
    
    stats = {}
    errors = {}
    total_calls = 0
    total_errors = 0
    
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        current_tool = None
        for line in f:
            if "=== MCP TOOL CALL:" in line:
                tool_name = line.split("=== MCP TOOL CALL:")[1].split("===")[0].strip()
                current_tool = tool_name
                stats[tool_name] = stats.get(tool_name, 0) + 1
                total_calls += 1
            elif "=== END (ERROR):" in line and current_tool:
                errors[current_tool] = errors.get(current_tool, 0) + 1
                total_errors += 1
    
    print("MCP Tool Call Statistics:")
    print("=" * 80)
    
    # Sort by call count
    sorted_tools = sorted(stats.items(), key=lambda x: x[1], reverse=True)
    
    for tool_name, count in sorted_tools:
        error_count = errors.get(tool_name, 0)
        error_info = f" ({error_count} errors)" if error_count > 0 else ""
        print(f"{tool_name:40s}: {count:3d} calls{error_info}")
    
    print("=" * 80)
    print(f"Total: {total_calls} calls")
    if total_errors > 0:
        print(f"Errors: {total_errors} failures")
    print("=" * 80)


def show_errors():
    """Display all error logs"""
    if not LOG_FILE.exists():
        print(f"Log file does not exist: {LOG_FILE}")
        return
    
    print("Error Logs:")
    print("=" * 80)
    
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        in_error = False
        for line in f:
            if "=== MCP TOOL CALL:" in line:
                in_error = False
                current_section = [line]
            elif in_error or "ERROR" in line or "Error in" in line:
                in_error = True
                print(line, end="")
            elif "=== END (ERROR):" in line:
                in_error = False
                print(line, end="")
                print()


def show_slow_calls(threshold_seconds=1.0):
    """Display calls exceeding execution time threshold"""
    if not LOG_FILE.exists():
        print(f"Log file does not exist: {LOG_FILE}")
        return
    
    print(f"Calls taking longer than {threshold_seconds}s:")
    print("=" * 80)
    
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        current_tool = None
        current_section = []
        
        for line in f:
            if "=== MCP TOOL CALL:" in line:
                current_tool = line.split("=== MCP TOOL CALL:")[1].split("===")[0].strip()
                current_section = [line]
            elif current_tool:
                current_section.append(line)
                if "Execution time:" in line:
                    time_str = line.split("Execution time:")[1].strip().rstrip("s")
                    try:
                        exec_time = float(time_str)
                        if exec_time >= threshold_seconds:
                            print("".join(current_section))
                            print()
                    except ValueError:
                        pass
                    current_tool = None
                    current_section = []


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
        print(f"  {sys.argv[0]} all                  - Show all logs")
        print(f"  {sys.argv[0]} recent [N]           - Show recent N lines (default 50)")
        print(f"  {sys.argv[0]} filter TOOL_NAME     - Filter logs by tool name")
        print(f"  {sys.argv[0]} stats                - Show statistics")
        print(f"  {sys.argv[0]} errors               - Show all errors")
        print(f"  {sys.argv[0]} slow [SECONDS]       - Show slow calls (default >1s)")
        print(f"  {sys.argv[0]} clear                - Clear log file")
        print()
        print("Examples:")
        print(f"  {sys.argv[0]} all")
        print(f"  {sys.argv[0]} recent 100")
        print(f"  {sys.argv[0]} filter list_resume_versions")
        print(f"  {sys.argv[0]} stats")
        print(f"  {sys.argv[0]} errors")
        print(f"  {sys.argv[0]} slow 2.0")
        return
    
    command = sys.argv[1]
    
    if command == "all":
        view_all_logs()
    elif command == "recent":
        lines = int(sys.argv[2]) if len(sys.argv) > 2 else 50
        view_recent_logs(lines)
    elif command == "filter":
        if len(sys.argv) < 3:
            print("Error: Please specify tool name")
            return
        filter_logs_by_tool(sys.argv[2])
    elif command == "stats":
        get_statistics()
    elif command == "errors":
        show_errors()
    elif command == "slow":
        threshold = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
        show_slow_calls(threshold)
    elif command == "clear":
        clear_logs()
    else:
        print(f"Unknown command: {command}")


if __name__ == "__main__":
    main()
