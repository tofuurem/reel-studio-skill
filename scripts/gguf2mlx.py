"""Convert Handy's Parakeet TDT 0.6B v3 GGUF (Q8_0) into a parakeet-mlx model folder — no re-download.

Usage: ~/.cache/reel-studio/pkvenv/bin/python -I gguf2mlx.py <model.gguf> <out_dir>   (setup_env.sh runs it)
out_dir must already hold the parakeet-mlx config.json (mlx-community/parakeet-tdt-0.6b-v3).
"""

import json
import re
import sys
from pathlib import Path

import mlx.core as mx
import numpy as np
from gguf import GGUFReader
from gguf.quants import dequantize
from mlx.utils import tree_flatten
from parakeet_mlx.utils import from_config

RENAMES = [
    (r"^enc\.blocks\.", "encoder.layers."),
    (r"^enc\.", "encoder."),
    (r"\.norm_ff(\d)\.", r".norm_feed_forward\1."),
    (r"\.ff(\d)\.", r".feed_forward\1."),
    (r"\.norm_attn\.", ".norm_self_att."),
    (r"\.attn\.", ".self_attn."),
    (r"\.conv\.pointwise(\d)\.", r".conv.pointwise_conv\1."),
    (r"\.conv\.depthwise\.", ".conv.depthwise_conv."),
    (r"\.conv\.bn\.", ".conv.batch_norm."),
    (r"^pred\.embed\.", "decoder.prediction.embed."),
    (r"^pred\.lstm\.", "decoder.prediction.dec_rnn.lstm."),
    (r"^joint\.out\.", "joint.joint_net.2."),
]


def rename(name: str) -> str:
    for pattern, repl in RENAMES:
        name = re.sub(pattern, repl, name)
    return name


def main(gguf_path: str, out_dir: str) -> None:
    out = Path(out_dir)
    config = json.loads((out / "config.json").read_text())
    expected = dict(tree_flatten(from_config(config).parameters()))

    reader = GGUFReader(gguf_path)
    tokens = [bytes(reader.fields["tokenizer.ggml.tokens"].parts[i]).decode() for i in reader.fields["tokenizer.ggml.tokens"].data]
    vocab = config["joint"]["vocabulary"]
    assert tokens[: len(vocab)] == vocab, "GGUF tokenizer differs from config vocabulary"

    weights = {}
    for t in reader.tensors:
        key = rename(t.name)
        assert key in expected, f"unmapped tensor {t.name} -> {key}"
        arr = dequantize(t.data, t.tensor_type).astype(np.float32).reshape(tuple(int(d) for d in reversed(t.shape)))
        want = tuple(expected[key].shape)
        if arr.shape != want:
            # PyTorch conv layouts -> MLX channels-last: (O, I, K) -> (O, K, I), (O, I, H, W) -> (O, H, W, I)
            arr = arr.transpose(0, 2, 1) if arr.ndim == 3 else arr.transpose(0, 2, 3, 1)
        assert arr.shape == want, f"{key}: {arr.shape} != {want}"
        weights[key] = mx.array(arr).astype(mx.bfloat16)

    missing = set(expected) - set(weights)
    assert not missing, f"missing: {sorted(missing)[:5]}"
    mx.save_safetensors(str(out / "model.safetensors"), weights)
    print(f"OK {len(weights)} tensors -> {out / 'model.safetensors'}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
