import requests
import os
import time
import subprocess
import signal
import sys
from pathlib import Path

# Configuration
PORT = 8083
URL = f"http://localhost:{PORT}/v1/compile"
DATA_DIR = Path("/workspace/data/resumes/output/aws_sdei_20260121_032832_latex")
OUTPUT_PDF = Path("verified_output.pdf")
WORKDIR = Path("/workspace/services/latex_compile_api")

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

def collect_files(data_dir):
    files_to_upload = []
    # Using 'files' list of tuples: ('files', (filename_with_path, file_handle, content_type))
    # We need to compute relative path for filename
    
    for root, dirs, files in os.walk(data_dir):
        for file in files:
            if file.endswith(".pdf") or file.endswith(".aux") or file.endswith(".log"):
                continue # Skip generated files
            
            full_path = Path(root) / file
            rel_path = full_path.relative_to(data_dir)
            
            # Open file in binary mode
            # Requests will close them? No, we should keep them open or read content.
            # Reading content is safer for a script.
            content = full_path.read_bytes()
            
            # Syntax: ('files', (filename, content))
            files_to_upload.append(('files', (str(rel_path), content)))
            print(f"Adding: {rel_path}")
            
    return files_to_upload

def main():
    proc = start_server()
    try:
        files = collect_files(DATA_DIR)
        print(f"Uploading {len(files)} files...")
        
        # We also need to send main_file param if it's not detected (it is resume.tex here)
        data = {"main_file": "resume.tex"}
        
        resp = requests.post(URL, files=files, data=data)
        
        if resp.status_code == 200:
            print("Success! PDF generated.")
            OUTPUT_PDF.write_bytes(resp.content)
            print(f"Saved to {OUTPUT_PDF.absolute()}")
        else:
            print(f"Failed: {resp.status_code}")
            print(resp.text)
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        stop_server(proc)

if __name__ == "__main__":
    main()
