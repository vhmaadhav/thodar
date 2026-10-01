"""Self-hosted AI4Bharat IndicConformer speech-to-text, so voice notes never leave our server.

The model is MIT-licensed but gated: accept its terms at
https://huggingface.co/ai4bharat/indic-conformer-600m-multilingual and run `hf auth login` first.

    uv run --with torch --with torchaudio --with transformers --with onnxruntime \
        python scripts/indicconformer_server.py   # serves POST http://localhost:8001/transcribe

Then set THODAR_STT_PROVIDER=indicconformer.
"""

import io

import torch
import torchaudio
import uvicorn
from fastapi import FastAPI, Form, UploadFile
from transformers import AutoModel

MODEL_ID = "ai4bharat/indic-conformer-600m-multilingual"
model = AutoModel.from_pretrained(MODEL_ID, trust_remote_code=True)
app = FastAPI(title="IndicConformer")


@app.post("/transcribe")
async def transcribe(file: UploadFile, language: str = Form("ta"), decoder: str = Form("rnnt")):
    wav, sr = torchaudio.load(io.BytesIO(await file.read()))
    wav = torch.mean(wav, dim=0, keepdim=True)  # mono
    if sr != 16000:
        wav = torchaudio.functional.resample(wav, sr, 16000)
    return {"text": model(wav, language, decoder), "model": MODEL_ID}


if __name__ == "__main__":
    uvicorn.run(app, port=8001)
