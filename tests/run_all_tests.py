#!/usr/bin/env python
"""
Main file to run all test cases
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
    # Create test suite
    test_suite = unittest.TestSuite()
    
    # Add all test cases
    test_suite.addTest(unittest.makeSuite(TestResumeBasics))
    test_suite.addTest(unittest.makeSuite(TestResumeOperations))
    # LLM-dependent JD tests removed for MCP-only setup
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # Return appropriate exit code
    sys.exit(not result.wasSuccessful())
