import json
import boto3
import logging
import time
import httpx
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from mcp_client import MCPClient
from llm_util import LLMUtil
from strategy_engine import StrategyEngine
from integration_engine import IntegrationEngine
from mcp_executor import MCPExecutor
from models import DetailedStrategy, DetailedStep

logger = logging.getLogger(__name__)

@dataclass
class Intent:
    requires_tool: bool
    tool_name: Optional[str] = None
    arguments: Optional[Dict[str, Any]] = None
    confidence: float = 0.0
    # 複数ツール対応
    requires_tools: list = None
    
    def __post_init__(self):
        if self.requires_tools is None:
            self.requires_tools = []

@dataclass
class DetailedStep:
    step: int
    tool: str
    reason: str
    
    # 実行時に追加される情報（初期値None）
    input: Optional[str] = None
    output: Optional[Dict] = None
    execution_time_ms: Optional[float] = None
    step_execution_debug: Optional[Dict] = None
    
    # LLM情報（統合）
    llm_prompt: Optional[str] = None
    llm_response: Optional[str] = None
    llm_execution_time_ms: Optional[float] = None

@dataclass
class AIAgent:
    def __init__(self):
        self.bedrock_client = boto3.client('bedrock-runtime', region_name='us-east-1')
        self.model_id = "anthropic.claude-3-sonnet-20240229-v1:0"
        
        # 新しいMCP管理クラス使用
        from mcp_tool_manager import MCPToolManager
        self.mcp_tool_manager = MCPToolManager()
        
        # MCP Client 初期化 - MCPToolManager 注入
        self.mcp_client = MCPClient(self.mcp_tool_manager)
        
        # LLMユーティリティ初期化
        self.llm_util = LLMUtil(self.bedrock_client, self.model_id)
        
        # エンジン初期化（mcp_tool_manager 使用）
        self.strategy_engine = StrategyEngine(
            self.bedrock_client, 
            self.llm_util,
            self.mcp_tool_manager
        )
        self.integration_engine = IntegrationEngine(self.bedrock_client, self.llm_util)
        self.mcp_executor = MCPExecutor()
    
    async def initialize(self):
        """AI Agent初期化"""
        try:
            await self.mcp_tool_manager.initialize()
            
            enabled_count = len([tool for tool in self.mcp_tool_manager.registered_tools.values() 
                               if tool.enabled])  # MCPTool.enabled 直接参照
            
            if enabled_count > 0:
                logger.info(f"MCP integration enabled ({enabled_count} tools available)")
        except Exception as e:
            logger.error(f"AI Agent initialization error: {e}")
    
    @property
    def enabled_tools(self):
        """MCPTool.enabled 直接参照による有効ツール取得"""
        return {
            tool_key: tool for tool_key, tool in self.mcp_tool_manager.registered_tools.items()
            if tool.enabled
        }
    
    def get_enabled_tools(self):
        """有効なツールのみ返す - MCPTool.enabled 直接参照"""
        return {
            tool_key: tool for tool_key, tool in self.mcp_tool_manager.registered_tools.items()
            if tool.enabled
        }
    
    def toggle_tool(self, tool_name: str) -> bool:
        """ツールの有効/無効を切り替え（MCPToolManagerに委譲）"""
        return self.mcp_tool_manager.toggle_tool_enabled(tool_name)
    
    async def process_message(self, user_message: str) -> Dict[str, Any]:
        """メッセージ処理（参照渡し設計・段階的実行）"""
        
        # Try外側でインスタンス作成（エラー時情報保持のため）
        from models import DetailedStrategy
        executed_strategy = DetailedStrategy(steps=[])
        
        try:
            # 段階1: 戦略立案
            logger.info(f"[DEBUG] 戦略立案開始")
            await self.strategy_engine.plan_strategy(user_message, executed_strategy)
            logger.info(f"[DEBUG] 戦略立案完了 - steps: {len(executed_strategy.steps)}")
            logger.info(f"[DEBUG] 戦略立案LLM情報確認 - prompt存在: {executed_strategy.strategy_llm_prompt is not None}")
            if executed_strategy.strategy_llm_prompt:
                logger.info(f"[DEBUG] 戦略立案LLM情報 - prompt長: {len(executed_strategy.strategy_llm_prompt)}, response長: {len(executed_strategy.strategy_llm_response or '')}")
            
            print(f"[AI_AGENT] === STRATEGY PLANNING ===")
            print(f"[AI_AGENT] Steps: {len(executed_strategy.steps)}")
            if executed_strategy.steps:
                print(f"[AI_AGENT] Tools: {[step.tool for step in executed_strategy.steps]}")
            
            # 段階2: 戦略実行
            logger.info(f"[DEBUG] 戦略実行開始")
            await self.execute_detailed_strategy(executed_strategy, user_message)
            logger.info(f"[DEBUG] 戦略実行完了")
            
            # 段階3: 応答生成
            logger.info(f"[DEBUG] 応答生成開始")
            await self.integration_engine.generate_final_response(
                user_message, executed_strategy
            )
            logger.info(f"[DEBUG] 応答生成完了 - 応答長: {len(executed_strategy.final_response or '')}")
            
            # 最終確認
            logger.info(f"[DEBUG] 最終戦略確認 - prompt存在: {executed_strategy.strategy_llm_prompt is not None}")
            
            return {
                "message": executed_strategy.final_response or "応答生成に失敗しました",
                "strategy": executed_strategy,
                "mcp_enabled": len(executed_strategy.steps) > 0
            }
            
        except Exception as e:
            logger.error(f"Message processing error: {e}")
            return {
                "message": executed_strategy.final_response or "申し訳ございません。処理中にエラーが発生しました。詳細はデバッグ情報をご確認ください。",
                "strategy": executed_strategy,  # 途中まで実行された情報保持
                "mcp_enabled": len(executed_strategy.steps) > 0,
                "error": str(e)
            }
    
    async def execute_detailed_strategy(self, strategy: DetailedStrategy, user_message: str) -> None:
        """戦略に基づく決定論的実行 - 既存オブジェクトに実行結果を埋め込み"""
        current_input = user_message
        
        # 戦略立案エラーの場合は特別処理
        if strategy.parse_error:
            error_step = strategy.steps[0]  # エラーステップ
            error_step.input = current_input
            error_step.output = {
                "error": "戦略立案でJSON解析エラーが発生しました",
                "parse_error_message": strategy.parse_error_message,
                "raw_llm_response": strategy.raw_response,
                "suggestion": "システムプロンプトの改善が必要です"
            }
            error_step.execution_time_ms = 0
            error_step.step_execution_debug = {
                "parse_error": True,
                "error_message": strategy.parse_error_message,
                "raw_response": strategy.raw_response
            }
            return strategy
        
        for step in strategy.steps:
            step_start_time = time.time()
            
            # MCP Client でツール実行 - ツール名のみ渡し
            tool_execution_result = await self.mcp_client.call_tool(step.tool, {"text_input": current_input})
            
            # 同じオブジェクトに実行結果を追加
            step.input = current_input
            step.output = tool_execution_result
            step.execution_time_ms = (time.time() - step_start_time) * 1000
            
            # MCP Client の構造化デバッグ情報を使用
            step.step_execution_debug = tool_execution_result.get("call_tool_info", {})
            
            # 次ステップ用（デバッグ情報除外）
            clean_result = {k: v for k, v in tool_execution_result.items() if k not in ["call_tool_info", "debug_response"]} if isinstance(tool_execution_result, dict) else tool_execution_result
            current_input = json.dumps(clean_result, ensure_ascii=False)
            
            print(f"[AI_AGENT] Step {step.step} completed: {step.tool} ({step.execution_time_ms:.2f}ms)")
        
        # 戻り値なし（参照渡し）
