# AIChat System - 回答統合エンジン
import json
import time
import logging
from typing import Dict, Any
from models import DetailedStrategy

logger = logging.getLogger(__name__)

class IntegrationEngine:
    """回答統合専用エンジン - 将来大幅拡張予定"""
    
    def __init__(self, bedrock_client):
        self.bedrock_client = bedrock_client
        self.model_id = "anthropic.claude-3-sonnet-20240229-v1:0"
        
        # === 将来拡張用（現在は空実装） ===
        self.context_templates = {}      # コンテキストテンプレート
        self.integration_patterns = {}   # 統合パターン
        self.quality_metrics = {}        # 品質メトリクス
    
    async def generate_response(self, user_message: str, executed_strategy: DetailedStrategy, 
                              conversation_context: str = "") -> str:
        """統合回答生成メイン処理（MCP結果 + 会話コンテキスト → 最終回答）"""
        
        if not executed_strategy.steps or not self.is_executed(executed_strategy):
            # MCP実行なしの場合は通常応答
            return await self.generate_simple_response(user_message, conversation_context)
        
        # 実行結果サマリー生成
        results_summary = "\\n\\n".join([
            f"【Step {step.step}: {step.tool}】\\n理由: {step.reason}\\n結果: {json.dumps(step.output, ensure_ascii=False, indent=2)}"
            for step in executed_strategy.steps if step.output
        ])
        
        # 動的システムプロンプト生成
        system_prompt = f"""証券会社の社内情報システムとして回答してください。

{conversation_context}

ユーザーの質問: {user_message}

実行結果:
{results_summary}

回答要件:
- 質問の意図に応じて適切に回答
- 実行した処理の流れを簡潔に説明
- 最終的な結果を分かりやすく提示
- 過度に営業的にならず、事実ベースで回答
- 実行時間: {sum(s.execution_time_ms or 0 for s in executed_strategy.steps)}ms"""

        response, prompt, llm_response, execution_time = await self.call_claude_with_llm_info(
            system_prompt, "上記を基に回答してください。"
        )
        
        # 最終応答LLM情報を記録
        executed_strategy.final_llm_prompt = prompt
        executed_strategy.final_llm_response = llm_response
        executed_strategy.final_llm_execution_time_ms = execution_time
        
        return response
    
    async def generate_simple_response(self, user_message: str, conversation_context: str = "") -> str:
        """シンプル回答生成（MCP実行なし）"""
        
        system_prompt = f"""あなたは親切な金融商品アドバイザーです。
ユーザーの質問に対して、親しみやすく分かりやすい回答をしてください。

{conversation_context}

特定の商品情報が必要な場合は、「詳細な商品情報をお調べしますので、具体的な商品名や条件を教えてください」のように案内してください。"""
        
        try:
            return await self.call_claude(system_prompt, user_message)
        except Exception as e:
            logger.error(f"AI response error: {e}")
            return "申し訳ございません。回答の生成中にエラーが発生しました。"
    
    async def call_claude_with_llm_info(self, system_prompt: str, user_message: str) -> tuple[str, str, str, float]:
        """LLM呼び出し（プロンプト・応答・実行時間を返却）"""
        start_time = time.time()
        full_prompt = f"System: {system_prompt}\\n\\nUser: {user_message}"
        
        try:
            response = await self.call_claude(system_prompt, user_message)
            execution_time = (time.time() - start_time) * 1000
            return response, full_prompt, response, execution_time
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            error_response = f"ERROR: {str(e)}"
            return error_response, full_prompt, error_response, execution_time
    
    async def call_claude(self, system_prompt: str, user_message: str) -> str:
        """Claude API呼び出し"""
        try:
            messages = [{"role": "user", "content": user_message}]
            
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 2000,
                "system": system_prompt,
                "messages": messages,
                "temperature": 0.1
            }
            
            response = self.bedrock_client.invoke_model(
                modelId=self.model_id,
                body=json.dumps(body)
            )
            
            response_body = json.loads(response['body'].read())
            return response_body['content'][0]['text']
            
        except Exception as e:
            logger.error(f"Claude API call failed: {e}")
            return f"申し訳ございません。AI応答の生成中にエラーが発生しました: {str(e)}"
    
    def is_executed(self, strategy: DetailedStrategy) -> bool:
        """戦略が実行済みかチェック"""
        return any(step.output is not None for step in strategy.steps)
    
    # === 将来拡張用メソッド（空実装） ===
    async def analyze_result_quality(self, mcp_results: dict) -> float:
        """結果品質分析（将来実装）"""
        pass
    
    async def build_adaptive_context(self, results: dict, query: str) -> str:
        """適応的コンテキスト構築（将来実装）"""
        pass
    
    async def detect_conflicts(self, mcp_results: dict) -> list:
        """結果矛盾検出（将来実装）"""
        pass
    
    async def optimize_prompt_template(self, query_type: str) -> str:
        """プロンプトテンプレート最適化（将来実装）"""
        pass
