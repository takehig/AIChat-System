        // CRM MCP関連関数
        async function toggleCrmMCP() {
            console.log("CRM MCP toggle clicked");
            try {
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
            if (!btn) return;
            
            const mcpEnabled = status.crm_enabled || false;
            
            if (mcpEnabled) {
                btn.textContent = "CRM: ON";
                btn.className = "btn btn-success btn-sm me-2";
            } else {
                btn.textContent = "CRM: OFF";
                btn.className = "btn btn-danger btn-sm me-2";
            }
        }

        async function initializeCrmMCP() {
            try {
                const response = await fetch("/aichat/api/status");
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}`);
                }
                const status = await response.json();
                updateCrmMCPButton(status);
            } catch (error) {
                console.error("CRM MCP initialization error:", error);
                const btn = document.getElementById("crmMcpBtn");
                if (btn) {
                    btn.textContent = "CRM: エラー";
                    btn.className = "btn btn-warning btn-sm me-2";
                }
            }
        }
