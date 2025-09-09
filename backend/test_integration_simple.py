#!/usr/bin/env python3
# AIChat統合テスト - 元の通りに動作するか確認

import asyncio
import sys
import os
sys.path.append(os.path.dirname(__file__))

from ai_agent import AIAgent
from prompt_client import SystemPromptClient

async def test_basic_functionality():
    """基本機能テスト"""
    print("🧪 === AIChat統合テスト開始 ===")
    
    try:
        # 1. SystemPrompt接続テスト
        print("\\n1. SystemPrompt Management 接続テスト...")
        prompt_client = SystemPromptClient()
        health = prompt_client.health_check()
        print(f"   SystemPrompt接続: {'✅ 成功' if health else '⚠️ フォールバック'}")
        
        # 2. AIAgent初期化テスト
        print("\\n2. AIAgent初期化テスト...")
        ai_agent = AIAgent()
        print("   AIAgent初期化: ✅ 成功")
        
        # 3. 戦略立案エンジンテスト
        print("\\n3. 戦略立案エンジンテスト...")
        test_message = "商品情報を教えて"
        strategy = await ai_agent.plan_detailed_strategy(test_message)
        print(f"   戦略立案: ✅ 成功 (steps: {len(strategy.steps)})")
        
        # 4. プロンプト取得テスト
        print("\\n4. プロンプト取得テスト...")
        prompt = prompt_client.get_prompt("strategy_planning")
        print(f"   プロンプト取得: ✅ 成功 ({len(prompt)}文字)")
        
        # 5. 統合確認
        print("\\n5. 統合確認...")
        if hasattr(ai_agent, 'strategy_engine'):
            print("   strategy_engine統合: ✅ 成功")
        else:
            print("   strategy_engine統合: ❌ 失敗")
            
        if hasattr(ai_agent.strategy_engine, 'prompt_client'):
            print("   SystemPrompt統合: ✅ 成功")
        else:
            print("   SystemPrompt統合: ❌ 失敗")
        
        print("\\n🎉 === 全テスト成功 ===")
        return True
        
    except Exception as e:
        print(f"\\n❌ === テスト失敗: {e} ===")
        import traceback
        traceback.print_exc()
        return False

async def test_api_simulation():
    """API動作シミュレーションテスト"""
    print("\\n🔄 === API動作シミュレーション ===")
    
    try:
        ai_agent = AIAgent()
        
        # 簡単な質問テスト
        test_cases = [
            "こんにちは",
            "商品情報を教えて", 
            "ありがとう"
        ]
        
        for i, message in enumerate(test_cases, 1):
            print(f"\\n{i}. テストメッセージ: '{message}'")
            strategy = await ai_agent.plan_detailed_strategy(message)
            print(f"   戦略結果: {len(strategy.steps)}ステップ")
            
            if strategy.steps:
                for step in strategy.steps:
                    print(f"     - Step {step.step}: {step.tool} ({step.reason})")
            else:
                print("     - ツール不要と判定")
        
        print("\\n✅ === API動作シミュレーション成功 ===")
        return True
        
    except Exception as e:
        print(f"\\n❌ === API動作シミュレーション失敗: {e} ===")
        return False

async def main():
    """メインテスト実行"""
    print("🚀 AIChat統合テスト実行")
    
    # 基本機能テスト
    basic_ok = await test_basic_functionality()
    
    # API動作テスト
    api_ok = await test_api_simulation() if basic_ok else False
    
    # 結果サマリー
    print("\\n" + "="*50)
    print("📊 テスト結果サマリー")
    print("="*50)
    print(f"基本機能テスト: {'✅ 成功' if basic_ok else '❌ 失敗'}")
    print(f"API動作テスト: {'✅ 成功' if api_ok else '❌ 失敗'}")
    
    if basic_ok and api_ok:
        print("\\n🎉 全テスト成功！統合完了です。")
        return 0
    else:
        print("\\n⚠️ 一部テスト失敗。修正が必要です。")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
