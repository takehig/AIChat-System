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
    
    def __init__(self, bedrock_client, available_tools: Dict[str, Any], llm_util):
        self.bedrock_client = bedrock_client
        self.model_id = "anthropic.claude-3-sonnet-20240229-v1:0"
        self.available_tools = available_tools
        self.llm_util = llm_util
        self.enabled_tools = set()
        
        # SystemPrompt Management クライアント初期化
        self.prompt_client = SystemPromptClient()
        
        # === 将来拡張用（現在は空実装） ===
        self.query_patterns = {}      # クエリパターン学習
        self.success_history = {}     # 成功戦略履歴
        self.learning_data = {}       # 学習データ
        
    async def plan_strategy(self, user_message: str) -> DetailedStrategy:
        """戦略立案メイン処理"""
        enabled_tools = self.get_enabled_tools()
        
        if not enabled_tools:
            # ツールが無い場合は空の戦略を返す
            return DetailedStrategy(steps=[])
        
        tools_description = "\\n".join([
            f"- {name}: {info['usage_context']}"
            for name, info in enabled_tools.items()
        ])
        
        # 動的部分を先頭に配置
        dynamic_context = f"""利用可能ツール:
{tools_description}

ユーザーリクエスト: {user_message}

---"""
        
        # SystemPrompt Management からベースプロンプトを取得
        base_prompt = self.prompt_client.get_prompt("strategy_planning")
        
        # 動的コンテキスト + ベースプロンプトで完全なプロンプト構成
        strategy_prompt = f"{dynamic_context}\n\n{base_prompt}"

        response, prompt, llm_response, execution_time = await self.llm_util.call_claude_with_llm_info(
            system_prompt=strategy_prompt,
            user_message="上記の利用可能ツールとユーザーリクエストを分析し、適切な戦略をJSON形式で出力してください。"
        )
        
        strategy = DetailedStrategy.from_json_string(response)
        # 戦略立案LLM情報を記録
        strategy.strategy_llm_prompt = prompt
        strategy.strategy_llm_response = llm_response
        strategy.strategy_llm_execution_time_ms = execution_time
        
        return strategy
    
    def get_enabled_tools(self):
        """有効なツールのみ返す"""
        return {
            name: info for name, info in self.available_tools.items()
            if name in self.enabled_tools
        }
    
    def toggle_tool(self, tool_name: str) -> bool:
        """ツール有効/無効切り替え"""
        if tool_name not in self.available_tools:
            return False
        
        if tool_name in self.enabled_tools:
            self.enabled_tools.remove(tool_name)
            logger.info(f"Tool disabled: {tool_name}")
            return False
        else:
            self.enabled_tools.add(tool_name)
            logger.info(f"Tool enabled: {tool_name}")
            return True
    
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
