import subprocess
import time
import os
import signal
import sys
from pathlib import Path

# Configuration
PORT = 8082
URL = f"http://localhost:{PORT}/v1/compile"
WORKDIR = Path(__file__).parent.parent

def start_server():
    print("Starting server...")
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app:app", "--port", str(PORT)],
        cwd=WORKDIR / "services/latex_compile_api",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        preexec_fn=os.setsid 
    )
    time.sleep(3) # Wait for startup
    return proc

def stop_server(proc):
    print("Stopping server...")
    os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    proc.wait()

def create_fixtures():
    fixtures_dir = WORKDIR / "tests/fixtures"
    fixtures_dir.mkdir(parents=True, exist_ok=True)
    
    (fixtures_dir / "main.tex").write_text(r"""
\documentclass{article}
\begin{document}
Hello World
\input{sub.tex}
\end{document}
""")

    (fixtures_dir / "sub.tex").write_text(r"""
From Sub File
""")

    # Create directory structure fixture
    (fixtures_dir / "chapters").mkdir(exist_ok=True)
    (fixtures_dir / "chapters/intro.tex").write_text(r"Intro Content")
    
    (fixtures_dir / "main_structure.tex").write_text(r"""
\documentclass{article}
\begin{document}
Structure Test
\input{chapters/intro.tex}
\end{document}
""")

    return fixtures_dir

def run_test_legacy(fixtures_dir):
    print("\n--- Test 1: Legacy Mode ---")
    # Legacy requires assets zip. let's make a dummy one.
    import zipfile
    zip_path = fixtures_dir / "assets.zip"
    with zipfile.ZipFile(zip_path, 'w') as zf:
        zf.write(fixtures_dir / "sub.tex", "sub.tex")
        
    cmd = [
        "curl", "-X", "POST", URL,
        "-F", f"latex_file=@{fixtures_dir / 'main.tex'}",
        "-F", f"assets_zip=@{zip_path}",
        "-o", str(fixtures_dir / "legacy_output.pdf"),
        "-s", "-w", "%{http_code}"
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.stdout.strip() == "200" and (fixtures_dir / "legacy_output.pdf").exists():
        print("PASS: Legacy mode produced PDF")
        return True
    else:
        print(f"FAIL: Legacy mode. Code: {result.stdout}, Stderr: {result.stderr}")
        return False

def run_test_multi_flat(fixtures_dir):
    print("\n--- Test 2: Multi-file Flat ---")
    # Upload main.tex and sub.tex as 'files'
    # curl -F files=@main.tex -F files=@sub.tex
    
    cmd = [
        "curl", "-X", "POST", URL,
        "-F", f"files=@{fixtures_dir / 'main.tex'}",
        "-F", f"files=@{fixtures_dir / 'sub.tex'}",
        "-o", str(fixtures_dir / "multi_flat_output.pdf"),
        "-s", "-w", "%{http_code}"
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.stdout.strip() == "200" and (fixtures_dir / "multi_flat_output.pdf").exists():
        print("PASS: Multi-file flat produced PDF")
        return True
    else:
        print(f"FAIL: Multi-file flat. Code: {result.stdout}, Stderr: {result.stderr}")
        return False

def run_test_structure(fixtures_dir):
    print("\n--- Test 3: Multi-file Structure (via filename shim) ---")
    # Curl by default sends the basename. 
    # To test directory structure, we need to artificially rename the file in the upload info or rely on client setting filename.
    # Curl allows setting filename with -F "key=@file;filename=path/to/file"
    
    cmd = [
        "curl", "-X", "POST", URL,
        "-F", f"files=@{fixtures_dir / 'main_structure.tex'};filename=main.tex",
        "-F", f"files=@{fixtures_dir / 'chapters/intro.tex'};filename=chapters/intro.tex",
        "-F", "main_file=main.tex", 
        "-o", str(fixtures_dir / "structure_output.pdf"),
        "-s", "-w", "%{http_code}"
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.stdout.strip() == "200" and (fixtures_dir / "structure_output.pdf").exists():
        print("PASS: Multi-file structure produced PDF")
        return True
    else:
        print(f"FAIL: Multi-file structure. Code: {result.stdout}, Stderr: {result.stderr}")
        return False

def main():
    proc = start_server()
    failed = False
    try:
        fixtures_dir = create_fixtures()
        if not run_test_legacy(fixtures_dir): failed = True
        if not run_test_multi_flat(fixtures_dir): failed = True
        if not run_test_structure(fixtures_dir): failed = True
    finally:
        stop_server(proc)
        
    if failed:
        sys.exit(1)
    else:
        print("\nAll tests passed!")

if __name__ == "__main__":
    main()
