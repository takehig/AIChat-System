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
        console.error("ProductMaster MCP initialization error:", error);
        const btn = document.getElementById("productMasterMcpBtn");
        const statusBadge = document.getElementById("productMasterStatus");
        if (btn && statusBadge) {
            btn.innerHTML = "<i class="fas fa-exclamation-triangle me-1"></i> エラー";
            btn.className = "btn btn-warning btn-sm w-100";
            statusBadge.textContent = "エラー";
            statusBadge.className = "badge bg-warning ms-auto";
        }
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
        console.error("ProductMaster MCP initialization error:", error);
        const btn = document.getElementById("productMasterMcpBtn");
        const statusBadge = document.getElementById("productMasterStatus");
        if (btn && statusBadge) {
            btn.innerHTML = "<i class="fas fa-exclamation-triangle me-1"></i> エラー";
            btn.className = "btn btn-warning btn-sm w-100";
            statusBadge.textContent = "エラー";
            statusBadge.className = "badge bg-warning ms-auto";
        }
    }
    }
}
// ProductMaster MCP関連関数更新
function updateProductMasterMCPButton(status) {
    const btn = document.getElementById('productMasterMcpBtn');
    const statusBadge = document.getElementById('productMasterStatus');
    const card = document.getElementById('productMasterCard');
    if (!btn || !statusBadge || !card) return;
    
    const mcpEnabled = status.mcp_enabled || status.productmaster_enabled || false;
    
    if (mcpEnabled) {
        btn.innerHTML = '<i class="fas fa-toggle-on me-1"></i> 無効化';
        btn.className = 'btn btn-primary btn-sm w-100';
        statusBadge.textContent = 'ON';
        statusBadge.className = 'badge bg-success ms-auto';
        card.style.borderLeft = '4px solid #0d6efd';
    } else {
        btn.innerHTML = '<i class="fas fa-toggle-off me-1"></i> 有効化';
        btn.className = 'btn btn-outline-primary btn-sm w-100';
        statusBadge.textContent = 'OFF';
        statusBadge.className = 'badge bg-secondary ms-auto';
        card.style.borderLeft = 'none';
    }
}

// CRM MCP関連関数更新
function updateCrmMCPButton(status) {
    const btn = document.getElementById('crmMcpBtn');
    const statusBadge = document.getElementById('crmStatus');
    const card = document.getElementById('crmCard');
    if (!btn || !statusBadge || !card) return;
    
    const mcpEnabled = status.crm_enabled || false;
    
    if (mcpEnabled) {
        btn.innerHTML = '<i class="fas fa-toggle-on me-1"></i> 無効化';
        btn.className = 'btn btn-info btn-sm w-100';
        statusBadge.textContent = 'ON';
        statusBadge.className = 'badge bg-success ms-auto';
        card.style.borderLeft = '4px solid #0dcaf0';
    } else {
        btn.innerHTML = '<i class="fas fa-toggle-off me-1"></i> 有効化';
        btn.className = 'btn btn-outline-info btn-sm w-100';
        statusBadge.textContent = 'OFF';
        statusBadge.className = 'badge bg-secondary ms-auto';
        card.style.borderLeft = 'none';
    }
}
