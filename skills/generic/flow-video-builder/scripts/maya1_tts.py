#!/usr/bin/env python3
"""Narrate a flow.json with Maya1 (https://huggingface.co/maya-research/maya1). Needs a CUDA GPU.

Writes the same files as tts.py (audio/<scene>.wav at 24 kHz and audio/timing.json), so record.js and assemble.py work unchanged.
The helper functions are the model card's reference code. This script has not been run on a GPU yet: test one scene first.

    pip install torch transformers accelerate snac soundfile numpy      # in a separate environment, with a GPU
    python maya1_tts.py --project DIR
"""
import argparse
import hashlib
import json
import os
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from snac import SNAC
import soundfile as sf
import numpy as np

CODE_START_TOKEN_ID = 128257
CODE_END_TOKEN_ID = 128258
CODE_TOKEN_OFFSET = 128266
SNAC_MIN_ID = 128266
SNAC_MAX_ID = 156937
SNAC_TOKENS_PER_FRAME = 7

SOH_ID = 128259
EOH_ID = 128260
SOA_ID = 128261
BOS_ID = 128000
TEXT_EOT_ID = 128009


def build_prompt(tokenizer, description: str, text: str) -> str:
    """Build formatted prompt for Maya1."""
    soh_token = tokenizer.decode([SOH_ID])
    eoh_token = tokenizer.decode([EOH_ID])
    soa_token = tokenizer.decode([SOA_ID])
    sos_token = tokenizer.decode([CODE_START_TOKEN_ID])
    eot_token = tokenizer.decode([TEXT_EOT_ID])
    bos_token = tokenizer.bos_token
    
    formatted_text = f'<description="{description}"> {text}'
    
    prompt = (
        soh_token + bos_token + formatted_text + eot_token +
        eoh_token + soa_token + sos_token
    )
    
    return prompt


def extract_snac_codes(token_ids: list) -> list:
    """Extract SNAC codes from generated tokens."""
    try:
        eos_idx = token_ids.index(CODE_END_TOKEN_ID)
    except ValueError:
        eos_idx = len(token_ids)
    
    snac_codes = [
        token_id for token_id in token_ids[:eos_idx]
        if SNAC_MIN_ID <= token_id <= SNAC_MAX_ID
    ]
    
    return snac_codes


def unpack_snac_from_7(snac_tokens: list) -> list:
    """Unpack 7-token SNAC frames to 3 hierarchical levels."""
    if snac_tokens and snac_tokens[-1] == CODE_END_TOKEN_ID:
        snac_tokens = snac_tokens[:-1]
    
    frames = len(snac_tokens) // SNAC_TOKENS_PER_FRAME
    snac_tokens = snac_tokens[:frames * SNAC_TOKENS_PER_FRAME]
    
    if frames == 0:
        return [[], [], []]
    
    l1, l2, l3 = [], [], []
    
    for i in range(frames):
        slots = snac_tokens[i*7:(i+1)*7]
        l1.append((slots[0] - CODE_TOKEN_OFFSET) % 4096)
        l2.extend([
            (slots[1] - CODE_TOKEN_OFFSET) % 4096,
            (slots[4] - CODE_TOKEN_OFFSET) % 4096,
        ])
        l3.extend([
            (slots[2] - CODE_TOKEN_OFFSET) % 4096,
            (slots[3] - CODE_TOKEN_OFFSET) % 4096,
            (slots[5] - CODE_TOKEN_OFFSET) % 4096,
            (slots[6] - CODE_TOKEN_OFFSET) % 4096,
        ])
    
    return [l1, l2, l3]

ap = argparse.ArgumentParser()
ap.add_argument("--project", default=".")
args = ap.parse_args()
PROJ = os.path.abspath(args.project)
flow = json.load(open(os.path.join(PROJ, "flow.json")))
cfg = flow.get("config", {})
DESCRIPTION = cfg.get("maya_description", "Realistic female voice in the 30s age with american accent. Normal pitch, warm timbre, soft and calm pacing, like a product walkthrough.")
RATE, GAP = 24000, 0.45


def load():
    model = AutoModelForCausalLM.from_pretrained("maya-research/maya1", torch_dtype=torch.bfloat16, device_map="auto", trust_remote_code=True)
    tokenizer = AutoTokenizer.from_pretrained("maya-research/maya1", trust_remote_code=True)
    snac_model = SNAC.from_pretrained("hubertsiuzdak/snac_24khz").eval()
    if torch.cuda.is_available():
        snac_model = snac_model.to("cuda")
    return model, tokenizer, snac_model


def speak(model, tokenizer, snac_model, text):
    inputs = tokenizer(build_prompt(tokenizer, DESCRIPTION, text), return_tensors="pt", add_special_tokens=False)
    if torch.cuda.is_available():
        inputs = {k: v.to("cuda") for k, v in inputs.items()}
    with torch.inference_mode():
        out = model.generate(**inputs, max_new_tokens=2048, min_new_tokens=28, temperature=0.4, top_p=0.9, repetition_penalty=1.1,
                             do_sample=True, eos_token_id=CODE_END_TOKEN_ID, pad_token_id=tokenizer.pad_token_id)
    snac_tokens = extract_snac_codes(out[0, inputs["input_ids"].shape[1]:].tolist())
    if len(snac_tokens) < 7:
        raise RuntimeError("no audio generated for: " + text[:60])
    device = "cuda" if torch.cuda.is_available() else "cpu"
    codes = [torch.tensor(level, dtype=torch.long, device=device).unsqueeze(0) for level in unpack_snac_from_7(snac_tokens)]
    with torch.inference_mode():
        audio = snac_model.decoder(snac_model.quantizer.from_codes(codes))[0, 0].cpu().numpy()
    return audio[2048:] if len(audio) > 2048 else audio


def main():
    audio_dir = os.path.join(PROJ, "audio")
    os.makedirs(audio_dir, exist_ok=True)
    tpath = os.path.join(audio_dir, "timing.json")
    old = json.load(open(tpath)) if os.path.exists(tpath) else {}
    timing = {}
    model = None
    for sc in flow["scenes"]:
        h = hashlib.md5(json.dumps([sc["narr"], "maya1", DESCRIPTION]).encode()).hexdigest()
        wav = os.path.join(audio_dir, sc["id"] + ".wav")
        if old.get(sc["id"], {}).get("hash") == h and os.path.exists(wav):
            timing[sc["id"]] = old[sc["id"]]
            continue
        if model is None:
            model, tokenizer, snac_model = load()
        gap = np.zeros(int(RATE * GAP), dtype=np.float32)
        parts, starts, t = [], [], 0.0
        for sentence in sc["narr"]:  # one sentence at a time keeps each take short and steady
            a = speak(model, tokenizer, snac_model, sentence)
            starts.append(round(t, 3))
            parts += [a, gap]
            t += len(a) / RATE + GAP
        sf.write(wav, np.concatenate(parts), RATE)
        timing[sc["id"]] = {"hash": h, "starts": starts, "total": round(t, 3), "rate": RATE}
        print("wrote", wav, round(t, 1), "s")
    json.dump(timing, open(tpath, "w"), indent=1)


if __name__ == "__main__":
    main()
