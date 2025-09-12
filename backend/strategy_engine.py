# AIChat System - 戦略立案エンジン
import json
import time
import logging
from typing import Dict, Any
from models import DetailedStrategy, DetailedStep

logger = logging.getLogger(__name__)

class StrategyEngine:
    """戦略立案専用エンジン - 将来大幅拡張予定"""
    
    def __init__(self, bedrock_client, available_tools: Dict[str, Any], llm_util, enabled_tools_ref):
        self.bedrock_client = bedrock_client
        self.model_id = "anthropic.claude-3-sonnet-20240229-v1:0"
        self.available_tools = available_tools
        self.llm_util = llm_util
        self.enabled_tools = enabled_tools_ref  # ai_agent の enabled_tools を共有参照
        
        # === 将来拡張用（現在は空実装） ===
        self.query_patterns = {}      # クエリパターン学習
        self.success_history = {}     # 成功戦略履歴
        self.learning_data = {}       # 学習データ
        
    async def plan_strategy(self, user_message: str) -> DetailedStrategy:
        """戦略立案メイン処理"""
        logger.info(f"[DEBUG] plan_strategy開始")
        enabled_tools = self.get_enabled_tools()
        logger.info(f"[DEBUG] enabled_tools取得: {len(enabled_tools)}個")
        logger.info(f"[DEBUG] enabled_tools: {list(enabled_tools.keys()) if enabled_tools else 'None'}")
        
        logger.info(f"[DEBUG] 戦略立案処理継続 - ツール有無に関わらず実行")
        
        # 戦略立案プロンプト（直接指定）
        base_prompt = """あなたは戦略立案の専門家です。上記の利用可能ツールとユーザーリクエストを分析し、必要最小限のツールのみを選択してください。

## 重要な判定ルール
1. ユーザーが明示的に要求していない情報は取得しない
2. 利用可能ツールの中から適切なものを選択する
3. ツールが不要な場合は steps を空配列 [] にする
4. 複数ツールの無駄な組み合わせを避ける

## 判定の考え方
- 情報要求の種類を特定する（商品情報、顧客情報、その他）
- 利用可能ツールの説明文と照らし合わせる
- 明示的に要求されていない情報は取得しない
- 一般的な挨拶や質問にはツールは不要

## 出力形式（必須）
以下の形式の純粋なJSONのみを返してください。説明文・前置き・後置きは一切不要です。

{{
    "steps": [
        {{"step": 1, "tool": "ツール名", "reason": "このツールを使う理由"}}
    ]
}}

## 出力例
情報取得が必要:
{{"steps": [{{"step": 1, "tool": "search_products_flexible", "reason": "商品情報を検索するため"}}]}}

複数ツール必要:
{{"steps": [{{"step": 1, "tool": "tool_a", "reason": "基本情報取得"}}, {{"step": 2, "tool": "tool_b", "reason": "詳細情報取得"}}]}}

ツール不要:
{{"steps": []}}

## 禁止事項
- 明示的に要求されていない情報の取得禁止
- 利用可能ツール以外の使用禁止
- JSON以外のテキスト出力禁止
- 説明文・コメント・前置き禁止

利用可能ツールの中から、ユーザーが明示的に要求した情報のみを取得する最小限のツール選択をしてください。"""
        
        # ツール説明文を生成（ツールがない場合は明示）
        tools_description = "\n".join([
            f"- {name}: {info['usage_context']}"
            for name, info in enabled_tools.items()
        ]) if enabled_tools else "(利用可能なツールはありません)"
        
        # 完全なシステムプロンプト構築
        complete_system_prompt = f"""{base_prompt}

質問内容: {user_message}

現在登録されているツールとその説明文:
{tools_description}"""
        
        # 純粋なLLM呼び出し
        logger.info(f"[DEBUG] LLM呼び出し開始 - プロンプト長: {len(complete_system_prompt)}")
        response, execution_time = await self.llm_util.call_llm_simple(complete_system_prompt)
        logger.info(f"[DEBUG] LLM呼び出し完了 - 応答長: {len(response)}, 実行時間: {execution_time}ms")
        
        strategy = DetailedStrategy.from_json_string(response)
        logger.info(f"[DEBUG] DetailedStrategy作成完了 - steps数: {len(strategy.steps)}")
        
        # 戦略立案LLM情報を記録
        strategy.strategy_llm_prompt = complete_system_prompt
        strategy.strategy_llm_response = response
        strategy.strategy_llm_execution_time_ms = execution_time
        logger.info(f"[DEBUG] LLM情報記録完了 - prompt長: {len(complete_system_prompt)}, response長: {len(response)}")
        
        return strategy
    
    def get_enabled_tools(self):
        """有効なツールのみ返す"""
        logger.info(f"[DEBUG] available_tools keys: {list(self.available_tools.keys())}")
        logger.info(f"[DEBUG] enabled_tools: {list(self.enabled_tools)}")
        
        result = {
            name: info for name, info in self.available_tools.items()
            if name in self.enabled_tools
        }
        
        logger.info(f"[DEBUG] get_enabled_tools result: {list(result.keys())}")
        return result
    
    # === 将来拡張用メソッド（空実装） ===
    async def learn_from_feedback(self, query: str, strategy: DetailedStrategy, success: bool):
        """戦略学習機能（将来実装）"""
        pass
    
    async def optimize_strategy(self, query: str) -> DetailedStrategy:
        """戦略最適化（将来実装）"""
        pass
    
    def analyze_query_patterns(self, query: str) -> Dict[str, Any]:
        """クエリパターン分析（将来実装）"""
        return {}
