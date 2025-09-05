# AIChat System - 新しい軽量統合クラス
import boto3
import logging
from typing import Dict, Any
from strategy_engine import StrategyEngine
from integration_engine import IntegrationEngine
from mcp_executor import MCPExecutor
from conversation_manager import ConversationManager

logger = logging.getLogger(__name__)

class AIAgent:
    """軽量統合クラス - 4つのエンジンを統合するだけ"""
    
    def __init__(self):
        self.bedrock_client = boto3.client('bedrock-runtime', region_name='us-east-1')
        
        # 4つの独立エンジン
        self.mcp_executor = MCPExecutor()
        self.strategy_engine = None  # 初期化後に設定
        self.integration_engine = IntegrationEngine(self.bedrock_client)
        self.conversation_manager = ConversationManager()
    
    async def initialize(self):
        """初期化"""
        await self.mcp_executor.initialize()
        
        # 戦略エンジン初期化（MCP情報が必要）
        self.strategy_engine = StrategyEngine(
            self.bedrock_client,
            self.mcp_executor.available_tools
        )
        
        # 戦略エンジンの enabled_tools を mcp_executor と同期
        self.strategy_engine.enabled_tools = self.mcp_executor.enabled_tools
    
    async def process_message(self, user_message: str, session_id: str = "default") -> Dict[str, Any]:
        """メッセージ処理（4エンジン統合）"""
        try:
            # 1. 会話履歴取得
            conversation_context = self.conversation_manager.get_conversation_context(session_id)
            
            if self.mcp_executor.mcp_available:
                # 2. 戦略立案
                strategy = await self.strategy_engine.plan_strategy(user_message)
                
                print(f"[AI_AGENT_NEW] === STRATEGY PLANNING ===")
                print(f"[AI_AGENT_NEW] Steps: {len(strategy.steps)}")
                if strategy.steps:
                    print(f"[AI_AGENT_NEW] Tools: {[step.tool for step in strategy.steps]}")
                
                # 3. MCP実行
                executed_strategy = await self.mcp_executor.execute_strategy(strategy, user_message)
                
                # 4. 回答統合
                response = await self.integration_engine.generate_response(
                    user_message, executed_strategy, conversation_context
                )
                
                # 5. 会話履歴保存
                self.conversation_manager.add_message(
                    session_id=session_id,
                    user_message=user_message,
                    ai_response=response,
                    strategy_info={"steps": len(executed_strategy.steps)}
                )
                
                return {
                    "message": response,
                    "strategy": executed_strategy,
                    "mcp_enabled": True
                }
            
            # 通常応答
            response = await self.integration_engine.generate_simple_response(
                user_message, conversation_context
            )
            
            # 会話履歴保存
            self.conversation_manager.add_message(
                session_id=session_id,
                user_message=user_message,
                ai_response=response
            )
            
            return {
                "message": response,
                "mcp_enabled": False
            }
            
        except Exception as e:
            logger.error(f"Message processing error: {e}")
            return {
                "message": "申し訳ございません。処理中にエラーが発生しました。",
                "mcp_enabled": False,
                "error": str(e)
            }
    
    # === 各エンジンへの委譲メソッド ===
    def toggle_tool(self, tool_name: str) -> bool:
        """ツール有効/無効切り替え"""
        result = self.mcp_executor.toggle_tool(tool_name)
        # 戦略エンジンと同期
        if self.strategy_engine:
            self.strategy_engine.enabled_tools = self.mcp_executor.enabled_tools
        return result
    
    def get_enabled_tools(self):
        """有効ツール取得"""
        if self.strategy_engine:
            return self.strategy_engine.get_enabled_tools()
        return {}
    
    @property
    def mcp_available(self) -> bool:
        """MCP利用可能性"""
        return self.mcp_executor.mcp_available
    
    @property
    def available_tools(self) -> Dict[str, Any]:
        """利用可能ツール"""
        return self.mcp_executor.available_tools
    
    @property
    def enabled_tools(self) -> set:
        """有効ツール"""
        return self.mcp_executor.enabled_tools
