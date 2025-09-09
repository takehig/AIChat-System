#!/usr/bin/env python3
# SystemPrompt統合テスト用スクリプト

import sys
import os
sys.path.append(os.path.dirname(__file__))

from prompt_client import SystemPromptClient

def test_prompt_client():
    """SystemPromptClient の動作テスト"""
    print("=== SystemPrompt統合テスト ===")
    
    # クライアント初期化
    client = SystemPromptClient()
    
    # ヘルスチェック
    print("1. ヘルスチェック...")
    is_healthy = client.health_check()
    print(f"   結果: {'成功' if is_healthy else '失敗（フォールバック使用）'}")
    
    # プロンプト取得テスト
    print("\\n2. プロンプト取得テスト...")
    prompt = client.get_prompt("strategy_planning")
    print(f"   取得したプロンプト長: {len(prompt)}文字")
    print(f"   プロンプト先頭: {prompt[:100]}...")
    
    # 存在しないキーのテスト
    print("\\n3. 存在しないキーのテスト...")
    fallback_prompt = client.get_prompt("nonexistent_key")
    print(f"   フォールバック長: {len(fallback_prompt)}文字")
    
    print("\\n=== テスト完了 ===")

if __name__ == "__main__":
    test_prompt_client()
