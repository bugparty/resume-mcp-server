import sys
from unittest.mock import MagicMock
from pathlib import Path
import os
import shutil
import time
import subprocess
import signal

# Mocks
sys.modules["myagent.resume_loader"] = MagicMock()
sys.modules["myagent.settings"] = MagicMock()
sys.modules["myagent.filesystem"] = MagicMock()
sys.modules["myagent.models"] = MagicMock()
sys.modules["myagent.models.agent_resume"] = MagicMock()
sys.modules["myagent.latex_jobs"] = MagicMock()
sys.modules["langchain_core"] = MagicMock()
sys.modules["langchain_core.messages"] = MagicMock()
sys.modules["langchain.tools"] = MagicMock()
sys.modules["langchain.tools.StructuredTool"] = MagicMock()
sys.modules["myagent.llm_config"] = MagicMock()

# Setup paths and environment
sys.path.append(str(Path("/workspace/src")))
os.environ["LATEX_COMPILE_API_URL"] = "http://localhost:8085"

# Import tool
from myagent.tools import compile_resume_pdf_tool

# Setup real filesystem mocks
from fs.osfs import OSFS
from fs.memoryfs import MemoryFS

# We need to mock get_output_fs to writing to a local dir we can check
OUTPUT_DIR = Path("test_tool_output")
if OUTPUT_DIR.exists():
    shutil.rmtree(OUTPUT_DIR)
OUTPUT_DIR.mkdir()

mock_fs = OSFS(str(OUTPUT_DIR))
sys.modules["myagent.filesystem"].get_output_fs.return_value = mock_fs

# Workdir for server
WORKDIR = Path("/workspace/services/latex_compile_api")

def start_server():
    print("Starting server...")
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app:app", "--port", "8085"],
        cwd=WORKDIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        preexec_fn=os.setsid
    )
    time.sleep(3)
    return proc

def stop_server(proc):
    print("Stopping server...")
    os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    proc.wait()

def main():
    proc = start_server()
    try:
        tex_content = r"""
\documentclass{article}
\begin{document}
Hello from Tool Test
\end{document}
"""
        print("Calling compile_resume_pdf_tool...")
        result = compile_resume_pdf_tool(tex_content, "test_version")
        
        print("Result:", result)
        
        # Check if output file exists in the mocked output fs (which maps to OUTPUT_DIR)
        # The tool returns Path("data://resumes/output/" + filename), but calls output_fs.writebytes(filename)
        # So we check OUTPUT_DIR for file starting with test_version and ending in .pdf
        
        found = list(OUTPUT_DIR.glob("test_version_*.pdf"))
        if found:
            print(f"Success! Found generated PDF: {found[0]}")
        else:
            print("Failed: No PDF found in output directory")
            sys.exit(1)
            
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
    finally:
        stop_server(proc)

if __name__ == "__main__":
    main()
