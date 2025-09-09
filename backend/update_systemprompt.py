#!/usr/bin/env python3
# SystemPrompt Management のプロンプトを完全版に更新

import requests
import json

def update_strategy_prompt():
    """strategy_planning プロンプトを完全版に更新"""
    
    # 完全版プロンプト
    complete_prompt = """あなたは戦略立案の専門家です。ユーザーリクエストを分析し、必要最小限のツールのみを選択してください。

## 重要な判定ルール
1. ユーザーが明示的に要求していない情報は取得しない
2. 利用可能ツールの中から適切なものを選択する
3. ツールが不要な場合は steps を空配列 [] にする
4. 複数ツールの無駄な組み合わせを避ける

## 判定の考え方
- 情報要求の種類を特定する（商品情報、顧客情報、その他）
- 利用可能ツールの説明文と照らし合わせる
- 明示的に要求されていない情報は取得しない
- 一般的な挨拶や質問にはツールは不要"""

    # SystemPrompt Management API経由で更新
    try:
        # まず現在のプロンプトIDを取得
        response = requests.get('http://localhost:8007/api/prompt/strategy_planning')
        if response.status_code == 200:
            print("✅ strategy_planning プロンプト取得成功")
            
            # 更新用データ準備
            update_data = {
                'description': '戦略立案用システムプロンプト（完全版）',
                'prompt_text': complete_prompt
            }
            
            print("📝 SystemPrompt Management で手動更新してください:")
            print("URL: http://44.217.45.24:8007/")
            print("キー: strategy_planning")
            print("説明: 戦略立案用システムプロンプト（完全版）")
            print("プロンプト:")
            print(complete_prompt)
            
        else:
            print(f"❌ プロンプト取得失敗: {response.status_code}")
            
    except Exception as e:
        print(f"❌ エラー: {e}")

if __name__ == "__main__":
    update_strategy_prompt()
