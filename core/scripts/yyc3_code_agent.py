#!/usr/bin/env python3
"""
YYC³ Code Agent - 基于 CodeGeeX4 的智能代码助手
"""
import os
from langchain_ollama import ChatOllama

def create_code_agent():
    """创建 CodeGeeX4 代码 Agent"""
    
    llm = ChatOllama(
        model="codegeex4",
        base_url="http://localhost:11434",
        temperature=0.7,
        num_ctx=8192,
    )
    
    return llm

def test_code_generation():
    """测试代码生成能力"""
    print("\n" + "="*60)
    print("🧪 测试 1: 代码生成")
    print("="*60)
    
    llm = create_code_agent()
    
    prompt = """写一个 Python 函数，实现以下功能：
1. 接收一个字符串列表
2. 过滤掉长度小于 3 的字符串
3. 按字母顺序排序
4. 返回去重后的结果"""
    
    response = llm.invoke(prompt)
    print(f"\n📝 生成代码:\n{response.content}")
    return response

def test_code_explanation():
    """测试代码解释能力"""
    print("\n" + "="*60)
    print("🧪 测试 2: 代码解释")
    print("="*60)
    
    llm = create_code_agent()
    
    code = """
def quicksort(arr):
    if len(arr) <= 1:
        return arr
    pivot = arr[len(arr) // 2]
    left = [x for x in arr if x < pivot]
    middle = [x for x in arr if x == pivot]
    right = [x for x in arr if x > pivot]
    return quicksort(left) + middle + quicksort(right)
"""
    
    prompt = f"""请解释以下 Python 代码的功能和原理：

```python
{code}
```"""
    
    response = llm.invoke(prompt)
    print(f"\n📖 代码解释:\n{response.content}")
    return response

def test_debug_assistance():
    """测试调试辅助能力"""
    print("\n" + "="*60)
    print("🧪 测试 3: 调试辅助")
    print("="*60)
    
    llm = create_code_agent()
    
    buggy_code = """
def find_duplicates(nums):
    result = []
    for i in range(len(nums)):
        for j in range(i+1, len(nums)):
            if nums[i] == nums[j] and nums[i] not in result:
                result.append(nums[i])
    return result
"""
    
    prompt = f"""请分析以下代码的性能问题，并提供优化方案：

```python
{buggy_code}
```"""
    
    response = llm.invoke(prompt)
    print(f"\n🔧 优化建议:\n{response.content}")
    return response

def interactive_mode():
    """交互模式"""
    print("\n" + "="*60)
    print("🎯 CodeGeeX4 交互模式")
    print("="*60)
    print("输入您的代码问题，输入 'quit' 或 'exit' 退出")
    print("-"*60)
    
    llm = create_code_agent()
    
    while True:
        try:
            user_input = input("\n👤 您: ").strip()
            
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("👋 再见！")
                break
            
            if not user_input:
                continue
                
            response = llm.invoke(user_input)
            print(f"\n🤖 CodeGeeX4: {response.content}")
            
        except KeyboardInterrupt:
            print("\n👋 再见！")
            break
        except Exception as e:
            print(f"❌ 错误: {e}")

def main():
    """主函数"""
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "test":
            test_code_generation()
            test_code_explanation()
            test_debug_assistance()
        elif command == "interactive":
            interactive_mode()
        else:
            print(f"未知命令: {command}")
            print("用法:")
            print("  python yyc3_code_agent.py test        # 运行测试")
            print("  python yyc3_code_agent.py interactive  # 交互模式")
    else:
        print("""
╔══════════════════════════════════════════════════════════════╗
║           YYC³ CodeGeeX4 Agent v1.0                       ║
║                                                              ║
║  用法:                                                       ║
║    python yyc3_code_agent.py test        # 运行测试         ║
║    python yyc3_code_agent.py interactive  # 交互模式         ║
╚══════════════════════════════════════════════════════════════╝
        """)

if __name__ == "__main__":
    main()
