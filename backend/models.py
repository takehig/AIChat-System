# AIChat System - 統合データモデル
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from pydantic import BaseModel

# === 戦略・実行関連データクラス ===
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

@dataclass
class DetailedStep:
    step: int
    tool: str
    reason: str
    
    # 実行時に追加される情報（初期値None）
    input: Optional[str] = None
    output: Optional[Dict] = None
    execution_time_ms: Optional[float] = None
    debug_info: Optional[Dict] = None
    
    # LLM情報（統合）
    llm_prompt: Optional[str] = None
    llm_response: Optional[str] = None
    llm_execution_time_ms: Optional[float] = None

@dataclass
class DetailedStrategy:
    steps: List[DetailedStep]
    
    # 戦略立案LLM情報
    strategy_llm_prompt: Optional[str] = None
    strategy_llm_response: Optional[str] = None
    strategy_llm_execution_time_ms: Optional[float] = None
    
    # パース情報
    parse_error: bool = False
    parse_error_message: Optional[str] = None
    raw_response: Optional[str] = None
    
    @classmethod
    def from_json_string(cls, json_str: str):
        """JSON文字列からDetailedStrategyを生成"""
        import json
        try:
            data = json.loads(json_str)
            steps = [
                DetailedStep(
                    step=step_data["step"],
                    tool=step_data["tool"], 
                    reason=step_data["reason"]
                )
                for step_data in data.get("steps", [])
            ]
            return cls(steps=steps, raw_response=json_str)
        except Exception as e:
            error_step = DetailedStep(
                step=1,
                tool="error",
                reason=f"戦略立案時のJSON解析エラー: {str(e)}"
            )
            return cls(
                steps=[error_step], 
                parse_error=True, 
                parse_error_message=str(e), 
                raw_response=json_str
            )

# === FastAPI用データモデル ===
class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = "default"

class ChatResponse(BaseModel):
    message: str
    timestamp: str
    strategy: Optional[Any] = None  # DetailedStrategyオブジェクト（Any型で受け入れ）
    mcp_enabled: bool = False
    error: Optional[str] = None

class SystemStatus(BaseModel):
    status: str
    mcp_available: bool
    productmaster_enabled: Optional[bool] = False
    crm_enabled: Optional[bool] = False

class MCPToggleRequest(BaseModel):
    tool_name: str
    enabled: bool

class MCPToggleResponse(BaseModel):
    tool_name: str
    enabled: bool
    message: str
