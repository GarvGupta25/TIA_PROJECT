import json
import os
import re

from confidence import assign_status
from validator import validate_record


MODEL_LOCAL_PATH = os.path.join(os.path.dirname(__file__), "models", "qwen2_5_vl_7b")
USE_4BIT = False
_MODEL = None
_PROCESSOR = None


def _model_ready():
    return os.path.exists(os.path.join(MODEL_LOCAL_PATH, "config.json"))


def _load_qwen():
    global _MODEL, _PROCESSOR
    if _MODEL is not None and _PROCESSOR is not None:
        return _MODEL, _PROCESSOR
    if not _model_ready():
        raise FileNotFoundError(
            f"Qwen weights not found at {MODEL_LOCAL_PATH}. Copy the Qwen2.5-VL-7B-Instruct snapshot there first."
        )
    from transformers import AutoProcessor

    try:
        from transformers import Qwen2_5_VLForConditionalGeneration as QwenModel
    except ImportError:
        from transformers import Qwen2VLForConditionalGeneration as QwenModel

    kwargs = {"local_files_only": True, "device_map": "auto"}
    if USE_4BIT:
        from transformers import BitsAndBytesConfig

        kwargs["quantization_config"] = BitsAndBytesConfig(load_in_4bit=True)
    _MODEL = QwenModel.from_pretrained(MODEL_LOCAL_PATH, **kwargs)
    _PROCESSOR = AutoProcessor.from_pretrained(MODEL_LOCAL_PATH, local_files_only=True)
    return _MODEL, _PROCESSOR


def _parse_json(text):
    match = re.search(r"\{.*\}|\[.*\]", text, re.S)
    if not match:
        raise ValueError("Qwen did not return JSON.")
    data = json.loads(match.group(0))
    return data if isinstance(data, list) else [data]


def extract_from_image(file_path: str, selected_client_code: str):
    from PIL import Image
    from qwen_vl_utils import process_vision_info

    model, processor = _load_qwen()
    image = Image.open(file_path).convert("RGB")
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image", "image": image},
                {
                    "type": "text",
                    "text": (
                        "Extract timesheet rows as JSON array. Fields: emp_id, full_name, "
                        "working_days, ot_hours, submitted_total, iban, reimbursements."
                    ),
                },
            ],
        }
    ]
    text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    image_inputs, video_inputs = process_vision_info(messages)
    inputs = processor(text=[text], images=image_inputs, videos=video_inputs, padding=True, return_tensors="pt").to(model.device)
    generated_ids = model.generate(**inputs, max_new_tokens=512)
    output_text = processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
    records = []
    for item in _parse_json(output_text):
        record = {
            "source": "image",
            "emp_id": item.get("emp_id"),
            "full_name": item.get("full_name"),
            "working_days": float(item.get("working_days") or 0),
            "ot_hours": float(item.get("ot_hours") or 0),
            "submitted_total": item.get("submitted_total"),
            "iban": item.get("iban"),
            "reimbursements": item.get("reimbursements") or [],
            "raw_input_snapshot": item,
            "anomaly_flags": [],
        }
        records.append(assign_status(validate_record(record, selected_client_code)))
    return records
