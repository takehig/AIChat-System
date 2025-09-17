# AIChat Backend Configuration

# Bedrock設定
BEDROCK_CONFIG = {
    "region_name": "us-east-1",
    "model_id": "anthropic.claude-3-sonnet-20240229-v1:0"
}

# サーバー設定
SERVER_CONFIG = {
    "title": "AIChat Backend",
    "version": "2.0.0",
    "port": 8002
}

# タイムアウト設定
TIMEOUT_CONFIG = {
    "mcp_request_timeout": 60.0,      # MCP リクエストタイムアウト（秒）
    "llm_request_timeout": 120.0,     # LLM処理タイムアウト（秒）
    "bedrock_request_timeout": 90.0   # Bedrock APIタイムアウト（秒）
}
