import sys
from pathlib import Path
import time
import subprocess
import os
import signal
import shutil

import sys
from unittest.mock import MagicMock

# Define Mocks before importing resume_renderer
sys.modules["myagent.resume_loader"] = MagicMock()
sys.modules["myagent.settings"] = MagicMock()
sys.modules["myagent.filesystem"] = MagicMock()
sys.modules["myagent.models"] = MagicMock()
sys.modules["myagent.models.agent_resume"] = MagicMock()

# Add src to pythonpath
sys.path.append(str(Path("/workspace/src")))
from myagent.resume_renderer import compile_tex_remote

# Server Config
PORT = 8084
os.environ["LATEX_COMPILE_API_URL"] = f"http://localhost:{PORT}"

WORKDIR = Path("/workspace/services/latex_compile_api")
DATA_DIR = Path("/workspace/data/resumes/output/aws_sdei_20260121_032832_latex")
TEST_OUTPUT = Path("remote_compile_test.pdf")

def start_server():
    print("Starting server...")
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app:app", "--port", str(PORT)],
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
    if not DATA_DIR.exists():
        print(f"Error: {DATA_DIR} not found")
        sys.exit(1)
        
    proc = start_server()
    try:
        # Use existing data directory and compile resume.tex inside it
        tex_path = DATA_DIR / "resume.tex"
        
        print(f"Calling compile_tex_remote with {tex_path}...")
        result_path = compile_tex_remote(tex_path, output_path=TEST_OUTPUT)
        
        if result_path.exists():
            print(f"Success! Output generated at {result_path}")
        else:
            print("Failed: No PDF generated")
            sys.exit(1)
            
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
    finally:
        stop_server(proc)

if __name__ == "__main__":
    main()
