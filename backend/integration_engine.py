# AIChat System - 回答統合エンジン
import json
import time
import logging
from typing import Dict, Any, List
from models import DetailedStrategy
from system_prompts_api import get_system_prompt_by_key

logger = logging.getLogger(__name__)

class IntegrationEngine:
    """回答統合専用エンジン - 戦略実行結果から最終回答を生成"""
    
    def __init__(self, bedrock_client, llm_util):
        self.bedrock_client = bedrock_client
        self.model_id = "anthropic.claude-3-sonnet-20240229-v1:0"
        self.llm_util = llm_util
    
    async def generate_final_response(self, user_message: str, executed_strategy: DetailedStrategy) -> str:
        """最終応答生成"""
        
        logger.info(f"[DEBUG] generate_final_response開始")
        logger.info(f"[DEBUG] parse_error: {executed_strategy.parse_error}")
        logger.info(f"[DEBUG] steps数: {len(executed_strategy.steps) if executed_strategy.steps else 0}")
        logger.info(f"[DEBUG] is_executed: {executed_strategy.is_executed()}")
        
        # 戦略立案エラー時は直接回答（ハルシネーション防止）
        if executed_strategy.parse_error:
            logger.info(f"[DEBUG] 戦略立案エラー処理開始")
            
            # direct_response_prompt を取得
            prompt_data = await get_system_prompt_by_key("direct_response_prompt")
            base_direct_prompt = prompt_data.get("prompt_text", "")
            if not base_direct_prompt:
                raise Exception("direct_response_prompt が空です")
            
            # 戦略立案エラー情報を付加
            direct_prompt = f"{base_direct_prompt}\n\n注意: 戦略立案処理でエラーが発生したため、直接回答します。"
            logger.info(f"[DEBUG] direct_prompt設定完了: {len(direct_prompt)}文字")
            
            combined_prompt = f"{direct_prompt}\n\nユーザーの質問: {user_message}"
            
            # LLM呼び出し・情報記録
            start_time = time.time()
            response = await self.llm_util.call_claude(direct_prompt, user_message)
            execution_time = (time.time() - start_time) * 1000
            
            logger.info(f"[DEBUG] LLM呼び出し完了 - 応答長: {len(response)}, prompt長: {len(combined_prompt)}")
            
            # 最終応答LLM情報を記録
            executed_strategy.final_response_llm_prompt = combined_prompt
            executed_strategy.final_response_llm_response = response
            executed_strategy.final_response_llm_execution_time_ms = execution_time
            logger.info(f"[DEBUG] 最終応答LLM情報記録完了")
            return response
        
        # ツール未実行時も直接回答
        if not executed_strategy.steps or not executed_strategy.is_executed():
            # direct_response_prompt を取得
            prompt_data = await get_system_prompt_by_key("direct_response_prompt")
            direct_prompt = prompt_data.get("prompt_text", "")
            if not direct_prompt:
                raise Exception("direct_response_prompt が空です")
            
            combined_prompt = f"{direct_prompt}\n\nユーザーの質問: {user_message}"
            
            # LLM呼び出し・情報記録
            start_time = time.time()
            response = await self.llm_util.call_claude(direct_prompt, user_message)
            execution_time = (time.time() - start_time) * 1000
            
            # 最終応答LLM情報を記録
            executed_strategy.final_response_llm_prompt = combined_prompt
            executed_strategy.final_response_llm_response = response
            executed_strategy.final_response_llm_execution_time_ms = execution_time
            return response
        
        # 実行結果サマリー生成
        results_summary = "\n\n".join([
            f"【Step {step.step}: {step.tool}】\n理由: {step.reason}\n結果: {json.dumps(step.output, ensure_ascii=False, indent=2)}"
            for step in executed_strategy.steps if step.output
        ])
        
        # SystemPrompt Management から戦略結果応答プロンプトを取得
        prompt_data = await get_system_prompt_by_key("strategy_result_response_prompt")
        strategy_prompt_template = prompt_data.get("prompt_text", "")
        if not strategy_prompt_template:
            raise Exception("strategy_result_response_prompt が空です")
        
        # 動的システムプロンプト生成
        total_execution_time = sum(s.execution_time_ms or 0 for s in executed_strategy.steps)
        system_prompt = strategy_prompt_template.format(
            user_message=user_message,
            results_summary=results_summary,
            total_execution_time=total_execution_time
        )
        
        # LLM呼び出し・情報記録
        start_time = time.time()
        response = await self.llm_util.call_claude(system_prompt, "上記を基に回答してください。")
        execution_time = (time.time() - start_time) * 1000
        
        # 最終応答LLM情報を記録
        executed_strategy.final_response_llm_prompt = system_prompt
        executed_strategy.final_response_llm_response = response
        executed_strategy.final_response_llm_execution_time_ms = execution_time
        
        return response
