import json
import boto3
import logging
import time
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from mcp_client import MCPClient

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
class ExecutionTrace:
    timestamp: str
    step_type: str  # "strategy_planning", "tool_execution", "llm_interaction"
    step_name: str
    llm_prompt: Optional[str] = None
    llm_response: Optional[str] = None
    input_data: Optional[Dict] = None
    output_data: Optional[Dict] = None
    execution_time_ms: Optional[float] = None

@dataclass
class DetailedStep:
    step: int
    tool: str
    purpose: str
    input_source: str  # "user_input" or "step_N_result"
    input_extraction: str
    expected_output: str

@dataclass
class DetailedStrategy:
    reasoning: str
    steps: List[DetailedStep]
    data_flow: str
    
    @classmethod
    def from_json(cls, json_str: str) -> 'DetailedStrategy':
        data = json.loads(json_str)
        steps = [DetailedStep(**step) for step in data["steps"]]
        return cls(
            reasoning=data["reasoning"],
            steps=steps,
            data_flow=data["data_flow"]
        )

class DebugCollector:
    def __init__(self):
        self.traces: List[ExecutionTrace] = []
    
    def add_llm_trace(self, step_name: str, prompt: str, response: str, execution_time: float):
        self.traces.append(ExecutionTrace(
            timestamp=datetime.now().isoformat(),
            step_type="llm_interaction",
            step_name=step_name,
            llm_prompt=prompt,
            llm_response=response,
            execution_time_ms=execution_time
        ))
    
    def add_tool_trace(self, step_name: str, input_data: Dict, output_data: Dict, execution_time: float):
        self.traces.append(ExecutionTrace(
            timestamp=datetime.now().isoformat(),
            step_type="tool_execution", 
            step_name=step_name,
            input_data=input_data,
            output_data=output_data,
            execution_time_ms=execution_time
        ))

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
        
        # デバッグ収集器
        self.debug_collector = None
    
    async def call_claude_with_trace(self, system_prompt: str, user_message: str, step_name: str) -> str:
        """LLM呼び出しをトレース付きで実行"""
        start_time = time.time()
        
        # 完全なプロンプトを記録
        full_prompt = f"System: {system_prompt}\n\nUser: {user_message}"
        
        try:
            response = await self.call_claude(system_prompt, user_message)
            execution_time = (time.time() - start_time) * 1000
            
            # トレース記録
            if self.debug_collector:
                self.debug_collector.add_llm_trace(
                    step_name=step_name,
                    prompt=full_prompt,
                    response=response,
                    execution_time=execution_time
                )
            
            return response
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            error_response = f"ERROR: {str(e)}"
            
            if self.debug_collector:
                self.debug_collector.add_llm_trace(
                    step_name=step_name,
                    prompt=full_prompt,
                    response=error_response,
                    execution_time=execution_time
                )
            raise
    
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
            # デバッグ収集器初期化
            self.debug_collector = DebugCollector()
            
            # MCP利用可能時は詳細戦略立案
            if self.mcp_available:
                # 詳細戦略立案
                strategy = await self.plan_detailed_strategy(user_message)
                
                print(f"[AI_AGENT] === DETAILED STRATEGY PLANNING ===")
                print(f"[AI_AGENT] Strategy: {strategy.reasoning}")
                print(f"[AI_AGENT] Steps: {len(strategy.steps)}")
                
                # 決定論的実行
                execution_result = await self.execute_detailed_strategy(strategy, user_message)
                
                # 動的システムプロンプトで応答生成
                response = await self.generate_contextual_response_with_strategy(
                    user_message, execution_result
                )
                
                return {
                    "message": response,
                    "tools_used": [r["tool"] for r in execution_result["results"]],
                    "mcp_enabled": True,
                    "debug_info": {
                        "strategy": {
                            "reasoning": strategy.reasoning,
                            "steps": [step.__dict__ for step in strategy.steps],
                            "data_flow": strategy.data_flow
                        },
                        "execution": execution_result,
                        "debug_traces": execution_result["debug_traces"]
                    }
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
    
    async def plan_detailed_strategy(self, user_message: str) -> DetailedStrategy:
        """詳細な実行戦略を立案"""
        enabled_tools = self.get_enabled_tools()
        
        tools_description = "\n".join([
            f"- {name}: {info['usage_context']}"
            for name, info in enabled_tools.items()
        ])
        
        strategy_prompt = f"""ユーザーリクエストを分析し、詳細な実行プランを作成してください。

利用可能ツール:
{tools_description}

以下のJSON形式で詳細プランを回答:
{{
    "reasoning": "戦略の理由",
    "steps": [
        {{
            "step": 1,
            "tool": "ツール名",
            "purpose": "実行目的", 
            "input_source": "user_input",
            "input_extraction": "入力から何を抽出するか",
            "expected_output": "期待される出力"
        }},
        {{
            "step": 2,
            "tool": "ツール名",
            "purpose": "実行目的",
            "input_source": "step_1_result",
            "input_extraction": "前ステップ結果から何を抽出するか",
            "expected_output": "期待される出力"
        }}
    ],
    "data_flow": "データの流れの説明"
}}

input_sourceは "user_input" または "step_N_result" を指定
input_extractionは具体的な抽出方法を記述"""

        response = await self.call_claude_with_trace(
            system_prompt=strategy_prompt,
            user_message=user_message,
            step_name="詳細戦略立案"
        )
        
        return DetailedStrategy.from_json(response)
        """動的システムプロンプトでツール選択"""
        enabled_tools = self.get_enabled_tools()
        
        if not enabled_tools:
            return Intent(requires_tool=False, requires_tools=[], confidence=0.0)
        
        # 動的ツール説明生成
        tools_description = "\n".join([
            f"- {name}: {info['usage_context']}"
            for name, info in enabled_tools.items()
        ])
        
        system_prompt = f"""ユーザーのメッセージを分析し、必要なツールを判定してください。

現在利用可能なツール:
{tools_description}

以下のJSON形式で回答してください：
{{"requires_tools": ["ツール名1", "ツール名2"], "tool_arguments": {{"ツール名1": {{"param": "value"}}}}, "confidence": 0.0-1.0}}

判定ルール:
- 複数ツールが必要な場合は配列で指定
- ツールが不要な場合は requires_tools を空配列に
- 引数は各ツールのパラメータに基づいて設定
- confidenceは判定の確信度（0.0-1.0）"""
        
        try:
            response = await self.call_claude(system_prompt, message)
            data = json.loads(response)
            return Intent(
                requires_tool=len(data.get('requires_tools', [])) > 0,
                requires_tools=data.get('requires_tools', []),
                tool_name=data.get('requires_tools', [None])[0],  # 後方互換性
                arguments=data.get('tool_arguments', {}),
                confidence=data.get('confidence', 0.0)
            )
        except Exception as e:
            logger.error(f"Dynamic intent analysis error: {e}")
            return Intent(requires_tool=False, requires_tools=[], confidence=0.0)
        """意図解析"""
        system_prompt = """あなたは金融商品検索アシスタントです。
ユーザーのメッセージを分析し、以下のツールが必要か判定してください。

利用可能ツール:
- search_products_flexible: 商品検索・探索
- get_product_details: 特定商品の詳細
- get_product_statistics: 統計・分析情報
- search_customers: 顧客情報検索
- get_customer_holdings: 顧客保有商品情報
- search_customers_by_bond_maturity: 債券満期日での顧客検索

以下のJSON形式で回答してください：
{"requires_tool": true/false, "tool_name": "ツール名", "arguments": {"パラメータ": "値"}, "confidence": 0.0-1.0}

判定基準:
- 商品検索・探索 → search_products_flexible
- 特定商品の詳細 → get_product_details
- 統計・分析情報 → get_product_statistics
- 顧客情報検索 → search_customers
- 顧客保有商品情報 → get_customer_holdings
- 満期の近い債券保有者・債券満期日検索 → search_customers_by_bond_maturity
- 一般的な質問・挨拶 → ツール不要"""
        
        try:
            response = await self.call_claude(system_prompt, message)
            data = json.loads(response)
            return Intent(
                requires_tool=data.get('requires_tool', False),
                tool_name=data.get('tool_name'),
                arguments=data.get('arguments', {}),
                confidence=data.get('confidence', 0.0)
            )
        except Exception as e:
            logger.error(f"Intent analysis error: {e}")
            return Intent(requires_tool=False)
    
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
    
    async def execute_detailed_strategy(self, strategy: DetailedStrategy, user_message: str) -> Dict[str, Any]:
        """戦略に基づく決定論的実行"""
        execution_context = {"user_input": user_message}
        results = []
        
        for step in strategy.steps:
            step_start_time = time.time()
            
            # 入力準備（決定論的、LLM不使用）
            tool_input = self.prepare_tool_input(step, execution_context)
            
            # ツール直接実行
            result = await self.execute_tool_directly(step.tool, tool_input)
            
            step_execution_time = (time.time() - step_start_time) * 1000
            
            # 結果を次ステップ用に保存
            execution_context[f"step_{step.step}_result"] = result
            
            results.append({
                "step": step.step,
                "tool": step.tool,
                "purpose": step.purpose,
                "input": tool_input,
                "result": result,
                "execution_time_ms": step_execution_time
            })
            
            # ツール実行トレース
            if self.debug_collector:
                self.debug_collector.add_tool_trace(
                    step_name=f"Step_{step.step}_{step.tool}",
                    input_data={"tool_input": tool_input, "step_info": step.__dict__},
                    output_data=result,
                    execution_time=step_execution_time
                )
        
        return {
            "strategy": strategy,
            "results": results,
            "debug_traces": self.debug_collector.traces if self.debug_collector else [],
            "total_execution_time_ms": sum(r["execution_time_ms"] for r in results)
        }
    
    def prepare_tool_input(self, step: DetailedStep, context: Dict) -> str:
        """入力準備（決定論的、LLM不使用）"""
        
        if step.input_source == "user_input":
            return context["user_input"]
        
        # 前ステップ結果から必要データを抽出
        source_data = context.get(step.input_source, {})
        
        # 抽出方法に基づいてデータ変換
        if step.input_extraction == "customer_ids":
            return self.extract_customer_ids_text(source_data)
        elif step.input_extraction == "product_codes":
            return self.extract_product_codes_text(source_data)
        elif step.input_extraction == "raw_result":
            return json.dumps(source_data, ensure_ascii=False)
        
        # デフォルトは結果全体をテキスト化
        return f"前回の結果: {json.dumps(source_data, ensure_ascii=False)}"
    
    def extract_customer_ids_text(self, data: Dict) -> str:
        """顧客IDをテキスト形式で抽出"""
        if isinstance(data, dict) and "data" in data:
            customers = data["data"]
            if isinstance(customers, list):
                customer_ids = [str(c.get("customer_id", "")) for c in customers if c.get("customer_id")]
                return f"顧客ID: {', '.join(customer_ids)}"
        return "顧客IDが見つかりませんでした"
    
    def extract_product_codes_text(self, data: Dict) -> str:
        """商品コードをテキスト形式で抽出"""
        if isinstance(data, dict) and "data" in data:
            products = data["data"]
            if isinstance(products, list):
                product_codes = [str(p.get("product_code", "")) for p in products if p.get("product_code")]
                return f"商品コード: {', '.join(product_codes)}"
        return "商品コードが見つかりませんでした"
    
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
    async def generate_contextual_response_with_strategy(self, user_message: str, execution_result: Dict) -> str:
        """戦略実行結果を含む動的応答生成"""
        if not execution_result["results"]:
            return await self.call_claude(
                "証券会社の社内情報システムとして、質問に適切に回答してください。",
                user_message
            )
        
        # 実行結果サマリー生成
        strategy = execution_result["strategy"]
        results = execution_result["results"]
        
        results_summary = "\n\n".join([
            f"【Step {result['step']}: {result['tool']}】\n目的: {result['purpose']}\n結果: {json.dumps(result['result'], ensure_ascii=False, indent=2)}"
            for result in results
        ])
        
        # 動的システムプロンプト生成
        system_prompt = f"""証券会社の社内情報システムとして回答してください。

ユーザーの質問: {user_message}

実行戦略: {strategy.reasoning}
データフロー: {strategy.data_flow}

実行結果:
{results_summary}

回答要件:
- 質問の意図に応じて適切に回答
- 実行した処理の流れを簡潔に説明
- 最終的な結果を分かりやすく提示
- 過度に営業的にならず、事実ベースで回答
- 実行時間: {execution_result.get('total_execution_time_ms', 0)}ms"""

        return await self.call_claude(system_prompt, "上記を基に回答してください。")
