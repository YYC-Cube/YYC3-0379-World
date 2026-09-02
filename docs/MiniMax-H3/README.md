# MiniMax-H3（DiffSynth本地版）· Mac M4 Max 128GB 资料库

> 本目录由两份源文档整理抽取而来，所有内容按「环境部署 → 推理脚本 → 批量迭代 → 提示词工程」分类归档，可独立使用。
>
> 源文档：
> - `Mac-M4-Max-128GB-MiniMax-H3-NF4完整部署脚本.md`
> - `MiniMax-H3-DiffSynth本地版-提示词模板.md`

## 目录结构

```text
MiniMax-H3/
├── README.md                          ← 本文件（总索引）
├── docs/                              ← 指南文档
│   ├── 01-环境部署指南.md              ← Miniforge + PyTorch MPS + DiffSynth-Studio 安装
│   ├── 02-避坑指南与排障手册.md         ← M4避坑清单 + 报错排查 + 提示词避坑
│   ├── 03-批量迭代流水线说明.md         ← 闭环工作流：生成→打分→分析→更新Seed
│   └── 04-演进规划与闭环优化机制.md     ← 现状评审 + 行业对标 + 6-Phase演进路线 + 双闭环
├── prompts/
│   └── README.md                      ← 提示词模板（Ref2VA/FL2VA/音色参考）+ 最佳实践
└── scripts/
    ├── batch_ref2va_nf4.py            ← ★ 主生成脚本 v2（manifest化+性能基线+断点续跑）
    ├── score_lipsync.py               ← ★ SyncNet自动口型评分（双后端：SyncNet/启发式）
    ├── lib/
    │   └── h3_common.py               ← ★ 共享库（模型加载/Manifest/性能计时/评分后端）
    ├── h3_m4_fl2va.py                 ← FL2VA 单次推理（文生音视频，推荐首选）
    ├── h3_m4_ref2va.py                ← Ref2VA 单次推理（参考图口型同步数字人）
    ├── h3_m4_ref2va_batch.py          ← Ref2VA 基础批量（多seed循环）
    ├── h3_m4_fl2va_batch.py           ← FL2VA 基础批量（多seed循环）
    ├── batch-full/                    ← 完整版批量（断点续跑+日志）
    │   ├── h3_m4_ref2va_batch_resume.py
    │   ├── h3_m4_fl2va_batch_resume.py
    │   ├── h3_pruned_ref2va_batch_resume.py
    │   ├── h3_pruned_fl2va_batch_resume.py
    │   ├── h3_pruned_ref2va_custom_ref.py    ← 自定义本地参考图
    │   └── h3_nf4_ref2va_custom_ref.py       ← 自定义本地参考图
    ├── multi-image-report/            ← 多图批量 + Markdown报告
    │   ├── h3_nf4_ref2va_multi.py            ← 多参考图循环（NF4）
    │   ├── h3_pruned_ref2va_multi.py         ← 多参考图循环（Pruned）
    │   ├── h3_nf4_ref2va_multi_report.py     ← 多图+报告+评分+缺陷标签+闭环框架（NF4）
    │   └── h3_pruned_ref2va_multi_report.py  ← 多图+报告+评分+缺陷标签+闭环框架（Pruned）
    └── pipeline-tools/                ← 闭环流水线工具链
        ├── pipeline_auto.py                  ← 一键全流程 v2（生成→自动评分→人工精评→分析→更新Seed）
        ├── analyze_report.py                 ← 报告分析 v2（双格式兼容：manifest/legacy md）
        ├── update_seed_list.py               ← 最优Seed自动写回主脚本
        ├── clean_batch.py                    ← 批次清理（保留打分记录）
        └── export_multi_batch_summary.py     ← 多批次评分汇总对比
```

## 快速开始

```bash
# 1. 环境部署（详见 docs/01-环境部署指南.md）
conda activate h3-m4

# 2. 单次推理验证
python scripts/h3_m4_fl2va.py

# 3. 数字人口型同步（需参考图）
python scripts/h3_m4_ref2va.py

# 4. 批量生产 + 迭代闭环（v2：含自动口型评分，详见 docs/03、docs/04）
python scripts/pipeline-tools/pipeline_auto.py
```

## 客观评估层（v2 新增）

| 组件 | 说明 |
| ---- | ---- |
| manifest.json | 批次单一事实源：参数/seed/状态/耗时/内存峰值/客观分/人工分 |
| score_lipsync.py | 双后端：SyncNet（`pip install syncnet-python`+权重）优先；无权重自动降级启发式音画活跃度匹配（合成验证：同步0.98 vs 错位0.76） |
| 性能基线 | 每次推理记录 gen_seconds / peak_rss_gb / mps_alloc_gb |

## 模型权重对照

| 版本 | model_id | 特点 |
| ---- | -------- | ---- |
| NF4原版 | `DiffSynth-Studio/MiniMax-H3-NF4` | 画质优先 |
| Pruned剪枝版 | `DiffSynth-Studio/MiniMax-H3-Pruned` | 推理更快、内存更低，画质略降，适合快速试seed |
| Pruned精简单文件 | `minimax-h3-fl2va-pruned-nf4.safetensors` | 单文件替换即用 |

## 关键参数速查

| 参数 | 值 | 说明 |
| ---- | -- | ---- |
| vram_limit | 96 | 128G统一内存预留96G |
| 分辨率 | 480×832 | 官方推荐 |
| num_frames | 124 | 必须满足 `% 17 == 5`（Ref2VA） |
| num_inference_steps | 50 | 官方默认 |
| fps / 采样率 | 24 / 32000 | 输出视频规格 |
| 模型缓存 | `~/.modelscope/` | 约72.5GB，硬盘预留>100GB |
