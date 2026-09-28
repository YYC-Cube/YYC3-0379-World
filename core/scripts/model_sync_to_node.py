# file: model_sync_to_node.py
# description: NAS 模型仓库 → 算力节点本地 SSD 增量同步脚本（rsync 封装 + 分片对账 + dry-run）
# author: YanYuCloudCube Team <admin@0379.email>
# version: v1.0.0
# created: 2026-09-27
# status: active
# tags: [model-asset],[sync],[nas],[rsync]
# spec: docs/模型接入与注册/01-接入现状规范-v2.3.md §2.4 / 05-监控告警与Runbook.md SOP-01 Step2

"""
@file: core/scripts/model_sync_to_node.py
@description: NAS → 算力节点增量同步（规划脚本 P1 落地，替代手动 rsync）。
    语义（对齐规范 01 §2.4 生产分发策略）：
      - rsync -a --info=progress2 --partial 增量传输（断点续传，权重 GB~TB 级必需）
      - 排除 NAS 侧校验报告与临时文件（model_checksum.report / *.tmp / .DS_Store）
      - 同步后自动分片对账（引用 model_asset_verify 的 shard_manifest 校验）
      - --dry-run 只输出计划不落盘（CI/预检）
    用法（在算力节点上执行；源经 NFS 挂载或 ssh）：
      python core/scripts/model_sync_to_node.py \\
          --src /Volume1/yyc3_hd/data/Qwen/Qwen3.8-27B \\
          --dst /home/yyc3/models/Qwen3.8-27B
      追加 --dry-run 预检；--ssh yyc3-45 走 ssh 远端源（NFS 未挂载场景）
@author: YanYuCloudCube Team <admin@0379.email>
@license: MIT
@copyright Copyright (c) 2026 YanYuCloudCube Team
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

# 复用校验脚本的分片对账（同包 core/scripts；脚本直跑场景 sys.path 兜底）
sys.path.insert(0, str(Path(__file__).resolve().parent))
from model_asset_verify import check_shard_manifest  # noqa: E402

EXCLUDES = ["model_checksum.report", "*.tmp", ".DS_Store", "__pycache__"]


def build_rsync_command(src: str, dst: str, ssh: Optional[str], dry_run: bool) -> List[str]:
    """构造 rsync 命令（--partial 断点续传；exclude 过滤 NAS 侧杂物）。"""
    cmd = ["rsync", "-a", "--info=progress2", "--partial"]
    for pattern in EXCLUDES:
        cmd += ["--exclude", pattern]
    if dry_run:
        cmd.append("--dry-run")
    if ssh:
        cmd += ["-e", f"ssh {ssh}"]
    cmd += [src.rstrip("/") + "/", dst.rstrip("/") + "/"]
    return cmd


def plan_sync(src: Path, dst: Path) -> dict:
    """增量计划（不经 rsync：对比源/目标文件集合，供 dry-run 与单测）。"""
    src_files = {p.relative_to(src).as_posix() for p in src.rglob("*") if p.is_file()}
    dst_files = (
        {p.relative_to(dst).as_posix() for p in dst.rglob("*") if p.is_file()}
        if dst.exists()
        else set()
    )
    to_copy = sorted(src_files - dst_files)
    # 同名但更小的文件视为「上次中断的残片」需重传（rsync --partial 语义近似）
    partial = sorted(
        f for f in (src_files & dst_files) if (src / f).stat().st_size > (dst / f).stat().st_size
    )
    return {
        "src": str(src),
        "dst": str(dst),
        "total_source_files": len(src_files),
        "already_synced": len(src_files & dst_files) - len(partial),
        "to_copy": to_copy,
        "partial_resume": partial,
    }


def run_sync(src: str, dst: str, ssh: Optional[str] = None, dry_run: bool = False) -> int:
    """执行同步；返回 rsync 退出码（同步后自动分片对账，失败返回 3）。"""
    src_path, dst_path = Path(src).expanduser(), Path(dst).expanduser()
    if not src_path.is_dir() and not ssh:
        print(f"❌ 源目录不存在: {src_path}", file=sys.stderr)
        return 2
    if not dry_run:
        dst_path.mkdir(parents=True, exist_ok=True)

    cmd = build_rsync_command(src, dst, ssh, dry_run)
    print(f"▶ {'[dry-run] ' if dry_run else ''}同步: {src} → {dst}")
    if shutil.which("rsync") is None:
        print("❌ 未找到 rsync（请安装：brew/apt install rsync）", file=sys.stderr)
        return 2
    completed = subprocess.run(cmd)
    if completed.returncode != 0:
        print(f"❌ rsync 退出码 {completed.returncode}", file=sys.stderr)
        return completed.returncode
    if dry_run:
        return 0

    # 同步后门禁：目标侧分片对账（权重映射 vs 实际文件）
    result = check_shard_manifest(dst_path)
    mark = "✅" if result.ok else "❌"
    print(f"{mark} 同步后分片对账: {result.message}")
    return 0 if result.ok else 3


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="NAS → 算力节点本地 SSD 模型增量同步")
    parser.add_argument("--src", required=True, help="源模型目录（NFS 挂载路径或 ssh 远端路径）")
    parser.add_argument("--dst", required=True, help="目标本地 SSD 路径")
    parser.add_argument("--ssh", default=None, help="可选：ssh 主机名（源走 ssh 传输）")
    parser.add_argument("--dry-run", action="store_true", help="只输出计划不落盘")
    parser.add_argument("--plan", action="store_true", help="输出本地增量计划（不经 rsync）")
    args = parser.parse_args(argv)

    if args.plan:
        src_path, dst_path = Path(args.src).expanduser(), Path(args.dst).expanduser()
        if not src_path.is_dir():
            print(f"❌ 源目录不存在: {src_path}", file=sys.stderr)
            return 2
        plan = plan_sync(src_path, dst_path)
        to_copy = plan["to_copy"]
        print(
            f"📋 增量计划: 共 {plan['total_source_files']} 文件，"
            f"已同步 {plan['already_synced']}，待传 {len(to_copy)}，续传 {len(plan['partial_resume'])}"
        )
        for f in to_copy[:20]:
            print(f"  + {f}")
        if len(to_copy) > 20:
            print(f"  … 其余 {len(to_copy) - 20} 项省略")
        return 0

    return run_sync(args.src, args.dst, ssh=args.ssh, dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
