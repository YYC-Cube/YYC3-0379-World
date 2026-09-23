# -*- coding: utf-8 -*-
"""
fuse_qkv.py — MiniCPM-V-4.6 视觉权重 qkv 融合手术（vLLM nightly 兼容转换）

背景（2026-09-24 实测定案）：openbmb hub 权重的 vision_tower 自注意力（encoder 27 层
+ vit_merger）为分离式 q/k/v_proj，vLLM nightly 的 MiniCPMV4_6ViTWindowAttentionSelfAttn
模块为融合式 qkv_proj。本脚本按行连续 thirds(q;k;v) 融合（QKVParallel 标准布局），
其余张量原样透传（语言层 q/k/v、linear_attn.in_proj_qkv 等不动）。

实测：转换后 EngineCore 权重装载全通过（原 k_proj 报错消失）；
后续仅受 N2 容量阻塞（0.80 负载无第三服务窗口），资产待部署窗口。

用法（在含 torch+safetensors 的容器内，如 yyc3/asr-qwen3:v1）：
  python3 fuse_qkv.py <src_model_dir> <dst_model_dir>
  # 例：/models/MiniCPM-V-4.6-hf → /models/MiniCPM-V-4.6-vllm
产物校验：vision 分离式残留=0；qkv_proj 总数=56（28 层×weight/bias）；张量 779→615。
"""
import re
import shutil
import sys
from pathlib import Path

import torch
from safetensors.torch import load_file, save_file

# encoder 27 层 + vit_merger（09-24 二次修复：首轮漏 merger 同报 k_proj 错）
LAYER_RE = re.compile(
    r"^(model\.vision_tower\.(?:encoder\.layers\.\d+|vit_merger))\.self_attn\.(q|k|v)_proj\.(weight|bias)$"
)


def main(src_dir: str, dst_dir: str):
    src, dst = Path(src_dir), Path(dst_dir)
    dst.mkdir(parents=True, exist_ok=True)

    # 非权重文件原样复制（config/tokenizer/chat_template/preprocessor 等）
    for f in src.iterdir():
        if f.suffix != ".safetensors" and f.is_file():
            shutil.copy(f, dst / f.name)

    state = load_file(str(src / "model.safetensors"))
    out = {}
    fused_layers = 0
    pending = {}  # prefix -> {"q.weight": t, "k.weight": t, ...}

    for key, tensor in state.items():
        m = LAYER_RE.match(key)
        if not m:
            out[key] = tensor
            continue
        prefix, part, wb = m.group(1), m.group(2), m.group(3)
        pending.setdefault(prefix, {})[part + "." + wb] = tensor

    for prefix, parts in pending.items():
        need = [p + "." + wb for p in "qkv" for wb in ("weight", "bias")]
        missing = [n for n in need if n not in parts]
        if missing:
            raise RuntimeError(f"{prefix} 缺失分量: {missing}")
        for wb in ("weight", "bias"):
            fused = torch.cat(
                [parts[f"{p}.{wb}"] for p in "qkv"], dim=0
            ).contiguous()
            out[f"{prefix}.self_attn.qkv_proj.{wb}"] = fused
        fused_layers += 1

    save_file(out, str(dst / "model.safetensors"), metadata={"format": "pt"})
    print(f"✅ 融合完成：{fused_layers} 处视觉自注意力 q/k/v → qkv_proj；张量总数 {len(state)} → {len(out)}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    main(sys.argv[1], sys.argv[2])
