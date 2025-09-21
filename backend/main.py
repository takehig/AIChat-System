from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import boto3
import json
import os
import logging
import httpx
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from ai_agent import AIAgent
from conversation_manager import ConversationManager
from system_prompts_api import get_system_prompt_by_key, list_system_prompts

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="AIChat System with MCP Integration", version="2.1.0")

# 会話履歴管理
conversation_manager = ConversationManager()

# CORS設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# グローバル変数
ai_agent: Optional[AIAgent] = None

# データモデル
class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None

class ChatResponse(BaseModel):
    message: str
    timestamp: str
    strategy: Optional[Any] = None  # DetailedStrategyオブジェクト（Any型で受け入れ）
    mcp_enabled: bool = False
    error: Optional[str] = None

class SystemStatus(BaseModel):
    status: str
    mcp_tools_count: int
    enabled_tools_count: int
    timestamp: str

# 起動時初期化
@app.on_event("startup")
async def startup_event():
    global ai_agent
    try:
        logger.info("🚀 Starting AIChat System...")
        ai_agent = AIAgent()
        await ai_agent.initialize()
        logger.info("✅ AIChat System initialized successfully")
    except Exception as e:
        logger.error(f"❌ Startup initialization failed: {e}")
        # MCPが失敗してもサービスは継続
        ai_agent = AIAgent()

# APIエンドポイント（静的ファイル配信より先に定義）
@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    global ai_agent
    
    if not ai_agent:
        raise HTTPException(status_code=503, detail="AI Agent not initialized")
    
    try:
        # フロントエンドからのセッションIDを優先使用
        session_id = request.conversation_id or str(uuid.uuid4())
        logger.info(f"Using session_id: {session_id}")
        
        # 前回の会話履歴を取得
        conversation_context = conversation_manager.get_conversation_context(session_id)
        
        # 会話履歴を含めたメッセージを作成
        enhanced_message = conversation_context + "## 今回の質問\n" + request.message if conversation_context else request.message
        
        logger.info(f"Processing message: {request.message[:50]}...")
        if conversation_context:
            logger.info(f"Using conversation context: {len(conversation_context)} chars")
        
        # AI Agentでメッセージ処理
        result = await ai_agent.process_message(enhanced_message)
        logger.info(f"[DEBUG] AI Agent処理完了: {list(result.keys())}")
        
        # strategy確認ログ
        strategy = result.get("strategy")
        logger.info(f"[DEBUG] Strategy object存在: {strategy is not None}")
        if strategy:
            logger.info(f"[DEBUG] Strategy type: {type(strategy)}")
            logger.info(f"[DEBUG] Strategy steps: {len(strategy.steps) if hasattr(strategy, 'steps') else 'No steps attr'}")
            logger.info(f"[DEBUG] Strategy strategy_llm_prompt存在: {hasattr(strategy, 'strategy_llm_prompt') and strategy.strategy_llm_prompt is not None}")
            if hasattr(strategy, 'strategy_llm_prompt'):
                logger.info(f"[DEBUG] Strategy strategy_llm_prompt長さ: {len(str(strategy.strategy_llm_prompt)) if strategy.strategy_llm_prompt else 0}")
        
        # to_dict()変換前後の確認
        strategy_dict = strategy.to_dict() if strategy else None
        logger.info(f"[DEBUG] Strategy dict作成: {strategy_dict is not None}")
        if strategy_dict:
            logger.info(f"[DEBUG] Strategy dict keys: {list(strategy_dict.keys())}")
            logger.info(f"[DEBUG] Strategy dict strategy_llm_prompt存在: {'strategy_llm_prompt' in strategy_dict}")
            if 'strategy_llm_prompt' in strategy_dict:
                logger.info(f"[DEBUG] Strategy dict strategy_llm_prompt値: {strategy_dict['strategy_llm_prompt'] is not None}")
        
        # 会話履歴に保存
        conversation_manager.add_message(
            session_id=session_id,
            user_message=request.message,  # 元のメッセージのみ保存
            ai_response=result["message"],
            strategy_info=strategy_dict or {}
        )
        
        return ChatResponse(
            message=result["message"],
            timestamp=datetime.now().isoformat(),
            strategy=strategy.to_dict() if strategy else None,  # to_dict()を明示的に使用
            mcp_enabled=result.get("mcp_enabled", False),
            error=result.get("error")
        )
        
    except Exception as e:
        logger.error(f"Chat processing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/clear-conversation")
async def clear_conversation(request: ChatRequest):
    """会話履歴をクリア"""
    try:
        session_id = request.conversation_id or "default"
        conversation_manager.clear_session(session_id)
        return {"status": "success", "message": f"会話履歴をクリアしました (session: {session_id})"}
    except Exception as e:
        logger.error(f"Clear conversation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/status", response_model=SystemStatus)
async def get_status():
    global ai_agent
    
    if ai_agent:
        total_tools = len(ai_agent.mcp_tool_manager.registered_tools)
        enabled_tools = len([k for k, v in ai_agent.mcp_tool_manager.registered_tools.items() 
                           if ai_agent.mcp_tool_manager.is_tool_enabled(k)])
    else:
        total_tools = 0
        enabled_tools = 0
    
    return SystemStatus(
        status="running",
        mcp_tools_count=total_tools,
        enabled_tools_count=enabled_tools,
        timestamp=datetime.now().isoformat()
    )

@app.get("/api/mcp/productmaster/status")
async def get_productmaster_status():
    """ProductMaster MCP専用の状態取得"""
    global ai_agent
    
    if ai_agent:
        productmaster_enabled = ai_agent.mcp_tool_manager.is_tool_enabled("get_product_details")
    else:
        productmaster_enabled = False
        
    return {
        "status": "success",
        "productmaster_enabled": productmaster_enabled,
        "timestamp": datetime.now().isoformat()
    }

@app.post("/api/mcp/productmaster/toggle")
async def toggle_productmaster_mcp():
    global ai_agent
    
    if not ai_agent:
        raise HTTPException(status_code=503, detail="AI Agent not initialized")
    
    try:
        # get_product_details ツールの状態を切り替え
        current_status = ai_agent.mcp_tool_manager.is_tool_enabled("get_product_details")
        await ai_agent.mcp_tool_manager.toggle_tool_enabled("get_product_details")
        new_status = not current_status
        
        return {
            "status": "success",
            "mcp_enabled": new_status,
            "productmaster_enabled": new_status,
            "message": f"ProductMaster MCP {'有効' if new_status else '無効'}に変更しました"
        }
    except Exception as e:
        logger.error(f"ProductMaster MCP toggle error: {e}")
        raise HTTPException(status_code=500, detail=str(e))



# 既存のエンドポイント保持（互換性のため）
@app.post("/chat")
async def legacy_chat(request: ChatRequest):
    """Legacy endpoint for backward compatibility"""
    return await chat(request)

@app.get("/api/tools")
async def get_all_tools():
    """全ツール情報取得（個別制御用）"""
    global ai_agent
    
    if not ai_agent:
        return {"available_tools": {}, "enabled_tools": []}
    
    return {
        "available_tools": ai_agent.available_tools,
        "enabled_tools": list(ai_agent.enabled_tools)
    }

@app.post("/api/tools/{tool_name}/toggle")
async def toggle_tool(tool_name: str):
    """個別ツールのON/OFF切り替え"""
    global ai_agent
    
    if not ai_agent or not hasattr(ai_agent, 'mcp_tool_manager'):
        return {"status": "error", "message": "MCP Tool Manager not initialized"}
    
    # MCPTool クラス経由で Enable/Disable 切り替え
    enabled = ai_agent.mcp_tool_manager.toggle_tool_enabled(tool_name)
    tool = ai_agent.mcp_tool_manager.registered_tools[tool_name]
    
    logger.info(f"Tool {tool_name} {'enabled' if enabled else 'disabled'}")
    
    return {
        "status": "success", 
        "tool_name": tool_name,
        "enabled": enabled,
        "tool_info": {
            "name": tool.tool_name,
            "description": tool.description,
            "mcp_server_name": tool.mcp_server_name,
            "available": tool.available
        },
        "message": f"Tool '{tool_name}' {'enabled' if enabled else 'disabled'}"
    }

@app.get("/api/mcp/tools")
async def get_mcp_tools():
    """MCPTool クラス直接参照による統一ツール一覧取得"""
    global ai_agent
    
    if not ai_agent or not hasattr(ai_agent, 'mcp_tool_manager'):
        return {
            "status": "error",
            "tools": {"productmaster": {"available": False, "enabled": False, "tools": []}, 
                     "crm": {"available": False, "enabled": False, "tools": []}},
            "timestamp": datetime.now().isoformat()
        }
    
    # MCPTool クラスから直接全ツール取得
    all_tools = ai_agent.mcp_tool_manager.registered_tools
    
    # MCP Server別に分類
    tools_info = {"productmaster": {"available": False, "enabled": False, "tools": []}, 
                  "crm": {"available": False, "enabled": False, "tools": []}}
    
    for tool_key, tool in all_tools.items():
        # MCP Server判定
        if tool.mcp_server_name == "ProductMaster MCP":
            mcp_type = "productmaster"
        elif tool.mcp_server_name == "CRM MCP":
            mcp_type = "crm"
        else:
            continue
        
        # MCPTool クラス情報を直接使用
        converted_tool = {
            "name": tool.tool_key,
            "description": tool.tool_name,
            "usage_context": tool.description,
            "mcp_server_name": tool.mcp_server_name,
            "enabled": ai_agent.mcp_tool_manager.is_tool_enabled(tool_key),
            "available": tool.available
        }
        
        # 分類して追加
        if tools_info[mcp_type]["tools"] == []:
            tools_info[mcp_type] = {"available": tool.available, "enabled": False, "tools": []}
        tools_info[mcp_type]["tools"].append(converted_tool)
    
    return {
        "status": "success",
        "tools": tools_info,
        "timestamp": datetime.now().isoformat()
    }
    
    return {
        "status": "success",
        "tools": tools_info,
        "timestamp": datetime.now().isoformat()
    }

# システムプロンプトAPI
@app.get("/api/system-prompts")
async def api_list_system_prompts():
    """システムプロンプト一覧取得"""
    return await list_system_prompts()

@app.get("/api/system-prompts/{prompt_key}")
async def api_get_system_prompt(prompt_key: str):
    """システムプロンプト取得"""
    return await get_system_prompt_by_key(prompt_key)

# 静的ファイル配信設定（最後に配置）
app.mount("/", StaticFiles(directory="../web", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)

