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
    
    def __init__(self, bedrock_client, available_tools: Dict[str, Any]):
        self.bedrock_client = bedrock_client
        self.model_id = "anthropic.claude-3-sonnet-20240229-v1:0"
        self.available_tools = available_tools
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
        
        # SystemPrompt Management からプロンプトを動的取得
        base_prompt = self.prompt_client.get_prompt("strategy_planning")
        
        strategy_prompt = f"""{base_prompt}

利用可能ツール:
{tools_description}

## 出力形式（必須）
以下の形式の純粋なJSONのみを返してください。説明文・前置き・後置きは一切不要です。

{{
    "steps": [
        {{"step": 1, "tool": "ツール名", "reason": "このツールを使う理由"}}
    ]
}}

## 出力例（架空のツール使用）
情報取得が必要:
{{"steps": [{{"step": 1, "tool": "example_tool", "reason": "要求された情報を取得するため"}}]}}

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

        response, prompt, llm_response, execution_time = await self.call_claude_with_llm_info(
            system_prompt=strategy_prompt,
            user_message=user_message
        )
        
        strategy = DetailedStrategy.from_json_string(response)
        # 戦略立案LLM情報を記録
        strategy.strategy_llm_prompt = prompt
        strategy.strategy_llm_response = llm_response
        strategy.strategy_llm_execution_time_ms = execution_time
        
        return strategy
    
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
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 4000,
                "system": system_prompt,
                "messages": [
                    {
                        "role": "user",
                        "content": user_message
                    }
                ]
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
