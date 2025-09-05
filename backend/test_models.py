# models.py の動作確認テスト
from models import DetailedStep, DetailedStrategy, ChatRequest, ChatResponse

def test_models():
    """基本的なデータモデルの動作確認"""
    
    # DetailedStep テスト
    step = DetailedStep(step=1, tool="test_tool", reason="テスト用")
    print(f"✅ DetailedStep: {step.tool}")
    
    # DetailedStrategy テスト
    strategy = DetailedStrategy(steps=[step])
    print(f"✅ DetailedStrategy: {len(strategy.steps)} steps")
    
    # JSON解析テスト
    json_str = '{"steps": [{"step": 1, "tool": "product_search", "reason": "商品検索"}]}'
    parsed_strategy = DetailedStrategy.from_json_string(json_str)
    print(f"✅ JSON Parse: {parsed_strategy.steps[0].tool}")
    
    # FastAPI モデルテスト
    request = ChatRequest(message="テストメッセージ")
    print(f"✅ ChatRequest: {request.message}")
    
    response = ChatResponse(
        message="テスト応答", 
        timestamp="2025-09-05T20:00:00Z",
        mcp_enabled=True
    )
    print(f"✅ ChatResponse: {response.mcp_enabled}")
    
    print("🎯 models.py 動作確認完了")

if __name__ == "__main__":
    test_models()
