#!/usr/bin/env python3
"""
YYC³ 本地AI模型测试脚本
快速测试 CogAgent-9B 和 CogVideoX-5B 是否正常工作
"""

import os
import sys

def test_cogagent():
    """测试 CogAgent-9B"""
    print("\n" + "="*50)
    print("测试 CogAgent-9B")
    print("="*50 + "\n")
    
    model_path = os.path.expanduser("~/ai_models/Cogagent-9B")
    
    if not os.path.exists(model_path):
        print("❌ 模型未找到:", model_path)
        return False
    
    try:
        import torch
        from transformers import AutoTokenizer, AutoModelForCausalLM
        
        print("1. 加载 Tokenizer...")
        tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
        print("   ✓ Tokenizer 加载成功")
        
        print("\n2. 加载模型...")
        device = "mps" if torch.backends.mps.is_available() else "cpu"
        print(f"   使用设备: {device}")
        
        model = AutoModelForCausalLM.from_pretrained(
            model_path,
            trust_remote_code=True,
            torch_dtype=torch.float16 if device != "cpu" else torch.float32,
            low_cpu_mem_usage=True
        ).to(device)
        print("   ✓ 模型加载成功")
        
        print("\n3. 测试对话...")
        response, _ = model.chat(
            tokenizer,
            "你好，请用一句话介绍你自己",
            history=[]
        )
        print(f"   用户: 你好，请用一句话介绍你自己")
        print(f"   AI: {response}")
        print("   ✓ 对话测试成功")
        
        print("\n✅ CogAgent-9B 测试通过")
        return True
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_cogvideox():
    """测试 CogVideoX-5B"""
    print("\n" + "="*50)
    print("测试 CogVideoX-5B")
    print("="*50 + "\n")
    
    model_path = os.path.expanduser("~/ai_models/Cogvideox-5B")
    
    if not os.path.exists(model_path):
        print("❌ 模型未找到:", model_path)
        return False
    
    try:
        import torch
        from diffusers import CogVideoXPipeline
        from diffusers.utils import export_to_video
        
        print("1. 加载模型...")
        device = "mps" if torch.backends.mps.is_available() else "cpu"
        print(f"   使用设备: {device}")
        
        pipe = CogVideoXPipeline.from_pretrained(
            model_path,
            torch_dtype=torch.float16 if device != "cpu" else torch.float32
        ).to(device)
        
        # 内存优化
        pipe.enable_model_cpu_offload()
        pipe.enable_vae_slicing()
        print("   ✓ 模型加载成功")
        
        print("\n2. 测试视频生成 (快速测试，仅生成1帧)...")
        video = pipe(
            prompt="A test video",
            num_frames=1,
            num_inference_steps=1,
        ).frames[0]
        print("   ✓ 视频生成测试成功")
        
        print("\n3. 保存测试视频...")
        output_path = "/tmp/test_cogvideox.mp4"
        export_to_video(video, output_path, fps=8)
        print(f"   ✓ 测试视频已保存: {output_path}")
        
        print("\n✅ CogVideoX-5B 测试通过")
        return True
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_dependencies():
    """检查依赖"""
    print("\n" + "="*50)
    print("检查依赖")
    print("="*50 + "\n")
    
    dependencies = {
        "torch": "PyTorch",
        "transformers": "Transformers",
        "diffusers": "Diffusers",
        "PIL": "Pillow",
        "cv2": "OpenCV",
    }
    
    all_ok = True
    for module, name in dependencies.items():
        try:
            __import__(module)
            version = __import__(module).__version__ if hasattr(__import__(module), '__version__') else "未知"
            print(f"✓ {name}: {version}")
        except ImportError:
            print(f"✗ {name}: 未安装")
            all_ok = False
    
    return all_ok


def main():
    """主函数"""
    print("="*50)
    print("YYC³ 本地AI模型测试工具")
    print("="*50)
    
    # 检查依赖
    deps_ok = check_dependencies()
    
    if not deps_ok:
        print("\n⚠ 缺少依赖，请先安装:")
        print("  pip install torch transformers diffusers pillow opencv-python")
        return
    
    # 测试模型
    results = {}
    
    # 测试 CogAgent-9B
    cogagent_path = os.path.expanduser("~/ai_models/Cogagent-9B")
    if os.path.exists(cogagent_path):
        results['CogAgent-9B'] = test_cogagent()
    else:
        print(f"\n⚠ CogAgent-9B 未找到: {cogagent_path}")
    
    # 测试 CogVideoX-5B
    cogvideox_path = os.path.expanduser("~/ai_models/Cogvideox-5B")
    if os.path.exists(cogvideox_path):
        results['CogVideoX-5B'] = test_cogvideox()
    else:
        print(f"\n⚠ CogVideoX-5B 未找到: {cogvideox_path}")
    
    # 总结
    print("\n" + "="*50)
    print("测试总结")
    print("="*50 + "\n")
    
    for model, passed in results.items():
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"{model}: {status}")
    
    if all(results.values()):
        print("\n🎉 所有测试通过！模型可以正常使用。")
    else:
        print("\n⚠ 部分测试失败，请检查错误信息。")


if __name__ == "__main__":
    main()
