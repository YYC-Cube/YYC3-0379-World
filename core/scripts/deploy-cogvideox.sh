#!/bin/bash

# YYC³ CogVideoX-5B 快速部署脚本
# 自动化部署视频生成模型

set -e

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "========================================"
echo "YYC³ CogVideoX-5B 部署工具"
echo "========================================"
echo ""

# 检测系统
detect_system() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        SYSTEM="mac"
        echo -e "${GREEN}检测到 macOS 系统${NC}"
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        SYSTEM="linux"
        echo -e "${GREEN}检测到 Linux 系统${NC}"
    else
        echo -e "${RED}不支持的系统: $OSTYPE${NC}"
        exit 1
    fi
}

# 检测 GPU
detect_gpu() {
    echo -e "${BLUE}[1/6] 检测 GPU...${NC}"
    
    if command -v nvidia-smi &> /dev/null; then
        GPU_TYPE="nvidia"
        GPU_INFO=$(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader | head -1)
        echo -e "${GREEN}✓ NVIDIA GPU: $GPU_INFO${NC}"
    elif [[ "$SYSTEM" == "mac" ]]; then
        GPU_TYPE="apple"
        CHIP=$(sysctl -n machdep.cpu.brand_string)
        echo -e "${GREEN}✓ Apple Silicon: $CHIP${NC}"
    else
        echo -e "${YELLOW}⚠ 未检测到 GPU，将使用 CPU（速度较慢）${NC}"
        GPU_TYPE="cpu"
    fi
}

# 检查 Python
check_python() {
    echo -e "${BLUE}[2/6] 检查 Python 环境...${NC}"
    
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
        echo -e "${GREEN}✓ Python 版本: $PYTHON_VERSION${NC}"
    else
        echo -e "${RED}✗ 未找到 Python3，请先安装 Python 3.10+${NC}"
        exit 1
    fi
    
    if command -v conda &> /dev/null; then
        echo -e "${GREEN}✓ Conda 已安装${NC}"
        USE_CONDA=true
    else
        echo -e "${YELLOW}⚠ Conda 未安装，将使用 venv${NC}"
        USE_CONDA=false
    fi
}

# 创建虚拟环境
create_env() {
    echo -e "${BLUE}[3/6] 创建虚拟环境...${NC}"
    
    ENV_NAME="cogvideox"
    
    if [ "$USE_CONDA" = true ]; then
        echo "使用 Conda 创建环境..."
        conda create -n $ENV_NAME python=3.10 -y
        echo -e "${GREEN}✓ Conda 环境已创建: $ENV_NAME${NC}"
        echo ""
        echo -e "${YELLOW}请运行以下命令激活环境:${NC}"
        echo "  conda activate $ENV_NAME"
    else
        echo "使用 venv 创建环境..."
        python3 -m venv ${ENV_NAME}-env
        echo -e "${GREEN}✓ venv 环境已创建: ${ENV_NAME}-env${NC}"
        echo ""
        echo -e "${YELLOW}请运行以下命令激活环境:${NC}"
        if [[ "$SYSTEM" == "mac" ]] || [[ "$SYSTEM" == "linux" ]]; then
            echo "  source ${ENV_NAME}-env/bin/activate"
        else
            echo "  ${ENV_NAME}-env\\Scripts\\activate"
        fi
    fi
}

# 安装依赖
install_dependencies() {
    echo -e "${BLUE}[4/6] 安装依赖包...${NC}"
    
    echo "安装 PyTorch..."
    if [ "$GPU_TYPE" = "nvidia" ]; then
        pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
    elif [ "$GPU_TYPE" = "apple" ]; then
        pip install torch torchvision torchaudio
    else
        pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
    fi
    
    echo "安装 CogVideoX..."
    pip install diffusers transformers accelerate sentencepiece
    
    echo "安装其他依赖..."
    pip install opencv-python pillow imageio imageio-ffmpeg
    
    echo -e "${GREEN}✓ 依赖安装完成${NC}"
}

# 下载模型
download_model() {
    echo -e "${BLUE}[5/6] 下载模型...${NC}"
    
    MODEL_DIR="$HOME/ai_models/CogVideoX-5b"
    
    if [ -d "$MODEL_DIR" ]; then
        echo -e "${YELLOW}模型目录已存在: $MODEL_DIR${NC}"
        read -p "是否重新下载? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo -e "${GREEN}✓ 使用现有模型${NC}"
            return
        fi
    fi
    
    echo "开始下载模型 (约 10GB)..."
    pip install huggingface_hub
    huggingface-cli download THUDM/CogVideoX-5b \
        --local-dir "$MODEL_DIR" \
        --local-dir-use-symlinks False
    
    echo -e "${GREEN}✓ 模型下载完成${NC}"
}

# 创建测试脚本
create_test_script() {
    echo -e "${BLUE}[6/6] 创建测试脚本...${NC}"
    
    cat > test_cogvideox.py <<'EOF'
import torch
from diffusers import CogVideoXPipeline
from diffusers.utils import export_to_video

print("加载模型...")
pipe = CogVideoXPipeline.from_pretrained(
    "THUDM/CogVideoX-5b",
    torch_dtype=torch.float16
)

# GPU 加速
if torch.cuda.is_available():
    print("使用 NVIDIA GPU")
    pipe.to("cuda")
elif torch.backends.mps.is_available():
    print("使用 Apple Metal")
    pipe.to("mps")
else:
    print("使用 CPU (速度较慢)")

# 内存优化
pipe.enable_model_cpu_offload()
pipe.enable_vae_slicing()

print("生成测试视频...")
prompt = "A beautiful sunset over the ocean, waves gently rolling onto the beach"
video = pipe(
    prompt=prompt,
    num_frames=49,
    num_inference_steps=50,
    guidance_scale=6.0,
).frames[0]

export_to_video(video, "test_output.mp4", fps=8)
print("✓ 测试视频已保存: test_output.mp4")
EOF
    
    echo -e "${GREEN}✓ 测试脚本已创建: test_cogvideox.py${NC}"
}

# 显示完成信息
show_completion() {
    echo ""
    echo "========================================"
    echo -e "${GREEN}✅ CogVideoX-5B 部署完成！${NC}"
    echo "========================================"
    echo ""
    echo "📋 后续步骤:"
    echo ""
    echo "1. 激活虚拟环境:"
    if [ "$USE_CONDA" = true ]; then
        echo "   conda activate cogvideox"
    else
        if [[ "$SYSTEM" == "mac" ]] || [[ "$SYSTEM" == "linux" ]]; then
            echo "   source cogvideox-env/bin/activate"
        else
            echo "   cogvideox-env\\Scripts\\activate"
        fi
    fi
    echo ""
    echo "2. 运行测试:"
    echo "   python test_cogvideox.py"
    echo ""
    echo "3. 查看文档:"
    echo "   cat CogVideoX-5B部署指南.md"
    echo ""
    echo "💡 提示:"
    echo "  - 首次运行会自动下载模型 (约10GB)"
    echo "  - 建议使用 GPU 加速"
    echo "  - 可通过调整参数优化性能"
    echo ""
}

# 主函数
main() {
    detect_system
    detect_gpu
    check_python
    
    echo ""
    read -p "是否继续部署? (Y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Nn]$ ]]; then
        echo "部署已取消"
        exit 0
    fi
    
    create_env
    echo ""
    echo -e "${YELLOW}请先激活虚拟环境，然后重新运行此脚本继续安装${NC}"
    echo ""
    read -p "环境已激活，是否继续安装依赖? (Y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        install_dependencies
        download_model
        create_test_script
        show_completion
    fi
}

main
