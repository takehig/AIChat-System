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
from system_prompts_api import get_system_prompt_by_key

logger = logging.getLogger(__name__)

async def get_prompt_from_management(prompt_name: str) -> str:
    """SystemPrompt Management からプロンプト取得"""
    try:
        prompt_data = await get_system_prompt_by_key(prompt_name)
        return prompt_data.get("content", "")
    except Exception as e:
        logger.error(f"SystemPrompt Management取得失敗 {prompt_name}: {e}")
        # フォールバック: 固定エラーメッセージ
        if prompt_name == "direct_response_prompt":
            return "証券会社の社内情報システムとして、質問に適切に回答してください。"
        elif prompt_name == "strategy_result_response_prompt":
            return "証券会社の社内情報システムとして回答してください。"
        else:
            return "システムエラーが発生しました。"

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
            response = await self.generate_contextual_response_with_strategy(
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
    
    async def generate_contextual_response_with_tools(self, user_message: str, tool_results: list, executed_strategy: DetailedStrategy = None) -> str:
        """ツール結果を含む動的応答生成（SystemPrompt Management v2.0.0対応・LLM情報記録対応）"""
        if not tool_results:
            direct_prompt = await get_prompt_from_management("direct_response_prompt")
            response, prompt, llm_response, execution_time = await self.llm_util.call_claude_with_llm_info(
                direct_prompt, user_message
            )
            # 最終応答LLM情報を記録
            if executed_strategy:
                executed_strategy.final_response_llm_prompt = prompt
                executed_strategy.final_response_llm_response = llm_response
                executed_strategy.final_response_llm_execution_time_ms = execution_time
            return response
        
        # 使用ツール情報を動的生成
        tools_used = [result["tool"] for result in tool_results if "result" in result]
        tools_failed = [result["tool"] for result in tool_results if "error" in result]
        
        tools_summary = "\n\n".join([
            f"【{result['tool']}の結果】\n{json.dumps(result.get('result', result.get('error')), ensure_ascii=False, indent=2)}"
            for result in tool_results
        ])
        
        # SystemPrompt Management からプロンプトテンプレート取得
        tool_prompt_template = await get_prompt_from_management("tool_result_response_prompt")
        
        # 動的変数準備
        tools_used_str = ', '.join(tools_used) if tools_used else 'なし'
        tools_failed_text = f'実行に失敗したツール: {", ".join(tools_failed)}' if tools_failed else ''
        tools_failed_requirement = '- 失敗したツールがある場合は、その旨を説明' if tools_failed else ''
        
        # 動的システムプロンプト生成
        system_prompt = tool_prompt_template.format(
            user_message=user_message,
            tools_used=tools_used_str,
            tools_failed_text=tools_failed_text,
            tools_summary=tools_summary,
            tools_failed_requirement=tools_failed_requirement
        )

        response, prompt, llm_response, execution_time = await self.llm_util.call_claude_with_llm_info(
            system_prompt, "上記を基に回答してください."
        )
        
        # 最終応答LLM情報を記録
        if executed_strategy:
            executed_strategy.final_response_llm_prompt = prompt
            executed_strategy.final_response_llm_response = llm_response
            executed_strategy.final_response_llm_execution_time_ms = execution_time
        
        return response
    
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
    
    async def generate_contextual_response_with_strategy(self, user_message: str, executed_strategy: DetailedStrategy) -> str:
        """戦略実行結果を含む動的応答生成（SystemPrompt Management v2.0.0対応）"""
        
        logger.info(f"[DEBUG] generate_contextual_response_with_strategy開始")
        logger.info(f"[DEBUG] parse_error: {executed_strategy.parse_error}")
        logger.info(f"[DEBUG] steps数: {len(executed_strategy.steps) if executed_strategy.steps else 0}")
        logger.info(f"[DEBUG] is_executed: {executed_strategy.is_executed()}")
        
        # 戦略立案エラー時は直接回答（ハルシネーション防止）
        if executed_strategy.parse_error:
            logger.info(f"[DEBUG] 戦略立案エラー処理開始")
            direct_prompt = await get_prompt_from_management("direct_response_prompt")
            logger.info(f"[DEBUG] direct_prompt取得完了: {len(direct_prompt) if direct_prompt else 0}文字")
            response, prompt, llm_response, execution_time = await self.llm_util.call_claude_with_llm_info(
                direct_prompt, user_message
            )
            logger.info(f"[DEBUG] LLM呼び出し完了 - 応答長: {len(response)}, prompt長: {len(prompt)}")
            # 最終応答LLM情報を記録
            executed_strategy.final_response_llm_prompt = prompt
            executed_strategy.final_response_llm_response = llm_response
            executed_strategy.final_response_llm_execution_time_ms = execution_time
            logger.info(f"[DEBUG] 最終応答LLM情報記録完了")
            return response
        
        # ツール未実行時も直接回答
        if not executed_strategy.steps or not executed_strategy.is_executed():
            direct_prompt = await get_prompt_from_management("direct_response_prompt")
            response, prompt, llm_response, execution_time = await self.llm_util.call_claude_with_llm_info(
                direct_prompt, user_message
            )
            # 最終応答LLM情報を記録
            executed_strategy.final_response_llm_prompt = prompt
            executed_strategy.final_response_llm_response = llm_response
            executed_strategy.final_response_llm_execution_time_ms = execution_time
            return response
        
        # 実行結果サマリー生成
        results_summary = "\n\n".join([
            f"【Step {step.step}: {step.tool}】\n理由: {step.reason}\n結果: {json.dumps(step.output, ensure_ascii=False, indent=2)}"
            for step in executed_strategy.steps if step.output
        ])
        
        # SystemPrompt Management からプロンプトテンプレート取得
        strategy_prompt_template = await get_prompt_from_management("strategy_result_response_prompt")
        
        # 動的システムプロンプト生成
        total_execution_time = sum(s.execution_time_ms or 0 for s in executed_strategy.steps)
        system_prompt = strategy_prompt_template.format(
            user_message=user_message,
            results_summary=results_summary,
            total_execution_time=total_execution_time
        )

        response, prompt, llm_response, execution_time = await self.llm_util.call_claude_with_llm_info(system_prompt, "上記を基に回答してください。")
        
        # 最終応答LLM情報を記録
        executed_strategy.final_response_llm_prompt = prompt
        executed_strategy.final_response_llm_response = llm_response
        executed_strategy.final_response_llm_execution_time_ms = execution_time
        
        return response
