"""
Installation Verification Script
Run this after pip install -r requirements.txt to confirm all packages are working.
"""
import sys
import importlib

REQUIRED = [
    ("numpy",                "numpy"),
    ("networkx",             "networkx"),
    ("sqlalchemy",           "sqlalchemy"),
    ("fastapi",              "fastapi"),
    ("pydantic",             "pydantic"),
    ("chromadb",             "chromadb"),
    ("sentence_transformers","sentence_transformers"),
    ("rank_bm25",            "rank_bm25"),
    ("pypdf",                "pypdf"),
    ("docx",                 "docx"),
    ("uvicorn",              "uvicorn"),
    ("yaml",                 "yaml"),
    ("dotenv",               "dotenv"),
]

OPTIONAL = [
    ("google.genai", "google-genai"),
    ("pandas",     "pandas"),
    ("matplotlib", "matplotlib"),
]

def check(packages, label):
    ok = fail = 0
    for display, mod in packages:
        try:
            m = importlib.import_module(mod)
            version = getattr(m, "__version__", "ok")
            print(f"  [OK]   {display:30s} {version}")
            ok += 1
        except Exception as e:
            print(f"  [FAIL] {display:30s} {e}")
            fail += 1
    return ok, fail

print(f"\nPython {sys.version}\n")
print("=== Required packages ===")
ok_r, fail_r = check(REQUIRED, "required")

print("\n=== Optional packages (LLM / analytics) ===")
ok_o, fail_o = check(OPTIONAL, "optional")

print(f"\nRequired: {ok_r} OK, {fail_r} FAILED")
print(f"Optional: {ok_o} OK, {fail_o} not installed\n")

if fail_r == 0:
    print("All required packages installed. System ready.")
else:
    print(f"Fix {fail_r} required package(s) before running the system.")
    sys.exit(1)
