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
    
    async def generate_final_response(self, user_message: str, executed_strategy: DetailedStrategy) -> None:
        """最終応答生成 - 既存オブジェクトに応答情報を追加"""
        
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
            executed_strategy.final_response = response  # 応答をオブジェクトに保存
            logger.info(f"[DEBUG] 最終応答LLM情報記録完了")
            return  # 戻り値なし（参照渡し）
        
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
            executed_strategy.final_response = response  # 応答をオブジェクトに保存
            return  # 戻り値なし（参照渡し）
        
        # 実行結果サマリー生成
        logger.info(f"[DEBUG] 実行結果サマリー生成開始")
        logger.info(f"[DEBUG] steps数: {len(executed_strategy.steps)}")
        
        try:
            # 各stepの詳細確認
            for i, step in enumerate(executed_strategy.steps):
                logger.info(f"[DEBUG] Step {i}: step={step.step}, tool={step.tool}, output存在={step.output is not None}")
                if step.output is not None:
                    logger.info(f"[DEBUG] Step {i} output type: {type(step.output)}")
                    logger.info(f"[DEBUG] Step {i} output keys: {list(step.output.keys()) if isinstance(step.output, dict) else 'not dict'}")
            
            results_summary = "\n\n".join([
                f"【Step {step.step}: {step.tool}】\n理由: {step.reason}\n結果: {json.dumps(step.output, ensure_ascii=False, indent=2)}"
                for step in executed_strategy.steps if step.output
            ])
            logger.info(f"[DEBUG] 実行結果サマリー生成完了 - 長さ: {len(results_summary)}")
            
        except Exception as e:
            logger.error(f"[DEBUG] 実行結果サマリー生成エラー: {e}")
            logger.error(f"[DEBUG] エラー詳細: {type(e).__name__}")
            raise
        
        # SystemPrompt Management から戦略結果応答プロンプトを取得
        logger.info(f"[DEBUG] SystemPrompt取得開始")
        try:
            prompt_data = await get_system_prompt_by_key("strategy_result_response_prompt")
            logger.info(f"[DEBUG] SystemPrompt取得完了: {prompt_data is not None}")
            strategy_prompt_template = prompt_data.get("prompt_text", "") if prompt_data else ""
            logger.info(f"[DEBUG] strategy_prompt_template長さ: {len(strategy_prompt_template)}")
            
            if not strategy_prompt_template:
                logger.warning(f"[DEBUG] strategy_result_response_prompt が空 - フォールバック処理")
                # フォールバックプロンプト
                strategy_prompt_template = """あなたは証券会社の営業支援システムのAIエージェントです。実行された戦略の結果を基に、営業員に対して分かりやすく有用な回答を生成してください。

ユーザーの質問: {user_message}

実行結果:
{results_summary}

実行時間: {total_execution_time}ms

取得した情報を整理し、営業活動に直接役立つ形で提示してください。"""
                logger.info(f"[DEBUG] フォールバックプロンプト使用 - 長さ: {len(strategy_prompt_template)}")
                
        except Exception as e:
            logger.error(f"[DEBUG] SystemPrompt取得エラー: {e}")
            logger.warning(f"[DEBUG] SystemPrompt取得失敗 - フォールバック処理")
            # フォールバックプロンプト
            strategy_prompt_template = """あなたは証券会社の営業支援システムのAIエージェントです。実行された戦略の結果を基に、営業員に対して分かりやすく有用な回答を生成してください。

ユーザーの質問: {user_message}

実行結果:
{results_summary}

実行時間: {total_execution_time}ms

取得した情報を整理し、営業活動に直接役立つ形で提示してください。"""
            logger.info(f"[DEBUG] フォールバックプロンプト使用 - 長さ: {len(strategy_prompt_template)}")
        
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
        executed_strategy.final_response = response  # 応答をオブジェクトに保存
        
        # 戻り値なし（参照渡し）
