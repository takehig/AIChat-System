# AIChat System 設計書

## 📋 システム概要

### システム名
**AIChat System** - AI対話・MCP統合システム

### 目的
- Amazon Bedrock Claude 3 Sonnet との AI対話
- Model Context Protocol (MCP) による拡張可能なアーキテクチャ
- 外部システム（ProductMaster等）との連携
- 金融業務に特化したAI支援機能

## 🏗️ アーキテクチャ

### 技術スタック
- **Backend**: Python 3.9+, FastAPI, asyncio
- **Frontend**: HTML5, JavaScript ES6+, Bootstrap 5
- **AI**: Amazon Bedrock Claude 3 Sonnet
- **Protocol**: Model Context Protocol (MCP)
- **Integration**: HTTP API, WebSocket（将来）
- **Deployment**: systemd, Nginx reverse proxy

### システム構成
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Web Browser   │    │   Nginx Proxy   │    │  FastAPI App    │
│                 │◄──►│  (/aichat/)     │◄──►│   (Port 8002)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                        │
                                                        ▼
┌─────────────────────────────────────────────────────────────────┐
│                    AIChat System Core                           │
│                                                                 │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────┐ │
│  │   Chat Engine   │    │   MCP Manager   │    │AI Assistant │ │
│  │                 │◄──►│                 │◄──►│             │ │
│  │• Message Queue  │    │• Server Registry│    │• Bedrock    │ │
│  │• Session Mgmt   │    │• Protocol Impl  │    │• Context    │ │
│  │• History Store  │    │• Health Check   │    │• Reasoning  │ │
│  └─────────────────┘    └─────────────────┘    └─────────────┘ │
│                                   │                             │
└───────────────────────────────────┼─────────────────────────────┘
                                    │ MCP Protocol
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                      MCP Servers                                │
│                                                                 │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────┐ │
│  │ProductMaster MCP│    │  [Future MCP]   │    │[Future MCP] │ │
│  │   (Port 8003)   │    │   (Port 8004)   │    │(Port 8005)  │ │
│  │                 │    │                 │    │             │ │
│  │• Product Search │    │• Market Data    │    │• Risk Calc  │ │
│  │• Product Info   │    │• Price Feed     │    │• Portfolio  │ │
│  └─────────────────┘    └─────────────────┘    └─────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## 🔧 MCP アーキテクチャ

### MCP Manager 設計
```python
class MCPManager:
    def __init__(self):
        self.servers = {
            'productmaster': {
                'name': 'ProductMaster',
                'description': '商品情報検索・管理',
                'url': 'http://localhost:8003',
                'enabled': True,
                'health_endpoint': '/health',
                'capabilities': ['search', 'info', 'list']
            },
            # 将来の拡張用
            'marketdata': {
                'name': 'MarketData',
                'description': '市場データ・価格情報',
                'url': 'http://localhost:8004',
                'enabled': False
            }
        }
```

### MCP プロトコル実装
```python
async def call_mcp_server(server_name: str, method: str, params: dict):
    """MCP サーバーへのAPI呼び出し"""
    server = self.servers.get(server_name)
    if not server or not server['enabled']:
        raise MCPServerNotAvailable(f"Server {server_name} not available")
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{server['url']}/mcp/{method}",
            json=params,
            timeout=30.0
        )
        return response.json()
```

## 🎯 機能仕様

### 1. AI チャット機能
- **自然言語対話**: Claude 3 Sonnet による高度な対話
- **コンテキスト保持**: セッション内での文脈維持
- **金融専門知識**: 投資・リスク・商品に関する専門的回答
- **多言語対応**: 日本語・英語対応

### 2. MCP 統合機能
- **動的サーバー管理**: MCP サーバーの動的追加・削除
- **ヘルスチェック**: サーバー状態の定期監視
- **負荷分散**: 複数サーバー間での負荷分散（将来）
- **エラーハンドリング**: サーバー障害時の適切な処理

### 3. 商品検索連携
```javascript
// フロントエンドでのMCP呼び出し例
async function searchProducts(query) {
    const response = await fetch('/aichat/api/mcp/call', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            server: 'productmaster',
            method: 'search',
            params: {query: query}
        })
    });
    return response.json();
}
```

## 🎨 UI/UX設計

### チャット画面構成
```
┌─────────────────────────────────────────┐
│  AIChat System                          │
├─────────────────────────────────────────┤
│  ┌─────────────────────────────────┐   │
│  │        Chat History             │   │
│  │                                 │   │
│  │  👤 ユーザー: トヨタの社債を教えて    │
│  │                                 │   │
│  │  🤖 AI: トヨタ自動車第51回社債は... │
│  │     [商品詳細] [比較] [お気に入り]   │
│  │                                 │   │
│  └─────────────────────────────────┘   │
│  ┌─────────────────────────────────┐   │
│  │  💬 メッセージを入力...    [送信]  │   │
│  └─────────────────────────────────┘   │
│                                         │
│  MCP Status: 🟢 ProductMaster Online    │
└─────────────────────────────────────────┘
```

### レスポンシブ対応
- **デスクトップ**: サイドバー付きレイアウト
- **タブレット**: 折りたたみ可能サイドバー
- **モバイル**: フルスクリーンチャット

## 🔧 API仕様

### エンドポイント一覧
```
# チャット機能
POST /api/chat              # メッセージ送信
GET  /api/chat/history      # チャット履歴取得
DELETE /api/chat/history    # 履歴クリア

# MCP管理
GET  /api/mcp/servers       # MCP サーバー一覧
POST /api/mcp/call          # MCP サーバー呼び出し
GET  /api/mcp/health        # MCP ヘルスチェック
POST /api/mcp/toggle        # MCP サーバー有効/無効切り替え

# システム
GET  /api/status            # システム状態
GET  /api/version           # バージョン情報
```

### MCP API 仕様
```json
{
  "request": {
    "server": "productmaster",
    "method": "search",
    "params": {
      "query": "トヨタ",
      "limit": 10,
      "type": "bond"
    }
  },
  "response": {
    "status": "success",
    "data": {
      "products": [...],
      "total": 3,
      "execution_time": "0.15s"
    },
    "server_info": {
      "name": "ProductMaster",
      "version": "1.0.0",
      "timestamp": "2025-09-05T10:00:00Z"
    }
  }
}
```

## 🚀 デプロイメント

### systemd設定
```ini
[Unit]
Description=AIChat System
After=network.target

[Service]
Type=simple
User=ec2-user
WorkingDirectory=/home/ec2-user/AIChat/backend
ExecStart=/usr/bin/python3 -m uvicorn main:app --host 0.0.0.0 --port 8002
Restart=always
RestartSec=3
Environment=PYTHONPATH=/home/ec2-user/AIChat/backend

[Install]
WantedBy=multi-user.target
```

### 環境設定
```python
# config.py
import os

# Bedrock設定
AWS_REGION = "us-east-1"
BEDROCK_MODEL_ID = "anthropic.claude-3-sonnet-20240229-v1:0"
BEDROCK_MAX_TOKENS = 4000

# MCP設定
MCP_SERVERS = {
    "productmaster": {
        "url": "http://localhost:8003",
        "timeout": 30,
        "retry_count": 3
    }
}

# セッション設定
SESSION_TIMEOUT = 3600  # 1時間
MAX_HISTORY_LENGTH = 100
```

## 📊 パフォーマンス

### 目標値
- **チャットレスポンス**: < 3秒
- **MCP呼び出し**: < 1秒
- **同時セッション**: 50セッション

### 最適化施策
```python
# 非同期処理
async def process_chat_message(message: str, session_id: str):
    # 並列処理でMCP呼び出しとBedrock呼び出し
    mcp_task = asyncio.create_task(call_mcp_if_needed(message))
    bedrock_task = asyncio.create_task(call_bedrock(message))
    
    mcp_result = await mcp_task
    bedrock_response = await bedrock_task
    
    return combine_responses(bedrock_response, mcp_result)
```

## 🔒 セキュリティ

### セッション管理
```python
class SessionManager:
    def __init__(self):
        self.sessions = {}
        self.session_timeout = 3600
    
    def create_session(self) -> str:
        session_id = secrets.token_urlsafe(32)
        self.sessions[session_id] = {
            'created_at': datetime.now(),
            'last_activity': datetime.now(),
            'messages': []
        }
        return session_id
```

### 入力検証
```python
def validate_chat_message(message: str) -> bool:
    # 長さ制限
    if len(message) > 1000:
        raise ValueError("メッセージが長すぎます")
    
    # 不正文字チェック
    if any(char in message for char in ['<', '>', '&']):
        raise ValueError("不正な文字が含まれています")
    
    return True
```

## 🧪 テスト戦略

### テストケース
```python
# チャット機能テスト
async def test_chat_message():
    response = await client.post("/api/chat", json={
        "message": "トヨタの社債について教えて",
        "session_id": "test_session"
    })
    assert response.status_code == 200
    assert "トヨタ" in response.json()["response"]

# MCP統合テスト
async def test_mcp_integration():
    response = await client.post("/api/mcp/call", json={
        "server": "productmaster",
        "method": "search",
        "params": {"query": "トヨタ"}
    })
    assert response.status_code == 200
    assert response.json()["status"] == "success"
```

## 📈 監視・運用

### ログ設定
```python
# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/aichat.log'),
        logging.StreamHandler()
    ]
)

# MCP呼び出しログ
logger.info(f"MCP Call: {server_name}.{method} - {params}")
```

### メトリクス
- **チャット応答時間**
- **MCP サーバー応答時間**
- **Bedrock API 使用量**
- **エラー発生率**

## 🔄 今後の拡張計画

### 短期（1-3ヶ月）
- **MarketData MCP**: 市場データ・価格情報連携
- **RiskCalculator MCP**: リスク計算・ポートフォリオ分析
- **音声入力**: Speech-to-Text 対応

### 中期（3-6ヶ月）
- **WebSocket**: リアルタイム通信
- **マルチモーダル**: 画像・ドキュメント解析
- **ワークフロー**: 複雑な業務プロセス自動化

### 長期（6ヶ月以降）
- **カスタムモデル**: 金融特化ファインチューニング
- **エージェント機能**: 自律的なタスク実行
- **API Gateway**: 外部システム統合

---

**Document Version**: v1.0.0  
**Repository**: https://github.com/takehig/AIChat-System  
**Last Updated**: 2025-09-05
