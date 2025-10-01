# 日志目录

此目录包含应用程序生成的日志文件。

## 文件说明

### markdown_parsing.log
记录所有markdown解析操作的详细日志，包括：
- 输入的markdown内容
- 解析前后的数据结构
- 字段变化的详细对比
- 错误和异常信息

## 查看日志

使用提供的工具脚本查看日志：

```bash
# 查看统计信息
python ../scripts/view_parsing_logs.py stats

# 查看最近的日志
python ../scripts/view_parsing_logs.py recent 50

# 按函数名过滤
python ../scripts/view_parsing_logs.py filter _parse_summary_markdown

# 清空日志（谨慎使用）
python ../scripts/view_parsing_logs.py clear
```

## 维护建议

- 定期检查日志文件大小
- 在问题排查后可清空日志
- 重要的日志记录可备份到其他位置

## 注意事项

⚠️ **隐私提醒**: 日志文件包含完整的简历内容，请注意保护数据安全。



