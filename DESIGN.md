# AIChat-System 設計書

## 📋 プロジェクト概要
**AI対話・MCP統合システム - 拡張可能アーキテクチャ**

### 🎯 システム目的
- Amazon Bedrock Claude 3 Sonnet との AI 対話
- Model Context Protocol (MCP) サーバー統合
- 拡張可能な MCP アーキテクチャ
- 金融商品検索・情報提供

## 🏗️ システム構成

### 📊 基本情報
- **リポジトリ**: https://github.com/takehig/AIChat-System
- **サービスポート**: 8002
- **アクセスURL**: http://44.217.45.24/aichat/
- **技術スタック**: Python FastAPI, MCP Protocol, HTML5, JavaScript ES6+

### 🔧 ファイル構造
```
AIChat-System/
├── backend/
│   ├── main.py              # FastAPI メインアプリケーション
│   ├── mcp_manager.py       # MCP サーバー管理
│   ├── ai_agent.py          # AI エージェント
│   └── requirements.txt     # Python 依存関係
├── web/
│   └── index.html          # フロントエンド（MCP統合版）
└── DESIGN.md              # 本設計書
```

## 🔑 主要機能

### ✅ 実装済み機能
1. **AI チャット機能**
   - Amazon Bedrock Claude 3 Sonnet 統合
   - リアルタイム AI 対話
   - チャット履歴管理

2. **MCP 統合機能**
   - ProductMaster MCP サーバー連携
   - 動的 MCP サーバー管理
   - MCP 有効/無効切り替え

3. **拡張可能アーキテクチャ**
   - 新規 MCP サーバー追加対応
   - プラグイン式 MCP 管理
   - 設定ベース MCP 制御

### 🔧 MCP サーバー構成
```python
MCP_SERVERS = {
    'productmaster': {
        'name': 'ProductMaster',
        'description': '金融商品検索・情報提供',
        'url': 'http://localhost:8003',
        'enabled': True
    },
    # 将来の拡張用
    'marketdata': {
        'name': 'MarketData',
        'description': '市場データ・価格情報',
        'url': 'http://localhost:8005',
        'enabled': False
    }
}
```

### 🔧 API エンドポイント
```
GET  /                    # メイン画面
GET  /api/status         # システム状態
POST /api/chat           # AI チャット実行
GET  /api/mcp/status     # MCP サーバー状態
POST /api/mcp/toggle     # MCP 有効/無効切り替え
GET  /api/mcp/test       # MCP 接続テスト
```

## 🤖 AI エージェント設計

### 🧠 AI エージェント機能
```python
class AIAgent:
    def __init__(self):
        self.bedrock_client = BedrockClient()
        self.mcp_manager = MCPManager()
    
    async def process_message(self, message: str):
        # 1. MCP サーバーから情報取得
        # 2. AI プロンプト生成
        # 3. Bedrock API 呼び出し
        # 4. レスポンス生成
```

### 🔗 MCP 統合フロー
```
1. ユーザー質問 → AI エージェント
2. MCP サーバー呼び出し → 商品情報取得
3. 取得情報 + 質問 → Bedrock Claude
4. AI 回答生成 → ユーザーに返却
```

## 🌐 MCP アーキテクチャ

### 📡 MCP プロトコル対応
- **標準準拠**: Model Context Protocol 仕様準拠
- **HTTP ベース**: RESTful API 経由での MCP 通信
- **非同期処理**: async/await パターン使用

### 🔧 MCP マネージャー
```python
class MCPManager:
    def __init__(self):
        self.servers = MCP_SERVERS
    
    async def call_mcp_server(self, server_name: str, query: str):
        # MCP サーバー呼び出し処理
    
    def toggle_server(self, server_name: str):
        # MCP サーバー有効/無効切り替え
```

## 🎨 フロントエンド設計

### 💬 チャット UI
- **リアルタイム表示**: メッセージの即座表示
- **MCP 状態表示**: 接続中 MCP サーバー表示
- **デバッグ機能**: MCP 呼び出し状況表示

### 🔧 JavaScript 機能
```javascript
// MCP 状態管理
async function updateMCPStatus() {
    // MCP サーバー状態を取得・表示
}

// AI チャット処理
async function sendMessage(message) {
    // AI チャット実行・レスポンス表示
}
```

## 🚀 デプロイ・運用

### 📦 systemd サービス
```ini
[Unit]
Description=AIChat Service
After=network.target

[Service]
Type=simple
User=ec2-user
WorkingDirectory=/home/ec2-user/AIChat/backend
ExecStart=/usr/bin/python3 -m uvicorn main:app --host 0.0.0.0 --port 8002
Restart=always

[Install]
WantedBy=multi-user.target
```

### 🔄 運用コマンド
```bash
# サービス管理
sudo systemctl start aichat
sudo systemctl stop aichat
sudo systemctl restart aichat
sudo systemctl status aichat

# ログ確認
sudo journalctl -u aichat -f
```

## 📈 パフォーマンス・監視

### 📊 監視項目
- **AI レスポンス時間**: Bedrock API 応答速度
- **MCP 接続状態**: 各 MCP サーバー接続状況
- **チャット利用量**: AI 対話使用状況
- **エラー率**: システムエラー発生頻度

## 🔮 今後の拡張予定

### 📋 計画中 MCP サーバー
1. **MarketData MCP**: 市場データ・価格情報提供
2. **News MCP**: 金融ニュース・情報提供
3. **Analytics MCP**: データ分析・レポート生成
4. **Notification MCP**: 通知・アラート機能

### 🛠️ 拡張機能
1. **マルチ MCP 対応**: 複数 MCP サーバー同時利用
2. **MCP キャッシュ**: 頻繁なクエリのキャッシュ機能
3. **AI 学習**: ユーザー対話からの学習機能
4. **音声対話**: 音声入力・出力対応

## 📝 更新履歴
- **2025-09-13**: 設計書更新・MCP統合アーキテクチャ反映
- **2025-08-30**: MCP 統合完了・拡張アーキテクチャ実装
- **2025-08-28**: AI チャット基本機能実装
- **2025-08-26**: プロジェクト開始
