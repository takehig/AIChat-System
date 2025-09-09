# AIChat System - 戦略立案エンジン
import json
import time
import logging
from typing import Dict, Any
from models import DetailedStrategy, DetailedStep
from prompt_client import SystemPromptClient

logger = logging.getLogger(__name__)

class StrategyEngine:
    """戦略立案専用エンジン - 将来大幅拡張予定"""
    
    def __init__(self, bedrock_client, available_tools: Dict[str, Any], llm_util, enabled_tools_ref):
        self.bedrock_client = bedrock_client
        self.model_id = "anthropic.claude-3-sonnet-20240229-v1:0"
        self.available_tools = available_tools
        self.llm_util = llm_util
        self.enabled_tools = enabled_tools_ref  # ai_agent の enabled_tools を共有参照
        
        # SystemPrompt Management クライアント初期化
        self.prompt_client = SystemPromptClient()
        
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
        
        # SystemPrompt Management からベースプロンプトを取得
        base_prompt = self.prompt_client.get_prompt("strategy_planning")
        
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
        return {
            name: info for name, info in self.available_tools.items()
            if name in self.enabled_tools
        }
    
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
