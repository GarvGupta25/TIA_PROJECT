# ==========================================
# 1. INSTALL PACKAGES
# ==========================================
print("Installing required libraries...")
!pip install -q fastapi python-multipart uvicorn pyngrok nest-asyncio

import io
import json
import re
import torch
import nest_asyncio
import uvicorn

from PIL import Image
from fastapi import FastAPI, File, UploadFile
from pyngrok import ngrok
from unsloth import FastVisionModel

# ==========================================
# 2. NGROK AUTHENTICATION
# ==========================================
NGROK_TOKEN = "3Fia5BGcyCIBYtZvuYBmNbT8vEI_7p26qKphjmbdP6CSp8vqK"
ngrok.set_auth_token(NGROK_TOKEN)

# ==========================================
# 3. LOAD FINE-TUNED MODEL
# ==========================================
print("Loading fine-tuned model...")

model, tokenizer = FastVisionModel.from_pretrained(
    model_name="/content/outputs/checkpoint-15",
    load_in_4bit=True,
)

FastVisionModel.for_inference(model)

print("Model loaded successfully!")

# IMPORTANT:
# Use the same instruction text you used in dataset.jsonl if possible.
INSTRUCTION = "Extract data into JSON"

# ==========================================
# 4. HELPERS
# ==========================================
def extract_json_from_text(text):
    """
    Tries to return clean JSON if the model output contains JSON.
    Otherwise returns the raw text.
    """
    if not text:
        return ""

    match = re.search(r"\[.*\]|\{.*\}", text, re.S)
    if not match:
        return text.strip()

    raw_json = match.group(0)
    try:
        return json.loads(raw_json)
    except Exception:
        return raw_json


def run_model_on_image(image):
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image", "image": image},
                {"type": "text", "text": INSTRUCTION},
            ],
        }
    ]

    text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
    )

    # This is the important fix.
    # Do NOT do tokenizer(["text"], images=[image], ...)
    inputs = tokenizer(
        text=[text],
        images=[image],
        return_tensors="pt",
    ).to("cuda")

    with torch.inference_mode():
        outputs = model.generate(
            **inputs,
            max_new_tokens=700,
            do_sample=False,
        )

    # Remove prompt tokens so response is only generated answer
    generated_ids = outputs[:, inputs.input_ids.shape[1]:]

    decoded = tokenizer.batch_decode(
        generated_ids,
        skip_special_tokens=True,
        clean_up_tokenization_spaces=False,
    )[0]

    return extract_json_from_text(decoded)

# ==========================================
# 5. FASTAPI APP
# ==========================================
app = FastAPI()

@app.get("/")
def root():
    return {"status": "ok", "message": "Image extraction API is running"}

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/extract")
async def extract_data(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        image = Image.open(io.BytesIO(contents)).convert("RGB")

        result = run_model_on_image(image)

        # Your local dashboard can read this shape.
        return {
            "status": "success",
            "result": result,
        }

    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
        }

# ==========================================
# 6. START NGROK + SERVER
# ==========================================
ngrok.kill()
ngrok_tunnel = ngrok.connect(8000)

public_extract_url = f"{ngrok_tunnel.public_url}/extract"

print("\n" + "=" * 70)
print("YOUR LIVE PUBLIC API URL:")
print(public_extract_url)
print("=" * 70)
print("\nUse this URL in your local dashboard as IMAGE_EXTRACT_URL if it changed.\n")

config = uvicorn.Config(
    app,
    host="0.0.0.0",
    port=8000,
    log_level="info",
)

server = uvicorn.Server(config)

nest_asyncio.apply()
await server.serve()