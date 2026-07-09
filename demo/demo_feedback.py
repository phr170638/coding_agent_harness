#!/usr/bin/env python3
"""演示：反馈闭环 — 测试运行→检查→失败→修正→重试。

用临时项目模拟 Agent 反馈循环：
1. 写一个有 bug 的测试
2. 运行测试 → 失败
3. 解析失败信息
4. 修正代码
5. 重新运行 → 通过
"""

import subprocess
import tempfile
from pathlib import Path

from myagent.feedback.test_runner import TestFeedbackRunner


def main():
    print("=" * 60)
    print("反馈演示 — 测试驱动修正循环")
    print("=" * 60)
    print()

    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp)

        # 步骤 1: 写有问题的代码
        print("[Step 1] 写入初始代码（含 bug）...")
        (project / "calculator.py").write_text("""
def add(a, b):
    return a + b

def subtract(a, b):
    return a - b  # bug: should be a - b
""")
        print("  calculator.py 已写入")
        print()

        # 步骤 2: 写测试
        print("[Step 2] 写入测试...")
        (project / "test_calc.py").write_text("""
from calculator import add, subtract

def test_add():
    assert add(2, 3) == 5

def test_subtract_failing():
    assert subtract(10, 4) == 6  # will fail if subtract does a + b
""")
        print("  test_calc.py 已写入")
        print()

        # 步骤 3: 运行测试（应失败 — 因为 subtract 实现错误）
        print("[Step 3] 运行测试（预期失败）...")
        env = {"PYTHONPATH": str(project), "PATH": __import__("os").environ["PATH"]}
        result = subprocess.run(
            ["python", "-m", "pytest", str(project), "-v", "--tb=short"],
            capture_output=True, text=True, timeout=30, env=env,
        )
        print(f"  退出码: {result.returncode}")
        if result.returncode != 0:
            print("  测试失败 — Agent 收到反馈信号")
            # 提取失败信息
            for line in result.stdout.split("\n"):
                if "FAILED" in line or "AssertionError" in line:
                    print(f"    {line.strip()}")
        print()

        # 步骤 4: Agent 根据反馈修正代码
        print("[Step 4] Agent 根据反馈修正代码...")
        (project / "calculator.py").write_text("""
def add(a, b):
    return a + b

def subtract(a, b):
    return a - b  # fixed
""")
        print("  已修正 subtract 函数")
        print()

        # 步骤 5: 重新运行测试（应通过）
        print("[Step 5] 重新运行测试（预期通过）...")
        result2 = subprocess.run(
            ["python", "-m", "pytest", str(project), "-v"],
            capture_output=True, text=True, timeout=30,
        )
        print(f"  退出码: {result2.returncode}")
        if result2.returncode == 0:
            print("  所有测试通过 — 反馈闭环完成！")
        print()

    print("=" * 60)
    print("反馈机制: 测试失败 → 解析错误 → LLM 收到上下文 → 修正 → 重测")
    print("=" * 60)


if __name__ == "__main__":
    main()
