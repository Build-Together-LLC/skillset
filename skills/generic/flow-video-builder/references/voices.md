# Voices

## Default: Piper (offline, CPU)

Piper is a small neural voice that runs on any machine without a GPU or an account. `setup.sh` installs it
and downloads one voice into `$FLOWVIDEO_HOME/voices`.

| Voice | Sound | Notes |
|---|---|---|
| `en_US-amy-medium` | Female, calm | The default. With `speed` 1.14 and `noise` 0.45 it is soft and steady. Used for the first video built with this skill |
| `en_US-hfc_female-medium` | Female, clear | A little brighter |
| `en_GB-jenny_dioco-medium` | Female, British | Warm; good for British spelling |
| `en_US-ryan-high` | Male | The first voice tried; clear, not soft |

To change voice: set `config.voice`, run `tts.py` (it downloads a missing voice). Every scene is generated
again because the voice is part of the cache key. All other Piper voices are listed at
https://huggingface.co/rhasspy/piper-voices.

### What makes it sound soft

- `speed` 1.10 to 1.20 (a slower speaking rate).
- `noise` 0.4 to 0.5 and `noise_w` 0.5 to 0.6 (less random variation between sentences).
- A short pause between sentences (0.45 seconds, built into `tts.py`).
- A low final loudness: `-21` LUFS and a 9 kHz low-pass in `assemble.py`.

### Reading things aloud

- Spell out letters: "S M S", "B F Funnel Settings", "U A T".
- Write numbers as the viewer would say them. "two reschedules", "six hours".
- Avoid symbols and long ids. Say "the booking reference" and show it.
- The warnings `Missing phoneme from id map` come from characters Piper does not know. They are harmless,
  but a word with a strange character may be read oddly; reword it.
- Listen to the result once. The build checks length, loudness and silence, not how it sounds.

## Maya1 (GPU, optional)

Maya1 (https://huggingface.co/maya-research/maya1) is a 3 billion parameter voice model with natural-language
voice descriptions and emotion tags. It needs a CUDA GPU with bf16 support and several GB of memory. It was
tried for this skill and **could not be used on the build machine**: no GPU and about 6 GB of free RAM, where
generating on the CPU would take hours for a 9 minute video.

`scripts/maya1_tts.py` writes the same files as `tts.py` (`audio/<scene>.wav` and `audio/timing.json`), so
`record.js` and `assemble.py` do not change. It is built from the model card's reference code and **has not
been run on a GPU**. On a GPU machine:

```bash
python -m venv maya && . maya/bin/activate
pip install torch transformers accelerate snac soundfile numpy
python maya1_tts.py --project DIR        # try one short scene first
```

Set the voice with `config.maya_description`, for example
`"Realistic female voice in the 30s age with american accent. Soft, calm, slow pacing."`.
Then record the scenes again (the timing differs from Piper), and assemble.

Do not install these packages into a project or bench environment. Installing `torch` and `transformers`
into a Frappe bench environment upgraded `click` and pulled several gigabytes of unused CUDA packages.

## Other options

Any engine that gives one WAV per scene and the start time of each sentence fits: write `audio/<id>.wav`
and `audio/timing.json` in the same format (`{"<id>": {"starts": [...], "total": seconds, "rate": hz, "hash": "..."}}`).
