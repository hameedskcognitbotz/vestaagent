from huggingface_hub import hf_hub_download, list_repo_files
import os

repo_id = "Claudio9701/cubicasa5k"
repo_type = "dataset"
local_dir = os.path.expanduser("~/datasets/cubicasa5k")

os.makedirs(local_dir, exist_ok=True)

try:
    print(f"Listing files in {repo_id}...")
    all_files = list_repo_files(repo_id=repo_id, repo_type=repo_type)
    print(f"Found {len(all_files)} files.")
    
    # Let's take first 20 PNGs and 20 SVGs
    png_files = [f for f in all_files if f.endswith(".png")][:20]
    svg_files = [f for f in all_files if f.endswith(".svg")][:20]
    
    files_to_download = png_files + svg_files
    print(f"Downloading {len(files_to_download)} sample files...")
    
    for filename in files_to_download:
        print(f"Downloading {filename}...")
        hf_hub_download(
            repo_id=repo_id,
            repo_type=repo_type,
            filename=filename,
            local_dir=local_dir
        )
    print("✅ Sample download complete.")
except Exception as e:
    print(f"❌ Error: {e}")
