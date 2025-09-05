from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import boto3
import json
import os
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from ai_agent_new import AIAgent
from models import ChatRequest, ChatResponse, SystemStatus, MCPToggleRequest, MCPToggleResponse

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="AIChat System with MCP Integration", version="2.2.0")

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

@app.on_event("startup")
async def startup_event():
    """アプリケーション起動時の初期化"""
    global ai_agent
    try:
        ai_agent = AIAgent()
        await ai_agent.initialize()
        logger.info("AIAgent initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize AIAgent: {e}")
        ai_agent = None

# ルート削除 - StaticFilesに任せる

@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """チャット処理"""
    if ai_agent is None:
        raise HTTPException(status_code=503, detail="AI Agent not initialized")
    
    try:
        # セッションID取得（簡易実装）
        session_id = request.conversation_id or "default"
        
        # AI Agent でメッセージ処理
        result = await ai_agent.process_message(request.message, session_id)
        
        return ChatResponse(
            message=result["message"],
            timestamp=datetime.now().isoformat(),
            strategy=result.get("strategy"),
            mcp_enabled=result.get("mcp_enabled", False),
            error=result.get("error")
        )
        
    except Exception as e:
        logger.error(f"Chat processing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/chat/history")
async def clear_chat_history():
    """会話履歴をクリア"""
    if ai_agent is None:
        raise HTTPException(status_code=503, detail="AI Agent not initialized")
    
    try:
        session_id = "default"  # 簡易実装
        ai_agent.conversation_manager.clear_session(session_id)
        return {"status": "success", "message": "会話履歴をクリアしました"}
    except Exception as e:
        logger.error(f"Clear history error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/status", response_model=SystemStatus)
async def get_system_status():
    """システム状態取得"""
    if ai_agent is None:
        return SystemStatus(
            status="error",
            mcp_available=False,
            productmaster_enabled=False,
            crm_enabled=False
        )
    
    enabled_tools = ai_agent.get_enabled_tools()
    
    return SystemStatus(
        status="healthy" if ai_agent.mcp_available else "limited",
        mcp_available=ai_agent.mcp_available,
        productmaster_enabled=any("product" in tool.lower() for tool in enabled_tools.keys()),
        crm_enabled=any("customer" in tool.lower() or "crm" in tool.lower() for tool in enabled_tools.keys())
    )

@app.post("/api/mcp/toggle", response_model=MCPToggleResponse)
async def toggle_mcp_tool(request: MCPToggleRequest):
    """MCPツールの有効/無効切り替え"""
    if ai_agent is None:
        raise HTTPException(status_code=503, detail="AI Agent not initialized")
    
    try:
        success = ai_agent.toggle_tool(request.tool_name)
        
        if request.tool_name not in ai_agent.available_tools:
            raise HTTPException(status_code=404, detail=f"Tool '{request.tool_name}' not found")
        
        return MCPToggleResponse(
            tool_name=request.tool_name,
            enabled=success,
            message=f"Tool '{request.tool_name}' {'enabled' if success else 'disabled'}"
        )
        
    except Exception as e:
        logger.error(f"MCP toggle error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/mcp/tools")
async def get_mcp_tools():
    """利用可能なMCPツール一覧"""
    if ai_agent is None:
        return {"available_tools": {}, "enabled_tools": []}
    
    return {
        "available_tools": ai_agent.available_tools,
        "enabled_tools": list(ai_agent.enabled_tools)
    }

# 静的ファイル配信（最後に配置）
app.mount("/", StaticFiles(directory="../web", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
