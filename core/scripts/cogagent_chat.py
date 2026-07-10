#!/usr/bin/env python3
"""
YYC³ CogAgent-9B 快速启动脚本
多模态对话模型交互式使用
"""

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from PIL import Image
import os
import sys

class CogAgentChat:
    """CogAgent 对话管理器"""
    
    def __init__(self, model_path: str = None):
        """
        初始化对话管理器
        
        Args:
            model_path: 模型路径，默认使用本地路径
        """
        if model_path is None:
            model_path = os.path.expanduser("~/ai_models/Cogagent-9B")
        
        print(f"正在加载模型: {model_path}")
        
        # 加载 tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(
            model_path,
            trust_remote_code=True
        )
        
        # 检测设备
        if torch.backends.mps.is_available():
            self.device = "mps"
            print("✓ 使用 Apple Metal 加速")
        elif torch.cuda.is_available():
            self.device = "cuda"
            print("✓ 使用 NVIDIA GPU 加速")
        else:
            self.device = "cpu"
            print("⚠ 使用 CPU (速度较慢)")
        
        # 加载模型
        self.model = AutoModelForCausalLM.from_pretrained(
            model_path,
            trust_remote_code=True,
            torch_dtype=torch.bfloat16 if self.device != "cpu" else torch.float32
        ).to(self.device)
        
        self.history = []
        print("✓ 模型加载完成\n")
    
    def chat(self, query: str, image_path: str = None):
        """
        对话
        
        Args:
            query: 用户输入
            image_path: 图像路径（可选）
        """
        # 加载图像
        image = None
        if image_path and os.path.exists(image_path):
            image = Image.open(image_path)
            print(f"📷 已加载图像: {image_path}")
        
        # 生成响应
        response, self.history = self.model.chat(
            self.tokenizer,
            query,
            history=self.history,
            image=image
        )
        
        return response
    
    def clear_history(self):
        """清空对话历史"""
        self.history = []
        print("✓ 对话历史已清空\n")
    
    def show_history(self):
        """显示对话历史"""
        if not self.history:
            print("对话历史为空\n")
            return
        
        print("\n=== 对话历史 ===")
        for i, (role, content) in enumerate(self.history, 1):
            print(f"{i}. [{role}]: {content}")
        print()


def interactive_mode():
    """交互式对话模式"""
    print("=" * 50)
    print("YYC³ CogAgent-9B 交互式对话")
    print("=" * 50)
    print()
    
    # 初始化
    chat = CogAgentChat()
    
    print("使用说明:")
    print("  - 直接输入文本进行对话")
    print("  - 输入 'image:路径' 加载图像")
    print("  - 输入 'clear' 清空对话历史")
    print("  - 输入 'history' 查看对话历史")
    print("  - 输入 'quit' 或 'exit' 退出")
    print()
    
    current_image = None
    
    while True:
        try:
            user_input = input("你: ").strip()
            
            if not user_input:
                continue
            
            # 命令处理
            if user_input.lower() in ['quit', 'exit']:
                print("\n再见！")
                break
            
            if user_input.lower() == 'clear':
                chat.clear_history()
                continue
            
            if user_input.lower() == 'history':
                chat.show_history()
                continue
            
            # 图像加载
            if user_input.lower().startswith('image:'):
                image_path = user_input[6:].strip()
                if os.path.exists(image_path):
                    current_image = image_path
                    print(f"✓ 已设置图像: {image_path}\n")
                else:
                    print(f"✗ 图像文件不存在: {image_path}\n")
                continue
            
            # 对话
            response = chat.chat(user_input, current_image)
            print(f"\nAI: {response}\n")
            
        except KeyboardInterrupt:
            print("\n\n再见！")
            break
        except Exception as e:
            print(f"\n错误: {e}\n")


def demo_mode():
    """演示模式"""
    print("=" * 50)
    print("YYC³ CogAgent-9B 演示模式")
    print("=" * 50)
    print()
    
    chat = CogAgentChat()
    
    # 演示对话
    demos = [
        "你好，请介绍一下你自己",
        "你能做什么？",
        "请解释一下什么是多模态AI"
    ]
    
    for i, query in enumerate(demos, 1):
        print(f"[演示 {i}/{len(demos)}]")
        print(f"你: {query}")
        response = chat.chat(query)
        print(f"AI: {response}\n")
    
    print("✓ 演示完成")


def main():
    """主函数"""
    if len(sys.argv) > 1:
        mode = sys.argv[1]
        if mode == '--demo':
            demo_mode()
        else:
            print(f"未知模式: {mode}")
            print("使用方法:")
            print("  python cogagent_chat.py          # 交互式对话")
            print("  python cogagent_chat.py --demo   # 演示模式")
    else:
        interactive_mode()


if __name__ == "__main__":
    main()
