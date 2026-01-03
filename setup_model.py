#!/usr/bin/env python3
"""
Setup script to download the Vosk English model.
"""
import os
import urllib.request
import zipfile
import sys

MODEL_URL = "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip"
MODEL_NAME = "vosk-model-small-en-us-0.15"

def download_model():
    """Download and extract the Vosk model."""
    if os.path.exists(MODEL_NAME):
        print(f"Model {MODEL_NAME} already exists. Skipping download.")
        return

    print(f"Downloading Vosk model from {MODEL_URL}...")
    zip_path = f"{MODEL_NAME}.zip"

    try:
        urllib.request.urlretrieve(MODEL_URL, zip_path)
        print("Download complete. Extracting...")

        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(".")

        os.remove(zip_path)
        print(f"Model extracted successfully to {MODEL_NAME}/")

    except Exception as e:
        print(f"Error downloading model: {e}")
        sys.exit(1)

if __name__ == "__main__":
    download_model()
