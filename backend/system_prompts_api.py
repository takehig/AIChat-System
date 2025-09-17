# AIChat Backend - System Prompts API

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import HTTPException
import logging

logger = logging.getLogger(__name__)

def get_aichat_db_connection():
    """AIChat データベース接続を取得（.env から設定読み込み）"""
    try:
        # .env から設定読み込み
        db_config = {
            "host": os.getenv("DB_HOST", "localhost"),
            "port": int(os.getenv("DB_PORT", "5432")),
            "database": os.getenv("DB_NAME", "aichat"),
            "user": os.getenv("DB_USER", "aichat_user"),
            "password": os.getenv("DB_PASSWORD", "aichat123")
        }
        return psycopg2.connect(**db_config)
    except Exception as e:
        logger.error(f"AIChat database connection failed: {e}")
        raise

async def get_system_prompt_by_key(prompt_key: str) -> dict:
    """システムプロンプトをキーで取得"""
    try:
        conn = get_aichat_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute(
            "SELECT prompt_key, prompt_text, created_at, updated_at FROM system_prompts WHERE prompt_key = %s",
            (prompt_key,)
        )
        
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if result:
            return {
                "prompt_key": result['prompt_key'],
                "prompt_text": result['prompt_text'],
                "created_at": result['created_at'].isoformat() if result['created_at'] else None,
                "updated_at": result['updated_at'].isoformat() if result['updated_at'] else None,
                "status": "success"
            }
        else:
            raise HTTPException(
                status_code=404, 
                detail=f"System prompt not found: {prompt_key}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get system prompt {prompt_key}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Database error: {str(e)}"
        )

async def list_system_prompts() -> dict:
    """全システムプロンプト一覧取得"""
    try:
        conn = get_aichat_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute(
            "SELECT prompt_key, LENGTH(prompt_text) as text_length, created_at, updated_at FROM system_prompts ORDER BY prompt_key"
        )
        
        results = cursor.fetchall()
        cursor.close()
        conn.close()
        
        prompts = []
        for result in results:
            prompts.append({
                "prompt_key": result['prompt_key'],
                "text_length": result['text_length'],
                "created_at": result['created_at'].isoformat() if result['created_at'] else None,
                "updated_at": result['updated_at'].isoformat() if result['updated_at'] else None
            })
        
        return {
            "prompts": prompts,
            "count": len(prompts),
            "status": "success"
        }
        
    except Exception as e:
        logger.error(f"Failed to list system prompts: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Database error: {str(e)}"
        )
