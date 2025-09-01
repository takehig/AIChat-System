// CRM MCP関連関数
async function toggleCrmMCP() {
    console.log("CRM MCP toggle clicked");
    try {
        console.log("[CRM DEBUG] API呼び出し開始: /aichat/api/mcp/crm/toggle");
        const response = await fetch("/aichat/api/mcp/crm/toggle", {
            method: "POST",
            headers: { "Content-Type": "application/json" }
        });
        const result = await response.json();
        updateCrmMCPButton(result);
        alert(result.message || "CRM MCP状態を変更しました");
    } catch (error) {
        console.error("CRM MCP toggle error:", error);
        alert("CRM MCP状態の変更に失敗しました");
    }
}

function updateCrmMCPButton(status) {
    const btn = document.getElementById("crmMcpBtn");
    const statusBadge = document.getElementById("crmStatus");
    const card = document.getElementById("crmCard");
    if (!btn || !statusBadge || !card) return;
    
    const mcpEnabled = status.crm_enabled || false;
    
    if (mcpEnabled) {
        btn.innerHTML = '<i class="fas fa-toggle-on me-1"></i> 無効化';
        btn.className = 'btn btn-primary btn-sm w-100';
        statusBadge.textContent = 'ON';
        statusBadge.className = 'badge bg-success ms-auto';
        card.style.borderLeft = '4px solid #0d6efd';
    } else {
        btn.innerHTML = '<i class="fas fa-toggle-off me-1"></i> 有効化';
        btn.className = 'btn btn-outline-info btn-sm w-100';
        statusBadge.textContent = 'OFF';
        statusBadge.className = 'badge bg-secondary ms-auto';
        card.style.borderLeft = 'none';
    }
}

async function initializeCrmMCP() {
    try {
        console.log("[CRM DEBUG] 初期化: /aichat/api/status");
        const response = await fetch("/aichat/api/status");
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        const status = await response.json();
        updateCrmMCPButton(status);
    } catch (error) {
        console.error("CRM MCP initialization error:", error);
        const btn = document.getElementById("crmMcpBtn");
        const statusBadge = document.getElementById("crmStatus");
        const card = document.getElementById("crmCard");
        if (btn && statusBadge && card) {
            btn.innerHTML = '<i class="fas fa-exclamation-triangle me-1"></i> エラー';
            btn.className = 'btn btn-warning btn-sm w-100';
            statusBadge.textContent = 'エラー';
            statusBadge.className = 'badge bg-warning ms-auto';
            card.style.borderLeft = '4px solid #ffc107';
        }
    }
}
