# models.py の基本動作確認（pydantic不要部分のみ）
import sys
sys.path.append('.')

def test_dataclasses_only():
    """データクラスのみの動作確認"""
    
    # 直接インポートしてテスト
    from dataclasses import dataclass
    from typing import List, Optional, Dict, Any
    
    @dataclass
    class TestStep:
        step: int
        tool: str
        reason: str
    
    @dataclass  
    class TestStrategy:
        steps: List[TestStep]
    
    # テスト実行
    step = TestStep(step=1, tool="test_tool", reason="テスト用")
    strategy = TestStrategy(steps=[step])
    
    print(f"✅ TestStep: {step.tool}")
    print(f"✅ TestStrategy: {len(strategy.steps)} steps")
    print("🎯 データクラス基本動作確認完了")

if __name__ == "__main__":
    test_dataclasses_only()
