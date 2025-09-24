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
    
    def __init__(self, bedrock_client, llm_util, mcp_tool_manager):
        self.bedrock_client = bedrock_client
        self.model_id = "anthropic.claude-3-sonnet-20240229-v1:0"
        self.llm_util = llm_util
        self.mcp_tool_manager = mcp_tool_manager  # 新しいMCP管理クラス使用
        
        # === 将来拡張用（現在は空実装） ===
        self.query_patterns = {}      # クエリパターン学習
        self.success_history = {}     # 成功戦略履歴
        self.optimization_rules = {}  # 最適化ルール
    
    def get_enabled_tools(self) -> Dict[str, Any]:
        """有効化されたツールのみを取得（MCPTool.enabled 直接参照）"""
        return {
            tool_key: tool for tool_key, tool in self.mcp_tool_manager.registered_tools.items()
            if tool.enabled  # MCPTool.enabled 直接参照
        }
    
    async def plan_strategy(self, user_message: str, strategy: DetailedStrategy) -> None:
        """戦略立案（MCPToolManager直接参照最適化版）"""
        logger.info(f"[DEBUG] 戦略立案開始: {user_message}")
        
        # MCPToolManager から直接有効ツール数確認
        enabled_count = len([tool for tool in self.mcp_tool_manager.registered_tools.values() 
                           if tool.enabled])  # MCPTool.enabled 直接参照
        logger.info(f"[DEBUG] MCPToolManager: {enabled_count}個のツール利用可能")
        
        # SystemPrompt Management から戦略立案プロンプトを取得
        prompt_data = await get_system_prompt_by_key("strategy_planning")
        base_prompt = prompt_data.get("prompt_text", "")
        if not base_prompt:
            raise Exception("strategy_planning が空です")
        
        # MCPToolManager から直接ツール情報生成（API不要）
        tools_description = self._generate_tools_description_from_manager()
        
        # システムプロンプト生成（base_prompt + tools_description のみ）
        system_prompt = f"""{base_prompt}\r\n\r\n## 利用可能なMCPツール\r\n{tools_description}"""
        
        # ユーザーメッセージ生成（入力プロンプトの素の状態）
        user_input = f"これが入力されたプロンプトです。\r\n{user_message}"
        
        logger.info(f"[DEBUG] LLM呼び出し開始 - システムプロンプト長: {len(system_prompt)}, ユーザー入力長: {len(user_input)}")
        
        # LLM呼び出し
        start_time = time.time()
        response = await self.llm_util.call_claude(system_prompt, user_input)
        execution_time = (time.time() - start_time) * 1000
        
        logger.info(f"[DEBUG] LLM呼び出し完了 - 応答長: {len(response)}, 実行時間: {execution_time}ms")
        
        # 戦略情報を既存オブジェクトに追加（参照渡し）
        strategy.strategy_llm_prompt = system_prompt
        strategy.strategy_llm_response = response
        strategy.raw_response = response  # 元レスポンス常に保存
        
        # Try外で初期化（エラー時情報保持）
        detailed_steps = []
        
        # JSON解析・ステップ抽出
        try:
            strategy_data = json.loads(response)
            steps = strategy_data.get("steps", [])
            
            # DetailedStep オブジェクト生成
            for step_data in steps:
                detailed_step = DetailedStep(
                    step=step_data.get("step", 0),
                    tool=step_data.get("tool", ""),
                    reason=step_data.get("reason", ""),
                    input="",
                    output="",
                    execution_time_ms=0,
                    step_execution_debug={}
                )
                detailed_steps.append(detailed_step)
            
            strategy.steps = detailed_steps
            logger.info(f"[DEBUG] 戦略立案完了: {len(detailed_steps)}ステップ")
            
        except json.JSONDecodeError as e:
            logger.error(f"[DEBUG] JSON解析エラー: {e}")
            logger.error(f"[DEBUG] レスポンス内容: {response}")
            
            # パースエラー修正を試行
            logger.info("[DEBUG] パースエラー修正を開始")
            fixed_response = await self._fix_parse_error_with_llm(response, str(e))
            
            # 修正後レスポンスで再パース試行
            try:
                strategy_data = json.loads(fixed_response)
                steps = strategy_data.get("steps", [])
                
                # DetailedStep オブジェクト生成
                for step_data in steps:
                    detailed_step = DetailedStep(
                        step=step_data.get("step", 0),
                        tool=step_data.get("tool", ""),
                        reason=step_data.get("reason", ""),
                        input="",
                        output="",
                        execution_time_ms=0,
                        step_execution_debug={}
                    )
                    detailed_steps.append(detailed_step)
                
                strategy.steps = detailed_steps
                strategy.strategy_llm_response = fixed_response  # 修正後レスポンス保存
                logger.info(f"[DEBUG] パースエラー修正成功: {len(detailed_steps)}ステップ")
                
            except json.JSONDecodeError as e2:
                logger.error(f"[DEBUG] 修正後も解析失敗: {e2}")
                strategy.steps = []
                strategy.parse_error = True
                strategy.parse_error_message = f"修正後も解析失敗: {str(e2)}"
            
        logger.info(f"[DEBUG] DetailedStrategy更新完了 - steps数: {len(detailed_steps)}")
    
    async def _fix_parse_error_with_llm(self, original_response: str, error_message: str) -> str:
        """パースエラーをLLMで修正"""
        try:
            # SystemPrompt Management からプロンプト取得（既存実装に合わせる）
            system_prompt_data = await get_system_prompt_by_key("strategy_planning_parse_error_fix")
            system_prompt = system_prompt_data.get("prompt_text", "")
            
            if not system_prompt:
                logger.error("[DEBUG] パースエラー修正用プロンプトが取得できませんでした")
                return original_response
            
            user_message = f"""エラー内容: {error_message}

元のレスポンス:
{original_response}"""

            fixed_response = await self.llm_util.call_claude(
                system_prompt=system_prompt,
                user_message=user_message,
                max_tokens=2000,
                temperature=0.1
            )
            
            logger.info(f"[DEBUG] パースエラー修正完了 - 元長: {len(original_response)}, 修正後長: {len(fixed_response)}")
            return fixed_response.strip()
            
        except Exception as e:
            logger.error(f"[DEBUG] パースエラー修正失敗: {e}")
            return original_response  # 修正失敗時は元レスポンス返却
    
    def _generate_tools_description_from_manager(self) -> str:
        """MCPToolManager から直接ツール情報生成（MCPTool.enabled 統一版）"""
        if not any(tool.enabled for tool in self.mcp_tool_manager.registered_tools.values()):
            return "現在利用可能なMCPツールはありません。"
        
        tools_info = []
        for tool_key, tool in self.mcp_tool_manager.registered_tools.items():
            if tool.enabled:  # MCPTool.enabled 直接参照
                tool_info = f"""ツール名: {tool.tool_name}
ツールキー: {tool_key}
説明: {tool.description}
サーバー: {tool.mcp_server_name}"""
                
                # システムプロンプト追加
                if tool.system_prompt:
                    tool_info += f"\nシステム指示: {tool.system_prompt}"
                
                tools_info.append(tool_info)
        
        return "\r\n\r\n".join(tools_info)
