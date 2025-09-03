import json
import boto3
import logging
from typing import Dict, Any, Optional
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
        
        # ツール名とMCPサーバーのマッピング（動的生成用）
        self.tool_routing = {}
    
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
        """メッセージ処理"""
        try:
            # MCP利用可能時は意図解析
            if self.mcp_available:
                intent = await self.analyze_intent_dynamic(user_message)
                
                if intent.requires_tools:
                    print(f"[AI_AGENT] === TOOL EXECUTION DECISION ===")
                    print(f"[AI_AGENT] Tool requested: {intent.tool_name}")
                    print(f"[AI_AGENT] Tool arguments: {intent.arguments}")
                    
                    # ツール名から適切なMCPクライアントを選択
                    mcp_name = self.tool_routing.get(intent.tool_name)
                    print(f"[AI_AGENT] Tool routing lookup: {intent.tool_name} -> {mcp_name}")
                    print(f"[AI_AGENT] Available MCP clients: {list(self.mcp_clients.keys())}")
                    print(f"[AI_AGENT] MCP client exists: {mcp_name in self.mcp_clients if mcp_name else False}")
                    
                    if mcp_name and mcp_name in self.mcp_clients:
                        client = self.mcp_clients[mcp_name]
                        print(f"[AI_AGENT] Using MCP client: {mcp_name}")
                        print(f"[AI_AGENT] Client URL: {client.server_url}")
                        
                        # ツール実行
                        tool_result = await client.call_tool(
                            intent.tool_name, intent.arguments or {}
                        )
                        
                        # debug_info確認ログ
                        logger.info(f"[DEBUG] tool_result in ai_agent: {tool_result}")
                        logger.info(f"[DEBUG] tool_result keys: {list(tool_result.keys()) if isinstance(tool_result, dict) else 'Not dict'}")
                        
                        # 結果整形
                        response = await self.format_tool_result(
                            user_message, intent.tool_name, tool_result
                        )
                        
                        return {
                            "message": response,
                            "tools_used": [intent.tool_name],
                            "mcp_enabled": True,
                            "mcp_server": mcp_name,
                            "debug_info": tool_result.get('debug_info', None)
                        }
                    else:
                        return {
                            "message": f"申し訳ございません。ツール '{intent.tool_name}' が見つかりません。",
                            "tools_used": [],
                            "mcp_enabled": True,
                            "error": f"Tool not found: {intent.tool_name}"
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
                "error": str(e),
                "tools_used": [],
                "mcp_enabled": False
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
    
    async def analyze_intent_dynamic(self, message: str) -> Intent:
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
