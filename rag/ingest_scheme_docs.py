import os
from pathlib import Path

def main():
    data_dir = Path(__file__).parent.parent / "data" / "scheme_guidelines"
    if not data_dir.exists():
        print(f"Data directory {data_dir} does not exist. Creating it...")
        data_dir.mkdir(parents=True, exist_ok=True)
        
    print(f"Scanning {data_dir} for scheme guidelines...")
    files = list(data_dir.glob("*.md"))
    
    if not files:
        print("No documents found to ingest.")
    else:
        print(f"Successfully 'ingested' {len(files)} scheme guideline documents into the mock vector store.")
        for f in files:
            print(f" - {f.name}")

if __name__ == "__main__":
    main()
