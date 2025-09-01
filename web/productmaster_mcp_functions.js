// ProductMaster MCP関連関数
async function toggleProductMasterMCP() {
    console.log('ProductMaster MCP toggle clicked');
    try {
        const response = await fetch('/aichat/api/mcp/productmaster/toggle', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        const result = await response.json();
        updateProductMasterMCPButton(result);
        alert(result.message || 'ProductMaster MCP状態を変更しました');
    } catch (error) {
        console.error('ProductMaster MCP toggle error:', error);
        alert('ProductMaster MCP状態の変更に失敗しました');
    }
}

function updateProductMasterMCPButton(status) {
    const btn = document.getElementById('productMasterMcpBtn');
    if (!btn) return;
    
    const mcpEnabled = status.mcp_enabled || status.productmaster_enabled || false;
    
    if (mcpEnabled) {
        btn.textContent = 'ProductMaster: ON';
        btn.className = 'btn btn-success btn-sm me-2';
    } else {
        btn.textContent = 'ProductMaster: OFF';
        btn.className = 'btn btn-danger btn-sm me-2';
    }
}

async function initializeProductMasterMCP() {
    try {
        const response = await fetch('/aichat/api/status');
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        const status = await response.json();
        updateProductMasterMCPButton(status);
    } catch (error) {
        console.error('ProductMaster MCP initialization error:', error);
        const btn = document.getElementById('productMasterMcpBtn');
        if (btn) {
            btn.textContent = 'ProductMaster: エラー';
            btn.className = 'btn btn-warning btn-sm me-2';
        }
    }
}
