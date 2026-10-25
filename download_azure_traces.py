import os
import urllib.request

def download_range(url, dest_path, max_bytes=15 * 1024 * 1024):
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    print(f"Downloading first {max_bytes / (1024*1024):.1f} MB from {url}...")
    req = urllib.request.Request(
        url,
        headers={
            "Range": f"bytes=0-{max_bytes}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        }
    )
    with urllib.request.urlopen(req) as resp:
        data = resp.read()
    
    # Trim to the last newline so we don't have a half-read row
    last_nl = data.rfind(b"\n")
    if last_nl > 0:
        data = data[:last_nl + 1]
    
    with open(dest_path, "wb") as f:
        f.write(data)
    print(f"Saved {len(data) / (1024*1024):.2f} MB to {dest_path}")

def main():
    base_url = "https://github.com/Azure/AzurePublicDataset/releases/download/dataset-llm-2024"
    code_url = f"{base_url}/AzureLLMInferenceTrace_code_1week.csv"
    conv_url = f"{base_url}/AzureLLMInferenceTrace_conv_1week.csv"

    download_range(code_url, "traces/raw_azure/AzureLLMInferenceTrace_code_3h.csv", max_bytes=15 * 1024 * 1024)
    download_range(conv_url, "traces/raw_azure/AzureLLMInferenceTrace_conv_3h.csv", max_bytes=18 * 1024 * 1024)

if __name__ == "__main__":
    main()
