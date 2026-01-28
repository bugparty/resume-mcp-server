#!/usr/bin/env python3
"""
查看和分析 Markdown 解析日志的工具脚本
"""
import sys
from pathlib import Path

# 日志文件路径
LOG_FILE = Path(__file__).resolve().parents[1] / "logs" / "markdown_parsing.log"


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


def filter_logs_by_function(function_name):
    """按函数名过滤日志"""
    if not LOG_FILE.exists():
        print(f"日志文件不存在: {LOG_FILE}")
        return
    
    print(f"过滤函数: {function_name}")
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
    """获取日志统计信息"""
    if not LOG_FILE.exists():
        print(f"日志文件不存在: {LOG_FILE}")
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
    
    print("日志统计信息:")
    print("=" * 80)
    for func_name, count in stats.items():
        print(f"{func_name:30s}: {count:3d} 次调用")
    print("=" * 80)
    total = sum(stats.values())
    print(f"总计: {total} 次解析操作")


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
        print(f"  {sys.argv[0]} all              - 显示所有日志")
        print(f"  {sys.argv[0]} recent [N]       - 显示最近N行日志 (默认50)")
        print(f"  {sys.argv[0]} filter FUNC_NAME - 按函数名过滤日志")
        print(f"  {sys.argv[0]} stats            - 显示统计信息")
        print(f"  {sys.argv[0]} clear            - 清空日志文件")
        print()
        print("示例:")
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
            print("错误: 请指定函数名")
            return
        filter_logs_by_function(sys.argv[2])
    elif command == "stats":
        get_statistics()
    elif command == "clear":
        clear_logs()
    else:
        print(f"未知命令: {command}")


if __name__ == "__main__":
    main()


