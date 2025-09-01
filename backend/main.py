from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import boto3
import json
import os
import logging
from datetime import datetime
from typing import List, Optional
from ai_agent import AIAgent

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="AIChat System with MCP Integration", version="2.1.0")

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
    conversation_id: Optional[str] = "default"

class ChatResponse(BaseModel):
    message: str
    timestamp: str
    tools_used: List[str] = []
    mcp_enabled: bool = False
    error: Optional[str] = None

class SystemStatus(BaseModel):
    status: str
    mcp_available: bool
    productmaster_enabled: Optional[bool] = False
    crm_enabled: Optional[bool] = False
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
        logger.info(f"Processing message: {request.message[:50]}...")
        
        # AI Agentでメッセージ処理
        result = await ai_agent.process_message(request.message)
        
        return ChatResponse(
            message=result["message"],
            timestamp=datetime.now().isoformat(),
            tools_used=result.get("tools_used", []),
            mcp_enabled=result.get("mcp_enabled", False),
            error=result.get("error")
        )
        
    except Exception as e:
        logger.error(f"Chat processing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/status", response_model=SystemStatus)
async def get_status():
    global ai_agent
    
    mcp_available = ai_agent.mcp_available if ai_agent else False
    
    return SystemStatus(
        status="running",
        mcp_available=mcp_available,
        productmaster_enabled=mcp_available,
        crm_enabled=False,  # ProductMaster MCPの状態
        timestamp=datetime.now().isoformat()
    )

@app.get("/api/mcp/productmaster/status")
async def get_productmaster_status():
    """ProductMaster MCP専用の状態取得"""
    global ai_agent
    productmaster_enabled = ai_agent.mcp_available if ai_agent else False
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
        # ProductMaster MCP状態を切り替え
        new_status = not ai_agent.mcp_available
        ai_agent.mcp_available = new_status
        
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

@app.get("/api/mcp/crm/status")
async def get_crm_status():
    """CRM MCP専用の状態取得"""
    global ai_agent
    crm_enabled = getattr(ai_agent, "crm_enabled", False)
    return {
        "status": "success",
        "crm_enabled": crm_enabled,
        "timestamp": datetime.now().isoformat()
    }

@app.post("/api/mcp/crm/toggle")
async def toggle_crm_mcp():
    global ai_agent
    try:
        current_status = getattr(ai_agent, "crm_enabled", False)
        new_status = not current_status
        ai_agent.crm_enabled = new_status
        return {"status": "success", "crm_enabled": new_status}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/mcp/tools")
async def get_mcp_tools():
    """利用可能なMCPツール一覧取得"""
    global ai_agent
    
    tools_info = {
        "productmaster": {
            "available": ai_agent.mcp_available if ai_agent else False,
            "enabled": ai_agent.mcp_available if ai_agent else False,
            "tools": [
                {"name": "search_products_flexible", "description": "柔軟な商品検索"},
                {"name": "get_product_details", "description": "商品詳細取得"},
                {"name": "get_all_products", "description": "全商品取得"},
                {"name": "get_statistics", "description": "統計情報取得"}
            ]
        },
        "crm": {
            "available": False,  # CRM MCPは未実装
            "enabled": getattr(ai_agent, "crm_enabled", False),
            "tools": [
                {"name": "search_customers", "description": "顧客情報を検索します"},
                {"name": "get_customer_holdings", "description": "顧客の保有商品情報を取得します"},
                {"name": "search_customers_by_bond_maturity", "description": "債券の満期日条件で顧客を検索します"}
            ]
        }
    }
    
    return {
        "status": "success",
        "tools": tools_info,
        "timestamp": datetime.now().isoformat()
    }

# 静的ファイル配信設定（最後に配置）
app.mount("/", StaticFiles(directory="../web", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)

