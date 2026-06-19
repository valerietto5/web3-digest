def build_ui_html() -> str:
  return """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>Web3 Digest — Swap Terminal</title>
  <style>
    :root {
      --bg-primary: #07111f;
      --bg-surface: #0b1829;
      --bg-elevated: #10233a;
      --bg-card: #0d1d31;
      --bg-card-soft: #132944;
      --text-primary: #edf7ff;
      --text-secondary: #b8c7d9;
      --text-muted: #7f91aa;
      --border-default: rgba(161, 190, 220, 0.18);
      --border-strong: rgba(127, 255, 213, 0.36);
      --accent-emerald: #34f5a3;
      --accent-emerald-soft: rgba(52, 245, 163, 0.14);
      --accent-purple: #9b7cff;
      --accent-cyan: #63e6ff;
      --semantic-success: #22c55e;
      --semantic-warning: #f59e0b;
      --semantic-danger: #f04438;
      --radius-sm: 8px;
      --radius-md: 10px;
      --radius-lg: 14px;
      --radius-xl: 20px;
      --shadow-card: 0 18px 48px rgba(1, 9, 20, 0.32);
      --shadow-glow: 0 0 0 1px rgba(52, 245, 163, 0.14), 0 0 28px rgba(52, 245, 163, 0.08);
      --font-xs: 12px;
      --font-sm: 13px;
      --font-md: 15px;
      --font-lg: 18px;
    }
    * { box-sizing: border-box; }
    body {
      font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;
      margin: 0;
      padding: 18px;
      min-height: 100vh;
      background:
        radial-gradient(circle at 18% 0%, rgba(99, 230, 255, 0.12), transparent 34%),
        radial-gradient(circle at 92% 8%, rgba(155, 124, 255, 0.13), transparent 30%),
        linear-gradient(180deg, #07111f 0%, #081424 48%, #050b16 100%);
      color: var(--text-primary);
    }
    h2, h3, h4 { color: var(--text-primary); letter-spacing: 0; }
    a { color: var(--accent-cyan); }
    .app-shell {
      width: min(100%, 980px);
      margin: 0 auto;
      display: flex;
      flex-direction: column;
    }
    .app-header {
      order: 1;
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 16px;
      margin: 2px 0 10px;
    }
    .app-title {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 9px;
      margin: 0;
      font-size: 24px;
      line-height: 1.12;
    }
    .brand-mark {
      display: inline-flex;
      align-items: center;
      padding: 4px 10px;
      border: 1px solid rgba(52, 245, 163, 0.26);
      border-radius: 999px;
      background: rgba(52, 245, 163, 0.1);
      color: var(--accent-emerald);
      box-shadow: 0 0 0 1px rgba(52, 245, 163, 0.08), 0 0 22px rgba(52, 245, 163, 0.08);
    }
    .app-title-sub {
      color: var(--text-secondary);
      font-size: 20px;
      font-weight: 650;
    }
    .app-confidence {
      max-width: 600px;
      margin-top: 7px;
      color: var(--text-secondary);
      font-size: var(--font-sm);
      line-height: 1.4;
    }
    .shell-detail {
      order: 3;
      border: 1px solid var(--border-default);
      border-radius: var(--radius-lg);
      background: rgba(11, 24, 41, 0.62);
      box-shadow: none;
    }
    #advancedPortfolioTools { order: 4; }
    .row { display: flex; gap: 12px; flex-wrap: wrap; align-items: end; }
    .card {
      border: 1px solid var(--border-default);
      border-radius: var(--radius-lg);
      padding: 12px;
      margin-top: 12px;
      background: linear-gradient(180deg, rgba(16, 35, 58, 0.92), rgba(10, 24, 41, 0.92));
      box-shadow: var(--shadow-card);
    }
    #swapCard {
      order: 2;
      border-color: rgba(99, 230, 255, 0.18);
      padding: 14px;
      margin-top: 0;
      background:
        linear-gradient(180deg, rgba(14, 31, 52, 0.98), rgba(8, 20, 36, 0.98));
      box-shadow: var(--shadow-card), var(--shadow-glow);
    }
    .swap-card-header {
      display: none;
    }
    .swap-card-title {
      display: flex;
      align-items: center;
      gap: 8px;
      margin: 0 0 5px 0;
      font-size: 18px;
      line-height: 1.25;
    }
    .swap-card-subtitle {
      color: var(--text-muted);
      font-size: 12px;
      line-height: 1.35;
    }
    .swap-wallet-panel {
      min-width: min(240px, 100%);
      padding: 9px;
      border: 1px solid rgba(161, 190, 220, 0.14);
      border-radius: var(--radius-md);
      background: rgba(5, 14, 26, 0.28);
      text-align: right;
    }
    .swap-wallet-panel .row {
      gap: 8px;
      align-items: center;
      justify-content: flex-end;
      margin-top: 0;
    }
    .swap-wallet-panel button {
      min-height: 34px;
      padding: 7px 9px;
      font-size: 12px;
    }
    #swapWalletStrip {
      margin-top: 6px;
      color: var(--text-secondary);
      font-size: 12px;
      line-height: 1.35;
    }
    #swapWalletConnectHint {
      display: none;
    }
    #btnSwapRefreshBalances {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      margin-top: 8px;
      min-height: 32px;
      padding: 7px 10px;
      font-size: 12px;
      border-radius: 999px;
      color: var(--text-secondary);
      background: rgba(99, 230, 255, 0.06);
    }
    .muted { color: var(--text-muted); }
    label { display: block; font-size: var(--font-xs); color: var(--text-secondary); margin-bottom: 4px; }
    input, select {
      padding: 8px;
      border-radius: var(--radius-sm);
      border: 1px solid var(--border-default);
      min-width: 220px;
      background: rgba(5, 14, 26, 0.82);
      color: var(--text-primary);
      outline: none;
    }
    input:focus, select:focus {
      border-color: var(--border-strong);
      box-shadow: 0 0 0 3px rgba(52, 245, 163, 0.11);
    }
    input::placeholder { color: var(--text-muted); }
    .swap-setup-panel {
      margin-top: 12px;
      padding: 12px;
      border: 1px solid rgba(161, 190, 220, 0.1);
      border-radius: var(--radius-xl);
      background:
        linear-gradient(180deg, rgba(5, 14, 26, 0.42), rgba(3, 10, 20, 0.26));
    }
    .swap-input-grid { display: grid; grid-template-columns: minmax(0, 1fr); gap: 0; align-items: start; }
    .swap-input-grid input { width: 100%; min-width: 0; box-sizing: border-box; }
    .swap-token-card {
      position: relative;
      min-height: 164px;
      border: 1px solid rgba(161, 190, 220, 0.14);
      border-radius: 24px;
      padding: 18px;
      background:
        linear-gradient(180deg, rgba(17, 34, 54, 0.96), rgba(8, 18, 32, 0.94));
      box-shadow:
        inset 0 1px 0 rgba(237, 247, 255, 0.04),
        0 14px 32px rgba(1, 9, 20, 0.24);
    }
    .swap-token-card-header {
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      gap: 10px;
      margin-bottom: 10px;
    }
    .swap-token-card-title {
      color: var(--text-primary);
      font-size: 18px;
      font-weight: 700;
      line-height: 1.15;
    }
    .swap-token-card-main {
      display: grid;
      grid-template-columns: minmax(150px, 0.48fr) minmax(180px, 1fr);
      gap: 18px;
      align-items: start;
    }
    .token-side,
    .amount-side {
      min-width: 0;
    }
    .token-side {
      display: flex;
      flex-direction: column;
      justify-content: flex-start;
      min-height: 84px;
      padding-top: 0;
      margin-top: 3px;
    }
    .amount-side {
      text-align: right;
    }
    .swap-field-label {
      position: absolute;
      width: 1px;
      height: 1px;
      padding: 0;
      margin: -1px;
      overflow: hidden;
      clip: rect(0, 0, 0, 0);
      white-space: nowrap;
      border: 0;
    }
    .swap-token-card input { min-height: 42px; background: rgba(7, 17, 31, 0.86); }
    .swap-token-card .amount-side input {
      min-height: 54px;
      padding: 0;
      border: 0;
      border-radius: 0;
      background: transparent;
      text-align: right;
      font-size: 40px;
      font-weight: 700;
      line-height: 1.1;
      box-shadow: none;
    }
    .swap-token-card .amount-side input:focus { box-shadow: none; }
    .swap-token-selector {
      display: flex;
      gap: 3px;
      align-items: center;
      width: fit-content;
      max-width: 100%;
      min-height: 50px;
      border: 1px solid rgba(161, 190, 220, 0.14);
      border-radius: 999px;
      background: rgba(3, 10, 20, 0.52);
      padding: 0 10px 0 10px;
      box-shadow: inset 0 1px 0 rgba(237, 247, 255, 0.03);
    }
    .swap-token-selector:hover { border-color: var(--border-strong); }
    .swap-token-selector input {
      width: 68px;
      min-height: 46px;
      border: 0;
      min-width: 0;
      flex: 0 1 68px;
      box-shadow: none;
      background: transparent;
      font-size: 18px;
      font-weight: 750;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .swap-token-selector.is-long-symbol input,
    .swap-token-selector input.token-symbol-compact {
      font-size: 15px;
      font-weight: 760;
      letter-spacing: 0;
      width: 74px;
      flex-basis: 74px;
    }
    .token-pill-icon {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 29px;
      height: 29px;
      border: 1px solid rgba(237, 247, 255, 0.14);
      border-radius: 999px;
      background-color: rgba(11, 24, 41, 0.9);
      background-position: center;
      background-repeat: no-repeat;
      background-size: cover;
      color: var(--text-primary);
      font-size: 10px;
      font-weight: 800;
      line-height: 1;
      overflow: hidden;
      flex: 0 0 auto;
    }
    .token-pill-icon.has-image { color: transparent; }
    .token-pill-icon-sol {
      background:
        linear-gradient(135deg, #14f195 0%, #80ecff 45%, #9945ff 100%);
      color: #031423;
    }
    .token-pill-icon-usdc {
      background: linear-gradient(135deg, #2775ca 0%, #63e6ff 100%);
      color: #ffffff;
    }
    .token-pill-icon-fallback {
      background: linear-gradient(135deg, rgba(155, 124, 255, 0.82), rgba(99, 230, 255, 0.72));
      color: #031423;
    }
    .token-pill-arrow,
    .swap-token-selector-arrow { color: var(--accent-emerald); font-size: 12px; line-height: 1; flex: 0 0 auto; }
    #swapToToken {
      width: 68px;
      min-height: 46px;
      border: 0;
      min-width: 0;
      flex: 0 1 68px;
      background: transparent;
      font-size: 18px;
      font-weight: 750;
      box-shadow: none;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    #swapToToken.token-symbol-compact,
    .swap-token-selector.is-long-symbol #swapToToken {
      width: 74px;
      flex-basis: 74px;
      font-size: 15px;
      font-weight: 760;
      letter-spacing: 0;
    }
    #swapBuyEstimate {
      min-height: 54px;
      padding: 0;
      color: var(--text-secondary);
      font-size: 40px;
      font-weight: 700;
      line-height: 1.1;
      text-align: right;
    }
    .swap-direction-row {
      position: relative;
      z-index: 2;
      display: flex;
      justify-content: center;
      height: 0;
      pointer-events: none;
    }
    .swap-direction-button {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 38px;
      height: 38px;
      margin-top: -19px;
      padding: 0;
      border: 1px solid rgba(99, 230, 255, 0.22);
      border-radius: 999px;
      background: linear-gradient(180deg, rgba(16, 35, 58, 0.98), rgba(7, 17, 31, 0.96));
      color: var(--accent-cyan);
      font-size: 21px;
      font-weight: 800;
      box-shadow: 0 10px 24px rgba(1, 9, 20, 0.34), 0 0 0 5px rgba(3, 10, 20, 0.72);
      cursor: pointer;
      pointer-events: auto;
    }
    .swap-direction-button:hover {
      border-color: rgba(52, 245, 163, 0.34);
      color: var(--accent-emerald);
    }
    #swapBuyCard { margin-top: 10px; }
    .swap-amount-actions { display: flex; gap: 6px; margin-top: 8px; justify-content: flex-end; }
    .swap-amount-actions button {
      min-height: 30px;
      padding: 6px 10px;
      font-size: 11px;
      border-radius: 999px;
    }
    .swap-actions {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 8px;
      margin-top: 10px;
      align-items: center;
    }
    .swap-actions button {
      min-height: 44px;
    }
    #btnClearSwap {
      color: var(--text-secondary);
      background: rgba(161, 190, 220, 0.06);
    }
    #swapInlineBaselineRow {
      margin-top: 10px;
      background: rgba(7, 17, 31, 0.54);
      box-shadow: none;
    }
    .swap-summary-grid { display:grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap:8px; }
    .swap-summary-item {
      padding: 8px;
      border: 1px solid rgba(161, 190, 220, 0.11);
      border-radius: var(--radius-md);
      background: rgba(11, 24, 41, 0.56);
    }
    .swap-summary-value { font-size:13px; line-height:1.25; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
    .route-flow { margin-top:8px; padding-right:220px; font-size:15px; line-height:1.35; }
    .route-flow.compact { padding-right:180px; font-size:14px; }
    .route-flow-row { display:flex; align-items:baseline; gap:6px; }
    .route-flow-symbol { font-weight:600; display:inline-block; min-width:12px; }
    .route-flow-minus { color: var(--semantic-danger); }
    .route-flow-plus { color: var(--semantic-success); }
    .token-preview { margin-top: 6px; font-size: 12px; line-height: 1.35; min-height: 18px; }
    .token-side .token-preview {
      color: var(--text-secondary);
      overflow-wrap: anywhere;
    }
    .amount-side .token-preview {
      color: var(--text-muted);
    }
    button {
      padding: 10px 12px;
      border-radius: var(--radius-md);
      border: 1px solid rgba(52, 245, 163, 0.35);
      background: linear-gradient(180deg, #39f7a8, #21d98c);
      color: #04111f;
      cursor: pointer;
      font-weight: 650;
      box-shadow: 0 10px 28px rgba(52, 245, 163, 0.16);
    }
    button.secondary,
    a.secondary {
      background: rgba(155, 124, 255, 0.08);
      color: var(--text-primary);
      border-color: var(--border-default);
      box-shadow: none;
    }
    button.secondary:hover,
    a.secondary:hover {
      border-color: rgba(155, 124, 255, 0.46);
      background: rgba(155, 124, 255, 0.14);
    }
    #btnPreviewSwap {
      background: linear-gradient(180deg, #4cffb3, var(--accent-emerald));
      color: #031423;
      border-color: rgba(52, 245, 163, 0.62);
      box-shadow: 0 0 0 1px rgba(52, 245, 163, 0.18), 0 14px 34px rgba(52, 245, 163, 0.24);
    }
    @media (max-width: 760px) {
      body { padding: 12px; }
      .app-header {
        display: block;
      }
      .app-title { font-size: 21px; }
      .app-title-sub { font-size: 18px; }
      .app-confidence { font-size: 12px; }
      .swap-wallet-panel {
        margin-top: 10px;
        text-align: left;
      }
      .swap-wallet-panel .row { justify-content: flex-start; }
      .swap-token-card {
        min-height: 152px;
        padding: 16px;
      }
      .swap-token-card-title { font-size: 17px; }
      .swap-token-card-main {
        grid-template-columns: minmax(112px, 0.48fr) minmax(0, 1fr);
        gap: 10px;
      }
      .swap-token-selector input {
        width: 62px;
        flex-basis: 62px;
        font-size: 16px;
      }
      .token-side {
        min-height: 82px;
        padding-top: 0;
      }
      #swapToToken {
        width: 62px;
        flex-basis: 62px;
        font-size: 16px;
      }
      .swap-actions { grid-template-columns: 1fr; }
      .swap-actions button { width: 100%; }
      .swap-token-card .amount-side input,
      #swapBuyEstimate {
        text-align: right;
        font-size: 30px;
      }
      input, select { min-width: 0; }
    }
    button:disabled { opacity: .6; cursor: not-allowed; }
    .token-resolve-use { padding: 3px 7px; border-radius: 7px; font-size: 11px; margin-left: 6px; vertical-align: middle; }
    .token-resolve-use-added { background: var(--accent-emerald-soft); color: var(--accent-emerald); border-color: var(--border-strong); }
    table { border-collapse: collapse; width: 100%; margin-top: 10px; }
    th, td { border-bottom: 1px solid var(--border-default); padding: 8px; text-align: left; font-size: 13px; }
    th { background: rgba(19, 41, 68, 0.94); color: var(--text-secondary); position: sticky; top: 0; }
    pre {
      background: rgba(3, 10, 20, 0.82);
      color: #c7d7eb;
      padding: 10px;
      border-radius: var(--radius-md);
      border: 1px solid rgba(127, 145, 170, 0.14);
      overflow: auto;
    }
    details > summary { color: var(--text-secondary); }
    .pill {
      display: inline-block;
      padding: 2px 8px;
      border-radius: 999px;
      font-size: 12px;
      border: 1px solid var(--border-default);
      background: rgba(99, 230, 255, 0.08);
      color: var(--accent-cyan);
    }
    .ok { background: rgba(34, 197, 94, 0.14); color: #bff7d1; border-color: rgba(34, 197, 94, 0.26); }
    .warn { background: rgba(245, 158, 11, 0.15); color: #ffd899; border-color: rgba(245, 158, 11, 0.28); }
    .err { background: rgba(240, 68, 56, 0.14); color: #ffc7c2; border-color: rgba(240, 68, 56, 0.28); }
    .modal-backdrop { position: fixed; inset: 0; display: none; align-items: center; justify-content: center; padding: 18px; background: rgba(0,0,0,.62); z-index: 50; }
    .modal-backdrop.is-open { display: flex; }
    .modal-panel { width: min(480px, 100%); background: var(--bg-elevated); border: 1px solid var(--border-default); border-radius: var(--radius-lg); padding: 14px; box-shadow: var(--shadow-card); }
    .modal-actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 12px; }
    .token-modal-backdrop { position: fixed; inset: 0; display: none; align-items: center; justify-content: center; padding: 18px; background: rgba(0,0,0,.62); z-index: 60; }
    .token-modal-backdrop.is-open { display: flex; }
    .token-modal { width: min(520px, 100%); max-height: min(720px, 92vh); overflow: auto; background: var(--bg-elevated); border: 1px solid var(--border-default); border-radius: var(--radius-lg); padding: 14px; box-shadow: var(--shadow-card), var(--shadow-glow); }
    .token-modal-search { width: 100%; box-sizing: border-box; margin-top: 8px; }
    .token-modal-section { margin-top: 12px; }
    .token-modal-row { display: flex; align-items: center; justify-content: space-between; gap: 10px; width: 100%; text-align: left; margin-top: 6px; padding: 8px; border: 1px solid var(--border-default); border-radius: var(--radius-sm); background: rgba(11, 24, 41, 0.76); color: var(--text-primary); }
    .token-modal-row-main { font-weight: 600; }
    .token-modal-row-sub { font-size: 12px; color: var(--text-muted); margin-top: 2px; overflow-wrap: anywhere; }
    .token-modal-action { padding: 6px 8px; border-radius: 8px; font-size: 12px; white-space: nowrap; }
  </style>
</head>
<body>
  <main class="app-shell">
  <header class="app-header">
    <div>
      <h2 class="app-title"><span class="brand-mark">Web3 Digest</span><span class="app-title-sub">Swap Terminal</span></h2>
      <div class="app-confidence">Compare Solana swap routes, understand costs, and approve safely through Phantom.</div>
    </div>
    <div class="swap-wallet-panel">
      <div class="row" id="swapWalletControls">
        <button id="btnSwapConnectPhantom" type="button" class="secondary">Connect Phantom</button>
        <button id="btnSwapDisconnectPhantom" type="button" class="secondary" style="display:none;">Disconnect</button>
      </div>
      <div class="muted" id="swapWalletStrip">Connected: not connected</div>
      <div class="muted" id="swapWalletConnectHint">Connect Phantom to prepare and approve swaps.</div>
    </div>
  </header>

  <details id="advancedDeveloperTools" class="card shell-detail" style="margin-top:12px;">
    <summary class="muted" style="cursor:pointer;">Advanced / Developer tools</summary>

  <div class="card">
    <div class="row">
      <div>
        <label>Account</label>
        <select id="accountSelect"></select>
      </div>

      <div>
        <label>Currency</label>
        <input id="currencyInput" value="usd" />
      </div>

      <div>
        <label>Assets override (optional)</label>
        <input id="assetsInput" placeholder="sol,usdc,spl:<mint>" />
      </div>

      <div>
        <label>Show unpriced</label>
        <select id="showUnpriced">
          <option value="false" selected>false</option>
          <option value="true">true</option>
        </select>
      </div>
    </div>

    <div class="row" style="margin-top: 10px;">
      <button id="btnLoad" class="secondary">Load Report</button>

      <div style="min-width: 12px;"></div>

      <div>
        <label>Force refresh</label>
        <select id="forceSelect">
          <option value="false" selected>false</option>
          <option value="true">true</option>
        </select>
      </div>

      <button id="btnRefreshBalances">Refresh Balances</button>
      <button id="btnRefreshPrices">Refresh Prices</button>

      <div style="min-width: 12px;"></div>

      <button id="btnConnectPhantom" class="secondary">Connect Phantom</button>
      <button id="btnDisconnectPhantom" class="secondary">Disconnect</button>
      <button id="btnSignMessage">Sign Message</button>

      
      <div>
        <label>Dex fallback (USD)</label>
        <select id="useDex">
          <option value="true" selected>true</option>
          <option value="false">false</option>
        </select>
      </div>

      <div>
        <label>Min liquidity USD</label>
        <input id="minLiq" value="5000" />
      </div>
    </div>

    <div id="status" class="card" style="display:none;"></div>

   


  <div class="card" id="walletCard">
    <div class="row">
      <div><span class="pill" id="pillWallet">wallet: ?</span></div>
      <div class="muted" id="walletAddress">address: —</div>
    </div>
    <div class="muted" id="walletBalance" style="margin-top:8px;">devnet balance: —</div>
    <div class="muted" id="walletSigMeta" style="margin-top:8px;">last signature: —</div>
    <pre id="walletSigPreview" style="display:none; margin-top:8px;"></pre>
  </div>

  <div class="card" id="sendSolCard">
    <h3 style="margin: 0 0 6px 0;">Send SOL <span class="pill warn">DEVNET</span></h3>
    <div class="muted">Build a devnet SOL transfer from the browser, then use Phantom to sign/send it.</div>

    <div class="row" style="margin-top: 10px;">
      <div>
        <label>Recipient address</label>
        <input id="sendRecipient" placeholder="Enter Solana address" />
      </div>

      <div>
        <label>Amount (SOL)</label>
        <input id="sendAmount" placeholder="0.01" />
      </div>

      <div>
        <label>Network</label>
        <input id="sendNetwork" value="devnet" disabled />
      </div>
    </div>

    <div class="row" style="margin-top: 10px;">
      <button id="btnValidateSend" class="secondary">Validate</button>
      <button id="btnSendSol">Send SOL</button>
      <button id="btnAirdropDevnet" class="secondary">Airdrop 1 SOL</button>
    </div>

    <div class="card" id="sendStateCard" style="margin-top:10px;">
      <div class="row">
        <div><span class="pill warn" id="pillSendState">state: Draft</span></div>
        <div class="muted" id="sendStateText">Ready to build a devnet SOL transfer.</div>
      </div>

      <div class="muted" id="sendSigLine" style="margin-top:8px;">tx signature: —</div>
      <div style="margin-top:8px;">
        <a id="sendExplorerLink" href="#" target="_blank" style="display:none;">Open in Solana Explorer (devnet)</a>
      </div>
    </div>

    <div id="sendSolStatus" class="card" style="display:none; margin-top:10px;"></div>
  </div>

  </details>


  <div class="card" id="swapCard">
    <div class="swap-card-header">
      <div>
        <h3 class="swap-card-title">Swap <span class="pill warn">SOLANA-FIRST</span></h3>
        <div class="swap-card-subtitle">Wallet-aware route preview</div>
      </div>
    </div>
    <div class="muted" id="swapBalanceFreshnessHint" style="display:none; margin-top:6px; font-size:12px;"></div>
    <button id="btnSwapRefreshBalances" type="button" class="secondary">Refresh balances</button>
    <details class="card" id="swapBalanceRefreshDebugWrap" style="display:none; margin-top:8px; font-size:12px;">
      <summary class="muted" style="cursor:pointer; font-weight:600;">Balance refresh diagnostics</summary>
      <pre id="swapBalanceRefreshDebug" style="margin-top:8px;">No balance refresh yet.</pre>
    </details>

    <div class="swap-setup-panel">
    <div class="swap-input-grid">
      <div class="swap-token-card" id="swapSellCard">
        <div class="swap-token-card-header">
          <div class="swap-token-card-title">You sell</div>
        </div>
        <div class="swap-token-card-main">
          <div class="token-side">
            <label class="swap-field-label" for="swapFromToken">Token</label>
            <div class="swap-token-selector" id="swapFromTokenSelector" title="Choose from wallet holdings or type a token mint">
              <input id="swapFromToken" list="swapTokenChoices" value="SOL" placeholder="SOL or token mint" autocomplete="off" />
              <span class="token-pill-icon token-pill-icon-sol" id="swapFromTokenIcon" aria-hidden="true">SOL</span>
              <span class="token-pill-arrow swap-token-selector-arrow" aria-hidden="true">▼</span>
            </div>
            <div id="swapHoldingsDropdown" class="card" style="display:none; margin-top:6px; max-height:180px; overflow:auto; font-size:12px;"></div>
            <div class="muted token-preview" id="swapFromTokenPreview"></div>
            <div class="muted token-preview" id="swapFromBalanceHint">Available: load wallet balances.</div>
          </div>
          <div class="amount-side">
            <label class="swap-field-label" for="swapAmount">Amount</label>
            <input id="swapAmount" placeholder="0.0" />
            <div class="muted token-preview" id="swapSellValueEstimate" style="text-align:right;">USD estimate: —</div>
            <div class="swap-amount-actions">
              <button id="btnSwapAmountHalf" type="button" class="secondary" disabled style="padding:6px 8px;">50%</button>
              <button id="btnSwapAmountMax" type="button" class="secondary" disabled style="padding:6px 8px;">MAX</button>
            </div>
            <div class="muted token-preview" id="swapAmountHelper">Use 50% or MAX after balances load.</div>
          </div>
        </div>
      </div>

      <div class="swap-direction-row">
        <button id="btnSwapDirection" class="swap-direction-button" type="button" aria-label="Swap sell and buy tokens">⇅</button>
      </div>

      <div class="swap-token-card" id="swapBuyCard">
        <div class="swap-token-card-header">
          <div class="swap-token-card-title">You buy</div>
        </div>
        <div class="swap-token-card-main">
          <div class="token-side">
            <label class="swap-field-label" for="swapToToken">Token</label>
            <div class="swap-token-selector" id="swapToTokenSelector" title="Choose a token to receive or type a token mint">
              <input id="swapToToken" list="swapTokenChoices" value="USDC" placeholder="USDC or token mint" autocomplete="off" />
              <span class="token-pill-icon token-pill-icon-usdc" id="swapToTokenIcon" aria-hidden="true">USDC</span>
              <span class="token-pill-arrow swap-token-selector-arrow" aria-hidden="true">▼</span>
            </div>
            <div class="muted token-preview" id="swapToTokenPreview"></div>
          </div>
          <div class="amount-side">
            <label class="swap-field-label" for="swapBuyEstimate">Estimated receive</label>
            <div id="swapBuyEstimate" class="muted">Preview quote</div>
            <div class="muted token-preview" id="swapBuyValueEstimate" style="text-align:right;">Estimated receive after preview.</div>
          </div>
        </div>
      </div>
    </div>
    <datalist id="swapTokenChoices">
      <option value="SOL">SOL - Solana</option>
      <option value="USDC">USDC - USD Coin</option>
    </datalist>

    <div class="swap-actions">
      <button id="btnPreviewSwap" type="button" class="secondary">Preview Quote</button>
      <button id="btnClearSwap" class="secondary">Clear</button>
    </div>

    <div class="card" id="holderConcentrationCard" style="display:none; margin-top:10px;">
      <div id="holderConcentrationBox" class="muted">No holder concentration check yet.</div>
    </div>

    <div class="card" id="swapInlineBaselineRow">
      <h4 style="margin: 0 0 8px 0;">Swap summary</h4>
      <div class="swap-summary-grid">
        <div class="swap-summary-item">
          <div class="muted" style="font-size:12px;">You sell</div>
          <div id="swapSpendValueHint" class="swap-summary-value">—</div>
        </div>
        <div class="swap-summary-item">
          <div class="muted" style="font-size:12px;">Market reference</div>
          <div id="swapBaselineDeltaHint" class="swap-summary-value">—</div>
        </div>
        <div class="swap-summary-item">
          <div class="muted" style="font-size:12px;">Best executable quote</div>
          <div id="swapIdealOutputHint" class="swap-summary-value">Preview Quote</div>
        </div>
        <div class="swap-summary-item">
          <div class="muted" style="font-size:12px;">Route difference vs reference</div>
          <div id="swapMarketCompareHint" class="swap-summary-value">—</div>
        </div>
      </div>
      <div class="muted" id="swapBaselineNote" style="margin-top:8px; font-size:12px; opacity:0.78;">Reference pricing is used only to compare route quality — not an executable route.</div>
    </div>
    </div>

    <div class="card" id="swapQuoteCard" style="margin-top:10px;">
      <div class="row" style="font-size:12px;">
        <div><span class="pill warn" id="pillSwapState" style="font-size:11px; padding:2px 7px;">Draft</span></div>
        <div class="muted" id="swapStateText" style="font-size:12px;">Ready to request a swap quote.</div>
      </div>
      <div class="muted" id="swapCoverageDepth" style="display:none; margin-top:6px; font-size:12px; opacity:0.82;"></div>
      <div class="muted" id="swapExternalTokenNotice" style="display:none; margin-top:6px; font-size:12px; opacity:0.82;"></div>
      <div class="muted" id="swapExecutionStatus" style="display:none; margin-top:6px; font-size:12px; opacity:0.86;">Ready to prepare a swap route.</div>
      <details class="card" id="swapVisiblePreflightDebugWrap" style="margin-top:8px; font-size:12px;">
        <summary class="muted" style="cursor:pointer; font-weight:600;">Latest preflight diagnostics</summary>
        <pre id="swapVisiblePreflightDebug" style="margin-top:8px;">No preflight check yet.</pre>
      </details>
      <div class="muted" id="swapQuoteFreshness" style="display:none; margin-top:6px; font-size:12px; opacity:0.86;"></div>
      <div id="swapPreparedAction" style="display:none; margin-top:8px;">
        <div id="swapPreparedSummary" class="muted" style="font-size:12px; line-height:1.45;"></div>
        <label class="muted" style="display:flex; align-items:flex-start; gap:6px; margin-top:8px; font-size:12px;">
          <input id="swapSignAcknowledgement" type="checkbox" style="width:auto; min-width:0; margin-top:2px;" />
          <span>I understand this is a real Solana mainnet swap and Phantom will ask me to approve it.</span>
        </label>
        <button id="btnSignPreparedSwap" type="button" class="secondary" disabled style="margin-top:8px;">Review and sign in Phantom</button>
      </div>

      <div class="muted" id="swapRecommendation" style="margin-top:8px;">recommendation: —</div>
      <div class="muted" id="swapCompareSummary" style="margin-top:8px;">comparison summary: —</div>
    </div>

    <div class="card" id="swapRecommendedCard" style="margin-top:10px;">
      <h4 style="margin: 0 0 6px 0;">Recommended executable route</h4>
      <div class="muted" id="swapRecommendedBox">No quote yet.</div>
    </div>

    <div class="card" id="swapDirectCard" style="margin-top:10px;">
      <h4 style="margin: 0 0 6px 0;">Direct/simple route check</h4>
      <div class="muted" id="swapDirectBox">No direct-route check yet.</div>
    </div>

    <div class="card" id="swapAlternativesCard" style="display:none; margin-top:10px;">
      <h4 style="margin: 0 0 6px 0;">Alternatives</h4>
      <div id="swapAlternativesBox"></div>
    </div>

    <details id="swapDebugWrap" class="card" style="margin-top:10px; display:none;">
      <summary class="muted" style="cursor:pointer;">Raw quote debug JSON</summary>
      <pre id="swapQuotePreview" style="margin-top:8px;"></pre>
      <div class="muted" style="margin-top:10px; font-size:12px;">Latest preflight diagnostics</div>
      <pre id="swapPreflightDebug" style="margin-top:8px;">No preflight check yet.</pre>
    </details>

    <div id="swapStatus" class="card" style="display:none; margin-top:10px;"></div>

    <div id="swapSuccessModal" class="modal-backdrop" aria-hidden="true">
      <div class="modal-panel" role="dialog" aria-modal="true" aria-labelledby="swapSuccessModalTitle">
        <h3 id="swapSuccessModalTitle" style="margin:0 0 8px 0;">Swap submitted successfully</h3>
        <div id="swapSuccessModalBody" class="muted" style="line-height:1.45;"></div>
        <div class="modal-actions">
          <a id="swapSuccessExplorerLink" class="secondary" href="#" target="_blank" style="display:none; padding:10px 12px; border-radius:10px; text-decoration:none;">Open in Solana Explorer</a>
          <button id="btnCloseSwapSuccessModal" type="button" class="secondary">Close</button>
        </div>
      </div>
    </div>

    <div id="swapTokenModalBackdrop" class="token-modal-backdrop" aria-hidden="true">
      <div class="token-modal" role="dialog" aria-modal="true" aria-labelledby="swapTokenModalTitle">
        <div class="row" style="align-items:center; justify-content:space-between;">
          <h3 id="swapTokenModalTitle" style="margin:0;">Select token</h3>
          <button id="btnCloseSwapTokenModal" type="button" class="secondary" aria-label="Close token selector">Close</button>
        </div>
        <input id="swapTokenModalSearch" class="token-modal-search" placeholder="Search symbol or paste Solana mint" autocomplete="off" />
        <div id="swapTokenModalBody"></div>
      </div>
    </div>

    </div>

  <details id="advancedPortfolioTools" class="card shell-detail" style="margin-top:12px;">
    <summary class="muted" style="cursor:pointer;">Advanced / Portfolio and debug tools</summary>

    <div class="card" id="summaryCard">
    <div class="row">
      <div><span class="pill" id="pillBalances">balances: ?</span></div>
      <div><span class="pill" id="pillPrices">prices: ?</span></div>
      <div><span class="pill" id="pillStale">stale: ?</span></div>
    </div>
    <div style="margin-top: 8px;">
      <strong>Total value:</strong> <span id="totalValue">—</span>
      <span class="muted" id="changeLabel"></span>
    </div>
  </div>

  <div class="card">
    <h3 style="margin: 0 0 6px 0;">Holdings</h3>
    <div class="muted">Values come from latest snapshots in SQLite.</div>
    <div style="max-height: 360px; overflow:auto;">
      <table id="positionsTable">
        <thead>
          <tr>
            <th>Asset</th>
            <th>Amount</th>
            <th>Price</th>
            <th>Value</th>
            <th>Balance TS</th>
            <th>Price TS</th>
          </tr>
        </thead>
        <tbody></tbody>
      </table>
    </div>
  </div>

  <div class="card">
    <h3 style="margin: 0 0 6px 0;">Portfolio History</h3>
    <div class="muted">From <code>get_portfolio_snapshot_history</code>.</div>
    <div id="history"></div>
  </div>


  <div class="card">
    <h3 style="margin: 0 0 6px 0;">Activity Log</h3>
    <div class="muted">Latest wallet / send / airdrop actions.</div>
    <div id="activityLog" style="margin-top:10px;"></div>
  </div>


  <div class="card">
    <h3 style="margin: 0 0 6px 0;">Raw JSON (debug)</h3>
    <pre id="raw"></pre>
  </div>

  </details>
  </main>

<script src="https://unpkg.com/@solana/web3.js@latest/lib/index.iife.min.js"></script>
<script>
  const $ = (id) => document.getElementById(id);
  console.log("ui script loaded");


  const DEVNET_RPC_URL = "https://api.devnet.solana.com";
  const DEVNET_EXPLORER_BASE = "https://explorer.solana.com/tx/";
  const MAINNET_EXPLORER_BASE = "https://explorer.solana.com/tx/";

  const ACTIVITY_LIMIT = 8;
  const SWAP_QUOTE_TTL_SECONDS = 90;
  const SWAP_BALANCE_FRESH_MS = 10 * 60 * 1000;
  const SWAP_SOL_FEE_ACCOUNT_SETUP_BUFFER_SOL = 0.001;
  const SWAP_DEFAULT_NETWORK_FEE_SOL = 0.0001;
  const SWAP_RECOGNIZED_TOKENS_STORAGE_KEY = "web3Digest.swapRecognizedTokens.v1";
  const activityItems = [];
  let swapTokenList = [
    { symbol: "SOL", display_name: "Solana", decimals: 9 },
    { symbol: "USDC", display_name: "USD Coin", decimals: 6 }
  ];
  let swapRecognizedTokenMap = {};
  const swapTokenResolveTimers = {};
  const swapTokenResolveState = {
    from: null,
    to: null
  };
  const swapSelectedRecognizedTokenMint = {
    from: "",
    to: ""
  };
  let holderConcentrationMint = null;
  let latestPortfolioReport = null;
  let latestPortfolioAccount = "";
  let latestSwapQuoteResponse = null;
  let latestHolderConcentrationData = null;
  let latestPreparedSwap = null;
  let latestSwapPreflightResponse = null;
  let latestSwapBalanceRefreshDiagnostics = null;
  let swapExecutionState = "idle";
  let swapQuoteExpiresAt = null;
  let swapQuoteTimerId = null;
  let swapBalancesStaleAfterSubmit = false;
  let activeTokenSide = "from";
  let tokenSearchQuery = "";
  let tokenModalResolvedExternalToken = null;
  let tokenModalResolveTimerId = null;

  function nowTimeLabel() {
    return new Date().toLocaleTimeString();
  }

  function logActivity(kind, title, payload=null) {
    activityItems.unshift({
      ts: nowTimeLabel(),
      kind: kind || "ok",
      title: title || "Event",
      payload
    });

    if (activityItems.length > ACTIVITY_LIMIT) {
      activityItems.length = ACTIVITY_LIMIT;
    }

    renderActivityLog();
  }

  function renderActivityLog() {
    const box = $("activityLog");
    if (!box) return;

    if (!activityItems.length) {
      box.innerHTML = "<div class='muted'>No activity yet.</div>";
      return;
    }

    let html = "";
    for (const item of activityItems) {
      html += `
        <div class="card ${escapeHtml(item.kind)}" style="margin-top:8px;">
          <div><strong>${escapeHtml(item.ts)} — ${escapeHtml(item.title)}</strong></div>
          ${
            item.payload
              ? `<pre style="margin-top:8px;">${escapeHtml(JSON.stringify(item.payload, null, 2))}</pre>`
              : ""
          }
        </div>
      `;
    }

    box.innerHTML = html;
  }

function normalizeSwapAssetKey(value) {
  return String(value || "").trim().replace(/^spl:/i, "").toUpperCase();
}

function formatSwapSnapshotAge(value) {
  if (!value) return "snapshot may be stale";
  const ts = Date.parse(value);
  if (!Number.isFinite(ts)) return "snapshot may be stale";
  const ageMs = Date.now() - ts;
  if (!Number.isFinite(ageMs) || ageMs < 0) return "updated just now";
  const minutes = Math.floor(ageMs / 60000);
  if (minutes < 1) return "updated just now";
  if (minutes < 60) return "updated " + minutes + "m ago";
  const hours = Math.floor(minutes / 60);
  if (hours < 48) return "updated " + hours + "h ago";
  const days = Math.floor(hours / 24);
  return "updated " + days + "d ago";
}

function isSwapBalanceSnapshotFresh(value) {
  if (!value) return false;
  const ts = Date.parse(value);
  if (!Number.isFinite(ts)) return false;
  const ageMs = Date.now() - ts;
  return Number.isFinite(ageMs) && ageMs >= 0 && ageMs <= SWAP_BALANCE_FRESH_MS;
}

function renderSwapBalanceFreshnessHint(holding=null) {
  const hint = $("swapBalanceFreshnessHint");
  const button = $("btnSwapRefreshBalances");
  if (!hint) return;

  const staleHolding = holding && !isSwapBalanceSnapshotFresh(holding.balance_ts);
  if (swapBalancesStaleAfterSubmit) {
    hint.textContent = "Balances may have changed after the last swap — refresh balances.";
    hint.style.display = "block";
    if (button) button.style.display = "inline-block";
    return;
  }
  if (staleHolding) {
    hint.textContent = "Balances are from snapshots. Refresh before swapping.";
    hint.style.display = "block";
    if (button) button.style.display = "inline-block";
    return;
  }

  hint.textContent = "";
  hint.style.display = "none";
  if (button) button.style.display = "inline-flex";
}

function portfolioBalanceRows() {
  const positions = latestPortfolioReport?.positions || {};
  return Object.entries(positions)
    .map(([asset, position]) => {
      const amount = Number(position?.amount);
      const rawAsset = String(asset || "");
      const splMint = rawAsset.toLowerCase().startsWith("spl:") ? rawAsset.slice(4) : "";
      const recognized = recognizedSwapTokenForAsset(rawAsset, position);
      const recognizedMint = recognized?.mint || "";
      const recognizedSymbol = recognized?.symbol || recognized?.display_name || "";
      const label = String(recognizedSymbol || position?.display || position?.symbol || rawAsset || "").replace(/^spl:/i, "").toUpperCase();
      return {
        asset: rawAsset,
        mint: splMint || recognizedMint,
        token_input_value: splMint || recognizedMint || rawAsset.replace(/^spl:/i, "").toUpperCase(),
        token_value: recognizedMint || rawAsset.replace(/^spl:/i, "").toUpperCase(),
        label,
        amount,
        balance_ts: position?.balance_ts || "",
        value: Number(position?.value)
      };
    })
    .filter((row) => Number.isFinite(row.amount))
    .sort((a, b) => (Number.isFinite(b.value) ? b.value : 0) - (Number.isFinite(a.value) ? a.value : 0));
}

function portfolioHoldingRows() {
  return portfolioBalanceRows().filter((row) => row.amount > 0);
}

function swapWalletAssetLabels(limit=4) {
  const labels = [];
  const seen = new Set();
  for (const row of portfolioHoldingRows()) {
    const label = String(row.label || row.token_value || "").trim();
    if (!label) continue;
    const keys = [
      row.asset,
      row.mint,
      row.token_input_value,
      row.token_value,
      label
    ]
      .map((value) => normalizeSwapAssetKey(value))
      .filter(Boolean);
    const duplicate = keys.some((key) => seen.has(key));
    if (duplicate) continue;
    keys.forEach((key) => seen.add(key));
    labels.push(label);
    if (labels.length >= limit) break;
  }
  return labels;
}

function selectedFromHolding() {
  const query = normalizeSwapAssetKey($("swapFromToken")?.value);
  const resolvedMint = normalizeSwapAssetKey(swapTokenResolveState.from?.mint);
  if (!query && !resolvedMint) return null;

  const matches = portfolioBalanceRows().filter((row) => {
    const asset = normalizeSwapAssetKey(row.asset);
    const mint = normalizeSwapAssetKey(row.mint);
    const label = normalizeSwapAssetKey(row.label);
    const value = normalizeSwapAssetKey(row.token_value);
    const inputValue = normalizeSwapAssetKey(row.token_input_value);
    return asset === query || mint === query || label === query || value === query || inputValue === query ||
      (resolvedMint && (asset === resolvedMint || mint === resolvedMint || value === resolvedMint || inputValue === resolvedMint));
  });
  matches.sort((left, right) => {
    const leftExactMint = resolvedMint && normalizeSwapAssetKey(left.mint || left.token_value || left.token_input_value) === resolvedMint;
    const rightExactMint = resolvedMint && normalizeSwapAssetKey(right.mint || right.token_value || right.token_input_value) === resolvedMint;
    if (leftExactMint !== rightExactMint) return leftExactMint ? -1 : 1;
    const leftTs = Date.parse(left.balance_ts || "");
    const rightTs = Date.parse(right.balance_ts || "");
    return (Number.isFinite(rightTs) ? rightTs : 0) - (Number.isFinite(leftTs) ? leftTs : 0);
  });
  return matches[0] || null;
}

function selectedFromHoldingDiagnostics() {
  const selectedToken = selectedFromRecognizedToken();
  const holding = selectedFromHolding();
  const positions = latestPortfolioReport?.positions || {};
  return {
    input_value: $("swapFromToken")?.value || "",
    resolved_mint: swapTokenResolveState.from?.mint || "",
    selected_token: selectedToken ? {
      symbol: selectedToken.symbol || "",
      mint: selectedToken.mint || "",
      asset_key: selectedToken.asset_key || selectedToken.asset || "",
      spl_asset_key: selectedToken.mint ? "spl:" + selectedToken.mint : ""
    } : null,
    portfolio_assets: Object.keys(positions),
    holding_rows: portfolioHoldingRows().map((row) => ({
      asset: row.asset,
      mint: row.mint,
      token_input_value: row.token_input_value,
      token_value: row.token_value,
      label: row.label,
      amount: row.amount,
      balance_ts: row.balance_ts
    })),
    balance_rows: portfolioBalanceRows().map((row) => ({
      asset: row.asset,
      mint: row.mint,
      token_input_value: row.token_input_value,
      token_value: row.token_value,
      label: row.label,
      amount: row.amount,
      balance_ts: row.balance_ts
    })),
    matched_holding: holding ? {
      asset: holding.asset,
      mint: holding.mint,
      token_input_value: holding.token_input_value,
      token_value: holding.token_value,
      label: holding.label,
      amount: holding.amount,
      balance_ts: holding.balance_ts,
      is_zero: holding.amount === 0,
      is_fresh: isSwapBalanceSnapshotFresh(holding.balance_ts)
    } : null,
    matched_holding_is_zero: holding ? holding.amount === 0 : false,
    matched_holding_is_fresh: holding ? isSwapBalanceSnapshotFresh(holding.balance_ts) : false
  };
}

function selectedSolHolding() {
  return portfolioHoldingRows().find((row) => normalizeSwapAssetKey(row.token_value) === "SOL" ||
    normalizeSwapAssetKey(row.label) === "SOL" ||
    normalizeSwapAssetKey(row.asset) === "SOL") || null;
}

function validateSwapInputBalanceBeforePrepare(amount) {
  const holding = selectedFromHolding();
  if (!holding) return { ok: true };
  const fresh = isSwapBalanceSnapshotFresh(holding.balance_ts) && !swapBalancesStaleAfterSubmit;
  if (!fresh) return { ok: true };

  const available = Number(holding.amount);
  const requested = Number(amount);
  if (!Number.isFinite(available) || !Number.isFinite(requested) || requested <= available) {
    return { ok: true };
  }

  const label = holding.label || holding.token_value || $("swapFromToken")?.value || "this token";
  const availableText = fmtNum(available, 6);
  const requestedText = fmtNum(requested, 6);
  const zero = available === 0;
  return {
    ok: false,
    label,
    available,
    requested,
    message: zero
      ? "You do not currently hold " + label + "."
      : "Insufficient " + label + " balance for this swap.",
    detail: "You only have " + availableText + " " + label + ", but you entered " + requestedText + " " + label + ". Enter an amount within your available balance."
  };
}

function renderSwapWalletStrip() {
  const box = $("swapWalletStrip");
  if (!box) return;

  box.textContent = phantomPubkey
    ? "Connected: " + shortenMiddle(phantomPubkey, 6, 6)
    : "Connected: not connected";
}

function renderSwapWalletControls() {
  const connect = $("btnSwapConnectPhantom");
  const disconnect = $("btnSwapDisconnectPhantom");
  const hint = $("swapWalletConnectHint");
  if (!connect || !disconnect || !hint) return;

  const providerAvailable = Boolean(getPhantomProvider());
  if (phantomPubkey) {
    connect.style.display = "none";
    disconnect.style.display = "inline-block";
    hint.textContent = "Connected: " + shortenMiddle(phantomPubkey, 6, 6);
    return;
  }

  connect.style.display = "inline-block";
  disconnect.style.display = "none";
  connect.disabled = !providerAvailable;
  hint.textContent = providerAvailable
    ? "Connect Phantom to prepare and approve swaps."
    : "Install or enable Phantom to prepare and approve swaps.";
}

function renderSwapFromBalance() {
  const hint = $("swapFromBalanceHint");
  const amountHelper = $("swapAmountHelper");
  const half = $("btnSwapAmountHalf");
  const max = $("btnSwapAmountMax");
  const holding = selectedFromHolding();
  const token = ($("swapFromToken")?.value || holding?.label || "").trim().toUpperCase();

  if (holding) {
    const label = holding.label || token || holding.token_value;
    const available = fmtNum(holding.amount, 6);
    const age = formatSwapSnapshotAge(holding.balance_ts);
    const fresh = isSwapBalanceSnapshotFresh(holding.balance_ts) && !swapBalancesStaleAfterSubmit;
    const zeroBalance = holding.amount === 0;
    if (hint) {
      hint.textContent = fresh
        ? "Available: " + available + " " + label
        : "Available snapshot: " + available + " " + label + " · " + age;
    }
    if (amountHelper) {
      if (fresh && zeroBalance) {
        amountHelper.textContent = "You do not currently hold " + label + ".";
      } else if (fresh) {
        amountHelper.textContent = label === "SOL"
          ? "MAX keeps SOL reserved for network fees/account setup."
          : "Use 50% or MAX from your loaded wallet balance.";
      } else if (swapBalancesStaleAfterSubmit) {
        amountHelper.textContent = "Balances may have changed after the last swap — refresh balances to use 50% or MAX.";
      } else {
        amountHelper.textContent = "Refresh balances to use 50% or MAX.";
      }
    }
    if (half) half.disabled = !fresh || zeroBalance;
    if (max) max.disabled = !fresh || zeroBalance;
    renderSwapBalanceFreshnessHint(holding);
    return;
  }

  if (hint) {
    hint.textContent = latestPortfolioReport
      ? "No fresh balance found for " + (token || "this token") + "."
      : "Available: connect wallet / refresh balances.";
  }
  if (amountHelper) amountHelper.textContent = latestPortfolioReport
    ? "No fresh balance found for this token."
    : "Use 50% or MAX after balances load.";
  if (half) half.disabled = true;
  if (max) max.disabled = true;
  renderSwapBalanceFreshnessHint(null);
}

function renderSwapHoldingsDropdown() {
  const box = $("swapHoldingsDropdown");
  if (!box) return;

  const rows = portfolioHoldingRows();
  const selectedRecognized = selectedFromRecognizedToken();
  const selectedHolding = selectedFromHolding();
  const selectedRecognizedKey = normalizeSwapAssetKey(
    selectedRecognized?.mint || selectedRecognized?.asset_key || selectedRecognized?.asset || ""
  );
  const hasSelectedRecognizedRow = selectedRecognizedKey && portfolioBalanceRows().some((row) =>
    [row.asset, row.mint, row.token_input_value, row.token_value, row.label]
      .some((value) => normalizeSwapAssetKey(value) === selectedRecognizedKey)
  );
  const selectedRecognizedHtml = selectedRecognized && selectedHolding && selectedHolding.amount === 0
    ? `
    <div class="muted" style="padding:6px 0;">
      Selected token: ${escapeHtml(selectedRecognized.symbol || selectedRecognized.display_name || selectedHolding.label || "External token")} · 0
    </div>
  `
    : selectedRecognized && !hasSelectedRecognizedRow
    ? `
    <div class="muted" style="padding:6px 0;">
      Selected token: ${escapeHtml(selectedRecognized.symbol || selectedRecognized.display_name || "External token")} · balance not loaded / refresh balances
    </div>
  `
    : "";
  if (!rows.length) {
    box.innerHTML = "<div class='muted'>Type or paste a token mint above.</div>" + selectedRecognizedHtml + "<div class='muted' style='margin-top:6px;'>No wallet balances loaded yet.</div>";
    return;
  }

  box.innerHTML = `
    <div class="muted" style="padding:4px 0 6px 0;">Type or paste a token mint above.</div>
  ` + selectedRecognizedHtml + rows.map((row) => `
    <button
      type="button"
      class="secondary"
      style="display:block; width:100%; text-align:left; margin-top:4px; padding:6px 8px;"
      data-swap-holding-token="${escapeHtml(row.token_value)}"
      data-swap-holding-input="${escapeHtml(row.token_input_value)}"
    >
      ${escapeHtml(row.label || row.token_value)} · ${escapeHtml(fmtNum(row.amount, 6))}
    </button>
  `).join("");
}

function setSwapAmountFromHolding(fraction) {
  const holding = selectedFromHolding();
  if (!holding) {
    const helper = $("swapAmountHelper");
    if (helper) helper.textContent = "No fresh balance found for this token.";
    return;
  }
  if (swapBalancesStaleAfterSubmit) {
    const helper = $("swapAmountHelper");
    if (helper) helper.textContent = "Balances may have changed after the last swap — refresh balances to use 50% or MAX.";
    renderSwapFromBalance();
    return;
  }
  if (!isSwapBalanceSnapshotFresh(holding.balance_ts)) {
    const helper = $("swapAmountHelper");
    if (helper) helper.textContent = "Refresh balances to use 50% or MAX.";
    renderSwapFromBalance();
    return;
  }

  let amount = holding.amount * fraction;
  const label = normalizeSwapAssetKey(holding.label || holding.token_value);
  if (fraction === 1 && label === "SOL") {
    amount = Math.max(0, holding.amount - defaultSwapSolReserveForMax());
  }
  $("swapAmount").value = amount > 0 ? String(Number(amount.toFixed(9))) : "";
  clearSwapQuoteFreshness();
  updateLiveSwapBaseline();
  renderSwapFromBalance();
}

function defaultSwapSolReserveForMax() {
  return SWAP_DEFAULT_NETWORK_FEE_SOL + SWAP_SOL_FEE_ACCOUNT_SETUP_BUFFER_SOL;
}

function openSwapHoldingsDropdown() {
  const box = $("swapHoldingsDropdown");
  if (!box) return;
  renderSwapHoldingsDropdown();
  box.style.display = "block";
}

function looksLikeSolanaMint(value) {
  return /^[1-9A-HJ-NP-Za-km-z]{32,44}$/.test(String(value || "").trim());
}

function currentTokenDisplay(side) {
  const input = $(side === "from" ? "swapFromToken" : "swapToToken");
  return (input?.value || "").trim();
}

function tokenModalRowHtml({label, sub, amount, action="Select", tokenValue="", tokenInputValue="", mint="", symbol="", source=""}) {
  return `
    <button
      type="button"
      class="token-modal-row"
      data-token-modal-select="true"
      data-token-value="${escapeHtml(tokenValue || label || symbol || mint)}"
      data-token-input-value="${escapeHtml(tokenInputValue || tokenValue || symbol || mint || label)}"
      data-token-mint="${escapeHtml(mint || "")}"
      data-token-symbol="${escapeHtml(symbol || label || "")}"
      data-token-source="${escapeHtml(source || "")}"
    >
      <span>
        <span class="token-modal-row-main">${escapeHtml(label || symbol || tokenValue || "Token")}</span>
        ${sub ? `<span class="token-modal-row-sub">${escapeHtml(sub)}</span>` : ""}
      </span>
      <span class="muted">${escapeHtml(amount || action)}</span>
    </button>
  `;
}

function tokenModalCommonRows(query) {
  const q = normalizeSwapAssetKey(query);
  const seen = new Set();
  return swapTokenList
    .filter((token) => {
      const symbol = String(token?.symbol || "").trim();
      if (!symbol) return false;
      const haystack = [
        symbol,
        token?.display_name,
        token?.name,
        token?.mint,
        token?.asset_key,
        token?.asset
      ].map((item) => normalizeSwapAssetKey(item)).join(" ");
      return !q || haystack.includes(q);
    })
    .filter((token) => {
      const key = normalizeSwapAssetKey(token?.mint || token?.symbol);
      if (!key || seen.has(key)) return false;
      seen.add(key);
      return true;
    })
    .slice(0, 12)
    .map((token) => tokenModalRowHtml({
      label: token.symbol || token.display_name,
      sub: token.mint ? shortenMiddle(String(token.mint), 6, 6) : (token.display_name || token.name || ""),
      tokenValue: token.symbol || token.mint,
      tokenInputValue: token.symbol || token.mint,
      mint: token.mint || "",
      symbol: token.symbol || "",
      source: token.source || "saved"
    }))
    .join("");
}

function tokenModalBalanceRows(query) {
  const q = normalizeSwapAssetKey(query);
  const rows = portfolioBalanceRows().filter((row) => row.amount > 0.0000000001).filter((row) => {
    if (!q) return true;
    return [
      row.label,
      row.asset,
      row.mint,
      row.token_input_value,
      row.token_value
    ].map((item) => normalizeSwapAssetKey(item)).some((value) => value.includes(q));
  });
  if (!rows.length) return "<div class='muted token-modal-row-sub'>No non-zero wallet balances found.</div>";
  return rows.slice(0, 12).map((row) => tokenModalRowHtml({
    label: row.label || row.token_value,
    sub: row.mint ? shortenMiddle(String(row.mint), 6, 6) : row.asset,
    amount: fmtNum(row.amount, 6),
    tokenValue: row.token_value,
    tokenInputValue: row.token_input_value,
    mint: row.mint || "",
    symbol: row.label || "",
    source: "balance"
  })).join("");
}

function renderTokenModalExternalResult(query) {
  const value = String(query || "").trim();
  if (!looksLikeSolanaMint(value)) return "";

  if (tokenModalResolvedExternalToken?.mint === value) {
    const token = tokenModalResolvedExternalToken;
    const symbol = token.symbol || token.display_name || "External token";
    const mint = shortenMiddle(String(token.mint), 6, 6);
    return `
      <div class="token-modal-section">
        <div class="muted" style="font-weight:600;">External token found</div>
        <div class="token-modal-row" style="cursor:default;">
          <span>
            <span class="token-modal-row-main">${escapeHtml(symbol)}</span>
            <span class="token-modal-row-sub">${escapeHtml(mint)} · Unverified token metadata</span>
          </span>
          <button type="button" class="secondary token-modal-action" data-token-modal-import="true">Import token</button>
        </div>
      </div>
    `;
  }

  if (tokenModalResolvedExternalToken === false) {
    return `
      <div class="token-modal-section">
        <div class="muted" style="font-weight:600;">External token found</div>
        <div class="muted token-modal-row-sub">Token metadata unavailable.</div>
      </div>
    `;
  }

  return `
    <div class="token-modal-section">
      <div class="muted" style="font-weight:600;">External token found</div>
      <div class="muted token-modal-row-sub">Resolving token metadata...</div>
    </div>
  `;
}

function renderSwapTokenModal() {
  const body = $("swapTokenModalBody");
  if (!body) return;
  const sideLabel = activeTokenSide === "from" ? "You sell" : "You buy";
  const isMintSearch = looksLikeSolanaMint(tokenSearchQuery);
  const externalResultHtml = renderTokenModalExternalResult(tokenSearchQuery);
  const balancesHtml = `
    <div class="token-modal-section">
      <div class="muted" style="font-weight:600;">Your balances</div>
      ${tokenModalBalanceRows(tokenSearchQuery)}
    </div>
  `;
  const commonHtml = isMintSearch
    ? ""
    : `
    <div class="token-modal-section">
      <div class="muted" style="font-weight:600;">Common tokens / Saved tokens</div>
      ${tokenModalCommonRows(tokenSearchQuery) || "<div class='muted token-modal-row-sub'>No saved tokens match this search.</div>"}
    </div>
  `;

  body.innerHTML = `
    <div class="muted" style="margin-top:8px;">Selecting for ${escapeHtml(sideLabel)}</div>
    ${isMintSearch ? externalResultHtml + balancesHtml : balancesHtml + commonHtml}
  `;
}

async function resolveTokenModalQuery() {
  const query = tokenSearchQuery;
  tokenModalResolvedExternalToken = null;
  if (!looksLikeSolanaMint(query)) {
    renderSwapTokenModal();
    return;
  }
  renderSwapTokenModal();
  let res;
  try {
    res = await fetchMaybeJson("/tokens/resolve?" + qs({ query, allow_external: true }));
  } catch (err) {
    tokenModalResolvedExternalToken = false;
    renderSwapTokenModal();
    return;
  }
  if (query !== tokenSearchQuery) return;
  tokenModalResolvedExternalToken = res.ok && res.data?.ok && res.data?.token
    ? res.data.token
    : false;
  renderSwapTokenModal();
}

function scheduleTokenModalResolve() {
  clearTimeout(tokenModalResolveTimerId);
  tokenModalResolveTimerId = setTimeout(resolveTokenModalQuery, 350);
}

function openSwapTokenModal(side) {
  activeTokenSide = side === "to" ? "to" : "from";
  tokenSearchQuery = "";
  tokenModalResolvedExternalToken = null;
  const backdrop = $("swapTokenModalBackdrop");
  const search = $("swapTokenModalSearch");
  if (!backdrop || !search) return;
  search.value = "";
  renderSwapTokenModal();
  backdrop.classList.add("is-open");
  backdrop.setAttribute("aria-hidden", "false");
  setTimeout(() => search.focus(), 0);
}

function closeSwapTokenModal() {
  const backdrop = $("swapTokenModalBackdrop");
  if (!backdrop) return;
  backdrop.classList.remove("is-open");
  backdrop.setAttribute("aria-hidden", "true");
}

function applySwapTokenSelection(side, token) {
  const input = $(side === "from" ? "swapFromToken" : "swapToToken");
  if (!input) return;

  const mint = String(token?.mint || "").trim();
  const symbol = String(token?.symbol || token?.label || "").trim();
  const inputValue = String(token?.tokenInputValue || token?.tokenValue || symbol || mint || "").trim();
  const displayValue = symbol || inputValue;

  input.value = displayValue;
  if (mint && symbol) {
    input.dataset.selectedMint = mint;
    input.dataset.selectedSymbol = symbol;
  } else {
    delete input.dataset.selectedMint;
    delete input.dataset.selectedSymbol;
  }

  resetSwapStateForTokenChange({ clearAmount: side === "from" });
  if (mint) {
    swapSelectedRecognizedTokenMint[side] = mint;
  } else {
    resetResolvedSwapTokenSelection(side);
  }
  resolveSwapTokenInput(side);
  if (side === "from") {
    renderSwapFromBalance();
    renderSwapHoldingsDropdown();
  }
  updateLiveSwapBaseline();
  closeSwapTokenModal();
}

function importTokenModalExternalToken() {
  const token = tokenModalResolvedExternalToken;
  if (!token || token === false) return;
  swapTokenResolveState[activeTokenSide] = token;
  useResolvedSwapToken(activeTokenSide);
  closeSwapTokenModal();
}









function setSwapPhase(phase, text) {
  const pill = $("pillSwapState");
  const line = $("swapStateText");

  pill.textContent = phase;

  let kind = "warn";
  const p = String(phase || "").toLowerCase();

  if (p === "ready") kind = "ok";
  else if (p === "quoted") kind = "ok";
  else if (p === "failed") kind = "err";
  else kind = "warn";

  pill.className = "pill " + kind;
  line.textContent = text || "";
}

function showSwapStatus(kind, title, payload) {
  const box = $("swapStatus");
  box.style.display = "block";
  box.className = "card " + (kind === "ok" ? "ok" : (kind === "warn" ? "warn" : "err"));
  box.innerHTML = "<strong>" + title + "</strong>";
  if (payload) {
    box.innerHTML += "<pre style='margin-top:8px;'>" + escapeHtml(JSON.stringify(payload, null, 2)) + "</pre>";
  }

  logActivity(kind, title, payload);
}

function setSwapExecutionStatus(state, text, detail = null) {
  swapExecutionState = state || "idle";
  const box = $("swapExecutionStatus");
  if (!box) return;

  if (!text) {
    box.textContent = "";
    box.style.display = "none";
    box.className = "muted";
    return;
  }

  const kind =
    swapExecutionState === "prepared" ||
    swapExecutionState === "submitted" ||
    swapExecutionState === "confirmed"
      ? "ok"
      : swapExecutionState === "failed"
        ? "err"
        : "warn";

  box.className = "muted " + kind;
  box.textContent = detail ? text + " " + detail : text;
  box.style.display = "block";
}

function sanitizeSwapPreflightDebug(value) {
  if (Array.isArray(value)) {
    return value.map((item) => sanitizeSwapPreflightDebug(item));
  }
  if (!value || typeof value !== "object") {
    return value;
  }

  const out = {};
  for (const [key, item] of Object.entries(value)) {
    const lowered = String(key || "").toLowerCase();
    if (
      lowered.includes("transaction_base64") ||
      lowered.includes("signed_transaction") ||
      lowered.includes("rpc_url") ||
      lowered.includes("api_key") ||
      lowered.includes("apikey") ||
      lowered.includes("secret")
    ) {
      continue;
    }
    out[key] = sanitizeSwapPreflightDebug(item);
  }
  return out;
}

function renderSwapPreflightDebug(response) {
  const wrap = $("swapDebugWrap");
  const box = $("swapPreflightDebug");
  const visibleBox = $("swapVisiblePreflightDebug");
  if (!wrap || !box || !visibleBox) return;

  latestSwapPreflightResponse = sanitizeSwapPreflightDebug(response || null);
  if (!latestSwapPreflightResponse) {
    box.textContent = "No preflight check yet.";
    visibleBox.textContent = "No preflight check yet.";
    return;
  }

  wrap.style.display = "block";
  const debugJson = JSON.stringify(latestSwapPreflightResponse, null, 2);
  box.textContent = debugJson;
  visibleBox.textContent = debugJson;
  console.debug("swap preflight", latestSwapPreflightResponse);
}

function clearSwapQuoteFreshness() {
  if (swapQuoteTimerId) {
    clearInterval(swapQuoteTimerId);
    swapQuoteTimerId = null;
  }
  swapQuoteExpiresAt = null;
  const box = $("swapQuoteFreshness");
  if (box) {
    box.textContent = "";
    box.style.display = "none";
    box.className = "muted";
  }
}

function isSwapQuoteExpired() {
  return !!swapQuoteExpiresAt && Date.now() >= swapQuoteExpiresAt;
}

function updateSwapQuoteFreshness() {
  const box = $("swapQuoteFreshness");
  if (!box || !swapQuoteExpiresAt) return;

  const remaining = Math.max(0, Math.ceil((swapQuoteExpiresAt - Date.now()) / 1000));
  box.style.display = "block";
  if (remaining > 0) {
    box.className = "muted warn";
    box.textContent = "Quote expires in " + remaining + "s";
    return;
  }

  box.className = "muted err";
  box.textContent = "Quote expired — preview again before swapping.";
  if (swapQuoteTimerId) {
    clearInterval(swapQuoteTimerId);
    swapQuoteTimerId = null;
  }
  setSwapPreparedActionVisible(false);
}

function startSwapQuoteFreshnessTimer() {
  clearSwapQuoteFreshness();
  swapQuoteExpiresAt = Date.now() + SWAP_QUOTE_TTL_SECONDS * 1000;
  updateSwapQuoteFreshness();
  swapQuoteTimerId = setInterval(updateSwapQuoteFreshness, 1000);
}

function setSwapPreparedActionVisible(visible) {
  const box = $("swapPreparedAction");
  if (!box) return;
  box.style.display = visible ? "block" : "none";
  if (!visible) {
    const summary = $("swapPreparedSummary");
    const ack = $("swapSignAcknowledgement");
    const button = $("btnSignPreparedSwap");
    if (summary) summary.textContent = "";
    if (ack) ack.checked = false;
    if (button) button.disabled = true;
  } else {
    updateSwapSignButtonState();
  }
}

function updateSwapSignButtonState() {
  const ack = $("swapSignAcknowledgement");
  const button = $("btnSignPreparedSwap");
  if (!button) return;
  button.disabled = !(latestPreparedSwap && ack?.checked);
}

function renderPreparedSwapSummary(prepared) {
  const box = $("swapPreparedSummary");
  if (!box) return;

  const summary = prepared?.quote_summary || {};
  const routeLabel = prepared?.execution_surface_label || summary.provider_label || "Jupiter";
  const lines = [];
  lines.push(`<div style="font-weight:600; color:#e5eefb;">Prepared swap</div>`);
  lines.push(`<div>Route: ${escapeHtml(routeLabel)}</div>`);

  if (summary.from_token || summary.amount != null) {
    const amount = summary.amount != null ? fmtNum(Number(summary.amount), 6) : "n/a";
    const fromToken = summary.from_token || "";
    lines.push(`<div>From: ${escapeHtml(amount)} ${escapeHtml(fromToken)}</div>`);
  }

  if (summary.to_token) {
    lines.push(`<div>To: ${escapeHtml(summary.to_token)}</div>`);
  }

  if (summary.estimated_output != null) {
    const out = fmtNum(Number(summary.estimated_output), 6);
    lines.push(`<div>Estimated receive: ${escapeHtml(out)} ${escapeHtml(summary.to_token || "")}</div>`);
  }

  if (summary.min_received != null) {
    const min = fmtNum(Number(summary.min_received), 6);
    lines.push(`<div>Minimum receive: ${escapeHtml(min)} ${escapeHtml(summary.to_token || "")}</div>`);
  }

  if (summary.slippage_bps != null) {
    lines.push(`<div>Slippage: ${escapeHtml(String(summary.slippage_bps))} bps</div>`);
  }

  lines.push(`<div>Network: Solana mainnet</div>`);
  lines.push(`<div style="margin-top:6px;">Phantom may require extra SOL for network fees or account setup beyond the entered amount.</div>`);
  lines.push(`<div style="margin-top:6px;">This is a real mainnet transaction. Review in Phantom before signing.</div>`);

  box.innerHTML = lines.join("");
}

function resetSwapExecutionPrepare() {
  latestPreparedSwap = null;
  latestSwapPreflightResponse = null;
  const preflightDebug = $("swapPreflightDebug");
  if (preflightDebug) preflightDebug.textContent = "No preflight check yet.";
  const visiblePreflightDebug = $("swapVisiblePreflightDebug");
  if (visiblePreflightDebug) visiblePreflightDebug.textContent = "No preflight check yet.";
  setSwapPreparedActionVisible(false);
  setSwapExecutionStatus("idle", "Ready to prepare a swap route.");
}

function resetSwapStateForTokenChange(options = {}) {
  if (options.clearAmount) {
    const amountInput = $("swapAmount");
    if (amountInput) amountInput.value = "";
  }
  resetSwapQuoteDisplay();
  resetSwapInlineBaseline();
}

function clearSwapUi() {
  $("swapAmount").value = "";
  $("swapDebugWrap").style.display = "none";
  $("swapQuotePreview").textContent = "";
  $("swapPreflightDebug").textContent = "No preflight check yet.";
  $("swapVisiblePreflightDebug").textContent = "No preflight check yet.";
  $("swapStatus").style.display = "none";
  latestSwapQuoteResponse = null;
  latestSwapPreflightResponse = null;
  setTokenResolvePreview("from", null, "");
  setTokenResolvePreview("to", null, "");
  resetHolderConcentration({ hideButton: true });
  setSwapPhase("Draft", "Ready to request a swap quote.");
  resetSwapQuoteDisplay();
  resetSwapExecutionPrepare();
  resetSwapInlineBaseline();
}



async function updateLiveSwapBaseline() {
  const fromToken = canonicalSwapTokenQuery("from");
  const toToken = canonicalSwapTokenQuery("to");
  const rawAmount = ($("swapAmount").value || "").trim();
  const amount = Number(rawAmount);

  if (!rawAmount || !Number.isFinite(amount) || amount <= 0 || fromToken === toToken) {
    resetSwapInlineBaseline();
    return;
  }

  const url =
    "/swap/inline-baseline?" +
    qs({
      from_token: fromToken,
      to_token: toToken,
      amount: amount,
      network: "solana"
    });

  let res;
  try {
    res = await fetchMaybeJson(url);
  } catch (err) {
    resetSwapInlineBaseline();
    $("swapBaselineNote").textContent = "Live baseline unavailable right now.";
    return;
  }

  if (!res.ok || !res.data?.ok || !res.data?.inline_baseline) {
    resetSwapInlineBaseline();
    $("swapBaselineNote").textContent = "Live baseline unavailable right now.";
    return;
  }

  renderSwapInlineBaseline(res.data.inline_baseline, null);
}



function resetSwapInlineBaseline() {
  const spend = $("swapSpendValueHint");
  const ideal = $("swapIdealOutputHint");
  const delta = $("swapBaselineDeltaHint");
  const compare = $("swapMarketCompareHint");
  const note = $("swapBaselineNote");
  const buyEstimate = $("swapBuyEstimate");
  const sellValue = $("swapSellValueEstimate");
  const buyValue = $("swapBuyValueEstimate");

  if (spend) spend.textContent = "—";
  if (ideal) ideal.textContent = "Preview Quote";
  if (delta) delta.textContent = "—";
  if (compare) compare.textContent = "—";
  if (note) note.textContent = "Reference pricing is used only to compare route quality — not an executable route.";
  if (buyEstimate) buyEstimate.textContent = "Preview quote";
  if (sellValue) sellValue.textContent = "USD estimate: —";
  if (buyValue) buyValue.textContent = "Reference estimate before preview.";
}



function formatUtcTimestamp(ts) {
  if (!ts) return null;

  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return ts;

  const yyyy = d.getUTCFullYear();
  const mm = String(d.getUTCMonth() + 1).padStart(2, "0");
  const dd = String(d.getUTCDate()).padStart(2, "0");
  const hh = String(d.getUTCHours()).padStart(2, "0");
  const min = String(d.getUTCMinutes()).padStart(2, "0");

  return `${yyyy}-${mm}-${dd} ${hh}:${min} UTC`;
}




function renderSwapInlineBaseline(baseline, delta = null) {
  const spend = $("swapSpendValueHint");
  const ideal = $("swapIdealOutputHint");
  const deltaLine = $("swapBaselineDeltaHint");
  const compareLine = $("swapMarketCompareHint");
  const note = $("swapBaselineNote");
  const sellValue = $("swapSellValueEstimate");
  const buyEstimate = $("swapBuyEstimate");
  const buyValue = $("swapBuyValueEstimate");

  if (!baseline) {
    resetSwapInlineBaseline();
    return;
  }

  const inputAmount =
    baseline.input_amount == null ? "—" : fmtNum(Number(baseline.input_amount), 6);
  const inputToken = baseline.input_token || "";
  const inputUsd =
    baseline.input_usd_value == null
      ? null
      : fmtUsdCost(Number(baseline.input_usd_value));

  const idealOut =
    baseline.ideal_output_amount == null
      ? null
      : fmtNum(Number(baseline.ideal_output_amount), 6);

  const outputToken = baseline.output_token || "";
  const outputUsd =
    baseline.output_usd_value == null
      ? null
      : fmtUsdCost(Number(baseline.output_usd_value));
  const uncertainUsdText = "USD estimate unavailable / reference uncertain";
  const inputUsdText = inputUsd || uncertainUsdText;
  const outputUsdText = outputUsd || uncertainUsdText;

  if (spend) {
    spend.textContent = inputAmount + " " + inputToken + " ≈ " + inputUsdText;
  }
  if (sellValue) {
    sellValue.textContent = "≈ " + inputUsdText;
  }

  function referenceSourceLabel(_source) {
    return "Market reference";
  }

  if (ideal) {
    if (delta && idealOut && delta.output_diff_abs != null) {
      const bestOut = Number(baseline.ideal_output_amount) + Number(delta.output_diff_abs);
      const bestUsd = Number.isFinite(Number(baseline.output_usd_price))
        ? bestOut * Number(baseline.output_usd_price)
        : null;
      const bestUsdText = Number.isFinite(bestUsd) ? fmtUsdCost(bestUsd) : uncertainUsdText;
      ideal.textContent = "~" + fmtNum(bestOut, 6) + " " + outputToken + " ≈ " + bestUsdText;
      if (buyEstimate) {
        buyEstimate.textContent = "~" + fmtNum(bestOut, 6) + " " + outputToken;
      }
      if (buyValue) {
        buyValue.textContent = "≈ " + bestUsdText;
      }
    } else {
      ideal.textContent = "Preview Quote to compare routes";
      if (buyEstimate) {
        buyEstimate.textContent = idealOut ? "~" + idealOut + " " + outputToken : "Preview quote";
      }
      if (buyValue) {
        buyValue.textContent = idealOut
          ? "≈ " + outputUsdText + " · Reference estimate before preview"
          : "Reference estimate before preview.";
      }
    }
  }

  if (deltaLine) {
    deltaLine.textContent = idealOut
      ? "~" + idealOut + " " + outputToken + " ≈ " + outputUsdText
      : "—";
  }

  if (compareLine) {
    if (delta && (delta.output_diff_abs != null || delta.output_diff_pct != null)) {
      const rawPct = Number(delta.output_diff_pct);
      if (Number.isFinite(rawPct)) {
        const direction = rawPct >= 0 ? "above" : "below";
        compareLine.textContent = "~" + fmtNum(Math.abs(rawPct), 4) + "% " + direction;
      } else {
        compareLine.textContent = "Unavailable";
      }
    } else {
      compareLine.textContent = "Preview live routes to compare.";
    }
  }

  if (note) {
    const source = baseline.pricing_source;
    const ts = baseline.pricing_ts;
    const tsUtc = formatUtcTimestamp(ts);

    if (source === "dexscreener_solana") {
      note.textContent = tsUtc
        ? "Reference source: DexScreener market price at " + tsUtc + ". Used only to compare route quality — not an executable route."
        : "Reference source: DexScreener market price. Used only to compare route quality — not an executable route.";
    } else if (source === "jupiter_price_v3") {
      note.textContent = tsUtc
        ? "Reference source: Jupiter Price V3 market price at " + tsUtc + ". Used only to compare route quality — not an executable route."
        : "Reference source: Jupiter Price V3 market price. Used only to compare route quality — not an executable route.";
    } else if (source === "coingecko_simple_price") {
      note.textContent = tsUtc
        ? "Reference source: CoinGecko market price at " + tsUtc + ". Used only to compare route quality — not an executable route."
        : "Reference source: CoinGecko market price. Used only to compare route quality — not an executable route.";
    } else if (source === "sqlite_usd_snapshots") {
      note.textContent = tsUtc
        ? "Reference source: cached USD price snapshot at " + tsUtc + ". Used only to compare route quality — not an executable route."
        : "Reference source: cached USD price snapshot. Used only to compare route quality — not an executable route.";
    }
  }
}



function resetSwapQuoteDisplay() {
  latestSwapQuoteResponse = null;
  clearSwapQuoteFreshness();
  $("swapRecommendation").textContent = "";
  $("swapCompareSummary").textContent = "";
  $("swapRecommendation").style.display = "none";
  $("swapCompareSummary").style.display = "none";
  const coverage = $("swapCoverageDepth");
  if (coverage) {
    coverage.textContent = "";
    coverage.style.display = "none";
  }
  const externalNotice = $("swapExternalTokenNotice");
  if (externalNotice) {
    externalNotice.textContent = "";
    externalNotice.style.display = "none";
  }
  $("swapRecommendedBox").innerHTML = "<div class='muted'>No quote yet.</div>";
  $("swapAlternativesCard").style.display = "none";
  $("swapAlternativesBox").innerHTML = "<div class='muted'>No alternatives yet.</div>";
  $("swapDirectBox").innerHTML = "<div class='muted'>No direct-route check yet.</div>";
  $("swapDebugWrap").style.display = "none";
  $("swapQuotePreview").textContent = "";
  resetSwapExecutionPrepare();
}



function getSwapHttpErrorInfo(status, data, rawText) {
  const detail =
    data?.detail ||
    data?.message ||
    rawText ||
    "Unknown quote error";
  const detailText = typeof detail === "object"
    ? JSON.stringify(detail)
    : String(detail);

  const d = detailText.toLowerCase();

  if (status === 400) {
    if (d.includes("token_resolution_failed")) {
      return {
        title: "Token metadata resolution failed",
        phase: "Could not resolve token metadata for quote preview.",
        kind: "warn"
      };
    }
    if (d.includes("token_metadata_incomplete") || d.includes("decimals")) {
      return {
        title: "Token decimals unresolved",
        phase: "Token metadata found, but decimals are unresolved. Quote preview is not safe yet.",
        kind: "warn"
      };
    }
    if (d.includes("unsupported token")) {
      return {
        title: "Unsupported pair",
        phase: "This token pair is not supported yet in the app.",
        kind: "warn"
      };
    }
    if (d.includes("must be different")) {
      return {
        title: "Invalid pair",
        phase: "Choose two different tokens.",
        kind: "warn"
      };
    }
    if (d.includes("amount")) {
      return {
        title: "Invalid amount",
        phase: "Enter a valid amount greater than 0.",
        kind: "warn"
      };
    }
    if (d.includes("route") || d.includes("could not find")) {
      return {
        title: "No route found",
        phase: "No swap route was found for this request.",
        kind: "warn"
      };
    }
    return {
      title: "Quote request invalid",
      phase: "The quote request could not be accepted.",
      kind: "warn"
    };
  }

  if (status === 401 || status === 403) {
    return {
      title: "Quote provider authorization failed",
      phase: "The quote provider rejected the request.",
      kind: "err"
    };
  }

  if (status === 404) {
    return {
      title: "No route found",
      phase: "No swap route was found for this request.",
      kind: "warn"
    };
  }

  if (status === 408 || status === 504) {
    return {
      title: "Quote request timed out",
      phase: "The quote provider took too long to respond.",
      kind: "warn"
    };
  }

  if (status === 429) {
    return {
      title: "Quote provider busy",
      phase: "The quote provider is rate-limited or temporarily busy.",
      kind: "warn"
    };
  }

  if (status === 500 || status === 502 || status === 503) {
    return {
      title: "Quote provider unavailable",
      phase: "The quote provider is temporarily unavailable.",
      kind: "err"
    };
  }

  return {
    title: "Swap preview failed",
    phase: "The quote request could not be completed.",
    kind: "warn"
  };
}

function getSwapThrownErrorInfo(err) {
  const msg =
    err?.message ||
    err?.toString?.() ||
    "Unknown network error";

  const m = String(msg).toLowerCase();

  if (m.includes("abort") || m.includes("timeout")) {
    return {
      title: "Quote request timed out",
      phase: "The quote request timed out before a response arrived.",
      kind: "warn"
    };
  }

  if (m.includes("failed to fetch") || m.includes("networkerror")) {
    return {
      title: "Network or provider error",
      phase: "The app could not reach the quote provider.",
      kind: "err"
    };
  }

  return {
    title: "Quote request failed",
    phase: "The quote request failed unexpectedly.",
    kind: "warn"
  };
}



const SWAP_EXECUTABLE_PROVIDERS = new Set([
  "jupiter-metis",
  "raydium-trade-api",
  "orca-whirlpool",
  "meteora-dlmm",
  "pumpswap"
]);

const SWAP_EXECUTABLE_VARIANTS = {
  "jupiter-metis": new Set([
    "recommended_default",
    "broader_search",
    "exclude_recommended_dexes",
    "direct_route_check"
  ]),
  "raydium-trade-api": new Set(["raydium_quote"]),
  "orca-whirlpool": new Set(["orca_whirlpool_quote"]),
  "meteora-dlmm": new Set(["meteora_dlmm_quote"]),
  "pumpswap": new Set(["pumpswap_quote"])
};

function isExecutableRouteOption(opt) {
  const provider = opt?.provider || "";
  const supportedVariants = SWAP_EXECUTABLE_VARIANTS[provider];
  return (
    SWAP_EXECUTABLE_PROVIDERS.has(provider) &&
    supportedVariants?.has(opt?.variant_id) === true &&
    opt?.execution_readiness?.execution_ready === true &&
    opt?.execution_readiness?.prepare_capable === true &&
    opt?.execution_readiness?.submit_capable === true &&
    opt?.is_clickable === true &&
    opt?.is_comparison_only !== true &&
    opt?.execution_status === "executable_capable" &&
    !!opt?.variant_id
  );
}

function executableRouteButtonLabel(opt) {
  if (opt?.provider === "raydium-trade-api") return "Swap via Raydium";
  if (opt?.provider === "orca-whirlpool") return "Swap via Orca";
  if (opt?.provider === "meteora-dlmm") return "Swap via Meteora";
  if (opt?.provider === "pumpswap") return "Swap via PumpSwap";
  return "Swap this route";
}

function renderRouteActionButton(label, opt, cardRole) {
  if (!isExecutableRouteOption(opt)) return "";

  return `
    <button
      type="button"
      class="secondary"
      style="min-width:160px;"
      data-swap-execute="true"
      data-provider="${escapeHtml(opt.provider)}"
      data-variant-id="${escapeHtml(opt.variant_id)}"
      data-card-role="${escapeHtml(cardRole || opt.kind || "route")}"
    >
      ${escapeHtml(label || executableRouteButtonLabel(opt))}
    </button>
  `;
}

function swapExecutionReadinessReasonLabel(reason) {
  const labels = {
    NON_JUPITER_ROUTE: "Quote-only route.",
    COMPARISON_ONLY_ROUTE: "Comparison-only route.",
    TOKEN_DECIMALS_UNAVAILABLE: "Token decimals unavailable.",
    UNSUPPORTED_NETWORK: "Unsupported network.",
    UNSUPPORTED_VARIANT: "Unsupported execution variant.",
    NOT_CLICKABLE: "Route is not executable yet."
  };
  return labels[reason] || "Quote-only route.";
}

function renderSwapExecutionReadinessLine(opt) {
  const readiness = opt?.execution_readiness || null;
  if (readiness?.execution_ready === true) {
    return "";
  }

  const providerStatus = readiness?.provider_status || "";
  const statusLabels = {
    execution_research: "Quote-only",
    benchmark_quote_only: "Benchmark",
    advanced_research: "Quote-only"
  };
  if (statusLabels[providerStatus]) {
    return `
      <div class="muted" style="margin-top:4px;">
        ${escapeHtml(statusLabels[providerStatus])}
      </div>
    `;
  }

  const reason = Array.isArray(readiness?.reasons) ? readiness.reasons[0] : null;
  if (!reason) return "";

  return `
    <div class="muted" style="margin-top:4px;">
      Quote-only: ${escapeHtml(swapExecutionReadinessReasonLabel(reason))}
    </div>
  `;
}

function surfaceRouteLabel(opt) {
  return opt?.execution_surface_label
    ? `Via ${opt.execution_surface_label}`
    : (opt?.route_label || "unknown-route");
}

function swapOptionCardTitle(opt, opts = {}) {
  if (opts.title) return opts.title;

  const kind = String(opt?.kind || "");

  if (opt?.provider === "phantom-routing-api") return "Benchmark";
  if (kind === "recommended" && opt?.is_comparison_only === true) return "Best quote";
  if (kind === "recommended") return "Recommended executable route";
  if (kind === "direct") return "Direct/simple route check";

  return opt?.label || opt?.execution_surface_label || "Route";
}

function shouldShowSwapOptionCardTitle(opt, opts = {}) {
  const kind = String(opt?.kind || "");
  return !(kind === "recommended" || kind === "direct");
}

function tokenListSymbolForMint(mint) {
  if (!mint) return "";
  const match = swapTokenList.find((token) => token?.mint === mint);
  return match?.symbol || "";
}

function routeTokenLabelFromMint(mint, opt, fallbackLabel = "") {
  if (!mint) return "";

  const steps = Array.isArray(opt?.route_steps) ? opt.route_steps : [];
  const firstInput = steps.length ? steps[0]?.input_mint : null;
  const lastOutput = steps.length ? steps[steps.length - 1]?.output_mint : null;

  if (mint === firstInput && opt?.from_token) return opt.from_token;
  if (mint === lastOutput && opt?.to_token) return opt.to_token;

  const knownLabel = mintLabel(mint);
  if (knownLabel !== shortenMiddle(String(mint), 4, 4)) return knownLabel;
  return fallbackLabel || knownLabel;
}

function cleanContinuousRouteMints(opt) {
  const steps = Array.isArray(opt?.route_steps) ? opt.route_steps : [];
  if (steps.length < 2) return null;

  const mints = [];
  for (const [idx, step] of steps.entries()) {
    const inputMint = step?.input_mint;
    const outputMint = step?.output_mint;

    if (!inputMint || !outputMint) return null;

    if (idx === 0) {
      mints.push(inputMint);
    } else if (mints[mints.length - 1] !== inputMint) {
      return null;
    }

    mints.push(outputMint);
  }

  return mints;
}

function formatCleanRoutePath(opt) {
  const routeMints = cleanContinuousRouteMints(opt);
  if (!routeMints || routeMints.length !== 3) return null;

  const firstInput = routeMints[0];
  const middleMint = routeMints[1];
  const lastOutput = routeMints[2];

  const fromLabel = opt?.from_token || routeTokenLabelFromMint(firstInput, opt);
  const middleLabel = routeTokenLabelFromMint(middleMint, opt, "intermediate token");
  const toLabel = opt?.to_token || routeTokenLabelFromMint(lastOutput, opt);

  if (!fromLabel || !middleLabel || !toLabel) return null;
  return `${fromLabel} -> ${middleLabel} -> ${toLabel}`;
}

function renderRouteShapeLine(opt, compact = false) {
  const routeShape = opt?.route_shape || "unknown";
  const routeSteps = Array.isArray(opt?.route_steps)
    ? opt.route_steps.length
    : Number(opt?.route_step_count || 0);
  const cleanRoutePath = formatCleanRoutePath(opt);
  const margin = compact ? "2px" : "4px";

  if (cleanRoutePath) {
    return `
      <div class="muted" style="margin-top:${margin};">
        ${escapeHtml(cleanRoutePath)}
      </div>
      <div class="muted" style="margin-top:2px;">
        two-hop · Steps: ${escapeHtml(String(routeSteps))}
      </div>
    `;
  }

  if (compact) {
    const shapeText =
      routeSteps > 1
        ? `${routeSteps}-step path`
        : (routeShape === "single-path" || routeShape === "direct")
          ? "single-path"
          : routeShape;

    return `
      <div class="muted" style="margin-top:2px;">
        ${escapeHtml(shapeText)}
      </div>
    `;
  }

  return `
    <div class="muted" style="margin-top:4px;">
      ${escapeHtml(routeShape)} · Steps: ${escapeHtml(String(routeSteps))}
    </div>
  `;
}

function collectLiveRouteCoverageLabels(quote) {
  const candidates = [
    quote?.recommended_option || quote?.recommended || quote?.best_quote_option || null,
    quote?.direct_route_check || null,
    quote?.recommended_executable_option || null,
    ...(Array.isArray(quote?.other_options) ? quote.other_options : [])
  ];

  const labels = [];
  const seen = new Set();

  for (const opt of candidates) {
    if (!opt || opt.quote_status !== "live") continue;

    const label = opt.execution_surface_label || opt.route_label || opt.provider;
    if (!label) continue;

    const key = String(label).trim().toLowerCase();
    if (!key || seen.has(key)) continue;

    seen.add(key);
    labels.push(String(label).trim());
  }

  return labels;
}

function renderSwapCoverageDepth(quote) {
  const box = $("swapCoverageDepth");
  if (!box) return;

  const labels = collectLiveRouteCoverageLabels(quote);
  if (!labels.length) {
    box.textContent = "";
    box.style.display = "none";
    return;
  }

  const prefix = labels.length <= 2
    ? "Limited live route coverage for this pair: "
    : `${labels.length} live route options checked: `;

  box.textContent = prefix + labels.join(", ");
  box.style.display = "block";
}

function renderSwapExternalTokenNotice(quote) {
  const box = $("swapExternalTokenNotice");
  if (!box) return;

  const tokens = Array.isArray(quote?.external_tokens) ? quote.external_tokens : [];
  if (!tokens.length) {
    box.textContent = "";
    box.style.display = "none";
    return;
  }

  const labels = [];
  const seen = new Set();
  for (const token of tokens) {
    const label = token?.symbol || token?.display_name || token?.mint;
    if (!label) continue;
    const key = String(label).trim().toLowerCase();
    if (!key || seen.has(key)) continue;
    seen.add(key);
    labels.push(String(label).trim());
  }

  if (!labels.length) {
    box.textContent = "";
    box.style.display = "none";
    return;
  }

  box.textContent = "External token metadata used: " + labels.join(", ") + " · unverified. External-token market references may be stale or incomplete. Use quoted output and wallet confirmation as source of truth.";
  box.style.display = "block";
}

function holderConcentrationTokenForSide(side) {
  const token = swapTokenResolveState[side];
  if (!token || !token.mint) return null;
  return token.source !== "registry" ? token : null;
}

function selectedExternalTokenForHolderConcentration() {
  return holderConcentrationTokenForSide("to") || holderConcentrationTokenForSide("from");
}

function resetHolderConcentration(opts = {}) {
  const card = $("holderConcentrationCard");
  const box = $("holderConcentrationBox");
  holderConcentrationMint = null;
  latestHolderConcentrationData = null;
  if (box) {
    box.className = "muted";
    box.textContent = "No holder concentration check yet.";
  }
  if (card) card.style.display = "none";
}

function formatHolderPct(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return "n/a";
  if (Math.abs(n) < 0.0001) return "< 0.0001%";
  if (Math.abs(n) < 0.01) return n.toFixed(4) + "%";
  if (Math.abs(n) < 1) return n.toFixed(3) + "%";
  return n.toFixed(2) + "%";
}

function formatCompactUsd(value) {
  const n = Number(value);
  if (!Number.isFinite(n) || n <= 0) return "";
  if (n >= 1_000_000_000) return "$" + (n / 1_000_000_000).toFixed(n >= 10_000_000_000 ? 0 : 1) + "B";
  if (n >= 1_000_000) return "$" + (n / 1_000_000).toFixed(n >= 10_000_000 ? 0 : 1) + "M";
  if (n >= 1_000) return "$" + (n / 1_000).toFixed(n >= 10_000 ? 0 : 1) + "K";
  return fmtUsdCost(n);
}

function tokenMintMatchesMarketStatsSource(token, source) {
  if (!token?.mint || !source) return false;
  const sourceMint = source?.mint || source?.address || source?.token_mint || source?.tokenMint;
  return !!sourceMint && String(sourceMint).toLowerCase() === String(token.mint).toLowerCase();
}

function tokenMarketStatsValues(source = {}) {
  return {
    liquidity: source?.liquidity_usd ?? source?.liquidity?.usd,
    volume24h: source?.volume_24h ?? source?.volume_h24 ?? source?.volume?.h24,
    fdv: source?.fdv ?? source?.fully_diluted_valuation,
    marketCap: source?.market_cap ?? source?.marketCap
  };
}

function mergeTokenMarketStats(sources = []) {
  const merged = {};
  for (const source of sources) {
    const stats = tokenMarketStatsValues(source || {});
    if (merged.liquidity == null && stats.liquidity != null) merged.liquidity = stats.liquidity;
    if (merged.volume24h == null && stats.volume24h != null) merged.volume24h = stats.volume24h;
    if (merged.fdv == null && stats.fdv != null) merged.fdv = stats.fdv;
    if (merged.marketCap == null && stats.marketCap != null) merged.marketCap = stats.marketCap;
  }
  return merged;
}

function selectedTokenMarketStats() {
  const token = selectedExternalTokenForHolderConcentration();
  const externalTokens = Array.isArray(latestSwapQuoteResponse?.external_tokens)
    ? latestSwapQuoteResponse.external_tokens
    : [];
  const pricingSourceDetail = latestSwapQuoteResponse?.inline_baseline?.pricing_source_detail || {};
  const toTokenDetail = pricingSourceDetail?.to_token || {};
  const fromTokenDetail = pricingSourceDetail?.from_token || {};
  const matchedExternalToken = externalTokens.find((item) => tokenMintMatchesMarketStatsSource(token, item));
  const singleExternalToken = externalTokens.length === 1 ? externalTokens[0] : null;
  const matchedToToken = tokenMintMatchesMarketStatsSource(token, toTokenDetail) ? toTokenDetail : null;
  const matchedFromToken = tokenMintMatchesMarketStatsSource(token, fromTokenDetail) ? fromTokenDetail : null;

  return mergeTokenMarketStats([
    matchedExternalToken,
    !matchedExternalToken ? singleExternalToken : null,
    matchedToToken,
    matchedFromToken,
    token
  ]);
}

function renderTokenMarketStatsLine() {
  const stats = selectedTokenMarketStats();
  const bits = [];
  const liquidity = formatCompactUsd(stats.liquidity);
  const volume = formatCompactUsd(stats.volume24h);
  const fdv = formatCompactUsd(stats.fdv);
  const marketCap = formatCompactUsd(stats.marketCap);
  if (liquidity) bits.push("Liquidity " + liquidity);
  if (volume) bits.push("24h volume " + volume);
  if (fdv) bits.push("FDV " + fdv);
  if (marketCap) bits.push("Mkt cap " + marketCap);
  return bits.length
    ? `<div style="margin-top:6px;">${escapeHtml(bits.join(" · "))}</div>`
    : "";
}

function renderHolderConcentration(data) {
  const card = $("holderConcentrationCard");
  const box = $("holderConcentrationBox");
  if (!card || !box) return;
  latestHolderConcentrationData = data || null;

  const fallbackMint = selectedExternalTokenForHolderConcentration()?.mint || "";
  const fallbackBubblemaps = fallbackMint
    ? "https://v2.bubblemaps.io/map?address=" + encodeURIComponent(fallbackMint) + "&chain=solana"
    : "";
  const bubblemaps = data?.links?.bubblemaps || fallbackBubblemaps;
  const linkHtml = bubblemaps
    ? `<a href="${escapeHtml(bubblemaps)}" target="_blank" rel="noopener">Open Bubblemaps</a>`
    : "Open Bubblemaps unavailable";
  const holderDiagnostics = data?.diagnostics && typeof data.diagnostics === "object"
    ? data.diagnostics
    : {};
  const holderDiagnosticFields = [
    "rpc_url_source",
    "rpc_methods_attempted",
    "rate_limited",
    "cached",
    "cache_age_seconds",
    "partial_data_available"
  ];
  const visibleHolderDiagnostics = {};
  for (const field of holderDiagnosticFields) {
    if (holderDiagnostics[field] !== undefined) visibleHolderDiagnostics[field] = holderDiagnostics[field];
  }
  const holderDiagnosticsJson = JSON.stringify(visibleHolderDiagnostics, null, 2);
  const holderDiagnosticsHtml = Object.keys(visibleHolderDiagnostics).length
    ? `
      <details style="margin-top:6px;">
        <summary class="muted" style="cursor:pointer; font-size:12px;">Holder diagnostics</summary>
        <pre style="margin-top:6px; font-size:11px;">${escapeHtml(holderDiagnosticsJson)}</pre>
      </details>
    `
    : "";

  if (!data?.ok) {
    const code = data?.error?.code || "";
    const statusCode = data?.error?.status_code;
    const partial = data?.partial_data_available === true || data?.diagnostics?.partial_data_available === true;
    const technicalMessage = code === "TOKEN_HOLDER_CONCENTRATION_RATE_LIMITED" || (
      code === "TOKEN_HOLDER_CONCENTRATION_HTTP_ERROR" && Number(statusCode) === 429
    )
      ? "Solana RPC is rate-limited right now. Try again later."
      : "Holder concentration unavailable right now.";
    box.className = "muted";
    box.innerHTML = `
      <div style="font-weight:600;">Token stats & holder concentration</div>
      ${renderTokenMarketStatsLine()}
      <div style="margin-top:6px;">${partial ? "Holder data partially available" : "Holder data unavailable"}</div>
      ${partial ? `<div class="muted" style="margin-top:6px; font-size:12px;">Supply found; largest accounts unavailable.</div>` : ""}
      <div style="margin-top:6px;">${linkHtml}</div>
      <div class="muted" style="margin-top:6px; font-size:12px;">${escapeHtml(technicalMessage)}</div>
      ${holderDiagnosticsHtml}
      <div class="muted" style="margin-top:6px; font-size:12px;">Distribution only — not a safety score.</div>
    `;
    card.style.display = "block";
    return;
  }

  const summary = data.summary || {};
  const topAccount = formatHolderPct(summary.top_account_pct);
  const top5 = formatHolderPct(summary.top_5_accounts_pct);
  const top10 = formatHolderPct(summary.top_10_accounts_pct);
  const accountCount = Number(summary.number_of_accounts_used || summary.sampled_account_count);
  const accountCountText = Number.isFinite(accountCount) && accountCount > 0
    ? String(accountCount) + " accounts sampled"
    : "";

  box.className = "muted";
  box.innerHTML = `
    <div style="font-weight:600; color:#e5eefb;">Token stats & holder concentration</div>
    ${renderTokenMarketStatsLine()}
    <div style="margin-top:6px;">Top holder ${escapeHtml(topAccount)} · Top 5 ${escapeHtml(top5)} · Top 10 ${escapeHtml(top10)}</div>
    ${accountCountText ? `<div>${escapeHtml(accountCountText)}</div>` : ""}
    <div class="muted" style="margin-top:6px; font-size:12px;">Based on visible token accounts from Solana RPC. Separate from route ranking.</div>
    <div style="margin-top:6px;">${linkHtml}</div>
    ${holderDiagnosticsHtml}
    <div class="muted" style="margin-top:6px; font-size:12px;">Distribution only — not a safety score.</div>
  `;
  card.style.display = "block";
}

async function runHolderConcentration() {
  const token = selectedExternalTokenForHolderConcentration();
  const card = $("holderConcentrationCard");
  const box = $("holderConcentrationBox");
  if (!token || !token.mint || !card || !box) {
    resetHolderConcentration();
    return;
  }

  holderConcentrationMint = token.mint;
  latestHolderConcentrationData = null;
  card.style.display = "block";
  box.className = "muted";
  box.textContent = "Checking holder concentration...";

  let res;
  try {
    res = await fetchMaybeJson("/tokens/holder-concentration?" + qs({
      mint: token.mint
    }));
  } catch (err) {
    renderHolderConcentration({
      ok: false,
      error: { code: "HOLDER_CONCENTRATION_REQUEST_FAILED" }
    });
    return;
  }

  if (!res.ok) {
    renderHolderConcentration({
      ok: false,
      error: {
        code: res.data?.error?.code || "HOLDER_CONCENTRATION_HTTP_ERROR",
        status_code: res.status
      }
    });
    return;
  }

  renderHolderConcentration(res.data || {});
}

function renderSwapOptionCard(opt, opts = {}) {
  if (!opt) {
    return "<div class='muted'>No data.</div>";
  }

  const title = swapOptionCardTitle(opt, opts);
  const note = opts.note || "";
  const compactDirect = !!opts.compactDirect;
  const showRecommendedAction = !!opts.showRecommendedAction;
  const showDirectAction = !!opts.showDirectAction;
  const showCostSummary = !!opts.showCostSummary;
  const isExecutableRoute = isExecutableRouteOption(opt);
  const isComparisonOnly = opt.is_comparison_only === true && !isExecutableRoute;
  const minReceived = opt.min_received == null ? "n/a" : fmtNum(Number(opt.min_received), 6);
  const impact = formatImpactPct(opt.price_impact_pct);
  const slippage = formatSettingPctFromBps(opt?.protections?.slippage_bps ?? opt?.slippage_bps);
  const routeLabel = surfaceRouteLabel(opt);

      const isRecommendedCard = (opt?.kind || "") === "recommended";

  const executionCostUsd = Number(opt?.execution_cost_usd);
  const networkCostUsd = Number(opt?.network_cost_usd);
  const routeFeesUsd = Number(opt?.route_fees_usd);
  const routeFeesDisclosed = !!opt?.route_fees_disclosed;
  const estimatedTotalSwapCostUsd = Number(opt?.estimated_total_swap_cost_usd);

  const executionCostUsdText = routeVsBestOutputText(opt, opts.bestOption) ||
    (Number.isFinite(executionCostUsd) && executionCostUsd !== 0
      ? "Quote vs market reference: " + fmtUsdCost(executionCostUsd)
      : "Output comparison unavailable");

  const networkCostUsdText =
    Number.isFinite(networkCostUsd) ? fmtUsdCost(networkCostUsd) : "n/a";

  const routeFeesUsdText = routeFeesDisclosed
    ? (Number.isFinite(routeFeesUsd) ? fmtUsdCost(routeFeesUsd) : "disclosed, USD not available")
    : "not disclosed for this swap";

  const estimatedTotalSwapCostUsdText =
    Number.isFinite(estimatedTotalSwapCostUsd)
      ? fmtUsdCost(estimatedTotalSwapCostUsd)
      : "n/a";
  const routeReferenceDifference = routeReferenceDifferenceText(opt);
  
      const tradeCostAmount = Number(opt?.estimated_trade_execution_cost?.amount);
    const tradeCostUsd = Number(opt?.estimated_trade_execution_cost?.amount_usd);
    const tradeCostToken =
              opt?.estimated_trade_execution_cost?.token || opt?.to_token || "";

    const tradeCostLine =
               Number.isFinite(tradeCostAmount) && tradeCostAmount > 0
                   ? "Execution gap vs reference: " +
                      fmtNum(tradeCostAmount, 6) +
                      " " +
                      tradeCostToken +
                      (Number.isFinite(tradeCostUsd) ? " ≈ " + fmtUsdCost(tradeCostUsd) : "")
                      : "Quoted output meets or exceeds the reference";

          const explicitFees = opt?.explicit_route_fees || null;
          const routeFeeItems = Array.isArray(explicitFees?.route_fee_items)
              ? explicitFees.route_fee_items
              : [];
          const hasExplicitFees = !!explicitFees?.has_explicit_fees;

          let explicitFeesText = "not disclosed in this quote";
          if (hasExplicitFees) {
              const feeBits = [];

              if (explicitFees?.platform_fee?.amount != null) {
                  feeBits.push(
                      "platform fee: " +
                          String(explicitFees.platform_fee.amount) +
                          (explicitFees.platform_fee.feeBps != null
                              ? " (" + String(explicitFees.platform_fee.feeBps) + " bps)"
                              : "")
                  );
              }

              for (const item of routeFeeItems) {
                  const amt =
                      item?.fee_amount != null
                          ? fmtNum(Number(item.fee_amount), 6)
                          : String(item?.fee_amount_raw || "unknown");
                  const token = item?.fee_token || "fee token";
                  const label = item?.label || "route leg";
                  feeBits.push(label + ": " + amt + " " + token);
              }

              if (feeBits.length) {
                  explicitFeesText = feeBits.join(" | ");
              }
          }

           const networkFee = opt?.estimated_network_fee;
    const networkFeeScope = opt?.network_fee_scope;
    const networkFeeDetail = opt?.network_fee_detail || "";

    const networkFeeText =
      networkFee && typeof networkFee === "object" && Number.isFinite(Number(networkFee.sol))
        ? fmtNum(Number(networkFee.sol), 9) + " SOL"
        : networkFeeScope === "wallet_not_connected"
          ? "connect Phantom to estimate"
          : networkFeeScope === "estimation_failed"
            ? "unavailable right now"
            : networkFeeScope === "estimation_unavailable"
              ? "unavailable right now"
              : networkFeeScope === "instructions_unavailable"
                ? "unavailable right now"
                : "not estimated yet";

              const costScopeNote =
                  "Route fees are shown separately for transparency and are not added to the headline.";





  return `
    <div class="card" style="margin-top:8px; position:relative;">
      ${shouldShowSwapOptionCardTitle(opt, opts) ? `<div><strong>${escapeHtml(title)}</strong></div>` : ""}
      <div style="margin-top:3px; font-weight:600;">${escapeHtml(routeLabel)}</div>
      ${isComparisonOnly && opt?.provider !== "phantom-routing-api" ? renderSwapExecutionReadinessLine(opt) : ""}
      ${
        isRecommendedCard && showRecommendedAction && isExecutableRoute
          ? `
            <div style="position:absolute; top:12px; right:12px;">
              ${renderRouteActionButton(executableRouteButtonLabel(opt), opt, opts.cardRole || "recommended")}
            </div>
          `
          : (compactDirect && showDirectAction && isExecutableRoute
              ? `
                <div style="position:absolute; top:12px; right:12px;">
                  ${renderRouteActionButton(executableRouteButtonLabel(opt), opt, opts.cardRole || "direct")}
                </div>
              `
              : "")
      }
      ${renderRouteFlowRows(opt)}
      ${renderRouteShapeLine(opt)}
      ${
  isRecommendedCard || showCostSummary
    ? `
      <div class="muted" style="margin-top:4px;">
        <strong>Swap cost: ${escapeHtml(estimatedTotalSwapCostUsdText)}</strong>
      </div>
      <div class="muted" style="margin-top:2px;">
        ${escapeHtml(routeReferenceDifference || "Reference unavailable")}
      </div>
      <div class="muted" style="margin-top:2px;">
        App fee: $0.00
      </div>
      <details style="margin-top:6px;">
        <summary class="muted" style="cursor:pointer;">Show cost breakdown</summary>
        <div class="muted" style="margin-top:6px;">
          Swap cost is estimated as the value gap between the reference market price and the route’s expected output. It may reflect price impact, spread, route quality, quote movement, or reference-price uncertainty. It is not a separate Web3 Digest fee.
        </div>
        <div class="muted" style="margin-top:6px;">
          Market gap estimate: ${escapeHtml(executionCostUsdText)}
        </div>
        <div class="muted" style="margin-top:2px;">
          Network cost: ${escapeHtml(networkCostUsdText)}
        </div>
        <div class="muted" style="margin-top:2px;">
          Route fee estimate: ${escapeHtml(routeFeesUsdText)}
        </div>
      </details>
    `
    : `
      ${
        compactDirect && Number.isFinite(executionCostUsd)
          ? `
            <div class="muted" style="margin-top:4px;">
              ${escapeHtml(executionCostUsdText)}
            </div>
          `
          : `
            <div class="muted" style="margin-top:4px;">
              ${escapeHtml(tradeCostLine)}
            </div>
          `
      }
      ${
        compactDirect
          ? ""
          : `
            <div class="muted" style="margin-top:2px;">
              Route fee estimate: ${escapeHtml(explicitFeesText)}
            </div>
            <div class="muted" style="margin-top:2px;">
              Estimated network fee: ${escapeHtml(networkFeeText)}
            </div>
            ${
              networkFeeDetail
                ? `<div class="muted" style="margin-top:2px;">Fee detail: ${escapeHtml(networkFeeDetail)}</div>`
                : ""
            }
            <div class="muted" style="margin-top:2px;">
              ${escapeHtml(costScopeNote)}
            </div>
          `
      } 
    `
}

    ${
      isRecommendedCard || compactDirect
        ? ""
        : `
          <div class="muted" style="margin-top:4px;">
            ${escapeHtml(opt.explanation || "No explanation available.")}
          </div>
        `
    }
      ${
        note
          ? `<div class="muted" style="margin-top:6px;"><em>${escapeHtml(note)}</em></div>`
          : ""
      }
    </div>
  `;
}



function routeReceiveUsdText(opt) {
  const estimatedOutput = Number(opt?.estimated_output);
  const receiveUsd = Number(opt?.estimated_output_usd);
  if (Number.isFinite(receiveUsd) && !(receiveUsd === 0 && estimatedOutput > 0)) {
    return " ≈ " + fmtUsdCost(receiveUsd);
  }
  const referenceUsdPrice = Number(opt?.estimated_trade_execution_cost?.token_usd_price);
  const referenceUsd = Number.isFinite(referenceUsdPrice) && Number.isFinite(estimatedOutput)
    ? estimatedOutput * referenceUsdPrice
    : null;
  if (referenceUsd && referenceUsd > 0) {
    return " ≈ " + fmtUsdCost(referenceUsd) + " est.";
  }
  if (opt?.usd_reference_uncertain) {
    return " · USD estimate unavailable / reference uncertain";
  }
  if (estimatedOutput > 0) {
    return " · USD estimate unavailable / reference uncertain";
  }
  return "";
}

function routeInputUsdText(opt) {
  const inputAmount = Number(opt?.input_amount);
  const directInputUsd = Number(opt?.input_usd_value ?? opt?.estimated_input_usd);
  if (Number.isFinite(directInputUsd) && !(directInputUsd === 0 && inputAmount > 0)) {
    return " ≈ " + fmtUsdCost(directInputUsd);
  }

  const baseline = latestSwapQuoteResponse?.inline_baseline || null;
  const baselineInput = Number(baseline?.input_amount);
  const baselineUsd = Number(baseline?.input_usd_value);
  const sameToken =
    !baseline?.input_token ||
    !opt?.from_token ||
    String(baseline.input_token).toLowerCase() === String(opt.from_token).toLowerCase();
  const sameAmount =
    Number.isFinite(inputAmount) &&
    Number.isFinite(baselineInput) &&
    Math.abs(inputAmount - baselineInput) <= Math.max(1e-12, Math.abs(baselineInput) * 1e-9);

  if (sameToken && sameAmount && Number.isFinite(baselineUsd) && !(baselineUsd === 0 && inputAmount > 0)) {
    return " ≈ " + fmtUsdCost(baselineUsd);
  }

  return "";
}

function renderRouteFlowRows(opt, compact = false) {
  const inputAmount = Number(opt?.input_amount);
  const inputText =
    (Number.isFinite(inputAmount) ? fmtNum(inputAmount, 6) : "n/a") +
    " " +
    (opt?.from_token || "") +
    routeInputUsdText(opt);
  const outputText =
    fmtNum(Number(opt?.estimated_output || 0), 6) +
    " " +
    (opt?.to_token || "") +
    routeReceiveUsdText(opt);

  return `
    <div class="route-flow${compact ? " compact" : ""}">
      <div class="route-flow-row">
        <span class="route-flow-symbol route-flow-minus">−</span>
        <span>${escapeHtml(inputText)}</span>
      </div>
      <div class="route-flow-row">
        <span class="route-flow-symbol route-flow-plus">+</span>
        <span>${escapeHtml(outputText)}</span>
      </div>
    </div>
  `;
}

function routeVsBestOutputText(opt, bestOption) {
  const output = Number(opt?.estimated_output);
  const bestOutput = Number(bestOption?.estimated_output);
  const token = opt?.to_token || bestOption?.to_token || "";
  if (!Number.isFinite(output) || !Number.isFinite(bestOutput) || bestOutput <= 0) {
    return "";
  }
  const diff = output - bestOutput;
  if (Math.abs(diff) < 1e-12) {
    return "Output vs best route: matches best route";
  }
  const pct = (diff / bestOutput) * 100;
  const direction = pct >= 0 ? "higher" : "lower";
  const absPct = Math.abs(pct);
  const pctText = absPct < 0.01
    ? "<0.01%"
    : "~" + Number(absPct).toFixed(2) + "%";
  return "Output vs best route: " + pctText + " " + direction;
}

function routeReferenceDifferenceText(opt) {
  const gap = Number(opt?.estimated_trade_execution_cost?.amount);
  const output = Number(opt?.estimated_output);
  if (!Number.isFinite(gap) || !Number.isFinite(output)) return "";
  const referenceOutput = output + gap;
  if (!Number.isFinite(referenceOutput) || referenceOutput <= 0) return "";
  const pct = (output - referenceOutput) / referenceOutput * 100;
  if (!Number.isFinite(pct)) return "";
  if (Math.abs(pct) < 0.0001) return "Matches reference";
  const direction = pct >= 0 ? "above reference" : "below reference";
  const absPct = Math.abs(pct);
  const pctText = absPct < 0.01
    ? "<0.01%"
    : "~" + Number(absPct).toFixed(2) + "%";
  return pctText + " " + direction;
}

function renderCompactAlternativeCard(opt, idx = 0, bestOption = null) {
  if (!opt) return "";

  const routeLabel = surfaceRouteLabel(opt);
  const isExecutableRoute = isExecutableRouteOption(opt);
  const isComparisonOnly = opt.is_comparison_only === true && !isExecutableRoute;
  const executionCostUsd = Number(opt?.execution_cost_usd);
  const executionCostText = routeVsBestOutputText(opt, bestOption) ||
    (Number.isFinite(executionCostUsd) && executionCostUsd !== 0
      ? "Quote vs market reference: " + fmtUsdCost(executionCostUsd)
      : "Output comparison unavailable");

  return `
    <div class="card" style="margin-top:8px; position:relative;">
      <div><strong>${opt?.provider === "phantom-routing-api" ? "Benchmark" : "Alternative " + (idx + 1)} — ${escapeHtml(routeLabel)}</strong></div>
      ${isComparisonOnly && opt?.provider !== "phantom-routing-api" ? renderSwapExecutionReadinessLine(opt) : ""}
      ${
        isExecutableRoute
          ? `
            <div style="position:absolute; top:12px; right:12px;">
              ${renderRouteActionButton(executableRouteButtonLabel(opt), opt, opt.kind || "alternative")}
            </div>
          `
          : ""
      }
      ${renderRouteFlowRows(opt, true)}
      ${renderRouteShapeLine(opt, true)}
      <div class="muted" style="margin-top:2px;">
        ${escapeHtml(executionCostText)}
      </div>
      ${
        opt?.provider === "phantom-routing-api"
          ? `
            <div class="muted" style="margin-top:4px;">
              Not executable here
            </div>
          `
          : ""
      }
    </div>
  `;
}

function compactSwapPrepareErrorText(value) {
  const text = String(value || "").trim();
  if (!text) return "";
  if (/transaction_base64|transactionBase64|signed_transaction|signedTransaction|swapTransaction|https?:\\/\\/|api[-_]?key|access_token|secret/i.test(text)) return "";
  if ((text.startsWith("{") || text.startsWith("[")) && text.length > 120) return "";
  if (text.length > 220) return text.slice(0, 217) + "...";
  return text;
}

function extractSwapPrepareErrorDetail(data) {
  const error = data?.error || {};
  return {
    code: compactSwapPrepareErrorText(error.code),
    message: compactSwapPrepareErrorText(error.message),
    detail: compactSwapPrepareErrorText(error.detail),
    providerMessage: compactSwapPrepareErrorText(error.provider_message),
    providerCode: compactSwapPrepareErrorText(error.provider_code),
    providerDetail: compactSwapPrepareErrorText(error.provider_detail)
  };
}

function redactSwapPrepareFailureResponse(value) {
  if (Array.isArray(value)) return value.map(redactSwapPrepareFailureResponse);
  if (!value || typeof value !== "object") return value;

  const redacted = {};
  Object.entries(value).forEach(([key, item]) => {
    if (/transaction_base64|swapTransaction/i.test(key)) {
      redacted[key] = "[redacted]";
    } else {
      redacted[key] = redactSwapPrepareFailureResponse(item);
    }
  });
  return redacted;
}

function swapPrepareErrorMessage(code, fallbackMessage = "") {
  const safeFallback = compactSwapPrepareErrorText(fallbackMessage);
  if (code === "SWAP_EXECUTION_WALLET_REQUIRED") {
    return "Connect Phantom to prepare this swap.";
  }
  if (
    code === "SWAP_EXECUTION_UNSUPPORTED_PROVIDER" ||
    code === "SWAP_EXECUTION_PROVIDER_NOT_IMPLEMENTED" ||
    code === "SWAP_EXECUTION_UNSUPPORTED_ROUTE"
  ) {
    return "This route is not executable yet.";
  }
  if (code === "SWAP_EXECUTION_UNSUPPORTED_NETWORK") {
    return "Only Solana execution is supported right now.";
  }
  if (code === "SWAP_EXECUTION_JUPITER_AUTH_REQUIRED") {
    return "Jupiter authorization is required for execution prepare. Configure JUP_API_KEY and preview again.";
  }
  if (code === "SWAP_EXECUTION_RATE_LIMITED") {
    return "Jupiter is rate-limited right now. Try again later.";
  }
  if (code === "SWAP_EXECUTION_QUOTE_FAILED") {
    return "Could not refresh quote. Preview again.";
  }
  if (code === "SWAP_EXECUTION_PREPARE_FAILED") {
    return "Swap preparation failed. Preview again.";
  }
  return safeFallback ? "Swap preparation failed. " + safeFallback : "Swap preparation failed.";
}

async function prepareSwapRoute(routeRequest) {
  latestPreparedSwap = null;
  setSwapPreparedActionVisible(false);

  if (isSwapQuoteExpired()) {
    setSwapExecutionStatus("failed", "Quote expired — preview again before swapping.");
    return;
  }

  const activeWalletPubkey =
    phantomProvider?.publicKey?.toString?.() || phantomPubkey || "";

  if (!activeWalletPubkey) {
    setSwapExecutionStatus("failed", "Connect Phantom to prepare this swap.");
    return;
  }

  const provider = routeRequest?.provider || "";
  if (!SWAP_EXECUTABLE_PROVIDERS.has(provider)) {
    setSwapExecutionStatus("failed", "This route is not executable yet.");
    return;
  }

  const variantId = routeRequest.variant_id || "";
  const supportedVariants = SWAP_EXECUTABLE_VARIANTS[provider];
  const fromToken = canonicalSwapTokenQuery("from");
  const toToken = canonicalSwapTokenQuery("to");
  const amount = Number(($("swapAmount").value || "").trim());

  if (supportedVariants?.has(variantId) !== true) {
    setSwapExecutionStatus("failed", "This route is not executable yet.");
    return;
  }

  if (!variantId || !Number.isFinite(amount) || amount <= 0) {
    setSwapExecutionStatus("failed", "Could not refresh quote. Preview again.");
    return;
  }

  const inputBalanceCheck = validateSwapInputBalanceBeforePrepare(amount);
  if (inputBalanceCheck.ok === false) {
    latestPreparedSwap = null;
    renderSwapPreflightDebug(null);
    setSwapPreparedActionVisible(false);
    setSwapExecutionStatus("failed", inputBalanceCheck.message, inputBalanceCheck.detail);
    return;
  }

  const payload = {
    provider,
    variant_id: variantId,
    from_token: fromToken,
    to_token: toToken,
    amount,
    slippage_bps: 50,
    user_public_key: activeWalletPubkey,
    network: "solana"
  };

  setSwapExecutionStatus("preparing", "Preparing swap…");

  let res;
  try {
    res = await fetchMaybeJson("/swap/execute/prepare", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
  } catch (err) {
    setSwapExecutionStatus("failed", "Swap preparation failed. Preview again.");
    return;
  }

  if (!res.ok || res.data?.ok === false) {
    const errorDetail = extractSwapPrepareErrorDetail(res.data);
    const code = errorDetail.code || "SWAP_EXECUTION_PREPARE_FAILED";
    console.warn("Swap execution prepare failed", {
      status: res.status,
      error: errorDetail,
      response: redactSwapPrepareFailureResponse(res.data)
    });
    setSwapExecutionStatus(
      "failed",
      swapPrepareErrorMessage(code, errorDetail.message || errorDetail.detail),
      errorDetail.providerDetail
        ? "Provider detail: " + errorDetail.providerDetail
        : errorDetail.providerMessage
          ? "Provider detail: " + errorDetail.providerMessage
          : errorDetail.code
            ? "Execution error: " + errorDetail.code
            : null
    );
    return;
  }

  latestPreparedSwap = res.data || null;
  if (latestPreparedSwap?.submit_preflight?.can_submit === false) {
    latestPreparedSwap = null;
    setSwapPreparedActionVisible(false);
    setSwapExecutionStatus("failed", "Swap cannot be submitted yet. Configure SWAP_SUBMIT_RPC_URL.");
    return;
  }

  const summary = latestPreparedSwap?.quote_summary || {};
  const receive = summary.estimated_output != null
    ? "Refreshed receive estimate: " + fmtNum(Number(summary.estimated_output), 6) + " " + (summary.to_token || "")
    : "";

  setSwapExecutionStatus(
    "prepared",
    "Swap transaction prepared. Review the summary before signing.",
    receive
  );
  renderPreparedSwapSummary(latestPreparedSwap);
  setSwapPreparedActionVisible(true);
}

function isPhantomUserRejection(err) {
  const code = err?.code ?? err?.data?.code;
  const message = String(err?.message || err || "").toLowerCase();
  return code === 4001 ||
    message.includes("rejected") ||
    message.includes("denied") ||
    message.includes("cancelled") ||
    message.includes("canceled");
}

function isExpiredSwapError(err) {
  const message = String(err?.message || err || "").toLowerCase();
  return message.includes("blockhash") ||
    message.includes("expired") ||
    message.includes("last valid block height") ||
    message.includes("transaction was not confirmed");
}

function mainnetExplorerLink(signature) {
  return `${MAINNET_EXPLORER_BASE}${signature}`;
}

function compactSwapRuntimeErrorText(value) {
  const text = String(value || "").trim();
  if (!text) return "";
  if (/transaction_base64|transactionBase64|signed_transaction|signedTransaction|swapTransaction|https?:\\/\\/|api[-_]?key|access_token|secret/i.test(text)) return "";
  if ((text.startsWith("{") || text.startsWith("[")) && text.length > 120) return "";
  if (text.length > 180) return text.slice(0, 177) + "...";
  return text;
}

function swapRuntimeErrorDetail(err) {
  const message = compactSwapRuntimeErrorText(err?.message || err?.reason || err);
  return message ? "Reason: " + message : "";
}

function swapRuntimeFailureMessage(phase, err) {
  if (phase === "deserialize") {
    return "Could not read prepared swap transaction. Preview again.";
  }
  if (phase === "signing") {
    return isPhantomUserRejection(err) ? "Swap was rejected in Phantom." : "Phantom signing failed.";
  }
  if (phase === "missing_signed_transaction") {
    return "Phantom signing did not return a signed transaction.";
  }
  if (phase === "submit") {
    return isExpiredSwapError(err) ? "Quote expired. Preview again." : "Transaction submission failed.";
  }
  if (phase === "confirm") {
    return isExpiredSwapError(err) ? "Quote expired. Preview again." : "Swap confirmation failed.";
  }
  if (phase === "expired") {
    return "Quote expired. Preview again.";
  }
  return "Swap failed.";
}

function swapSubmitErrorMessage(code) {
  if (code === "SWAP_SUBMIT_FORBIDDEN") {
    return "Transaction submission was blocked by RPC.";
  }
  if (code === "SWAP_SUBMIT_RATE_LIMITED") {
    return "RPC is rate-limited. Try again later.";
  }
  if (code === "SWAP_SUBMIT_RPC_CONFIG_MISSING") {
    return "Swap submission RPC is not configured.";
  }
  if (code === "SWAP_SUBMIT_UNSUPPORTED_NETWORK") {
    return "Only Solana transaction submission is supported right now.";
  }
  if (code === "SWAP_SUBMIT_SIGNED_TRANSACTION_REQUIRED") {
    return "Transaction submission failed.";
  }
  return "Transaction submission failed.";
}

function collectSwapRouteOptions(value, out = []) {
  if (!value || typeof value !== "object") return out;
  if (Array.isArray(value)) {
    value.forEach((item) => collectSwapRouteOptions(item, out));
    return out;
  }
  if (value.provider || value.provider_id || value.variant_id) out.push(value);
  Object.entries(value).forEach(([key, child]) => {
    if (key === "raw" || key === "quote_response") return;
    if (child && typeof child === "object") collectSwapRouteOptions(child, out);
  });
  return out;
}

function currentPreparedRouteOption() {
  const summary = latestPreparedSwap?.quote_summary || {};
  const provider = String(latestPreparedSwap?.provider || summary.provider || "").toLowerCase();
  const variant = String(summary.variant_id || "").toLowerCase();
  const options = collectSwapRouteOptions(latestSwapQuoteResponse || {});
  return options.find((opt) => {
    const optProvider = String(opt?.provider || opt?.provider_id || "").toLowerCase();
    const optVariant = String(opt?.variant_id || "").toLowerCase();
    return (!provider || optProvider === provider) && (!variant || optVariant === variant);
  }) || null;
}

function preparedSwapEstimatedNetworkFeeSol() {
  const option = currentPreparedRouteOption();
  const fee = option?.estimated_network_fee;
  const feeSol = fee && typeof fee === "object" ? Number(fee.sol) : NaN;
  return Number.isFinite(feeSol) && feeSol > 0 ? feeSol : SWAP_DEFAULT_NETWORK_FEE_SOL;
}

function preparedSwapProviderId() {
  const summary = latestPreparedSwap?.quote_summary || {};
  return String(latestPreparedSwap?.provider || summary.provider || "").toLowerCase();
}

function preflightSolRequirementBeforePhantom() {
  const solHolding = selectedSolHolding();
  if (!solHolding || !isSwapBalanceSnapshotFresh(solHolding.balance_ts) || swapBalancesStaleAfterSubmit) {
    return { ok: true, skipped: "sol_balance_unknown_or_stale" };
  }

  const availableSol = Number(solHolding.amount);
  if (!Number.isFinite(availableSol)) return { ok: true, skipped: "sol_balance_unavailable" };

  const summary = latestPreparedSwap?.quote_summary || {};
  const provider = preparedSwapProviderId();
  const fromToken = normalizeSwapAssetKey(summary.from_token || $("swapFromToken")?.value);
  const inputSol = fromToken === "SOL" ? Number(summary.amount ?? $("swapAmount")?.value) : 0;
  const swapAmountSol = Number.isFinite(inputSol) && inputSol > 0 ? inputSol : 0;
  const estimatedFeeSol = preparedSwapEstimatedNetworkFeeSol();
  const bufferSol = SWAP_SOL_FEE_ACCOUNT_SETUP_BUFFER_SOL;
  const requiredSol = swapAmountSol + estimatedFeeSol + bufferSol;
  const suggestedMaxSol = Math.max(0, availableSol - estimatedFeeSol - bufferSol);

  if (availableSol + 1e-12 >= requiredSol) {
    return { ok: true, provider, availableSol, swapAmountSol, estimatedFeeSol, bufferSol, requiredSol, suggestedMaxSol };
  }

  return {
    ok: false,
    provider,
    availableSol,
    swapAmountSol,
    estimatedFeeSol,
    bufferSol,
    requiredSol,
    suggestedMaxSol,
    reason: "SOL is required for network fees and account setup."
  };
}

function enrichSwapPreflightWithSolDiagnostics(preflight) {
  if (!preflight || typeof preflight !== "object") return preflight;
  const summary = latestPreparedSwap?.quote_summary || {};
  const fromToken = normalizeSwapAssetKey(summary.from_token || $("swapFromToken")?.value);

  const setupLamports = Number(preflight.setup_cost_estimate_lamports || 0);
  const feeLamports = Math.round(preparedSwapEstimatedNetworkFeeSol() * 1_000_000_000);
  const categoryNeedsSolContext = preflight.error_category === "account_setup" || preflight.error_category === "insufficient_funds";
  if (
    fromToken !== "SOL" &&
    (!Number.isFinite(setupLamports) || setupLamports <= 0) &&
    (!Number.isFinite(feeLamports) || feeLamports <= 0) &&
    !categoryNeedsSolContext
  ) {
    return preflight;
  }

  const solHolding = selectedSolHolding();
  const solBalanceFresh = Boolean(solHolding && isSwapBalanceSnapshotFresh(solHolding.balance_ts) && !swapBalancesStaleAfterSubmit);
  if (!solHolding || !solBalanceFresh) {
    if (fromToken !== "SOL") {
      preflight.client_sol_diagnostics = {
        sol_balance_available_for_diagnostics: false,
        fee_estimate_lamports: Number.isFinite(feeLamports) ? feeLamports : 0,
        setup_cost_estimate_lamports: Number.isFinite(setupLamports) ? setupLamports : 0,
        estimated_non_input_sol_required_lamports: Math.max(0, (Number.isFinite(setupLamports) ? setupLamports : 0) + (Number.isFinite(feeLamports) ? feeLamports : 0)),
        suggested_action: "refresh_sol_balance_for_account_setup_check"
      };
    }
    return preflight;
  }

  const availableSol = Number(solHolding.amount);
  if (!Number.isFinite(availableSol)) return preflight;

  const availableLamports = Math.round(availableSol * 1_000_000_000);
  if (fromToken !== "SOL") {
    const requiredLamports = Math.max(0, (Number.isFinite(setupLamports) ? setupLamports : 0) + (Number.isFinite(feeLamports) ? feeLamports : 0));
    const shortfallLamports = Math.max(0, requiredLamports - availableLamports);
    const unexplained = categoryNeedsSolContext && shortfallLamports === 0;
    preflight.client_sol_diagnostics = {
      available_sol_lamports: availableLamports,
      fee_estimate_lamports: Number.isFinite(feeLamports) ? feeLamports : 0,
      setup_cost_estimate_lamports: Number.isFinite(setupLamports) ? setupLamports : 0,
      estimated_non_input_sol_required_lamports: requiredLamports,
      estimated_sol_shortfall_lamports: shortfallLamports,
      account_setup_failure_not_explained_by_sol_balance: unexplained,
      suggested_action: shortfallLamports > 0 ? "add_sol_for_account_setup" : (unexplained ? "enough_sol_for_setup_but_preflight_failed" : "enough_sol_for_account_setup")
    };
    return preflight;
  }

  const inputSol = Number(summary.amount ?? $("swapAmount")?.value);
  if (!Number.isFinite(inputSol)) return preflight;

  const inputLamports = Math.round(inputSol * 1_000_000_000);
  const requiredLamports = inputLamports + setupLamports + feeLamports;
  const shortfallLamports = Math.max(0, requiredLamports - availableLamports);
  const suggestedMaxLamports = Math.max(0, availableLamports - setupLamports - feeLamports);

  preflight.client_sol_diagnostics = {
    input_amount_lamports: inputLamports,
    available_sol_lamports: availableLamports,
    fee_estimate_lamports: feeLamports,
    setup_cost_estimate_lamports: setupLamports,
    estimated_total_required_lamports: requiredLamports,
    estimated_shortfall_lamports: shortfallLamports,
    suggested_max_input_lamports: suggestedMaxLamports,
    suggested_max_input_sol: suggestedMaxLamports / 1_000_000_000
  };
  return preflight;
}

function renderSolRequirementBlock(result) {
  const lines = [
    result.provider === "orca-whirlpool" ? "Provider: Orca" : "Provider: Solana route",
    "Available SOL: " + fmtNum(result.availableSol, 9),
    "Swap amount: " + fmtNum(result.swapAmountSol, 9) + " SOL",
    "Estimated network fee: " + fmtNum(result.estimatedFeeSol, 9) + " SOL",
    "Fee/account setup buffer: " + fmtNum(result.bufferSol, 9) + " SOL",
    "Suggested max spend: " + fmtNum(result.suggestedMaxSol, 9) + " SOL"
  ].filter(Boolean);
  if (result.reason) lines.push("Reason: " + result.reason);
  return lines.join(". ");
}

function safeSwapPreflightLogPreview(logs) {
  if (!Array.isArray(logs)) return "";
  return logs
    .map((line) => compactSwapRuntimeErrorText(line))
    .filter(Boolean)
    .slice(0, 4)
    .join(" | ");
}

function renderSwapPreflightFailureDetail(preflight) {
  const bits = [];
  const provider = preflight?.provider === "orca-whirlpool" ? "Orca" : (preflight?.provider || "selected route");
  bits.push("Provider: " + provider);
  if (preflight?.variant_id) bits.push("Variant: " + preflight.variant_id);
  if (preflight?.error_category) bits.push("Simulation category: " + preflight.error_category);
  if (preflight?.error_category === "insufficient_funds" || preflight?.error_category === "account_setup") {
    bits.push("This route appears to require additional SOL for account setup/rent.");
  }
  if (preflight?.transaction_diagnostics?.decode_ok) {
    bits.push("Technical diagnostics available in debug.");
  }
  bits.push("Try a lower amount, add SOL, or choose another route.");
  return bits.join(". ");
}

async function preflightPreparedSwapBeforePhantom() {
  const summary = latestPreparedSwap?.quote_summary || {};
  const payload = {
    network: "solana",
    provider: latestPreparedSwap?.provider || summary.provider || "",
    variant_id: summary.variant_id || "",
    user_public_key: phantomProvider?.publicKey?.toString?.() || phantomPubkey || "",
    transaction_base64: latestPreparedSwap?.transaction_base64 || ""
  };
  const response = await fetchMaybeJson("/swap/execute/preflight", {
    method: "POST",
    headers: {"content-type": "application/json"},
    body: JSON.stringify(payload)
  });
  if (!response.ok) {
    const fallback = {
      ok: false,
      provider: payload.provider,
      variant_id: payload.variant_id,
      simulation_supported: false,
      error_category: "rpc_unavailable",
      message: "Could not preflight this route right now.",
      logs_preview: []
    };
    const enrichedFallback = enrichSwapPreflightWithSolDiagnostics(fallback);
    renderSwapPreflightDebug(enrichedFallback);
    return enrichedFallback;
  }
  const result = response.data || {
    ok: false,
    provider: payload.provider,
    variant_id: payload.variant_id,
    simulation_supported: false,
    error_category: "simulation_failed",
    message: "Preflight returned an unexpected response.",
    logs_preview: []
  };
  const enrichedResult = enrichSwapPreflightWithSolDiagnostics(result);
  renderSwapPreflightDebug(enrichedResult);
  return enrichedResult;
}

function bytesToBase64(bytes) {
  let binary = "";
  const chunkSize = 0x8000;
  for (let i = 0; i < bytes.length; i += chunkSize) {
    const chunk = bytes.slice(i, i + chunkSize);
    binary += String.fromCharCode.apply(null, chunk);
  }
  return btoa(binary);
}

function closeSwapSuccessModal() {
  const modal = $("swapSuccessModal");
  if (!modal) return;
  modal.classList.remove("is-open");
  modal.setAttribute("aria-hidden", "true");
}

function showSwapSuccessModal(details) {
  const modal = $("swapSuccessModal");
  const body = $("swapSuccessModalBody");
  const explorerLink = $("swapSuccessExplorerLink");
  if (!modal || !body) return;

  const lines = [
    details.provider ? "Provider: " + details.provider : "",
    details.spent ? "Spent: " + details.spent : "",
    details.expected ? "Expected received: " + details.expected : "",
    details.swapCost ? "Swap cost: " + details.swapCost : "",
    "Network: Solana mainnet"
  ].filter(Boolean);

  body.innerHTML = lines.map((line) => `<div>${escapeHtml(line)}</div>`).join("");

  if (explorerLink && details.explorer) {
    explorerLink.href = details.explorer;
    explorerLink.style.display = "inline-block";
  } else if (explorerLink) {
    explorerLink.removeAttribute("href");
    explorerLink.style.display = "none";
  }

  modal.classList.add("is-open");
  modal.setAttribute("aria-hidden", "false");
}

function appendUsdEstimateText(baseText, usdValue) {
  const usd = Number(usdValue);
  if (!baseText || !Number.isFinite(usd) || usd <= 0) return baseText || "";
  return baseText + " ≈ " + fmtUsdCost(usd);
}

function preparedSwapDisplayCost(summary) {
  const cost = Number(
    summary?.estimated_total_swap_cost_usd ??
    summary?.execution_cost_usd ??
    summary?.estimated_trade_execution_cost?.amount_usd
  );
  return Number.isFinite(cost) && cost > 0 ? fmtUsdCost(cost) : "";
}

function renderSwapSubmittedSuccess(signature) {
  const box = $("swapExecutionStatus");
  if (!box) return;

  const summary = latestPreparedSwap?.quote_summary || {};
  const providerLabel = latestPreparedSwap?.execution_surface_label || summary.provider_label || "Selected route";
  const fromToken = summary.from_token || "";
  const toToken = summary.to_token || "";
  const spent = summary.amount != null
    ? fmtNum(Number(summary.amount), 6) + (fromToken ? " " + fromToken : "")
    : "";
  const expected = summary.estimated_output != null
    ? fmtNum(Number(summary.estimated_output), 6) + (toToken ? " " + toToken : "")
    : "";
  const spentWithUsd = appendUsdEstimateText(
    spent,
    summary.input_usd_value ?? summary.swap_usd_value ?? summary.spend_usd
  );
  const expectedWithUsd = appendUsdEstimateText(
    expected,
    summary.estimated_output_usd ?? summary.output_usd_value
  );
  const swapCostText = preparedSwapDisplayCost(summary);
  const explorer = mainnetExplorerLink(signature);
  const tokenText = toToken ? toToken + " received — check your Phantom wallet." : "Token received — check your Phantom wallet.";

  const lines = [
    `<div style="font-weight:600; color:#e5eefb;">Swap submitted successfully</div>`,
    `<div>Provider: ${escapeHtml(providerLabel)}</div>`,
    spentWithUsd ? `<div>Spent: ${escapeHtml(spentWithUsd)}</div>` : "",
    expectedWithUsd ? `<div>Expected received: ${escapeHtml(expectedWithUsd)}</div>` : "",
    swapCostText ? `<div>Swap cost: ${escapeHtml(swapCostText)}</div>` : "",
    `<div>Network: Solana mainnet</div>`,
    `<div><a href="${escapeHtml(explorer)}" target="_blank">Open in Solana Explorer</a></div>`,
    `<div style="margin-top:4px;">${escapeHtml(tokenText)}</div>`,
    `<div class="muted" id="swapPostSuccessBalanceStatus" style="margin-top:4px;">Refreshing balances…</div>`
  ].filter(Boolean);

  swapExecutionState = "submitted";
  swapBalancesStaleAfterSubmit = true;
  box.className = "muted ok";
  box.innerHTML = lines.join("");
  box.style.display = "block";
  showSwapSuccessModal({
    provider: providerLabel,
    spent: spentWithUsd,
    expected: expectedWithUsd,
    swapCost: swapCostText,
    explorer,
  });
  renderSwapBalanceFreshnessHint(selectedFromHolding());
  renderSwapFromBalance();
  refreshBalancesAfterSwap(summary);
}

async function signAndSubmitPreparedSwap() {
  if (!latestPreparedSwap || !latestPreparedSwap.transaction_base64) {
    setSwapPreparedActionVisible(false);
    setSwapExecutionStatus("failed", swapRuntimeFailureMessage("expired"), "Execution phase: prepare");
    return;
  }

  const ack = $("swapSignAcknowledgement");
  if (!ack?.checked) {
    setSwapExecutionStatus("failed", "Confirm you understand this is a real mainnet swap before signing.");
    return;
  }

  if (latestPreparedSwap.transaction_format !== "versioned") {
    setSwapPreparedActionVisible(false);
    setSwapExecutionStatus("failed", "Swap preparation failed. Preview again.");
    return;
  }

  phantomProvider = getPhantomProvider();
  const activeWalletPubkey =
    phantomProvider?.publicKey?.toString?.() || phantomPubkey || "";

  if (!phantomProvider || !activeWalletPubkey) {
    setSwapExecutionStatus("failed", "Connect Phantom to continue.");
    return;
  }

  if (!solanaWeb3?.VersionedTransaction?.deserialize) {
    setSwapExecutionStatus("failed", "Swap signing is not supported in this browser session.");
    return;
  }

  const solRequirement = preflightSolRequirementBeforePhantom();
  if (solRequirement && solRequirement.ok === false) {
    setSwapExecutionStatus(
      "failed",
      solRequirement.provider === "orca-whirlpool"
        ? "This Orca route needs more SOL before Phantom can approve it."
        : "Not enough SOL to approve this route before opening Phantom.",
      renderSolRequirementBlock(solRequirement)
    );
    return;
  }

  const preparedPreflight = await preflightPreparedSwapBeforePhantom();
  if (preparedPreflight && preparedPreflight.ok === false) {
    const provider = preparedPreflight.provider || preparedSwapProviderId();
    const mustBlock =
      provider === "orca-whirlpool" ||
      preparedPreflight.simulation_supported === true ||
      preparedPreflight.error_category !== "rpc_unavailable";
    if (mustBlock) {
      latestPreparedSwap = null;
      setSwapPreparedActionVisible(false);
      setSwapExecutionStatus(
        "failed",
        provider === "orca-whirlpool"
          ? "This Orca route would likely fail before Phantom approval."
          : "This route would likely fail before Phantom approval.",
        renderSwapPreflightFailureDetail(preparedPreflight)
      );
      return;
    }
  }

  let tx;
  try {
    const transactionBase64 = latestPreparedSwap.transaction_base64;
    const bytes = Uint8Array.from(atob(transactionBase64), c => c.charCodeAt(0));
    tx = solanaWeb3.VersionedTransaction.deserialize(bytes);
  } catch (err) {
    console.error("swap deserialize error:", err);
    setSwapPreparedActionVisible(false);
    const reason = swapRuntimeErrorDetail(err);
    setSwapExecutionStatus(
      "failed",
      swapRuntimeFailureMessage("deserialize", err),
      reason ? "Execution phase: deserialize. " + reason : "Execution phase: deserialize"
    );
    return;
  }

  let signedTx;
  try {
    const signButton = $("btnSignPreparedSwap");
    if (signButton) signButton.disabled = true;
    setSwapExecutionStatus("signing", "Review and sign in Phantom…");
    signedTx = await phantomProvider.signTransaction(tx);
  } catch (err) {
    console.error("swap signing error:", err);
    const reason = swapRuntimeErrorDetail(err);
    setSwapExecutionStatus(
      "failed",
      swapRuntimeFailureMessage("signing", err),
      reason ? "Execution phase: signing. " + reason : "Execution phase: signing"
    );
    setSwapPreparedActionVisible(true);
    updateSwapSignButtonState();
    return;
  }

  if (!signedTx) {
    setSwapExecutionStatus(
      "failed",
      swapRuntimeFailureMessage("missing_signed_transaction"),
      "Execution phase: signing"
    );
    setSwapPreparedActionVisible(true);
    updateSwapSignButtonState();
    return;
  }

  setSwapPreparedActionVisible(false);

  let signature;
  let explorer;
  try {
    setSwapExecutionStatus("submitting", "Submitting transaction…");
    const signedTransactionBase64 = bytesToBase64(signedTx.serialize());
    const submitResponse = await fetchMaybeJson("/swap/execute/submit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        network: "solana",
        signed_transaction_base64: signedTransactionBase64,
        skip_preflight: false,
        preflight_commitment: "confirmed"
      })
    });

    if (!submitResponse.ok || submitResponse.data?.ok === false) {
      const code = submitResponse.data?.error?.code || "SWAP_SUBMIT_FAILED";
      const err = new Error(swapSubmitErrorMessage(code));
      err.code = code;
      throw err;
    }

    signature = submitResponse.data?.signature;
    if (!signature) {
      const err = new Error("Transaction submission failed.");
      err.code = "SWAP_SUBMIT_FAILED";
      throw err;
    }

    explorer = mainnetExplorerLink(signature);
    renderSwapSubmittedSuccess(signature);
  } catch (err) {
    console.error("swap submit error:", err);
    const reason = swapRuntimeErrorDetail(err);
    setSwapExecutionStatus(
      "failed",
      err?.code ? swapSubmitErrorMessage(err.code) : swapRuntimeFailureMessage("submit", err),
      reason ? "Execution phase: submit. " + reason : "Execution phase: submit"
    );
    return;
  }
}

function handleSwapExecuteClick(event) {
  const button = event.target?.closest?.('[data-swap-execute="true"]');
  if (!button) return;

  event.preventDefault();
  prepareSwapRoute({
    provider: button.dataset.provider,
    variant_id: button.dataset.variantId,
    card_role: button.dataset.cardRole
  });
}


async function previewSwap() {
  showSwapStatus("warn", "Preview clicked", { step: "previewSwap entered" });
  latestSwapQuoteResponse = null;
  latestPreparedSwap = null;
  setSwapPreparedActionVisible(false);
  clearSwapQuoteFreshness();
  setSwapExecutionStatus("idle", "Ready to prepare a swap route.");

  const fromToken = canonicalSwapTokenQuery("from");
  const toToken = canonicalSwapTokenQuery("to");
  const rawAmount = ($("swapAmount").value || "").trim();
  const amount = Number(rawAmount);

  if (!rawAmount) {
    setSwapPhase("Failed", "Enter an amount first.");
    showSwapStatus("warn", "Swap preview failed", { error: "Amount is required." });
    return;
  }

  if (!Number.isFinite(amount) || amount <= 0) {
    setSwapPhase("Failed", "Amount must be a valid number greater than 0.");
    showSwapStatus("warn", "Swap preview failed", { error: "Invalid amount." });
    return;
  }

  if (fromToken === toToken) {
    setSwapPhase("Failed", "From token and to token cannot be the same.");
    showSwapStatus("warn", "Swap preview failed", { error: "Choose two different tokens." });
    return;
  }

  runHolderConcentration();

  setSwapPhase("Draft", "Requesting backend quote preview...");

  const feeEstimatePubkey =
    phantomProvider?.publicKey?.toString?.() || phantomPubkey || "";

  const url =
    "/swap/quote?" +
    qs({
      from_token: fromToken,
      to_token: toToken,
      amount: amount,
      network: "solana",
      user_public_key: feeEstimatePubkey || undefined,
    });

  let res;
  try {
    res = await fetchMaybeJson(url);
  } catch (err) {
    resetSwapQuoteDisplay();
    const info = getSwapThrownErrorInfo(err);
    setSwapPhase("Failed", info.phase);
    showSwapStatus(info.kind, info.title, {
      error: err?.message || String(err),
      raw: err
    });
    return;
  }

  if (!res.ok) {
    resetSwapQuoteDisplay();
    const info = getSwapHttpErrorInfo(res.status, res.data, res.text);
    setSwapPhase("Failed", info.phase);
    showSwapStatus(info.kind, info.title, {
      status: res.status,
      data: res.data,
      raw: res.text
    });
    return;
  }

  const quote = res.data || {};
  latestSwapQuoteResponse = quote;
  if (latestHolderConcentrationData) {
    renderHolderConcentration(latestHolderConcentrationData);
  }
  renderSwapInlineBaseline(
    quote.inline_baseline,
    quote.inline_baseline_vs_recommended
  );

  const bestQuote = quote?.best_quote_option || null;
  const recommended = quote?.recommended_option || quote?.recommended || null;
  const recommendedExecutable = quote?.recommended_executable_option || null;
  const otherOptions = Array.isArray(quote?.other_options) ? quote.other_options : [];
  const directRoute = quote?.direct_route_check || null;

  if (!quote?.ok || !(bestQuote || recommended)) {
    clearSwapQuoteFreshness();
    setSwapPreparedActionVisible(false);
    setSwapExecutionStatus("idle", "Ready to prepare a swap route.");
    setSwapPhase("Failed", "No executable route found for this token/amount.");
    $("swapRecommendedBox").innerHTML =
      "<div class='muted'>No executable route found. Reference price is available, but no live route was found.</div>";
    $("swapDirectBox").innerHTML =
      "<div class='muted'>No direct/simple route returned for this token/amount.</div>";
    $("swapAlternativesCard").style.display = "none";
    $("swapAlternativesBox").innerHTML = "<div class='muted'>No alternatives yet.</div>";
    $("swapRecommendation").style.display = "block";
    $("swapRecommendation").textContent = "No executable route found for this token/amount.";
    $("swapCompareSummary").style.display = "block";
    $("swapCompareSummary").textContent =
      "Reference price is available, but no live route was found. Reference pricing is not an executable route.";
    $("swapQuotePreview").textContent = JSON.stringify(quote, null, 2);
    $("swapDebugWrap").style.display = "block";
    showSwapStatus("warn", "No executable route found", { quote });
    return;
  }

  startSwapQuoteFreshnessTimer();

  function numOrNull(x) {
    const n = Number(x);
    return Number.isFinite(n) ? n : null;
  }

  function fmtTokenAmount(x, digits = 6) {
    const n = numOrNull(x);
    if (n === null) return "n/a";
    return fmtNum(n, digits);
  }

  const displayRec = recommended || bestQuote;
  const executableRec = recommendedExecutable || displayRec;
  renderSwapCoverageDepth(quote);
  renderSwapExternalTokenNotice(quote);

  function sameOption(a, b) {
    if (!a || !b) return false;
    return (
      a?.provider === b?.provider &&
      a?.execution_surface_label === b?.execution_surface_label &&
      a?.variant_id === b?.variant_id &&
      String(a?.estimated_output_raw) === String(b?.estimated_output_raw)
    );
  }

  function outputsAreComparable(a, b) {
    const aRaw = Number(a?.estimated_output_raw);
    const bRaw = Number(b?.estimated_output_raw);
    if (!Number.isFinite(aRaw) || !Number.isFinite(bRaw) || bRaw <= 0) return false;

    const diffPct = Math.abs(aRaw - bRaw) / bRaw;
    return diffPct <= 0.0001;
  }

  function routeDisplayKey(opt) {
    if (!opt) return "";
    return [
      opt?.provider || "",
      opt?.execution_surface_label || "",
      opt?.variant_id || "",
      String(opt?.estimated_output_raw ?? opt?.estimated_output ?? "")
    ].join("|");
  }

  function isDirectSimpleRouteOption(opt) {
    if (!opt) return false;
    if (opt?.provider === "phantom-routing-api") return false;
    const shape = String(opt?.route_shape || "").toLowerCase();
    const steps = Number(opt?.route_step_count || 0);
    return opt?.variant_id === "direct_route_check" ||
      steps === 1 ||
      shape === "direct" ||
      shape === "single-pool" ||
      shape === "single-path" ||
      shape === "single-clob-market" ||
      shape === "wallet-routing";
  }

  function directRouteDisplayPriority(opt) {
    if (isExecutableRouteOption(opt)) return 0;
    if (
      opt?.execution_readiness?.execution_ready === true ||
      opt?.execution_status === "executable_capable" ||
      opt?.is_clickable === true
    ) {
      return 1;
    }
    return 2;
  }

  function chooseDisplayDirectRoute(candidates) {
    return candidates
      .filter(isDirectSimpleRouteOption)
      .map((opt, idx) => ({ opt, idx, priority: directRouteDisplayPriority(opt) }))
      .sort((a, b) => a.priority - b.priority || a.idx - b.idx)[0]?.opt || null;
  }

  function uniqueRouteOptions(options) {
    const seen = new Set();
    const out = [];
    for (const opt of options) {
      if (!opt) continue;
      const key = routeDisplayKey(opt);
      if (seen.has(key)) continue;
      seen.add(key);
      out.push(opt);
    }
    return out;
  }

  const recommendationText =
    (displayRec?.is_comparison_only === true ? "Best quote: " : "Recommended: ") +
    (surfaceRouteLabel(displayRec) || "unknown-route") +
    " • ~" +
    fmtTokenAmount(displayRec.estimated_output) +
    " " +
    (displayRec.to_token || toToken);

  try {
    const variantErrors = Array.isArray(quote?.debug?.variant_errors)
      ? quote.debug.variant_errors
      : [];

    const broaderSearchTierBlocked = variantErrors.some((e) => {
      const detail = String(e?.detail || "").toLowerCase();
      return detail.includes("restrict_intermediate_tokens") && detail.includes("free tier");
    });

    const displayCandidates = uniqueRouteOptions([
      directRoute,
      recommendedExecutable,
      ...otherOptions
    ]);
    const displayDirectRoute = chooseDisplayDirectRoute(displayCandidates);
    const directMatchesRecommended =
      displayDirectRoute &&
      sameOption(displayRec, displayDirectRoute);

    const defaultAlternativeOptions = uniqueRouteOptions([
      recommendedExecutable,
      directRoute,
      ...otherOptions
    ]).filter((opt) => {
      if (sameOption(opt, displayRec)) return false;
      if (displayDirectRoute && !directMatchesRecommended && sameOption(opt, displayDirectRoute)) return false;
      return true;
    });

    let compareSummary = "Other options: " + defaultAlternativeOptions.length;

    if (displayDirectRoute && !directMatchesRecommended) {
      compareSummary += " • Direct route available";
    }

    if (broaderSearchTierBlocked) {
      compareSummary += " • Broader search limited";
    }

    $("swapRecommendation").textContent = "";
    $("swapCompareSummary").textContent = "";
    $("swapRecommendation").style.display = "none";
    $("swapCompareSummary").style.display = "none";

    const alternativesHtml = defaultAlternativeOptions.length
      ? defaultAlternativeOptions
          .map((opt, idx) => renderCompactAlternativeCard(opt, idx, displayRec))
          .join("")
      : "";

    $("swapRecommendedBox").innerHTML = renderSwapOptionCard({...displayRec, kind: "recommended"}, {
      showRecommendedAction: displayRec?.is_comparison_only !== true,
      cardRole: "recommended"
    });

    $("swapAlternativesCard").style.display = "block";
    $("swapAlternativesBox").innerHTML = alternativesHtml ||
      "<div class='muted'>No remaining alternatives returned for this quote.</div>";

    let directNote = "";
    let directMatchesAlternative = false;

    if (displayDirectRoute) {
      directMatchesAlternative = defaultAlternativeOptions.some((opt) => {
        return (
          opt?.route_label === displayDirectRoute?.route_label &&
          String(opt?.estimated_output_raw) === String(displayDirectRoute?.estimated_output_raw)
        );
      });

      if (directMatchesRecommended) {
        directNote = "Direct route is also the current recommendation.";
        $("swapDirectBox").innerHTML = renderSwapOptionCard({...displayRec, ...displayDirectRoute, ...displayRec, kind: "direct"}, {
          note: directNote,
          compactDirect: true,
          showDirectAction: true,
          showCostSummary: true,
          cardRole: "direct",
          bestOption: displayRec
        });
      } else {
        if (displayDirectRoute?.is_comparison_only === true && !isExecutableRouteOption(displayDirectRoute)) {
          directNote = "Quote-only direct check. No swap action is available for this provider yet.";
        } else if (directMatchesAlternative) {
          directNote = "This direct route also appears in the alternatives.";
        } else if (outputsAreComparable(displayDirectRoute, displayRec)) {
          directNote = "Direct route with comparable output.";
        } else {
          directNote = "Direct route check, not necessarily the best output.";
        }

        $("swapDirectBox").innerHTML = renderSwapOptionCard({...displayDirectRoute, kind: "direct"}, {
          note: directNote,
          compactDirect: true,
          showDirectAction: true,
          showCostSummary: true,
          cardRole: "direct",
          bestOption: displayRec
        });
      }
    } else {
      $("swapDirectBox").innerHTML =
        "<div class='muted'>No direct-route check was returned for this request.</div>";
    }

    $("swapDebugWrap").style.display = "block";
    $("swapQuotePreview").textContent = JSON.stringify(quote, null, 2);

    setSwapPhase("Quoted", "Backend quote preview ready.");
    showSwapStatus("ok", "Swap preview ready", quote);
  } catch (err) {
    console.error("previewSwap render error:", err);
    setSwapPhase("Failed", "Swap quote rendering failed in the browser.");
    showSwapStatus("err", "Swap preview render failed", {
      error: err?.message || String(err)
    });
  }
}















function mintLabel(mint) {
    if (!mint) return "unknown";
    if (mint === "So11111111111111111111111111111111111111112") return "SOL";
    if (mint === "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v") return "USDC";
    if (mint === "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB") return "USDT";
    if (mint === "USD1ttGY1N17NEEHLmELoaybftRBUSErhqYiQzvEmuB") return "USD1";
    const knownSymbol = tokenListSymbolForMint(mint);
    if (knownSymbol) return knownSymbol;
    return shortenMiddle(String(mint), 4, 4);
  }
  

  function fmtSol(x) {
    if (x === null || x === undefined) return "—";
    const n = Number(x);
    if (!Number.isFinite(n)) return String(x);
    return n.toFixed(6);
  }

  async function refreshWalletBalance() {
    const bal = $("walletBalance");

    if (!phantomPubkey) {
      bal.textContent = "devnet balance: —";
      return;
    }

    try {
      const connection = new solanaWeb3.Connection(DEVNET_RPC_URL, "confirmed");
      const pubkey = new solanaWeb3.PublicKey(phantomPubkey);
      const lamports = await connection.getBalance(pubkey, "confirmed");
      const sol = lamportsToSol(lamports);
      bal.textContent = "devnet balance: " + fmtSol(sol) + " SOL";
    } catch (err) {
      bal.textContent = "devnet balance: error";
      console.error("refreshWalletBalance error:", err);
    }
  }



  function setSendPhase(phase, text) {
    const pill = $("pillSendState");
    const line = $("sendStateText");

    pill.textContent = "state: " + phase;

    let kind = "warn";
    const p = String(phase || "").toLowerCase();

    if (p === "confirmed") kind = "ok";
    else if (p === "failed") kind = "err";
    else if (p === "submitted") kind = "ok";
    else if (p === "awaiting signature") kind = "warn";
    else kind = "warn";

    pill.className = "pill " + kind;
    line.textContent = text || "";
  }

  function setSendSignature(signature) {
    const line = $("sendSigLine");
    const link = $("sendExplorerLink");

    if (!signature) {
      line.textContent = "tx signature: —";
      link.style.display = "none";
      link.href = "#";
      return;
    }

    line.textContent = "tx signature: " + signature;
    link.href = devnetExplorerLink(signature);
    link.style.display = "inline";
  }

  function resetSendStateUi() {
    setSendPhase("Draft", "Ready to build a devnet SOL transfer.");
    setSendSignature(null);
  }



  async function confirmTransactionWithTimeout(connection, payload, commitment="confirmed", timeoutMs=20000) {
    return await Promise.race([
      connection.confirmTransaction(payload, commitment),
      new Promise((_, reject) =>
        setTimeout(() => reject(new Error("Confirmation timeout after " + timeoutMs + "ms")), timeoutMs)
      )
    ]);
  }



  function devnetExplorerLink(signature) {
    return `${DEVNET_EXPLORER_BASE}${signature}?cluster=devnet`;
  }


  function parseRecipientPubkey() {
    const recipient = ($("sendRecipient").value || "").trim();
    if (!recipient) {
      throw new Error("Recipient address is required.");
    }

    try {
      return new solanaWeb3.PublicKey(recipient);
    } catch (err) {
      throw new Error("Recipient is not a valid Solana address.");
    }
  }


  function amountToLamports(amountSol) {
    const lamports = Math.round(amountSol * solanaWeb3.LAMPORTS_PER_SOL);
    if (!Number.isFinite(lamports) || lamports <= 0) {
      throw new Error("Amount is too small or invalid after lamports conversion.");
    } 
    return lamports;
  }


  function showSendStatus(kind, title, payload) {
    const box = $("sendSolStatus");
    box.style.display = "block";
    box.className = "card " + (kind === "ok" ? "ok" : (kind === "warn" ? "warn" : "err"));
    box.innerHTML = "<strong>" + title + "</strong>";
    if (payload) {
      box.innerHTML += "<pre style='margin-top:8px;'>" + escapeHtml(JSON.stringify(payload, null, 2)) + "</pre>";
    }

    logActivity(kind, title, payload);
  }

  function parseSendAmount() {
    const raw = ($("sendAmount").value || "").trim();
    const amount = Number(raw);
    if (!raw) {
      throw new Error("Amount is required.");
    }
    if (!Number.isFinite(amount)) {
      throw new Error("Amount must be a valid number.");
    }
    if (amount <= 0) {
      throw new Error("Amount must be greater than 0.");
    }
    return amount;
  }

  function parseRecipient() {
    const recipient = ($("sendRecipient").value || "").trim();
    if (!recipient) {
      throw new Error("Recipient address is required.");
    }

    // light validation for Monday:
    // Solana pubkeys are base58 and usually 32-44 chars.
    if (recipient.length < 32 || recipient.length > 44) {
      throw new Error("Recipient address length looks invalid for Solana.");
    }

    return recipient;
  }

  function validateSendSolForm() {
    try {
      const recipientPubkey = parseRecipientPubkey();
      const amount = parseSendAmount();
      const lamports = amountToLamports(amount);

      showSendStatus("ok", "Send form looks valid", {
        network: "devnet",
        recipient: recipientPubkey.toBase58(),
        amount_sol: amount,
        lamports
      });

      return { ok: true, recipientPubkey, amount, lamports };
    } catch (err) {
      showSendStatus("warn", "Validation failed", {
        error: err?.message || String(err)
      });
      return { ok: false };
    }
  }
  


  async function validateSendSol() {
    const form = validateSendSolForm();
    if (form.ok) {
      setSendPhase("Draft", "Form is valid and ready for wallet approval.");
    } else {
      setSendPhase("Failed", "Validation failed. Fix the input and try again.");
    }
  }

  function lamportsToSol(lamports) {
    return Number(lamports) / solanaWeb3.LAMPORTS_PER_SOL;
  }




  async function sendSol() {
    const form = validateSendSolForm();
    if (!form.ok) return;
    
    setSendSignature(null);
    setSendPhase("Draft", "Transaction built locally and ready to request wallet approval.");

    phantomProvider = getPhantomProvider();
    setWalletLine();

    if (!phantomProvider) {
      showSendStatus("warn", "Phantom not detected", {
        error: "Install/enable Phantom browser extension first."
      });
      return;
    }

    if (!phantomPubkey) {
      await connectPhantom(false);
      if (!phantomPubkey) {
        showSendStatus("warn", "Wallet not connected", {
          error: "Connect Phantom before sending."
        });
        return;
      }
    }


    const providerPubkeyStr = phantomProvider?.publicKey?.toString?.() || null;
    const activeWalletPubkey = providerPubkeyStr || phantomPubkey;

    if (!activeWalletPubkey) {
      showSendStatus("warn", "Wallet public key missing", {
        phantomPubkey,
        providerPubkey: providerPubkeyStr
      });
      return;
    }

    if (providerPubkeyStr && phantomPubkey && providerPubkeyStr !== phantomPubkey) {
      console.warn("Phantom key mismatch detected", {
        phantomPubkey,
        providerPubkey: providerPubkeyStr
      });

      phantomPubkey = providerPubkeyStr;
      setWalletLine();
    }

    await refreshWalletBalance();

    try {
      showSendStatus("ok", "Preparing transaction", {
        from_ui: phantomPubkey,
        from_provider: providerPubkeyStr,
        from_active: activeWalletPubkey,
        to: form.recipientPubkey.toBase58(),
        amount_sol: form.amount,
        lamports: form.lamports,
        network: "devnet"
      });

      const connection = new solanaWeb3.Connection(DEVNET_RPC_URL, "confirmed");
      const fromPubkey = new solanaWeb3.PublicKey(activeWalletPubkey);

      const { blockhash, lastValidBlockHeight } = await connection.getLatestBlockhash("confirmed");

      const tx = new solanaWeb3.Transaction({
        feePayer: fromPubkey,
        recentBlockhash: blockhash,
      }).add(
        solanaWeb3.SystemProgram.transfer({
          fromPubkey,
          toPubkey: form.recipientPubkey,
          lamports: form.lamports,
        })
      );


      // ---- PRE-FLIGHT BALANCE CHECK (must happen BEFORE Phantom send) ----
      const senderBalanceLamports = await connection.getBalance(fromPubkey, "confirmed");

      let estimatedFeeLamports = 5000; // fallback
      try {
        const feeResp = await connection.getFeeForMessage(tx.compileMessage(), "confirmed");
        if (feeResp && typeof feeResp.value === "number") {
          estimatedFeeLamports = feeResp.value;
        }
      } catch (e) {
        console.warn("Could not estimate fee, using fallback:", e);
      }
 
      const totalNeededLamports = form.lamports + estimatedFeeLamports;

      const preflightPayload = {
        wallet_ui: phantomPubkey,
        wallet_provider: providerPubkeyStr,
        wallet_active: activeWalletPubkey,
        senderBalanceLamports,
        senderBalanceSol: lamportsToSol(senderBalanceLamports),
        amountLamports: form.lamports,
        amountSol: form.amount,
        estimatedFeeLamports,
        estimatedFeeSol: lamportsToSol(estimatedFeeLamports),
        totalNeededLamports,
        totalNeededSol: lamportsToSol(totalNeededLamports),
        recipient: form.recipientPubkey.toBase58(),
        network: "devnet"
      };

      console.log("Preflight balance check", preflightPayload);
      showSendStatus("ok", "Preflight check", preflightPayload);

      if (senderBalanceLamports < totalNeededLamports) {
        setSendPhase("Failed", "Not enough devnet SOL for amount + network fee.");
        showSendStatus("warn", "Insufficient SOL balance", {
          wallet: phantomPubkey,
          balance_sol: lamportsToSol(senderBalanceLamports),
          amount_sol: form.amount,
          estimated_fee_sol: lamportsToSol(estimatedFeeLamports),
          total_needed_sol: lamportsToSol(totalNeededLamports),
          network: "devnet"
        });
        return;
      }

      setSendPhase("Awaiting Signature", "Waiting for Phantom approval...");

      showSendStatus("ok", "Awaiting Phantom approval", {
        from_ui: phantomPubkey,
        from_provider: providerPubkeyStr,
        from_active: activeWalletPubkey,
        to: form.recipientPubkey.toBase58(),
        amount_sol: form.amount,
        network: "devnet"
      });

      // Ask Phantom to sign only; submit via our own devnet RPC
      console.log("About to request Phantom signature", {
        from_ui: phantomPubkey,
        from_provider: providerPubkeyStr,
        from_active: activeWalletPubkey,
        to: form.recipientPubkey.toBase58(),
        lamports: form.lamports,
        network: "devnet"
      });

      showSendStatus("ok", "Awaiting Phantom signature", {
        from_ui: phantomPubkey,
        from_provider: providerPubkeyStr,
        from_active: activeWalletPubkey,
        to: form.recipientPubkey.toBase58(),
        amount_sol: form.amount,
        network: "devnet"
      });

      const signedTx = await phantomProvider.signTransaction(tx);

      if (!signedTx) {
        throw new Error("Phantom did not return a signed transaction.");
      }

      showSendStatus("ok", "Signed by Phantom, submitting via app RPC", {
        from_active: activeWalletPubkey,
        to: form.recipientPubkey.toBase58(),
        network: "devnet"
      });

      const rawTx = signedTx.serialize();

      const signature = await connection.sendRawTransaction(rawTx, {
        skipPreflight: false,
        preflightCommitment: "confirmed"
      });

      if (!signature) {
        throw new Error("No transaction signature returned after RPC submission.");
      }

      setSendSignature(signature);
      setSendPhase("Submitted", "Transaction submitted via app RPC. Waiting for devnet confirmation...");
      showSendStatus("ok", "Transaction submitted", {
        signature,
        explorer: devnetExplorerLink(signature),
        status: "submitted-via-app-rpc"
      });


      // Confirmation step
      const confirmation = await confirmTransactionWithTimeout(
        connection,
        {
          signature,
          blockhash,
          lastValidBlockHeight,
        },
        "confirmed",
        20000
      );

      if (confirmation?.value?.err) {
        setSendPhase("Failed", "Transaction reached the network but failed.");
        showSendStatus("err", "Transaction failed", {
          signature,
          explorer: devnetExplorerLink(signature),
          error: confirmation.value.err
        });
        return;
      }

      setSendPhase("Confirmed", "Transaction confirmed on devnet.");

      showSendStatus("ok", "Transaction confirmed", {
        signature,
        explorer: devnetExplorerLink(signature),
        status: "confirmed"
      });

    } catch (err) {
      console.error("sendSol raw error:", err);

      const raw =
        err?.message ||
        err?.error?.message ||
        err?.data?.message ||
        err?.details ||
        err?.toString?.() ||
        JSON.stringify(err, Object.getOwnPropertyNames(err || {})) ||
        "Unknown error";

      const msg = String(raw);

      let title = "Send SOL failed";
      let kind = "warn";

      const lower = msg.toLowerCase();

      if (lower.includes("insufficient")) {
        title = "Insufficient SOL balance";
      } else if (lower.includes("user rejected") || err?.code === 4001) {
        title = "User rejected transaction";
      } else if (lower.includes("invalid")) {
        title = "Invalid transaction input";
      } else if (lower.includes("timeout")) {
        title = "RPC timeout";
      }
      
      setSendPhase("Failed", "Transaction could not be completed.");
      showSendStatus(kind, title, {
        error: msg,
        code: err?.code ?? null,
        raw: err
      });
    }
  }




  async function requestDevnetAirdrop() {
    phantomProvider = getPhantomProvider();
    setWalletLine();

    if (!phantomProvider) {
      showSendStatus("warn", "Phantom not detected", {
        error: "Install/enable Phantom browser extension first."
      });
      return;
    }

    if (!phantomPubkey) {
      await connectPhantom(false);
      if (!phantomPubkey) {
        showSendStatus("warn", "Wallet not connected", {
          error: "Connect Phantom before requesting an airdrop."
        });
        return;
      }
    }

    try {
      setSendPhase("Draft", "Requesting devnet airdrop...");
      showSendStatus("ok", "Requesting devnet airdrop", {
        wallet: phantomPubkey,
        amount_sol: 1,
        network: "devnet"
      });

      const connection = new solanaWeb3.Connection(DEVNET_RPC_URL, "confirmed");
      const pubkey = new solanaWeb3.PublicKey(phantomPubkey);

      const signature = await connection.requestAirdrop(
        pubkey,
        solanaWeb3.LAMPORTS_PER_SOL
      );

      setSendSignature(signature);
      setSendPhase("Submitted", "Airdrop requested. Waiting for confirmation...");

      const latest = await connection.getLatestBlockhash("confirmed");

      const confirmation = await confirmTransactionWithTimeout(
        connection,
        {
          signature,
          blockhash: latest.blockhash,
          lastValidBlockHeight: latest.lastValidBlockHeight,
        },
        "confirmed",
        20000
      );

      if (confirmation?.value?.err) {
        setSendPhase("Failed", "Airdrop request reached the network but failed.");
        showSendStatus("err", "Airdrop failed", {
          signature,
          explorer: devnetExplorerLink(signature),
          error: confirmation.value.err
        });
        return;
      }

      await refreshWalletBalance();

      setSendPhase("Confirmed", "Devnet airdrop confirmed.");
      showSendStatus("ok", "Airdrop confirmed", {
        signature,
        explorer: devnetExplorerLink(signature),
        wallet: phantomPubkey,
        new_balance_hint: $("walletBalance").textContent
      });

    } catch (err) {
    console.error("requestDevnetAirdrop raw error:", err);

    const raw =
      err?.message ||
      err?.error?.message ||
      err?.data?.message ||
      err?.details ||
      err?.toString?.() ||
      JSON.stringify(err, Object.getOwnPropertyNames(err || {})) ||
      "Unknown error";

    const msg = String(raw);
    const lower = msg.toLowerCase();

    let title = "Airdrop failed";
    let friendly =
      "Devnet airdrop could not be completed.";

    if (lower.includes('"code": 429') || lower.includes(" 429 ") || lower.includes("faucet has run dry")) {
      title = "Devnet faucet unavailable";
      friendly = "You may have hit the airdrop limit, or the public devnet faucet is temporarily out of test SOL.";
    } else if (lower.includes("internal error")) {
      title = "Devnet airdrop unavailable";
      friendly = "The public devnet RPC/faucet returned an internal error. Try again later.";
    } else if (lower.includes("timeout")) {
      title = "Airdrop timeout";
      friendly = "The devnet faucet did not confirm in time. Try again later.";
    }

    setSendPhase("Failed", friendly);
    showSendStatus("warn", title, {
      message: friendly,
      error: msg,
      code: err?.code ?? null,
      raw: err
    });
  }
}





  



function qs(params) {
    const sp = new URLSearchParams();
    Object.entries(params).forEach(([k,v]) => {
      if (v === undefined || v === null || v === "") return;
      sp.set(k, String(v));
    });
    return sp.toString();
  }

  async function fetchMaybeJson(url, opts={}) {
    const res = await fetch(url, opts);
    const text = await res.text();
    let data = null;
    try { data = JSON.parse(text); } catch(e) {}
    return { ok: res.ok, status: res.status, text, data };
  }

  function tokenInputValue(side) {
    const id = side === "from" ? "swapFromToken" : "swapToToken";
    return ($(id)?.value || "").trim();
  }

  function canonicalSwapTokenQuery(side) {
    const id = side === "from" ? "swapFromToken" : "swapToToken";
    const input = $(id);
    const selectedMint = String(input?.dataset?.selectedMint || "").trim();
    const selectedSymbol = String(input?.dataset?.selectedSymbol || "").trim();
    const visibleValue = String(input?.value || "").trim();
    if (
      selectedMint &&
      selectedSymbol &&
      visibleValue.toLowerCase() === selectedSymbol.toLowerCase()
    ) {
      return selectedMint;
    }
    return visibleValue;
  }

  function recognizedSwapTokenKey(token) {
    const mint = String(token?.mint || "").trim();
    return mint ? mint.toLowerCase() : "";
  }

  function normalizeRecognizedSwapToken(token) {
    if (!token || typeof token !== "object") return null;
    const mint = String(token.mint || "").trim();
    const decimals = Number(token.decimals);
    const registryToken = swapTokenList.find((item) =>
      mint && String(item?.mint || "").trim().toLowerCase() === mint.toLowerCase()
    );
    const symbol = String(token.symbol || registryToken?.symbol || token.display_name || "").trim();
    if (!mint || !Number.isInteger(decimals) || decimals < 0 || !symbol) return null;
    const assetKey = String(
      token.asset_key ||
      token.asset ||
      registryToken?.asset_key ||
      registryToken?.asset ||
      ("spl:" + mint)
    ).trim();
    return {
      symbol,
      display_name: String(token.display_name || token.name || registryToken?.display_name || symbol).trim() || symbol,
      name: String(token.name || token.display_name || registryToken?.display_name || symbol).trim() || symbol,
      mint: String(registryToken?.mint || mint).trim(),
      asset_key: assetKey,
      decimals,
      logo_uri: token.logo_uri || token.logoURI || token.icon_uri || token.iconUrl || token.image || token.image_url || "",
      source: token.source || token.resolver_source || "external_resolver",
      decimals_source: token.decimals_source || "",
      verified: Boolean(token.verified),
      default_enabled: false,
      can_quote: true
    };
  }

  function recognizedSwapTokenAssetKey(token) {
    const normalized = normalizeRecognizedSwapToken(token);
    if (!normalized) return "";
    const registryToken = swapTokenList.find((item) =>
      normalized.mint && String(item?.mint || "").trim().toLowerCase() === normalized.mint.toLowerCase()
    );
    if (registryToken?.asset_key || registryToken?.asset) {
      return String(registryToken.asset_key || registryToken.asset).trim();
    }
    return normalized.asset_key || ("spl:" + normalized.mint);
  }

  function recognizedSwapTokenAssetKeys() {
    return Object.values(swapRecognizedTokenMap)
      .map((token) => recognizedSwapTokenAssetKey(token))
      .filter(Boolean);
  }

  function recognizedSwapTokenForAsset(asset, position=null) {
    const assetKey = String(asset || "").trim().toLowerCase();
    const positionMint = String(position?.mint || "").trim().toLowerCase();
    return Object.values(swapRecognizedTokenMap).find((token) => {
      const mint = String(token?.mint || "").trim().toLowerCase();
      const tokenAsset = String(token?.asset_key || token?.asset || "").trim().toLowerCase();
      const symbol = String(token?.symbol || "").trim().toLowerCase();
      const registryToken = swapTokenList.find((item) =>
        mint && String(item?.mint || "").trim().toLowerCase() === mint
      );
      const registryAsset = String(registryToken?.asset_key || registryToken?.asset || "").trim().toLowerCase();
      return (mint && (assetKey === mint || assetKey === "spl:" + mint || positionMint === mint)) ||
        (tokenAsset && assetKey === tokenAsset) ||
        (registryAsset && assetKey === registryAsset) ||
        (symbol && assetKey === symbol);
    }) || null;
  }

  function swapPortfolioAssetRequestValue() {
    const typedAssets = String($("assetsInput")?.value || "")
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
    const currentAssets = Object.keys(latestPortfolioReport?.positions || {});
    const baseAssets = typedAssets.length ? typedAssets : (currentAssets.length ? currentAssets : ["sol", "usdc"]);
    const assets = [];
    const seen = new Set();
    const addAsset = (asset) => {
      const value = String(asset || "").trim();
      if (!value) return;
      const recognized = recognizedSwapTokenForAsset(value);
      const mint = String(recognized?.mint || "").trim();
      const keyParts = [
        value,
        value.replace(/^spl:/i, ""),
        recognized?.asset_key,
        recognized?.asset,
        mint,
        mint ? "spl:" + mint : "",
        recognized?.symbol
      ]
        .map((item) => normalizeSwapAssetKey(item))
        .filter(Boolean);
      const duplicate = keyParts.some((key) => seen.has(key));
      if (duplicate) return;
      keyParts.forEach((key) => seen.add(key));
      assets.push(value);
    };
    baseAssets.forEach(addAsset);
    for (const asset of recognizedSwapTokenAssetKeys()) {
      addAsset(asset);
    }
    if (!assets.length) return "";
    return assets.join(",");
  }

  function loadRecognizedSwapTokens() {
    swapRecognizedTokenMap = {};
    try {
      const raw = localStorage.getItem(SWAP_RECOGNIZED_TOKENS_STORAGE_KEY);
      const parsed = raw ? JSON.parse(raw) : [];
      const tokens = Array.isArray(parsed) ? parsed : [];
      for (const item of tokens) {
        const token = normalizeRecognizedSwapToken(item);
        const key = recognizedSwapTokenKey(token);
        if (key) swapRecognizedTokenMap[key] = token;
      }
    } catch (err) {
      swapRecognizedTokenMap = {};
    }
  }

  function saveRecognizedSwapTokens() {
    try {
      localStorage.setItem(
        SWAP_RECOGNIZED_TOKENS_STORAGE_KEY,
        JSON.stringify(Object.values(swapRecognizedTokenMap).slice(0, 50))
      );
    } catch (err) {
      // Session recognition still works without localStorage.
    }
  }

  function mergeRecognizedSwapTokensIntoList() {
    const byMint = new Map();
    const merged = [];
    for (const token of swapTokenList) {
      const mint = String(token?.mint || "").toLowerCase();
      if (mint) byMint.set(mint, token);
      merged.push(token);
    }
    for (const token of Object.values(swapRecognizedTokenMap)) {
      const mint = String(token?.mint || "").toLowerCase();
      if (!mint || byMint.has(mint)) continue;
      byMint.set(mint, token);
      merged.push(token);
    }
    swapTokenList = merged;
  }

  function rememberResolvedSwapToken(token) {
    const normalized = normalizeRecognizedSwapToken(token);
    const key = recognizedSwapTokenKey(normalized);
    if (!key) return null;
    swapRecognizedTokenMap[key] = normalized;
    saveRecognizedSwapTokens();
    mergeRecognizedSwapTokensIntoList();
    renderSwapTokenChoices();
    return normalized;
  }

  function useResolvedSwapToken(side) {
    const token = swapTokenResolveState[side];
    const recognized = rememberResolvedSwapToken(token);
    if (!recognized) return;
    const input = $(side === "from" ? "swapFromToken" : "swapToToken");
    const selectedValue = recognized.symbol || recognized.display_name || recognized.mint;
    if (input) input.value = selectedValue;
    if (input) {
      input.dataset.selectedMint = recognized.mint;
      input.dataset.selectedSymbol = recognized.symbol || recognized.display_name || "";
    }
    swapSelectedRecognizedTokenMint[side] = recognized.mint;
    resetSwapStateForTokenChange({ clearAmount: side === "from" });
    setTokenResolvePreview(side, recognized);
    if (side === "from") {
      renderSwapFromBalance();
      renderSwapHoldingsDropdown();
    }
    updateLiveSwapBaseline();
  }

  function resetResolvedSwapTokenSelection(side) {
    swapSelectedRecognizedTokenMint[side] = "";
    const input = $(side === "from" ? "swapFromToken" : "swapToToken");
    if (input) {
      delete input.dataset.selectedMint;
      delete input.dataset.selectedSymbol;
    }
    renderSwapTokenPillIcon(side);
  }

  function selectedFromRecognizedToken() {
    const query = normalizeSwapAssetKey($("swapFromToken")?.value);
    const resolvedMint = normalizeSwapAssetKey(swapTokenResolveState.from?.mint);
    return Object.values(swapRecognizedTokenMap).find((token) => {
      const mint = normalizeSwapAssetKey(token?.mint);
      const asset = normalizeSwapAssetKey(token?.asset_key || token?.asset);
      const symbol = normalizeSwapAssetKey(token?.symbol);
      return (query && (query === mint || query === asset || query === symbol)) ||
        (resolvedMint && resolvedMint === mint);
    }) || null;
  }

  function renderSwapTokenChoices() {
    const list = $("swapTokenChoices");
    if (!list) return;

    list.innerHTML = "";
    for (const token of swapTokenList) {
      const symbol = String(token.symbol || "").toUpperCase();
      if (!symbol) continue;

      const opt = document.createElement("option");
      opt.value = symbol;
      const name = token.display_name || symbol;
      opt.label = name === symbol ? symbol : symbol + " - " + name;
      list.appendChild(opt);
    }
  }

  function renderSwapTokenSelectors() {
    renderSwapTokenChoices();
    if (!$("swapFromToken").value) $("swapFromToken").value = "SOL";
    if (!$("swapToToken").value) $("swapToToken").value = "USDC";
    renderSwapTokenPillIcons();
  }

  function tokenLogoUri(token) {
    return String(
      token?.logo_uri ||
      token?.logoURI ||
      token?.icon_uri ||
      token?.iconUrl ||
      token?.image ||
      token?.image_url ||
      ""
    ).trim();
  }

  function safeTokenLogoUri(value) {
    const uri = String(value || "").trim();
    if (!uri) return "";
    const lower = uri.toLowerCase();
    return lower.startsWith("http://") || lower.startsWith("https://") || lower.startsWith("data:image/")
      ? uri
      : "";
  }

  function tokenDisplaySymbolForSide(side) {
    const input = $(side === "from" ? "swapFromToken" : "swapToToken");
    return String(input?.dataset?.selectedSymbol || input?.value || "").trim();
  }

  function applyTokenSymbolFit(side, symbol) {
    const input = $(side === "from" ? "swapFromToken" : "swapToToken");
    const selector = $(side === "from" ? "swapFromTokenSelector" : "swapToTokenSelector");
    const normalized = normalizeSwapAssetKey(symbol).replace(/^SPL:/, "");
    const isLongSymbol = normalized.length >= 5;
    input?.classList.toggle("token-symbol-compact", isLongSymbol);
    selector?.classList.toggle("is-long-symbol", isLongSymbol);
    if (selector) selector.dataset.longSymbol = isLongSymbol ? "true" : "false";
  }

  function tokenForPillIcon(side) {
    const input = $(side === "from" ? "swapFromToken" : "swapToToken");
    const value = normalizeSwapAssetKey(input?.value);
    const selectedMint = normalizeSwapAssetKey(input?.dataset?.selectedMint);
    const resolved = swapTokenResolveState[side];
    const resolvedMint = normalizeSwapAssetKey(resolved?.mint);
    const recognizedMint = normalizeSwapAssetKey(swapSelectedRecognizedTokenMint[side]);
    const candidates = [
      resolved,
      ...swapTokenList,
      ...Object.values(swapRecognizedTokenMap)
    ].filter(Boolean);

    return candidates.find((token) => {
      const symbol = normalizeSwapAssetKey(token?.symbol);
      const displayName = normalizeSwapAssetKey(token?.display_name || token?.name);
      const mint = normalizeSwapAssetKey(token?.mint);
      const asset = normalizeSwapAssetKey(token?.asset_key || token?.asset);
      return (
        (value && (value === symbol || value === displayName || value === mint || value === asset)) ||
        (selectedMint && selectedMint === mint) ||
        (resolvedMint && resolvedMint === mint) ||
        (recognizedMint && recognizedMint === mint)
      );
    }) || null;
  }

  function renderSwapTokenPillIcon(side) {
    const icon = $(side === "from" ? "swapFromTokenIcon" : "swapToTokenIcon");
    if (!icon) return;

    const token = tokenForPillIcon(side);
    const rawSymbol = token?.symbol || tokenDisplaySymbolForSide(side) || (side === "from" ? "SOL" : "USDC");
    const symbol = normalizeSwapAssetKey(rawSymbol).replace(/^SPL:/, "") || "?";
    const logoUri = safeTokenLogoUri(tokenLogoUri(token));
    const initials = symbol.slice(0, symbol.length >= 4 ? 4 : 3);

    applyTokenSymbolFit(side, symbol);
    icon.className = "token-pill-icon";
    icon.style.backgroundImage = "";
    icon.textContent = initials;

    if (logoUri) {
      icon.classList.add("has-image");
      icon.style.backgroundImage = "url(" + JSON.stringify(logoUri) + ")";
      return;
    }

    if (symbol === "SOL") {
      icon.classList.add("token-pill-icon-sol");
      icon.textContent = "SOL";
      return;
    }
    if (symbol === "USDC") {
      icon.classList.add("token-pill-icon-usdc");
      icon.textContent = "$";
      return;
    }
    icon.classList.add("token-pill-icon-fallback");
  }

  function renderSwapTokenPillIcons() {
    renderSwapTokenPillIcon("from");
    renderSwapTokenPillIcon("to");
  }

  function selectedTokenDataset(side) {
    const input = $(side === "from" ? "swapFromToken" : "swapToToken");
    return {
      mint: String(input?.dataset?.selectedMint || ""),
      symbol: String(input?.dataset?.selectedSymbol || "")
    };
  }

  function applySelectedTokenDataset(side, data) {
    const input = $(side === "from" ? "swapFromToken" : "swapToToken");
    if (!input) return;
    if (data?.mint) input.dataset.selectedMint = data.mint;
    else delete input.dataset.selectedMint;
    if (data?.symbol) input.dataset.selectedSymbol = data.symbol;
    else delete input.dataset.selectedSymbol;
  }

  function parseSwapReceiveAmountText(value) {
    const text = String(value || "").trim();
    if (!text || text === "—" || /preview quote/i.test(text) || text.includes("$")) return null;
    const match = text.match(/~?[ \t]*([0-9][0-9,]*(?:[.][0-9]+)?|[.][0-9]+)/);
    if (!match) return null;
    const amountText = match[1].replace(/,/g, "");
    const amount = Number(amountText);
    return Number.isFinite(amount) && amount > 0 ? amountText : null;
  }

  function currentSwapReceiveAmountText() {
    return parseSwapReceiveAmountText($("swapBuyEstimate")?.textContent);
  }

  function swapSellBuyTokens() {
    const fromInput = $("swapFromToken");
    const toInput = $("swapToToken");
    if (!fromInput || !toInput) return;

    const fromValue = fromInput.value;
    const toValue = toInput.value;
    const amountInput = $("swapAmount");
    const currentAmount = amountInput?.value || "";
    const receiveAmount = currentSwapReceiveAmountText();
    const fromDataset = selectedTokenDataset("from");
    const toDataset = selectedTokenDataset("to");
    const fromSelectedMint = swapSelectedRecognizedTokenMint.from;
    const toSelectedMint = swapSelectedRecognizedTokenMint.to;

    fromInput.value = toValue;
    toInput.value = fromValue;
    applySelectedTokenDataset("from", toDataset);
    applySelectedTokenDataset("to", fromDataset);
    swapSelectedRecognizedTokenMint.from = toSelectedMint;
    swapSelectedRecognizedTokenMint.to = fromSelectedMint;

    resetSwapStateForTokenChange({ clearAmount: false });
    if (amountInput) amountInput.value = receiveAmount || currentAmount;
    resolveSwapTokenInput("from");
    resolveSwapTokenInput("to");
    renderSwapFromBalance();
    renderSwapHoldingsDropdown();
    renderSwapTokenPillIcons();
    updateLiveSwapBaseline();
  }

  function tokenSourceLabel(token) {
    const source = String(token?.source || token?.resolver_source || "").toLowerCase();
    const decimalsSource = String(token?.decimals_source || "").toLowerCase();

    if (source === "registry") return "Registry";
    if (source.includes("dexscreener") && decimalsSource.includes("solana")) {
      return "DexScreener + Solana RPC";
    }
    if (source.includes("dexscreener")) return "DexScreener";
    if (decimalsSource.includes("solana")) return "Solana RPC";
    return token?.source || "external lookup";
  }

  function setTokenResolvePreview(side, token, message, kind = "muted") {
    const id = side === "from" ? "swapFromTokenPreview" : "swapToTokenPreview";
    const box = $(id);
    if (!box) return;

    box.className = kind === "err" ? "muted err" : "muted";

    if (!token) {
      box.textContent = message || "";
      swapTokenResolveState[side] = null;
      renderSwapTokenPillIcon(side);
      if (side === "from") renderSwapFromBalance();
      if (holderConcentrationMint) resetHolderConcentration();
      return;
    }

    const symbol = token.symbol || "Unknown";
    const mint = token.mint ? shortenMiddle(String(token.mint), 6, 6) : "unknown";
    const external = token.source !== "registry" || token.verified === false;
    const selectedMint = String(swapSelectedRecognizedTokenMint[side] || "");
    const isSelectedRecognizedToken = Boolean(token.mint && selectedMint === String(token.mint));

    if (!Number.isInteger(token.decimals)) {
      box.textContent = "Token metadata found, but decimals are unresolved. Quote preview is not safe yet.";
    } else if (external) {
      rememberResolvedSwapToken(token);
      const actionLabel = isSelectedRecognizedToken ? "Token added ✓" : "Use token";
      const actionClass = isSelectedRecognizedToken
        ? "mini-btn token-resolve-use token-resolve-use-added"
        : "mini-btn token-resolve-use";
      const disabledAttr = isSelectedRecognizedToken ? " disabled" : "";
      box.innerHTML = `
        <span>${escapeHtml(symbol)} — ${escapeHtml(mint)} · quote ready</span>
        <button type="button" class="${actionClass}" data-token-resolve-use="${escapeHtml(side)}"${disabledAttr}>${actionLabel}</button>
      `;
    } else {
      box.textContent = "";
    }

    const previousExternalMint = selectedExternalTokenForHolderConcentration()?.mint || null;
    swapTokenResolveState[side] = token;
    renderSwapTokenPillIcon(side);
    if (side === "from") renderSwapFromBalance();
    const nextExternalMint = selectedExternalTokenForHolderConcentration()?.mint || null;
    if (holderConcentrationMint && previousExternalMint !== nextExternalMint) {
      resetHolderConcentration();
    }
  }

  function renderTokenResolveFailure(side, data) {
    const code = data?.code || data?.error?.code || data?.detail?.code || "";
    const detail = data?.detail || data?.message || data?.error?.message || "";

    if (String(code).includes("DECIMALS") || String(detail).toLowerCase().includes("decimals")) {
      setTokenResolvePreview(
        side,
        null,
        "Token metadata found, but decimals are unresolved. Quote preview is not safe yet.",
        "err"
      );
      return;
    }

    setTokenResolvePreview(side, null, "Could not resolve token metadata.", "err");
  }

  async function resolveSwapTokenInput(side) {
    const value = canonicalSwapTokenQuery(side);
    if (!value) {
      setTokenResolvePreview(side, null, "");
      return;
    }

    const id = side === "from" ? "swapFromTokenPreview" : "swapToTokenPreview";
    const box = $(id);
    if (box) box.textContent = "Resolving token metadata...";

    let res;
    try {
      res = await fetchMaybeJson("/tokens/resolve?" + qs({
        query: value,
        allow_external: true
      }));
    } catch (err) {
      setTokenResolvePreview(side, null, "Could not resolve token metadata.", "err");
      return;
    }

    if (!res.ok || !res.data?.ok || !res.data?.token) {
      renderTokenResolveFailure(side, res.data || {});
      updateLiveSwapBaseline();
      return;
    }

    setTokenResolvePreview(side, res.data.token);
    updateLiveSwapBaseline();
  }

  function scheduleSwapTokenResolve(side) {
    clearTimeout(swapTokenResolveTimers[side]);
    const value = tokenInputValue(side);
    if (!value) {
      setTokenResolvePreview(side, null, "");
      updateLiveSwapBaseline();
      return;
    }

    swapTokenResolveTimers[side] = setTimeout(() => {
      resolveSwapTokenInput(side);
      updateLiveSwapBaseline();
    }, 450);
  }

  async function loadSwapTokens() {
    try {
      const res = await fetchMaybeJson("/swap/tokens");
      const tokens = Array.isArray(res.data?.tokens) ? res.data.tokens : [];
      if (res.ok && res.data?.ok && tokens.length) {
        swapTokenList = tokens;
        mergeRecognizedSwapTokensIntoList();
      }
    } catch (err) {
      // Keep the built-in SOL/USDC fallback if the registry endpoint is unavailable.
    }

    renderSwapTokenSelectors();
  }

  function fmtNum(x, digits=6) {
    if (x === null || x === undefined) return "—";
    if (typeof x !== "number") return String(x);
    // smarter rounding: small numbers keep more precision
    const abs = Math.abs(x);
    if (abs === 0) return "0";
    if (abs < 0.001) return x.toPrecision(6);
    if (abs < 1) return x.toFixed(6);
    if (abs < 1000) return x.toFixed(4);
    return x.toFixed(2);
  }


  function formatImpactPct(x) {
    if (x === null || x === undefined || x === "") return "n/a";
    const n = Number(x);
    if (!Number.isFinite(n)) return "n/a";
    if (n === 0) return "0%";
    if (Math.abs(n) < 0.001) return "< 0.001%";
    if (Math.abs(n) < 0.01) return n.toFixed(4) + "%";
    return n.toFixed(2) + "%";
  }

  function formatSettingPctFromBps(bps) {
    const n = Number(bps);
    if (!Number.isFinite(n)) return "n/a";
    return (n / 100).toFixed(2) + "%";
  }

  function tokenDecimals(token) {
    const t = String(token || "").toUpperCase();
    const found = swapTokenList.find((item) =>
      String(item.symbol || "").toUpperCase() === t ||
      String(item.mint || "").toUpperCase() === t
    );
    if (found && found.decimals !== undefined && found.decimals !== null) {
      const n = Number(found.decimals);
      if (Number.isInteger(n) && n >= 0) return n;
    }
    return null;
  }

  function uiAmountFromRaw(token, rawAmount) {
    const dec = tokenDecimals(token);
    if (dec === null || rawAmount === null || rawAmount === undefined) return null;

    const n = Number(rawAmount);
    if (!Number.isFinite(n)) return null;

    return n / (10 ** dec);
  }

  function setPill(id, label, kind) {
    const el = $(id);
    el.textContent = label;
    el.className = "pill " + (kind || "");
  }

  function showStatus(kind, title, payload) {
    const box = $("status");
    box.style.display = "block";
    box.className = "card " + (kind === "ok" ? "ok" : (kind === "warn" ? "warn" : "err"));
    box.innerHTML = "<strong>" + title + "</strong>";
    if (payload) {
      box.innerHTML += "<pre style='margin-top:8px;'>" + escapeHtml(JSON.stringify(payload, null, 2)) + "</pre>";
    }

    logActivity(kind, title, payload);
  }

  function escapeHtml(s) {
    return String(s).replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;");
  }


function shortenMiddle(s, left=6, right=6) {
  if (!s) return "—";
  if (s.length <= left + right + 1) return s;
  return s.slice(0, left) + "…" + s.slice(-right);
}

function setWalletUi() {
  const pill = $("pillWallet");
  const addr = $("walletAddress");

  if (!phantomProvider) {
    pill.textContent = "wallet: Phantom not detected";
    pill.className = "pill warn";
    addr.textContent = "address: —";
    renderSwapWalletStrip();
    renderSwapWalletControls();
    return;
  }

  if (!phantomPubkey) {
    pill.textContent = "wallet: not connected";
    pill.className = "pill warn";
    addr.textContent = "address: —";
    renderSwapWalletStrip();
    renderSwapWalletControls();
    return;
  }

  pill.textContent = "wallet: connected";
  pill.className = "pill ok";
  addr.textContent = "address: " + shortenMiddle(phantomPubkey, 8, 8);
  renderSwapWalletStrip();
  renderSwapWalletControls();
}




// ---- Phantom wallet helpers (browser extension) ----
// Phantom docs: provider is available at window.phantom and Solana provider at window.phantom.solana
// Connect: provider.connect(); Sign message: provider.signMessage(encodedMessage, "utf8")
function getPhantomProvider() {
  const p = window?.phantom?.solana;
  if (p && p.isPhantom) return p;

  // some environments expose window.solana; we only accept it if it looks like Phantom
  const s = window?.solana;
  if (s && s.isPhantom) return s;

  return null;
}

let phantomProvider = null;
let phantomPubkey = null;

function setWalletLine() {
  setWalletUi();
}
  
async function connectPhantom(eager=false) {
  phantomProvider = getPhantomProvider();
  setWalletLine();
  
  if (!phantomProvider) {
    showStatus("warn", "Phantom not detected", "Install/enable Phantom browser extension, then refresh.");
    return;
  }

  try {
    // Eager connect = connect only if already trusted (no popup).
    // Phantom docs: connect({ onlyIfTrusted: true })
    const opts = eager ? { onlyIfTrusted: true } : undefined;
    const resp = opts ? await phantomProvider.connect(opts) : await phantomProvider.connect();
    phantomPubkey = resp?.publicKey?.toString?.() || phantomProvider.publicKey?.toString?.() || null;
    setWalletLine();
    await refreshWalletBalance();
    showStatus("ok", "Connected to Phantom", { publicKey: phantomPubkey, eager });
  } catch (err) {
    // Common error: user rejected (code 4001)
    phantomPubkey = null;
    setWalletLine();
    showStatus("warn", "Connect failed", err);
  }
}

async function disconnectPhantom() {
  phantomProvider = getPhantomProvider();
  if (!phantomProvider) {
    showStatus("warn", "Phantom not detected", null);
    return;
  }
  try {
    await phantomProvider.disconnect();
  } catch (err) {
    // ignore
  }
  phantomPubkey = null;
  setWalletLine();
  await refreshWalletBalance();
  $("walletSigMeta").textContent = "last signature: —";
  $("walletSigPreview").style.display = "none";
  $("walletSigPreview").textContent = "";
  showStatus("ok", "Disconnected", null);
}

// Convert Uint8Array → hex string (easy to display / copy)
function bytesToHex(bytes) {
  if (!bytes) return "";
  return Array.from(bytes).map(b => b.toString(16).padStart(2, "0")).join("");
}

async function signMessageWithPhantom() {
  phantomProvider = getPhantomProvider();
  setWalletLine();

  if (!phantomProvider) {
    showStatus("warn", "Phantom not detected", "Install Phantom extension and refresh.");
    return;
  }

  // Ensure connected first (prompts user if needed)
  if (!phantomPubkey) {
    await connectPhantom(false);
    if (!phantomPubkey) return;
  }

  // Simple “proof of ownership” message (no blockchain tx; just signature)
  const msg = `Web3 Digest authentication (devnet-safe)\nAccount: ${phantomPubkey}\nTime: ${new Date().toISOString()}`;
  const encoded = new TextEncoder().encode(msg);

  try {
    let signed;
    if (typeof phantomProvider.signMessage === "function") {
      // Phantom docs: provider.signMessage(encodedMessage, "utf8")
      signed = await phantomProvider.signMessage(encoded, "utf8");
    } else {
      // Fallback: request interface
      signed = await phantomProvider.request({
        method: "signMessage",
        params: { message: encoded, display: "hex" },
      });
    }

    // Phantom commonly returns { signature: Uint8Array, publicKey: ... }
    const sigBytes = signed?.signature || signed?.data?.signature || null;
    const sigHex = sigBytes ? bytesToHex(sigBytes) : "(no signature bytes?)";
  
    $("walletSigMeta").textContent = "last signature: " + new Date().toLocaleString();
    $("walletSigPreview").style.display = "block";
    $("walletSigPreview").textContent =
      "message:\\n" + msg + "\\n\\n" +
      "signature_hex:\\n" + sigHex;


    showStatus("ok", "Message signed", {
      publicKey: phantomPubkey,
      message: msg,
      signature_hex: sigHex,
    });
  } catch (err) {
    showStatus("warn", "Sign message failed", err);
  }
}




  function renderReport(resp) {
    const report = resp?.report;
    $("raw").textContent = JSON.stringify(resp, null, 2);

    if (!report) {
      latestPortfolioReport = null;
      latestPortfolioAccount = "";
      setPill("pillBalances", "balances: ?", "warn");
      setPill("pillPrices", "prices: ?", "warn");
      setPill("pillStale", "stale: ?", "warn");
      $("totalValue").textContent = "—";
      renderSwapWalletStrip();
      renderSwapFromBalance();
      renderSwapHoldingsDropdown();
      return;
    }

    latestPortfolioReport = report;
    latestPortfolioAccount = resp?.account || report.account || "";
    const stale = report.stale_prices || [];
    setPill("pillBalances", "balances: " + (report.balances_updated || "unknown"), stale.length ? "warn" : "ok");
    setPill("pillPrices", "prices: " + (report.prices_updated || "unknown"), stale.length ? "warn" : "ok");
    setPill("pillStale", "stale: " + stale.length, stale.length ? "warn" : "ok");

    $("totalValue").textContent = fmtNum(report.total_value, 6) + " " + (report.currency || "");
    $("changeLabel").textContent = report.change_label ? (" — " + report.change_label) : "";

    const tbody = $("positionsTable").querySelector("tbody");
    tbody.innerHTML = "";
    const positions = report.positions || {};
    const keys = Object.keys(positions);

    // sort by value desc
    keys.sort((a,b) => (positions[b]?.value ?? 0) - (positions[a]?.value ?? 0));

    for (const k of keys) {
      const p = positions[k];
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${escapeHtml(p.display || p.symbol || p.asset || k)}</td>
        <td>${escapeHtml(fmtNum(p.amount))}</td>
        <td>${escapeHtml(fmtNum(p.price))}</td>
        <td>${escapeHtml(fmtNum(p.value))}</td>
        <td>${escapeHtml(p.balance_ts || "—")}</td>
        <td>${escapeHtml(p.price_ts || "—")}</td>
      `;
      tbody.appendChild(tr);
    }
    renderSwapWalletStrip();
    renderSwapFromBalance();
    renderSwapHoldingsDropdown();
  }


  function fmtMoney(x) {
    if (x === null || x === undefined) return "—";
    const n = Number(x);
    if (!Number.isFinite(n)) return String(x);
    return n.toFixed(2);
  }

function fmtUsdCost(x) {
  if (x === null || x === undefined) return "n/a";

  const n = Number(x);
  if (!Number.isFinite(n)) return "n/a";

  if (n === 0) return "$0.00";
  const sign = n < 0 ? "-" : "";
  const abs = Math.abs(n);
  if (abs < 0.01) return sign + "$" + abs.toFixed(6);
  if (abs < 1) return sign + "$" + abs.toFixed(4);
  return sign + "$" + abs.toFixed(2);
}

  function renderHistory(resp) {
    const history = resp?.history || [];
    // sort newest-first (history row format: [ts, total, source])
    history.sort((a, b) => String(b?.[0] || "").localeCompare(String(a?.[0] || "")));
    if (!history.length) {
      $("history").innerHTML = "<div class='muted'>No history rows yet.</div>";
      return;
    }
    let html = "<table><thead><tr><th>TS</th><th>Total ($)</th><th>Source</th></tr></thead><tbody>";
    for (const row of history) {
      // row is typically [ts, total, source]
      const ts = row[0];
      const total = row[1];
      const src = row[2];
      html += `<tr><td>${escapeHtml(ts)}</td><td>${escapeHtml(fmtMoney(total))}</td><td>${escapeHtml(src)}</td></tr>`;
    }
    html += "</tbody></table>";
    $("history").innerHTML = html;
  }

  async function loadAccounts() {
    const r = await fetchMaybeJson("/accounts");
    if (!r.ok) {
      showStatus("err", "Failed to load /accounts", r.data || r.text);
      return;
    }
    const list = r.data.accounts || [];
    const sel = $("accountSelect");
    sel.innerHTML = "";
    for (const a of list) {
      const opt = document.createElement("option");
      opt.value = a.name;
      opt.textContent = a.name + " (" + (a.chain || "?") + ")";
      sel.appendChild(opt);
    }
    if (list.length) sel.value = list[0].name;
  }

  async function loadReportAndHistory() {
    const account = $("accountSelect").value;
    const currency = $("currencyInput").value || "usd";
    const assets = swapPortfolioAssetRequestValue();
    const showUnpriced = $("showUnpriced").value;

    const r1 = await fetchMaybeJson("/portfolio/latest?" + qs({
      account, currency, assets, show_unpriced: showUnpriced
    }));
    if (!r1.ok) {
      showStatus("err", "GET /portfolio/latest failed", r1.data || r1.text);
      renderReport(null);
      return false;
    }
    showStatus("ok", "Loaded latest portfolio", null);
    renderReport(r1.data);

    const r2 = await fetchMaybeJson("/portfolio/history?" + qs({ account, currency, limit: 30 }));
    if (r2.ok) renderHistory(r2.data);
    return true;
  }

  function swapAssetRefreshKeyForToken(tokenValue) {
    const raw = String(tokenValue || "").trim();
    if (!raw) return "";
    if (normalizeSwapAssetKey(raw) === "SOL") return "sol";

    const token = swapTokenList.find((item) => {
      const symbol = normalizeSwapAssetKey(item?.symbol);
      const mint = normalizeSwapAssetKey(item?.mint);
      const asset = normalizeSwapAssetKey(item?.asset_key || item?.asset);
      const query = normalizeSwapAssetKey(raw);
      return query === symbol || query === mint || query === asset;
    });
    if (token?.asset_key || token?.asset) return String(token.asset_key || token.asset).trim();
    if (token?.mint) return "spl:" + String(token.mint).trim();

    const recognized = recognizedSwapTokenForAsset(raw) || Object.values(swapRecognizedTokenMap).find((item) => {
      const query = normalizeSwapAssetKey(raw);
      return query === normalizeSwapAssetKey(item?.symbol) ||
        query === normalizeSwapAssetKey(item?.mint) ||
        query === normalizeSwapAssetKey(item?.asset_key || item?.asset);
    });
    if (recognized) return recognizedSwapTokenAssetKey(recognized);
    if (looksLikeSolanaMint(raw)) return "spl:" + raw;
    return raw;
  }

  function swapPostSuccessRefreshAssets(summary) {
    const seen = new Set();
    const assets = [];
    const add = (value) => {
      const key = swapAssetRefreshKeyForToken(value);
      if (!key) return;
      const normalized = normalizeSwapAssetKey(key);
      if (seen.has(normalized)) return;
      seen.add(normalized);
      assets.push(key);
    };
    add("SOL");
    add(summary?.from_token || canonicalSwapTokenQuery("from"));
    add(summary?.to_token || canonicalSwapTokenQuery("to"));
    return assets.join(",");
  }

  async function refreshBalances(options = {}) {
    const account = $("accountSelect").value;
    const force = "true";
    const assets = options.assetsOverride || swapPortfolioAssetRequestValue();
    const r = await fetchMaybeJson("/refresh/balances?" + qs({ account, force, assets }), { method: "POST" });
    if (!r.ok) {
      if (!options.silent) showStatus("err", "POST /refresh/balances failed", r.data || r.text);
      return false;
    }
    if (!options.silent) showStatus("ok", "Balances refreshed", r.data);
    const loaded = await loadReportAndHistory();
    latestSwapBalanceRefreshDiagnostics = {
      requested_assets_sent_by_ui: assets,
      backend_response: r.data || null,
      portfolio_assets_returned: Object.keys(latestPortfolioReport?.positions || {}),
      selected_from_holding: selectedFromHoldingDiagnostics()
    };
    const debugWrap = $("swapBalanceRefreshDebugWrap");
    const debugBox = $("swapBalanceRefreshDebug");
    if (debugWrap) debugWrap.style.display = "block";
    if (debugBox) debugBox.textContent = JSON.stringify(latestSwapBalanceRefreshDiagnostics, null, 2);
    console.debug("swap balance refresh diagnostics", latestSwapBalanceRefreshDiagnostics);
    if (loaded) {
      swapBalancesStaleAfterSubmit = false;
      renderSwapBalanceFreshnessHint(selectedFromHolding());
      renderSwapFromBalance();
    }
    return Boolean(loaded);
  }

  async function refreshBalancesAfterSwap(summary) {
    const status = $("swapPostSuccessBalanceStatus");
    if (status) status.textContent = "Refreshing balances…";
    const assets = swapPostSuccessRefreshAssets(summary);
    const ok = await refreshBalances({ assetsOverride: assets || null, silent: true, afterSwap: true });
    if (ok) {
      swapBalancesStaleAfterSubmit = false;
      if (status) status.textContent = "Balances updated just now.";
      renderSwapBalanceFreshnessHint(selectedFromHolding());
      renderSwapFromBalance();
      renderSwapWalletStrip();
    } else {
      if (status) status.textContent = "Swap confirmed. Balance refresh failed — refresh manually.";
      renderSwapBalanceFreshnessHint(selectedFromHolding());
    }
  }

  async function refreshPrices() {
    const account = $("accountSelect").value;
    const currency = $("currencyInput").value || "usd";
    const assets = $("assetsInput").value;
    const force = $("forceSelect").value;
    const useDex = $("useDex").value;
    const minLiq = $("minLiq").value;

    const r = await fetchMaybeJson("/refresh/prices?" + qs({
      account, currency, assets,
      force,
      use_dex: useDex,
      min_liquidity_usd: minLiq,
      source: "coingecko"
    }), { method: "POST" });

    if (!r.ok) {
      showStatus("err", "POST /refresh/prices failed", r.data || r.text);
      return;
    }
    showStatus("ok", "Prices refreshed", r.data);
    await loadReportAndHistory();
  }

  console.log("attaching listeners");

  $("btnLoad").addEventListener("click", loadReportAndHistory);
  $("btnRefreshBalances").addEventListener("click", refreshBalances);
  $("btnSwapRefreshBalances").addEventListener("click", refreshBalances);
  $("btnRefreshPrices").addEventListener("click", refreshPrices);

  $("btnConnectPhantom").addEventListener("click", () => connectPhantom(false));
  $("btnDisconnectPhantom").addEventListener("click", disconnectPhantom);
  $("btnSwapConnectPhantom").addEventListener("click", () => connectPhantom(false));
  $("btnSwapDisconnectPhantom").addEventListener("click", disconnectPhantom);
  $("btnSignMessage").addEventListener("click", signMessageWithPhantom);
  $("btnValidateSend").addEventListener("click", validateSendSol);
  $("btnSendSol").addEventListener("click", sendSol);
  $("btnAirdropDevnet").addEventListener("click", requestDevnetAirdrop);
  $("btnPreviewSwap").addEventListener("click", previewSwap);
  $("btnSignPreparedSwap").addEventListener("click", signAndSubmitPreparedSwap);
  $("swapSignAcknowledgement").addEventListener("change", updateSwapSignButtonState);
  $("btnClearSwap").addEventListener("click", clearSwapUi);
  $("btnCloseSwapSuccessModal").addEventListener("click", closeSwapSuccessModal);
  $("btnCloseSwapTokenModal").addEventListener("click", closeSwapTokenModal);
  $("swapSuccessModal").addEventListener("click", (event) => {
    if (event.target?.id === "swapSuccessModal") closeSwapSuccessModal();
  });
  $("swapTokenModalBackdrop").addEventListener("click", (event) => {
    if (event.target?.id === "swapTokenModalBackdrop") closeSwapTokenModal();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeSwapSuccessModal();
      closeSwapTokenModal();
    }
  });
  $("btnSwapAmountHalf").addEventListener("click", () => setSwapAmountFromHolding(0.5));
  $("btnSwapAmountMax").addEventListener("click", () => setSwapAmountFromHolding(1));
  $("btnSwapDirection").addEventListener("click", swapSellBuyTokens);
  $("swapFromTokenSelector").addEventListener("click", () => openSwapTokenModal("from"));
  $("swapToTokenSelector").addEventListener("click", () => openSwapTokenModal("to"));
  $("swapToToken").addEventListener("click", () => openSwapTokenModal("to"));
  $("swapTokenModalSearch").addEventListener("input", (event) => {
    tokenSearchQuery = String(event.target?.value || "");
    tokenModalResolvedExternalToken = null;
    renderSwapTokenModal();
    scheduleTokenModalResolve();
  });
  $("swapTokenModalBody").addEventListener("click", (event) => {
    const importButton = event.target?.closest?.("[data-token-modal-import]");
    if (importButton) {
      importTokenModalExternalToken();
      return;
    }
    const row = event.target?.closest?.("[data-token-modal-select]");
    if (!row) return;
    applySwapTokenSelection(activeTokenSide, {
      tokenValue: row.dataset.tokenValue || "",
      tokenInputValue: row.dataset.tokenInputValue || "",
      mint: row.dataset.tokenMint || "",
      symbol: row.dataset.tokenSymbol || "",
      source: row.dataset.tokenSource || ""
    });
  });
  $("swapHoldingsDropdown").addEventListener("click", (event) => {
    const button = event.target?.closest?.("[data-swap-holding-token]");
    if (!button) return;
    $("swapFromToken").value = button.dataset.swapHoldingInput || button.dataset.swapHoldingToken || "";
    $("swapHoldingsDropdown").style.display = "none";
    resetSwapStateForTokenChange({ clearAmount: true });
    resolveSwapTokenInput("from");
    renderSwapFromBalance();
    renderSwapTokenPillIcon("from");
  });
  $("swapCard").addEventListener("click", handleSwapExecuteClick);
  $("swapCard").addEventListener("click", (event) => {
    const button = event.target.closest("[data-token-resolve-use]");
    if (!button) return;
    useResolvedSwapToken(button.dataset.tokenResolveUse || "from");
  });
  $("swapAmount").addEventListener("input", () => {
    clearSwapQuoteFreshness();
    updateLiveSwapBaseline();
  });
  $("swapFromToken").addEventListener("focus", () => {
    openSwapTokenModal("from");
  });
  $("swapFromToken").addEventListener("input", () => {
    resetSwapStateForTokenChange({ clearAmount: true });
    resetResolvedSwapTokenSelection("from");
    renderSwapFromBalance();
    renderSwapTokenPillIcon("from");
    scheduleSwapTokenResolve("from");
  });
  $("swapToToken").addEventListener("input", () => {
    resetSwapStateForTokenChange({ clearAmount: false });
    resetResolvedSwapTokenSelection("to");
    renderSwapTokenPillIcon("to");
    scheduleSwapTokenResolve("to");
  });
  $("swapFromToken").addEventListener("change", () => {
    resetSwapStateForTokenChange({ clearAmount: true });
    resolveSwapTokenInput("from");
    updateLiveSwapBaseline();
    renderSwapFromBalance();
    renderSwapTokenPillIcon("from");
  });
  $("swapToToken").addEventListener("change", () => {
    resetSwapStateForTokenChange({ clearAmount: false });
    resolveSwapTokenInput("to");
    renderSwapTokenPillIcon("to");
    updateLiveSwapBaseline();
  });

  // init
  (async () => {
    resetSendStateUi();
    renderActivityLog();
    loadRecognizedSwapTokens();
    await loadSwapTokens();
    resolveSwapTokenInput("from");
    resolveSwapTokenInput("to");
    await loadAccounts();
    await loadReportAndHistory();
    await connectPhantom(true);
    await refreshWalletBalance();
  })();
</script>
</body>
</html>
"""
