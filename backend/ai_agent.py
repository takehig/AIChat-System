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
        
        # 複数MCPクライアント
        self.mcp_clients = {
            'productmaster': MCPClient("http://localhost:8003"),
            'crm': MCPClient("http://localhost:8004")
        }
        self.mcp_available = False
        
        # ツール個別管理
        self.available_tools = {}  # ツール名 -> ツール情報
        self.enabled_tools = set()  # 有効ツール一覧
        
        # LLMユーティリティ初期化
        self.llm_util = LLMUtil(self.bedrock_client, self.model_id)
        
        # エンジン統合
        self.strategy_engine = StrategyEngine(self.bedrock_client, self.available_tools, self.llm_util, self.enabled_tools)
        self.integration_engine = IntegrationEngine(self.bedrock_client, self.llm_util)
        self.mcp_executor = MCPExecutor()
    
    async def initialize(self):
        """AI Agent初期化"""
        try:
            available_count = 0
            for name, client in self.mcp_clients.items():
                try:
                    if await client.health_check():
                        if await client.initialize():
                            await client.list_tools()
                            available_count += 1
                            logger.info(f"{name} MCP initialized")
                        else:
                            logger.warning(f"{name} MCP initialization failed")
                    else:
                        logger.warning(f"{name} MCP server not available")
                except Exception as e:
                    logger.error(f"{name} MCP initialization error: {e}")
            
            self.mcp_available = available_count > 0
            if self.mcp_available:
                logger.info(f"MCP integration enabled ({available_count} servers)")
                # ツール情報を収集
                await self.discover_available_tools()
        except Exception as e:
            logger.error(f"AI Agent initialization error: {e}")
    
    async def discover_available_tools(self):
        """全MCPサーバーからツール情報を収集"""
        self.available_tools.clear()  # 既存辞書をクリア（参照は維持）
        self.tool_routing = {}
        
        for mcp_name, client in self.mcp_clients.items():
            try:
                if await client.health_check():
                    # ツール情報APIを呼び出し
                    tools_response = await client.get_tool_descriptions()
                    if tools_response and "tools" in tools_response:
                        for tool in tools_response["tools"]:
                            tool_name = tool["name"]
                            self.available_tools[tool_name] = {
                                'mcp_server': mcp_name,
                                'description': tool.get('description', ''),
                                'usage_context': tool.get('usage_context', ''),
                                'parameters': tool.get('parameters', {})
                            }
                            self.tool_routing[tool_name] = mcp_name
                            # 発見されたツールを自動的に有効化
                            self.enabled_tools.add(tool_name)
                            logger.info(f"Discovered tool: {tool_name} from {mcp_name}")
            except Exception as e:
                logger.error(f"Failed to discover tools from {mcp_name}: {e}")
        
        logger.info(f"Total tools discovered: {len(self.available_tools)}")
    
    def get_enabled_tools(self):
        """有効なツールのみ返す"""
        return {
            name: info for name, info in self.available_tools.items()
            if name in self.enabled_tools
        }
    
    def toggle_tool(self, tool_name: str) -> bool:
        """ツールの有効/無効を切り替え"""
        if tool_name in self.available_tools:
            if tool_name in self.enabled_tools:
                self.enabled_tools.remove(tool_name)
                return False
            else:
                self.enabled_tools.add(tool_name)
                return True
        return False
    
    async def process_message(self, user_message: str) -> Dict[str, Any]:
        """メッセージ処理（常に戦略立案・決定論的実行）"""
        try:
            # 常に戦略立案実行（判断は strategy_engine に委譲）
            logger.info(f"[DEBUG] 戦略立案開始")
            strategy = await self.strategy_engine.plan_strategy(user_message)
            logger.info(f"[DEBUG] 戦略立案完了 - steps: {len(strategy.steps)}")
            logger.info(f"[DEBUG] 戦略立案LLM情報確認 - prompt存在: {strategy.strategy_llm_prompt is not None}")
            if strategy.strategy_llm_prompt:
                logger.info(f"[DEBUG] 戦略立案LLM情報 - prompt長: {len(strategy.strategy_llm_prompt)}, response長: {len(strategy.strategy_llm_response or '')}")
            
            print(f"[AI_AGENT] === STRATEGY PLANNING ===")
            print(f"[AI_AGENT] Steps: {len(strategy.steps)}")
            if strategy.steps:
                print(f"[AI_AGENT] Tools: {[step.tool for step in strategy.steps]}")
            
            # 決定論的実行
            logger.info(f"[DEBUG] 戦略実行開始")
            executed_strategy = await self.execute_detailed_strategy(strategy, user_message)
            logger.info(f"[DEBUG] 戦略実行完了")
            
            # 動的システムプロンプトで応答生成
            logger.info(f"[DEBUG] 応答生成開始")
            response = await self.integration_engine.generate_contextual_response_with_strategy(
                user_message, executed_strategy
            )
            logger.info(f"[DEBUG] 応答生成完了 - 応答長: {len(response)}")
            
            # 最終確認
            logger.info(f"[DEBUG] 最終戦略確認 - prompt存在: {executed_strategy.strategy_llm_prompt is not None}")
            
            return {
                "message": response,
                "strategy": executed_strategy,
                "mcp_enabled": len(executed_strategy.steps) > 0  # 実際にツールを使ったかどうか
            }
            
        except Exception as e:
            logger.error(f"Message processing error: {e}")
            return {
                "message": "申し訳ございません。処理中にエラーが発生しました。",
                "tools_used": [],
                "mcp_enabled": False,
                "error": str(e)
            }
    
    async def execute_tools(self, tool_requests: list, tool_arguments: dict) -> list:
        """複数ツールの実行"""
        results = []
        for tool_name in tool_requests:
            if tool_name not in self.available_tools:
                results.append({"tool": tool_name, "error": "Tool not available"})
                continue
                
            if tool_name not in self.enabled_tools:
                results.append({"tool": tool_name, "error": "Tool not enabled"})
                continue
            
            mcp_server_name = self.available_tools[tool_name]['mcp_server']
            client = self.mcp_clients[mcp_server_name]
            
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
    
    async def call_claude(self, system_prompt: str, user_message: str) -> str:
        """Claude 3.5 Sonnet呼び出し"""
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
            logger.error(f"Claude API error: {e}")
            raise
    
    async def execute_detailed_strategy(self, strategy: DetailedStrategy, user_message: str) -> DetailedStrategy:
        """戦略に基づく決定論的実行 - 同じオブジェクトに実行結果を埋め込み"""
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
        
        return strategy  # 実行結果が埋め込まれた同じオブジェクト
    
    async def execute_tool_directly(self, tool_name: str, tool_input: str) -> Dict[str, Any]:
        """ツールを直接実行"""
        if tool_name not in self.available_tools:
            return {"error": f"Tool '{tool_name}' not available"}
        
        if tool_name not in self.enabled_tools:
            return {"error": f"Tool '{tool_name}' not enabled"}
        
        mcp_server_name = self.available_tools[tool_name]['mcp_server']
        client = self.mcp_clients[mcp_server_name]
        
        try:
            if await client.health_check():
                # テキスト入力でツール実行
                result = await client.call_tool(tool_name, {"text_input": tool_input})
                return result
            else:
                return {"error": "MCP server unavailable"}
        except Exception as e:
            return {"error": str(e)}
