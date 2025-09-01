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

class AIAgent:
    def __init__(self):
        self.bedrock_client = boto3.client('bedrock-runtime', region_name='us-east-1')
        self.model_id = "anthropic.claude-3-sonnet-20240229-v1:0"
        self.mcp_client = MCPClient()
        self.mcp_available = False
    
    async def initialize(self):
        """AI Agent初期化"""
        try:
            if await self.mcp_client.health_check():
                if await self.mcp_client.initialize():
                    await self.mcp_client.list_tools()
                    self.mcp_available = True
                    logger.info("MCP integration enabled")
                else:
                    logger.warning("MCP initialization failed")
            else:
                logger.warning("MCP server not available")
        except Exception as e:
            logger.error(f"AI Agent initialization error: {e}")
    
    async def process_message(self, user_message: str) -> Dict[str, Any]:
        """メッセージ処理"""
        try:
            # MCP利用可能時は意図解析
            if self.mcp_available:
                intent = await self.analyze_intent(user_message)
                
                if intent.requires_tool and intent.tool_name:
                    # ツール実行
                    tool_result = await self.mcp_client.call_tool(
                        intent.tool_name, intent.arguments or {}
                    )
                    
                    # 結果整形
                    response = await self.format_tool_result(
                        user_message, intent.tool_name, tool_result
                    )
                    
                    return {
                        "message": response,
                        "tools_used": [intent.tool_name],
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
                "error": str(e),
                "tools_used": [],
                "mcp_enabled": False
            }
    
    async def analyze_intent(self, message: str) -> Intent:
        """意図解析"""
        system_prompt = """あなたは金融商品検索アシスタントです。
ユーザーのメッセージを分析し、以下のツールが必要か判定してください。

利用可能ツール:
- search_products_flexible: 商品検索・探索
- get_product_details: 特定商品の詳細
- get_product_statistics: 統計・分析情報
- search_customers: 顧客情報検索
- get_customer_holdings: 顧客保有商品情報

以下のJSON形式で回答してください：
{"requires_tool": true/false, "tool_name": "ツール名", "arguments": {"パラメータ": "値"}, "confidence": 0.0-1.0}

判定基準:
- 商品検索・探索 → search_products_flexible
- 特定商品の詳細 → get_product_details
- 統計・分析情報 → get_product_statistics
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
        system_prompt = f"""あなたは親切な金融商品アドバイザーです。
ユーザーの質問に対して、ツール実行結果を基に自然で分かりやすい回答を作成してください。

ユーザーの質問: {user_message}
使用したツール: {tool_name}
ツール実行結果: {json.dumps(tool_result, ensure_ascii=False, indent=2)}

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
