import json
import boto3
import logging
import time
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
    debug_info: Optional[Dict] = None
    
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
        
        # レガシー互換性（段階的移行のため）
        self.mcp_available = False
        
        # LLMユーティリティ初期化
        self.llm_util = LLMUtil(self.bedrock_client, self.model_id)
        
        # エンジン初期化（mcp_tool_manager 使用）
        self.strategy_engine = StrategyEngine(
            self.bedrock_client, 
            self.llm_util,
            self.mcp_tool_manager  # 新しいMCP管理クラス使用
        )
        self.integration_engine = IntegrationEngine(self.bedrock_client, self.llm_util)
        self.mcp_executor = MCPExecutor()
    
    async def initialize(self):
        """AI Agent初期化（新MCPToolManager使用）"""
        try:
            # 新しいMCP管理クラス初期化
            await self.mcp_tool_manager.initialize()
            
            # レガシー互換性
            enabled_tools = self.mcp_tool_manager.get_enabled_tools()
            self.mcp_available = len(enabled_tools) > 0
            
            if self.mcp_available:
                logger.info(f"MCP integration enabled ({len(enabled_tools)} tools available)")
        except Exception as e:
            logger.error(f"AI Agent initialization error: {e}")
    
    # レガシー互換性のためのプロパティ
    @property
    def available_tools(self):
        """MCPTool クラス直接参照による available_tools"""
        return {
            tool_key: {
                'name': tool.tool_name,
                'description': tool.description,
                'mcp_server': tool.mcp_server_name,
                'enabled': self.mcp_tool_manager.is_tool_enabled(tool_key),
                'available': tool.available
            }
            for tool_key, tool in self.mcp_tool_manager.registered_tools.items()
        }
    
    @property
    def enabled_tools(self):
        """MCPToolManager の enabled_tools を参照"""
        return self.mcp_tool_manager.enabled_tools
    
    def get_enabled_tools(self):
        """有効なツールのみ返す"""
        return self.mcp_tool_manager.get_enabled_tools()
    
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
    
    async def execute_tools(self, tool_requests: list, tool_arguments: dict) -> list:
        """複数ツールの実行"""
        results = []
        for tool_name in tool_requests:
            if tool_name not in self.available_tools:
                results.append({"tool": tool_name, "error": "Tool not available"})
                continue
                
            if tool_name not in self.mcp_manager.available_tools:
                results.append({"tool": tool_name, "error": "Tool not enabled"})
                continue
            
            mcp_server_name = self.available_tools[tool_name]['mcp_server']
            client = self.mcp_manager.clients[mcp_server_name]
            
            try:
                if await client.health_check():
                    result = await client.call_tool(tool_name, tool_arguments.get(tool_name, {}))
                    results.append({"tool": tool_name, "result": result})
                else:
                    results.append({"tool": tool_name, "error": "MCP server unavailable"})
            except Exception as e:
                results.append({"tool": tool_name, "error": str(e)})
        
        return results
    
    def merge_tool_debug_info(self, tool_results: list) -> dict:
        """複数ツールのデバッグ情報をマージ"""
        merged_debug = {}
        for result in tool_results:
            tool_name = result["tool"]
            if "result" in result and isinstance(result["result"], dict):
                debug_info = result["result"].get("debug_info", {})
                if debug_info:
                    merged_debug[tool_name] = debug_info
        return merged_debug
    
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
            error_step.debug_info = {
                "parse_error": True,
                "error_message": strategy.parse_error_message,
                "raw_response": strategy.raw_response
            }
            return strategy
        
        for step in strategy.steps:
            step_start_time = time.time()
            
            # ツール直接実行
            result = await self.execute_tool_directly(step.tool, current_input)
            
            # 同じオブジェクトに実行結果を追加
            step.input = current_input
            step.output = result
            step.execution_time_ms = (time.time() - step_start_time) * 1000
            step.debug_info = result.get("debug_info", {}) if isinstance(result, dict) else {}
            
            # 次ステップ用（debug_info除外）
            clean_result = {k: v for k, v in result.items() if k != "debug_info"} if isinstance(result, dict) else result
            current_input = json.dumps(clean_result, ensure_ascii=False)
            
            print(f"[AI_AGENT] Step {step.step} completed: {step.tool} ({step.execution_time_ms:.2f}ms)")
        
        # 戻り値なし（参照渡し）
    
    async def execute_tool_directly(self, tool_name: str, tool_input: str) -> Dict[str, Any]:
        """ツールを直接実行"""
        if tool_name not in self.available_tools:
            return {"error": f"Tool '{tool_name}' not available"}
        
        if tool_name not in self.mcp_manager.available_tools:
            return {"error": f"Tool '{tool_name}' not enabled"}
        
        mcp_server_name = self.available_tools[tool_name]['mcp_server']
        client = self.mcp_manager.clients[mcp_server_name]
        
        try:
            if await client.health_check():
                # テキスト入力でツール実行
                result = await client.call_tool(tool_name, {"text_input": tool_input})
                return result
            else:
                return {"error": "MCP server unavailable"}
        except Exception as e:
            return {"error": str(e)}
