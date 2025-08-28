from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
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

app = FastAPI(title="AIChat System with MCP Integration", version="2.0.0")

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

# Pydanticモデル
class ChatRequest(BaseModel):
    message: str
    user_id: Optional[str] = "default"

class ChatResponse(BaseModel):
    message: str
    timestamp: str
    tools_used: List[str] = []
    mcp_enabled: bool = False
    error: Optional[str] = None

class SystemStatus(BaseModel):
    status: str
    mcp_available: bool
    timestamp: str

# 起動時初期化
@app.on_event("startup")
async def startup_event():
    global ai_agent
    logger.info("🚀 Starting AIChat with MCP Integration")
    
    try:
        # AI Agent初期化
        ai_agent = AIAgent()
        await ai_agent.initialize()
        
        logger.info("✅ AIChat with MCP initialized successfully")
    except Exception as e:
        logger.error(f"❌ Startup initialization failed: {e}")
        # MCPが失敗してもサービスは継続
        ai_agent = AIAgent()

# メインエンドポイント
@app.get("/", response_class=HTMLResponse)
async def root():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>AIChat with MCP Integration</title>
        <meta charset="utf-8">
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }
            .container { max-width: 800px; margin: 0 auto; background-color: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            .header { text-align: center; margin-bottom: 20px; }
            .status { background-color: #e8f5e8; padding: 10px; border-radius: 5px; margin-bottom: 20px; font-size: 0.9em; }
            .chat-container { border: 1px solid #ddd; height: 400px; overflow-y: auto; padding: 15px; margin: 10px 0; background-color: #fafafa; border-radius: 5px; }
            .message { margin: 10px 0; padding: 12px; border-radius: 8px; max-width: 80%; }
            .user-message { background-color: #007bff; color: white; margin-left: auto; text-align: right; }
            .ai-message { background-color: #f8f9fa; border: 1px solid #dee2e6; }
            .tools-used { font-size: 0.8em; color: #28a745; margin-top: 8px; font-weight: bold; }
            .mcp-indicator { font-size: 0.8em; color: #6c757d; margin-top: 5px; }
            .input-container { display: flex; gap: 10px; margin-top: 20px; }
            .message-input { flex: 1; padding: 12px; border: 1px solid #ddd; border-radius: 5px; font-size: 16px; }
            .send-button { padding: 12px 24px; background-color: #007bff; color: white; border: none; border-radius: 5px; cursor: pointer; font-size: 16px; }
            .send-button:hover { background-color: #0056b3; }
            .loading { color: #6c757d; font-style: italic; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🤖 AIChat with MCP Integration</h1>
                <p>Claude 3.5 Sonnet + ProductMaster 商品検索</p>
            </div>
            <div class="status" id="status">システム初期化中...</div>
            <div class="chat-container" id="chatContainer">
                <div class="ai-message">
                    こんにちは！金融商品に関するご質問をお気軽にどうぞ。<br>
                    例: 「高利回りの米国債券を教えて」「AAPLの詳細を教えて」
                </div>
            </div>
            <div class="input-container">
                <input type="text" id="messageInput" class="message-input" placeholder="メッセージを入力してください..." onkeypress="handleKeyPress(event)">
                <button onclick="sendMessage()" class="send-button">送信</button>
            </div>
        </div>

        <script>
            let isLoading = false;

            async function checkStatus() {
                try {
                    const response = await fetch('/aichat/api/status');
                    const status = await response.json();
                    const mcpStatus = status.mcp_available ? '✅ MCP有効' : '⚠️ MCP無効';
                    document.getElementById('status').innerHTML = 
                        `✅ システム稼働中 | ${mcpStatus} | Claude 3.5 Sonnet 利用可能`;
                } catch (error) {
                    document.getElementById('status').innerHTML = '❌ システムエラー';
                }
            }

            async function sendMessage() {
                if (isLoading) return;
                
                const input = document.getElementById('messageInput');
                const message = input.value.trim();
                if (!message) return;

                isLoading = true;
                addMessage(message, 'user');
                input.value = '';
                
                // ローディング表示
                const loadingDiv = addMessage('処理中...', 'ai', [], true);

                try {
                    const response = await fetch('/aichat/api/chat', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ message: message })
                    });

                    const result = await response.json();
                    
                    // ローディング削除
                    loadingDiv.remove();
                    
                    // AIレスポンス表示
                    addMessage(result.message, 'ai', result.tools_used, false, result.mcp_enabled);

                } catch (error) {
                    loadingDiv.remove();
                    addMessage('エラーが発生しました: ' + error.message, 'ai');
                } finally {
                    isLoading = false;
                }
            }

            function addMessage(message, type, toolsUsed = [], isLoading = false, mcpEnabled = false) {
                const container = document.getElementById('chatContainer');
                const messageDiv = document.createElement('div');
                messageDiv.className = `message ${type}-message`;
                
                if (isLoading) {
                    messageDiv.className += ' loading';
                }
                
                let toolsInfo = '';
                if (toolsUsed && toolsUsed.length > 0) {
                    toolsInfo = `<div class="tools-used">🔧 使用ツール: ${toolsUsed.join(', ')}</div>`;
                }
                
                let mcpInfo = '';
                if (type === 'ai' && !isLoading) {
                    mcpInfo = `<div class="mcp-indicator">MCP: ${mcpEnabled ? '有効' : '無効'}</div>`;
                }
                
                messageDiv.innerHTML = `${message}${toolsInfo}${mcpInfo}`;
                container.appendChild(messageDiv);
                container.scrollTop = container.scrollHeight;
                
                return messageDiv;
            }

            function handleKeyPress(event) {
                if (event.key === 'Enter' && !isLoading) {
                    sendMessage();
                }
            }

            // 初期化
            checkStatus();
            setInterval(checkStatus, 30000);
        </script>
    </body>
    </html>
    """

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
    
    return SystemStatus(
        status="running",
        mcp_available=ai_agent.mcp_available if ai_agent else False,
        timestamp=datetime.now().isoformat()
    )

# 既存のエンドポイント保持（互換性のため）
@app.post("/chat")
async def legacy_chat(request: ChatRequest):
    """Legacy endpoint for backward compatibility"""
    return await chat(request)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
