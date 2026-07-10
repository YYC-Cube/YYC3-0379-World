"""
YYC³ CogVideoX-5B 视频生成示例
快速开始使用视频生成模型
"""

import torch
from diffusers import CogVideoXPipeline, CogVideoXDPMScheduler
from diffusers.utils import export_to_video
import gc
import os
from datetime import datetime


class CogVideoXGenerator:
    """CogVideoX 视频生成器"""
    
    def __init__(
        self,
        model_path: str = None,
        use_memory_efficient: bool = True,
        use_fast_scheduler: bool = True,
    ):
        """
        初始化视频生成器
        
        Args:
            model_path: 模型路径或HuggingFace模型ID
            use_memory_efficient: 使用内存优化
            use_fast_scheduler: 使用快速调度器
        """
        # 使用本地模型路径
        if model_path is None:
            model_path = os.path.expanduser("~/ai_models/Cogvideox-5B")
        
        print(f"加载模型: {model_path}")
        
        # 加载模型
        self.pipe = CogVideoXPipeline.from_pretrained(
            model_path,
            torch_dtype=torch.float16
        )
        
        # 使用快速调度器
        if use_fast_scheduler:
            self.pipe.scheduler = CogVideoXDPMScheduler.from_config(
                self.pipe.scheduler.config
            )
        
        # 内存优化
        if use_memory_efficient:
            self.pipe.enable_model_cpu_offload()
            self.pipe.enable_vae_slicing()
            self.pipe.enable_vae_tiling()
        
        # GPU 加速
        if torch.cuda.is_available():
            print("使用 NVIDIA GPU 加速")
            self.pipe.to("cuda")
        elif torch.backends.mps.is_available():
            print("使用 Apple Metal 加速")
            self.pipe.to("mps")
        else:
            print("使用 CPU (速度较慢)")
        
        print("✓ 模型加载完成")
    
    def generate(
        self,
        prompt: str,
        output_path: str = None,
        num_frames: int = 49,
        num_inference_steps: int = 50,
        guidance_scale: float = 6.0,
        seed: int = None,
    ) -> str:
        """
        生成视频
        
        Args:
            prompt: 文本提示词
            output_path: 输出路径
            num_frames: 帧数 (默认49帧，约6秒)
            num_inference_steps: 推理步数
            guidance_scale: 引导系数
            seed: 随机种子
        
        Returns:
            输出视频路径
        """
        # 生成输出路径
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"video_{timestamp}.mp4"
        
        # 设置随机种子
        generator = None
        if seed is not None:
            generator = torch.Generator().manual_seed(seed)
        
        print(f"生成视频: {prompt}")
        print(f"参数: frames={num_frames}, steps={num_inference_steps}, guidance={guidance_scale}")
        
        # 生成视频
        video = self.pipe(
            prompt=prompt,
            num_videos_per_prompt=1,
            num_inference_steps=num_inference_steps,
            num_frames=num_frames,
            guidance_scale=guidance_scale,
            generator=generator,
        ).frames[0]
        
        # 保存视频
        export_to_video(video, output_path, fps=8)
        print(f"✓ 视频已保存: {output_path}")
        
        return output_path
    
    def cleanup(self):
        """清理内存"""
        del self.pipe
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        print("✓ 内存已清理")


def main():
    """主函数 - 示例用法"""
    
    # 创建输出目录
    os.makedirs("outputs", exist_ok=True)
    
    # 初始化生成器
    generator = CogVideoXGenerator(
        model_path="THUDM/CogVideoX-5b",
        use_memory_efficient=True,
        use_fast_scheduler=True,
    )
    
    # 示例提示词
    prompts = [
        "A beautiful sunset over the ocean, waves gently rolling onto the beach, golden hour lighting",
        "A serene mountain lake at sunrise, mist rising from the water, peaceful atmosphere",
        "A futuristic city skyline at night, neon lights reflecting on wet streets, cyberpunk style",
    ]
    
    # 批量生成
    for i, prompt in enumerate(prompts):
        print(f"\n[{i+1}/{len(prompts)}] 生成视频...")
        output = generator.generate(
            prompt=prompt,
            output_path=f"outputs/video_{i+1}.mp4",
            num_frames=49,
            num_inference_steps=50,
            guidance_scale=6.0,
        )
    
    # 清理内存
    generator.cleanup()
    
    print("\n✅ 所有视频生成完成！")
    print(f"输出目录: {os.path.abspath('outputs')}")


if __name__ == "__main__":
    main()
