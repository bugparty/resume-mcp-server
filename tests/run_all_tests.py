#!/usr/bin/env python
"""
运行所有测试用例的主文件
"""
import unittest
import sys
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.test_basic_functions import TestResumeBasics
from tests.test_resume_operations import TestResumeOperations

if __name__ == "__main__":
    # 创建测试套件
    test_suite = unittest.TestSuite()
    
    # 添加所有测试用例
    test_suite.addTest(unittest.makeSuite(TestResumeBasics))
    test_suite.addTest(unittest.makeSuite(TestResumeOperations))
    # LLM-dependent JD tests removed for MCP-only setup
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # 返回适当的退出代码
    sys.exit(not result.wasSuccessful())
