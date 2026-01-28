#!/usr/bin/env python3
"""
查看和分析 MCP Server 日志的工具脚本
"""
import sys
from pathlib import Path

# 日志文件路径
LOG_FILE = Path(__file__).resolve().parents[1] / "logs" / "mcp_server.log"


def view_all_logs():
    """显示所有日志内容"""
    if not LOG_FILE.exists():
        print(f"日志文件不存在: {LOG_FILE}")
        return
    
    print(f"读取日志文件: {LOG_FILE}")
    print("=" * 80)
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        print(f.read())


def view_recent_logs(lines=50):
    """显示最近的日志条目"""
    if not LOG_FILE.exists():
        print(f"日志文件不存在: {LOG_FILE}")
        return
    
    print(f"显示最近 {lines} 行日志:")
    print("=" * 80)
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        all_lines = f.readlines()
        recent = all_lines[-lines:]
        print("".join(recent))


def filter_logs_by_tool(tool_name):
    """按工具名过滤日志"""
    if not LOG_FILE.exists():
        print(f"日志文件不存在: {LOG_FILE}")
        return
    
    print(f"过滤工具: {tool_name}")
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
    """获取日志统计信息"""
    if not LOG_FILE.exists():
        print(f"日志文件不存在: {LOG_FILE}")
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
    
    print("MCP 工具调用统计:")
    print("=" * 80)
    
    # 按调用次数排序
    sorted_tools = sorted(stats.items(), key=lambda x: x[1], reverse=True)
    
    for tool_name, count in sorted_tools:
        error_count = errors.get(tool_name, 0)
        error_info = f" ({error_count} errors)" if error_count > 0 else ""
        print(f"{tool_name:40s}: {count:3d} 次调用{error_info}")
    
    print("=" * 80)
    print(f"总计: {total_calls} 次调用")
    if total_errors > 0:
        print(f"错误: {total_errors} 次失败")
    print("=" * 80)


def show_errors():
    """显示所有错误日志"""
    if not LOG_FILE.exists():
        print(f"日志文件不存在: {LOG_FILE}")
        return
    
    print("错误日志:")
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
    """显示执行时间超过阈值的调用"""
    if not LOG_FILE.exists():
        print(f"日志文件不存在: {LOG_FILE}")
        return
    
    print(f"执行时间超过 {threshold_seconds}s 的调用:")
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
    """清空日志文件"""
    if not LOG_FILE.exists():
        print(f"日志文件不存在: {LOG_FILE}")
        return
    
    confirm = input(f"确定要清空日志文件 {LOG_FILE}? (yes/no): ")
    if confirm.lower() == "yes":
        LOG_FILE.write_text("")
        print("日志文件已清空")
    else:
        print("操作已取消")


def main():
    if len(sys.argv) < 2:
        print("用法:")
        print(f"  {sys.argv[0]} all                  - 显示所有日志")
        print(f"  {sys.argv[0]} recent [N]           - 显示最近N行日志 (默认50)")
        print(f"  {sys.argv[0]} filter TOOL_NAME     - 按工具名过滤日志")
        print(f"  {sys.argv[0]} stats                - 显示统计信息")
        print(f"  {sys.argv[0]} errors               - 显示所有错误")
        print(f"  {sys.argv[0]} slow [SECONDS]       - 显示慢调用 (默认>1s)")
        print(f"  {sys.argv[0]} clear                - 清空日志文件")
        print()
        print("示例:")
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
            print("错误: 请指定工具名")
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
        print(f"未知命令: {command}")


if __name__ == "__main__":
    main()


