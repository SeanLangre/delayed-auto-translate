#!/usr/bin/env python3
"""
Download a larger, more accurate Vosk model.
The larger model is ~1.8GB but provides much better accuracy.
"""
import os
import urllib.request
import zipfile
import sys

# Large model - much better accuracy but bigger download
MODEL_URL = "https://alphacephei.com/vosk/models/vosk-model-en-us-0.22.zip"
MODEL_NAME = "vosk-model-en-us-0.22"

def download_model():
    """Download and extract the large Vosk model."""
    if os.path.exists(MODEL_NAME):
        print(f"Model {MODEL_NAME} already exists. Skipping download.")
        return MODEL_NAME

    print(f"Downloading large Vosk model (1.8GB)...")
    print("This will take a while but provides much better accuracy.")
    zip_path = f"{MODEL_NAME}.zip"

    try:
        def show_progress(block_num, block_size, total_size):
            downloaded = block_num * block_size
            percent = min(downloaded * 100 / total_size, 100)
            print(f"\rProgress: {percent:.1f}%", end='', flush=True)

        urllib.request.urlretrieve(MODEL_URL, zip_path, show_progress)
        print("\n\nDownload complete. Extracting...")

        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(".")

        os.remove(zip_path)
        print(f"Model extracted successfully to {MODEL_NAME}/")
        print(f"\nTo use this model, edit live_translate.py and change:")
        print(f'  MODEL_PATH = "vosk-model-small-en-us-0.15"')
        print(f'to:')
        print(f'  MODEL_PATH = "{MODEL_NAME}"')

        return MODEL_NAME

    except Exception as e:
        print(f"\n\nError downloading model: {e}")
        sys.exit(1)

if __name__ == "__main__":
    download_model()
