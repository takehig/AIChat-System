import json
import boto3
import logging
import time
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from mcp_client import MCPClient
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
class DetailedStrategy:
    steps: List[DetailedStep]
    
    # 戦略立案LLM情報
    strategy_llm_prompt: Optional[str] = None
    strategy_llm_response: Optional[str] = None
    strategy_llm_execution_time_ms: Optional[float] = None
    
    # 最終応答LLM情報
    final_llm_prompt: Optional[str] = None
    final_llm_response: Optional[str] = None
    final_llm_execution_time_ms: Optional[float] = None
    
    # エラーハンドリング情報
    parse_error: bool = False
    parse_error_message: str = ""
    raw_response: str = ""
    
    def is_executed(self) -> bool:
        """実行済みかどうか判定"""
        return all(step.output is not None for step in self.steps)
    
    def get_final_output(self) -> Optional[Dict]:
        """最終出力取得"""
        return self.steps[-1].output if self.steps and self.steps[-1].output else None
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換（JSON serialization用）"""
        return {
            "steps": [step.__dict__ for step in self.steps],
            "is_executed": self.is_executed(),
            "total_execution_time_ms": sum(s.execution_time_ms or 0 for s in self.steps),
            # LLM情報追加
            "strategy_llm_prompt": self.strategy_llm_prompt,
            "strategy_llm_response": self.strategy_llm_response,
            "strategy_llm_execution_time_ms": self.strategy_llm_execution_time_ms,
            "final_llm_prompt": self.final_llm_prompt,
            "final_llm_response": self.final_llm_response,
            "final_llm_execution_time_ms": self.final_llm_execution_time_ms
        }
    
    @classmethod
    def from_json(cls, json_str: str) -> 'DetailedStrategy':
        try:
            data = json.loads(json_str)
            steps = [DetailedStep(
                step=step["step"],
                tool=step["tool"], 
                reason=step["reason"]
            ) for step in data.get("steps", [])]
            return cls(steps=steps)
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.error(f"DetailedStrategy.from_json error: {e}, input: {json_str}")
            # エラー時は戦略立案失敗を示すステップを返す
            error_step = DetailedStep(
                step=1,
                tool="strategy_parse_error",
                reason=f"戦略立案時のJSON解析エラー: {str(e)}"
            )
            return cls(
                steps=[error_step], 
                parse_error=True, 
                parse_error_message=str(e), 
                raw_response=json_str
            )

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
        
        # エンジン統合
        self.strategy_engine = StrategyEngine(self.bedrock_client, self.available_tools)
        self.integration_engine = IntegrationEngine(self.bedrock_client)
        self.mcp_executor = MCPExecutor()
    
    async def call_claude_with_llm_info(self, system_prompt: str, user_message: str) -> tuple[str, str, str, float]:
        """LLM呼び出し（プロンプト・応答・実行時間を返却）"""
        start_time = time.time()
        full_prompt = f"System: {system_prompt}\n\nUser: {user_message}"
        
        try:
            response = await self.call_claude(system_prompt, user_message)
            execution_time = (time.time() - start_time) * 1000
            return response, full_prompt, response, execution_time
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            error_response = f"ERROR: {str(e)}"
            return error_response, full_prompt, error_response, execution_time
    
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
        """メッセージ処理（詳細戦略立案・決定論的実行）"""
        try:
            # MCP利用可能時は詳細戦略立案
            if self.mcp_available:
                # 戦略立案（直接 strategy_engine 呼び出し）
                strategy = await self.strategy_engine.plan_strategy(user_message)
                
                print(f"[AI_AGENT] === DETAILED STRATEGY PLANNING ===")
                print(f"[AI_AGENT] Steps: {len(strategy.steps)}")
                if strategy.steps:
                    print(f"[AI_AGENT] Tools: {[step.tool for step in strategy.steps]}")
                
                # 決定論的実行
                executed_strategy = await self.execute_detailed_strategy(strategy, user_message)
                
                # 動的システムプロンプトで応答生成
                response = await self.generate_contextual_response_with_strategy(
                    user_message, executed_strategy
                )
                
                return {
                    "message": response,
                    "strategy": executed_strategy,  # 全情報が含まれたオブジェクト
                    "mcp_enabled": True
                }
            
            # 通常のAI応答
            response = await self.generate_ai_response(user_message)
            return {
                "message": response,
                "tools_used": [],
                "mcp_enabled": self.mcp_available
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
    
    async def generate_contextual_response_with_tools(self, user_message: str, tool_results: list) -> str:
        """ツール結果を含む動的応答生成"""
        if not tool_results:
            return await self.call_claude(
                "証券会社の社内情報システムとして、質問に適切に回答してください。",
                user_message
            )
        
        # 使用ツール情報を動的生成
        tools_used = [result["tool"] for result in tool_results if "result" in result]
        tools_failed = [result["tool"] for result in tool_results if "error" in result]
        
        tools_summary = "\n\n".join([
            f"【{result['tool']}の結果】\n{json.dumps(result.get('result', result.get('error')), ensure_ascii=False, indent=2)}"
            for result in tool_results
        ])
        
        # 動的システムプロンプト生成
        system_prompt = f"""証券会社の社内情報システムとして回答してください。

ユーザーの質問: {user_message}

実行したツール: {', '.join(tools_used) if tools_used else 'なし'}
{f'実行に失敗したツール: {", ".join(tools_failed)}' if tools_failed else ''}

ツール実行結果:
{tools_summary}

回答要件:
- 質問の意図に応じて適切に回答
- 使用したツール名を回答の最後に明記: 「※使用ツール: {', '.join(tools_used)}」
- 過度に営業的にならず、事実ベースで回答
{f'- 失敗したツールがある場合は、その旨を説明' if tools_failed else ''}"""

        return await self.call_claude(system_prompt, "上記を基に回答してください。")
    
    async def format_tool_result(self, user_message: str, tool_name: str, tool_result: Dict[str, Any]) -> str:
        """ツール結果整形"""
        # tool_resultから実際の結果を取得
        actual_result = tool_result.get('result', tool_result)
        
        system_prompt = f"""あなたは親切な金融商品アドバイザーです。
ユーザーの質問に対して、ツール実行結果を基に自然で分かりやすい回答を作成してください。

ユーザーの質問: {user_message}
使用したツール: {tool_name}
ツール実行結果: {json.dumps(actual_result, ensure_ascii=False, indent=2)}

回答ガイドライン:
1. ユーザーの質問に直接答える
2. 結果を分かりやすく整理して提示
3. 必要に応じて追加の提案をする
4. 親しみやすい口調で回答

JSONをそのまま表示せず、自然な日本語で回答してください。"""
        
        try:
            return await self.call_claude(system_prompt, "上記の情報を基に回答を作成してください。")
        except Exception as e:
            logger.error(f"Tool result formatting error: {e}")
            return f"ツール実行結果: {json.dumps(tool_result, ensure_ascii=False, indent=2)}"
    
    async def generate_ai_response(self, message: str) -> str:
        """通常のAI応答"""
        system_prompt = """あなたは親切な金融商品アドバイザーです。
ユーザーの質問に対して、親しみやすく分かりやすい回答をしてください。

特定の商品情報が必要な場合は、「詳細な商品情報をお調べしますので、具体的な商品名や条件を教えてください」のように案内してください。"""
        
        try:
            return await self.call_claude(system_prompt, message)
        except Exception as e:
            logger.error(f"AI response error: {e}")
            return "申し訳ございません。回答の生成中にエラーが発生しました。"
    
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
        """戦略実行結果を含む動的応答生成"""
        if not executed_strategy.steps or not executed_strategy.is_executed():
            return await self.call_claude(
                "証券会社の社内情報システムとして、質問に適切に回答してください。",
                user_message
            )
        
        # 実行結果サマリー生成
        results_summary = "\n\n".join([
            f"【Step {step.step}: {step.tool}】\n理由: {step.reason}\n結果: {json.dumps(step.output, ensure_ascii=False, indent=2)}"
            for step in executed_strategy.steps if step.output
        ])
        
        # 動的システムプロンプト生成
        system_prompt = f"""証券会社の社内情報システムとして回答してください。

ユーザーの質問: {user_message}

実行結果:
{results_summary}

回答要件:
- 質問の意図に応じて適切に回答
- 実行した処理の流れを簡潔に説明
- 最終的な結果を分かりやすく提示
- 過度に営業的にならず、事実ベースで回答
- 実行時間: {sum(s.execution_time_ms or 0 for s in executed_strategy.steps)}ms"""

        response, prompt, llm_response, execution_time = await self.call_claude_with_llm_info(system_prompt, "上記を基に回答してください。")
        
        # 最終応答LLM情報を記録
        executed_strategy.final_llm_prompt = prompt
        executed_strategy.final_llm_response = llm_response
        executed_strategy.final_llm_execution_time_ms = execution_time
        
        return response
