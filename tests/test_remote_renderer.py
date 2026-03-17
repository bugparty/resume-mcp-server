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
sys.modules["resume_platform.resume.repository"] = MagicMock()
sys.modules["resume_platform.infrastructure.filesystem"] = MagicMock()
sys.modules["resume_platform.models"] = MagicMock()
sys.modules["resume_platform.models.agent_resume"] = MagicMock()

# Add src to pythonpath
sys.path.append(str(Path("/workspace/src")))
from resume_platform.resume_renderer import compile_tex_remote

# Server Config
PORT = 8084
os.environ["LATEX_COMPILE_API_URL"] = f"http://localhost:{PORT}"

WORKDIR = Path("/workspace/services/latex_compile_api")
DATA_DIR = Path("/workspace/data/resumes/output/aws_sdei_20260121_032832_latex")
TEST_OUTPUT = Path("remote_compile_test.pdf")

# Default port for local test server
PORT = 8001

def start_server():
    print(f"Starting local server on port {PORT}...")
    env = os.environ.copy()
    # Ensure local server knows where to find things if needed, 
    # though usually it runs entirely in the temp dir context.
    
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app:app", "--port", str(PORT)],
        cwd=WORKDIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        preexec_fn=os.setsid
    )
    time.sleep(3) # Wait for startup
    return proc

def stop_server(proc):
    if proc:
        print("Stopping server...")
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        proc.wait()

def main():
    if not DATA_DIR.exists():
        print(f"Error: {DATA_DIR} not found")
        sys.exit(1)

    # Check if we should use an external API
    # The default in resume_renderer is http://latex_compile_api:8080
    # If the user wants to test that specifically, they can set this env var
    # or if we are running in a mode where we want to test the docker service.
    
    # We'll support an explicit flag or env var to skip local server
    use_remote = os.getenv("USE_REMOTE_API", "false").lower() == "true"
    api_url = os.getenv("LATEX_COMPILE_API_URL")
    
    proc = None
    
    try:
        if use_remote or (api_url and "localhost" not in api_url and "127.0.0.1" not in api_url):
             print(f"Using remote API: {api_url or 'default (http://latex_compile_api:8080)'}")
        else:
            # Start local server
            proc = start_server()
            # If we started a local server, ensure the client uses it
            # We override the env var for the function call context if needed, 
            # but compile_tex_remote reads os.environ. 
            # Since we can't easily patch os.environ for the imported function without affecting global state,
            # we should update os.environ here before calling it, or pass the url explicitly.
            current_api_url = f"http://localhost:{PORT}"
            print(f"Using local API: {current_api_url}")
            
            # We verify the server actually started
            if proc.poll() is not None:
                stdout, stderr = proc.communicate()
                print(f"Server failed to start:\nSTDOUT: {stdout.decode()}\nSTDERR: {stderr.decode()}")
                sys.exit(1)
                
            # For local test, we explicitly pass the URL to avoid relying on the default env var
            # which might assume the docker service name.
            # But since compile_tex_remote reads env var if arg is None, we can just pass arg.
            
        # Use existing data directory and compile resume.tex inside it
        tex_path = DATA_DIR / "resume.tex"
        
        print(f"Calling compile_tex_remote with {tex_path}...")
        
        # If proc is None, we are using remote. If proc is set, we use localhost.
        target_url = None
        if proc:
             target_url = f"http://localhost:{PORT}"
        
        # Note: compile_tex_remote will check env var LATEX_COMPILE_API_URL if target_url is None
        result_path = compile_tex_remote(tex_path, output_path=TEST_OUTPUT, api_base_url=target_url)
        
        if result_path.exists():
            print(f"Success! Output generated at {result_path}")
        else:
            print("Failed: No PDF generated")
            sys.exit(1)
            
    except Exception as e:
        print(f"Error: {e}")
        if proc:
             print("Server logs (tail):")
             # This might block if pipe is full, but strictly for debugging
             # In production tests, use proper non-blocking reads.
        sys.exit(1)
    finally:
        stop_server(proc)

if __name__ == "__main__":
    main()
