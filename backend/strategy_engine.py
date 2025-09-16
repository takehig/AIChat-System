# AIChat System - 戦略立案エンジン
import json
import time
import logging
from typing import Dict, Any
from models import DetailedStrategy, DetailedStep
from system_prompts_api import get_system_prompt_by_key

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
        self.optimization_rules = {}  # 最適化ルール
    
    def get_enabled_tools(self) -> Dict[str, Any]:
        """有効化されたツールのみを取得"""
        return {name: info for name, info in self.available_tools.items() 
                if name in self.enabled_tools}
    
    async def plan_strategy(self, user_message: str, strategy: DetailedStrategy) -> None:
        """戦略立案 - 既存オブジェクトに戦略情報を追加"""
        
        logger.info(f"[DEBUG] plan_strategy開始")
        logger.info(f"[DEBUG] available_tools keys: {list(self.available_tools.keys())}")
        logger.info(f"[DEBUG] enabled_tools: {self.enabled_tools}")
        
        # 有効ツール取得
        enabled_tools = self.get_enabled_tools()
        logger.info(f"[DEBUG] get_enabled_tools result: {list(enabled_tools.keys())}")
        logger.info(f"[DEBUG] enabled_tools取得: {len(enabled_tools)}個")
        logger.info(f"[DEBUG] enabled_tools: {list(enabled_tools.keys())}")
        
        logger.info(f"[DEBUG] 戦略立案処理継続 - ツール有無に関わらず実行")
        
        # SystemPrompt Management から戦略立案プロンプトを取得
        prompt_data = await get_system_prompt_by_key("strategy_planning")
        base_prompt = prompt_data.get("prompt_text", "")
        if not base_prompt:
            raise Exception("strategy_planning が空です")
        
        # ツール説明文を生成（ツールがない場合は明示）
        tools_description = "\n".join([
            f"- {name}: {info['usage_context']}"
            for name, info in enabled_tools.items()
        ]) if enabled_tools else "(利用可能なツールはありません)"
        
        # 動的プロンプト生成
        system_prompt = f"{base_prompt}\n\n質問内容: {user_message}\n\n現在登録されているツールとその説明文:\n{tools_description}"
        
        logger.info(f"[DEBUG] LLM呼び出し開始 - プロンプト長: {len(system_prompt)}")
        
        # LLM呼び出し
        start_time = time.time()
        response = await self.llm_util.call_claude(system_prompt, "上記の質問に対する戦略をJSONで返してください。")
        execution_time = (time.time() - start_time) * 1000
        
        logger.info(f"[DEBUG] LLM呼び出し完了 - 応答長: {len(response)}, 実行時間: {execution_time}ms")
        
        # JSON解析
        try:
            strategy_data = json.loads(response)
            steps = strategy_data.get("steps", [])
            
            # DetailedStep オブジェクト生成
            detailed_steps = []
            for step_data in steps:
                detailed_step = DetailedStep(
                    step=step_data.get("step", 0),
                    tool=step_data.get("tool", ""),
                    reason=step_data.get("reason", ""),
                    output=None,
                    execution_time_ms=None
                )
                detailed_steps.append(detailed_step)
            
            # 既存オブジェクトに戦略情報を追加
            strategy.steps = detailed_steps
            strategy.parse_error = False
            strategy.strategy_llm_prompt = system_prompt
            strategy.strategy_llm_response = response
            strategy.strategy_llm_execution_time_ms = execution_time
            
            logger.info(f"[DEBUG] DetailedStrategy更新完了 - steps数: {len(detailed_steps)}")
            
        except json.JSONDecodeError as e:
            logger.error(f"[DEBUG] JSON解析エラー: {e}")
            logger.error(f"[DEBUG] 応答内容: {response}")
            
            # 解析エラー時の戦略情報を既存オブジェクトに設定
            strategy.steps = []
            strategy.parse_error = True
            strategy.parse_error_message = str(e)
            strategy.raw_response = response
            strategy.strategy_llm_prompt = system_prompt
            strategy.strategy_llm_response = response
            strategy.strategy_llm_execution_time_ms = execution_time
        
        # LLM情報記録
        logger.info(f"[DEBUG] LLM情報記録完了 - prompt長: {len(system_prompt)}, response長: {len(response)}")
        
        # 戻り値なし（参照渡し）
