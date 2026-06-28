!pip install "unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git"
!pip install --no-deps "xformers<0.0.27" "trl<0.9.0" peft accelerate bitsandbytes
import os
import random
import requests
from PIL import Image, ImageDraw, ImageFont

OUTPUT_DIR = "/content/realistic_invoices"
FONT_CURSIVE_PATH = "cursive.ttf"
FONT_URL = "https://raw.githubusercontent.com/google/fonts/main/ofl/greatvibes/GreatVibes-Regular.ttf"

os.makedirs(OUTPUT_DIR, exist_ok=True)

# Download font if missing
if not os.path.exists(FONT_CURSIVE_PATH):
    response = requests.get(FONT_URL)
    with open(FONT_CURSIVE_PATH, 'wb') as f:
        f.write(response.content)

# Generate 5 quick mock images for a fast demo setup
for i in range(1, 51):
    img = Image.new("RGB", (800, 1000), (245, 245, 235))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype(FONT_CURSIVE_PATH, 40)
    except:
        font = ImageFont.load_default()

    draw.text((100, 100), f"Invoice #{i}", fill=(40, 40, 100))
    draw.text((100, 200), f"Employee: Employee_{i}", font=font, fill=(15, 25, 65))
    draw.text((100, 300), f"Amount: {random.randint(100, 500)} AED", font=font, fill=(15, 25, 65))

    img.save(f"{OUTPUT_DIR}/invoice_{i}.png")

print(f"Successfully recreated 5 mock images in {OUTPUT_DIR}!")
import torch
from unsloth import FastVisionModel
from unsloth.trainer import UnslothVisionDataCollator
from datasets import Dataset
import json
from PIL import Image
from trl import SFTTrainer, SFTConfig

# 1. Load Model
model, tokenizer = FastVisionModel.from_pretrained(
    model_name = "unsloth/Qwen2.5-VL-7B-Instruct-bnb-4bit",
    load_in_4bit = True,
    use_gradient_checkpointing = "unsloth",
)

# 2. Setup LoRA
model = FastVisionModel.get_peft_model(
    model,
    finetune_vision_layers = False,
    finetune_language_layers = True,
    finetune_attention_modules = True,
    finetune_mlp_modules = True,
    r = 16,
    lora_alpha = 16,
    lora_dropout = 0,
    bias = "none",
)
FastVisionModel.for_training(model)

# 3. RAM-Safe Dataset Generator
def gen_dataset():
    with open("/content/dataset.jsonl", "r") as f:
        for line in f:
            data = json.loads(line)
            img = Image.open(data["image"]).convert("RGB")
            yield {
                "messages": [
                    {"role": "user", "content": [
                        {"type": "image", "image": img},
                        {"type": "text", "text": data["instruction"]}
                    ]},
                    {"role": "assistant", "content": [{"type": "text", "text": data["output"]}]}
                ]
            }

formatted_dataset = Dataset.from_generator(gen_dataset)

# 4. Initialize Trainer
trainer = SFTTrainer(
    model = model,
    tokenizer = tokenizer,
    train_dataset = formatted_dataset,
    data_collator = UnslothVisionDataCollator(model, tokenizer),
    args = SFTConfig(
        per_device_train_batch_size = 1,
        gradient_accumulation_steps = 4,
        warmup_steps = 2,
        max_steps = 15, # Dropped to 15 steps for a super fast hackathon confirmation run
        learning_rate = 2e-4,
        fp16 = not torch.cuda.is_bf16_supported(),
        bf16 = torch.cuda.is_bf16_supported(),
        logging_steps = 1,
        output_dir = "outputs",
        optim = "adamw_8bit",
    ),
)

print("Starting safe training pipeline...")
trainer.train()
print("Training complete! Your fine-tuned adapters are ready to show off.")