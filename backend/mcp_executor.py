# AIChat System - MCP実行エンジン
import json
import time
import logging
from typing import Dict, Any
from mcp_client import MCPClient
from models import DetailedStrategy

logger = logging.getLogger(__name__)

class MCPExecutor:
    """MCP実行専用エンジン - 将来大幅拡張予定"""
    
    def __init__(self):
        self.mcp_clients = {
            'productmaster': MCPClient("http://localhost:8003"),
            'crm': MCPClient("http://localhost:8004")
        }
        self.mcp_available = False
        self.available_tools = {}
        self.enabled_tools = set()
        self.tool_routing = {}
        
        # === 将来拡張用（現在は空実装） ===
        self.execution_cache = {}        # 実行結果キャッシュ
        self.performance_metrics = {}    # パフォーマンスメトリクス
        self.retry_strategies = {}       # リトライ戦略
    
    async def initialize(self):
        """MCP初期化"""
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
                await self.discover_tools()
        except Exception as e:
            logger.error(f"MCP Executor initialization error: {e}")
    
    async def discover_tools(self):
        """全MCPサーバーからツール情報を収集"""
        self.available_tools = {}
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
                            logger.info(f"Discovered tool: {tool_name} from {mcp_name}")
            except Exception as e:
                logger.error(f"Failed to discover tools from {mcp_name}: {e}")
        
        logger.info(f"Total tools discovered: {len(self.available_tools)}")
    
    async def execute_strategy(self, strategy: DetailedStrategy, user_message: str) -> DetailedStrategy:
        """戦略実行メイン処理"""
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
            
            print(f"[MCP_EXECUTOR] Step {step.step} completed: {step.tool} ({step.execution_time_ms:.2f}ms)")
        
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
            logger.error(f"Tool execution error: {e}")
            return {"error": str(e)}
    
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
    async def execute_parallel(self, steps: list) -> list:
        """並列実行（将来実装）"""
        pass
    
    async def cache_result(self, key: str, result: dict):
        """結果キャッシュ（将来実装）"""
        pass
    
    async def health_check_all(self) -> dict:
        """全MCP健康状態チェック（将来実装）"""
        pass
    
    async def optimize_execution_order(self, steps: list) -> list:
        """実行順序最適化（将来実装）"""
        pass
