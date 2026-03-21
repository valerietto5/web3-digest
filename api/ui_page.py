def build_ui_html() -> str:
  return """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>Web3 Digest — Wallet Cockpit</title>
  <style>
    body { font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; margin: 20px; }
    .row { display: flex; gap: 12px; flex-wrap: wrap; align-items: end; }
    .card { border: 1px solid #ddd; border-radius: 10px; padding: 12px; margin-top: 12px; }
    .muted { color: #666; }
    label { display: block; font-size: 12px; color: #333; margin-bottom: 4px; }
    input, select { padding: 8px; border-radius: 8px; border: 1px solid #ccc; min-width: 220px; }
    button { padding: 10px 12px; border-radius: 10px; border: 1px solid #333; background: #111; color: #fff; cursor: pointer; }
    button.secondary { background: #fff; color: #111; border-color: #aaa; }
    button:disabled { opacity: .6; cursor: not-allowed; }
    table { border-collapse: collapse; width: 100%; margin-top: 10px; }
    th, td { border-bottom: 1px solid #eee; padding: 8px; text-align: left; font-size: 13px; }
    th { background: #fafafa; position: sticky; top: 0; }
    pre { background: #0b1020; color: #d6deeb; padding: 10px; border-radius: 10px; overflow: auto; }
    .pill { display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 12px; border: 1px solid #ddd; }
    .ok { background: #e8fff0; }
    .warn { background: #fff4e5; }
    .err { background: #ffecec; }
  </style>
</head>
<body>
  <h2>Web3 Digest — Wallet Cockpit (V1 runway)</h2>
  <div class="muted">Simple UI served by FastAPI. Uses your own API endpoints under the hood.</div>

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


  <div class="card" id="swapCard">
    <h3 style="margin: 0 0 6px 0;">Swap <span class="pill warn">SOLANA-FIRST</span></h3>
    <div class="muted">Quote surface only for now. No execution yet.</div>

    <div class="row" style="margin-top: 10px;">
      <div>
        <label>From token</label>
        <select id="swapFromToken">
          <option value="SOL" selected>SOL</option>
          <option value="USDC">USDC</option>
        </select>
      </div>

      <div>
        <label>To token</label>
        <select id="swapToToken">
          <option value="USDC" selected>USDC</option>
          <option value="SOL">SOL</option>
        </select>
      </div>

      <div>
        <label>Amount</label>
        <input id="swapAmount" placeholder="1.0" />
      </div>
    </div>

    <div class="row" style="margin-top: 10px;">
      <button id="btnPreviewSwap" class="secondary">Preview Quote</button>
      <button id="btnClearSwap" class="secondary">Clear</button>
    </div>

    <div class="card" id="swapQuoteCard" style="margin-top:10px;">
      <div class="row">
        <div><span class="pill warn" id="pillSwapState">state: Draft</span></div>
        <div class="muted" id="swapStateText">Ready to request a swap quote.</div>
      </div>

      <div class="muted" id="swapRecommendation" style="margin-top:8px;">recommendation: —</div>

      <div class="muted" id="swapQuoteSummary" style="margin-top:8px;">quote: —</div>
      <div class="muted" id="swapProtectionLine" style="margin-top:8px;">protections: —</div>
      <details id="swapDebugWrap" style="margin-top:8px; display:none;">
        <summary class="muted" style="cursor:pointer;">Raw quote debug JSON</summary>
        <pre id="swapQuotePreview" style="margin-top:8px;"></pre>
      </details>
    </div>

    <div class="card" id="swapRoutesCard" style="margin-top:10px;">
      <h4 style="margin: 0 0 6px 0;">Route Comparison</h4>
      <div class="muted" id="swapCompareSummary" style="margin-top:4px;">comparison summary: —</div>
      <div class="muted" id="swapRoutePath" style="margin-top:8px;">route path: —</div>
      <div class="muted" id="swapRoutesText" style="margin-top:8px;">
        Placeholder for Jupiter first, then later Phantom / Meteora / other route sources.
      </div>
    </div>

    <div id="swapStatus" class="card" style="display:none; margin-top:10px;"></div>
  </div>



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

<script src="https://unpkg.com/@solana/web3.js@latest/lib/index.iife.min.js"></script>
<script>
  const $ = (id) => document.getElementById(id);


  const DEVNET_RPC_URL = "https://api.devnet.solana.com";
  const DEVNET_EXPLORER_BASE = "https://explorer.solana.com/tx/";


  const ACTIVITY_LIMIT = 8;
  const activityItems = [];

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


function setSwapPhase(phase, text) {
  const pill = $("pillSwapState");
  const line = $("swapStateText");

  pill.textContent = "state: " + phase;

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

function clearSwapUi() {
  $("swapAmount").value = "";
  $("swapQuoteSummary").textContent = "quote: —";
  $("swapDebugWrap").style.display = "none";
  $("swapQuotePreview").textContent = "";
  $("swapStatus").style.display = "none";
  setSwapPhase("Draft", "Ready to request a swap quote.");
  $("swapRoutesText").textContent =
    "Placeholder for Jupiter first, then later Phantom / Meteora / other route sources.";
  $("swapRecommendation").textContent = "recommendation: —";
  $("swapProtectionLine").textContent = "protections: —";
  $("swapCompareSummary").textContent = "comparison summary: —";
  $("swapRoutePath").textContent = "route path: —";
}



function resetSwapQuoteDisplay() {
  $("swapRecommendation").textContent = "recommendation: —";
  $("swapQuoteSummary").textContent = "quote: —";
  $("swapProtectionLine").textContent = "protections: —";
  $("swapCompareSummary").textContent = "comparison summary: —";
  $("swapRoutePath").textContent = "route path: —";
  $("swapRoutesText").textContent =
    "Placeholder for Jupiter first, then later Phantom / Meteora / other route sources.";
  $("swapDebugWrap").style.display = "none";
  $("swapQuotePreview").textContent = "";
}





function getSwapHttpErrorInfo(status, data, rawText) {
  const detail =
    data?.detail ||
    data?.message ||
    rawText ||
    "Unknown quote error";

  const d = String(detail).toLowerCase();

  if (status === 400) {
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




async function previewSwap() {
  const fromToken = $("swapFromToken").value;
  const toToken = $("swapToToken").value;
  const rawAmount = ($("swapAmount").value || "").trim();
  const amount = Number(rawAmount);

  if (!rawAmount) {
    setSwapPhase("Failed", "Enter an amount first.");
    showSwapStatus("warn", "Swap preview failed", {
      error: "Amount is required."
    });
    return;
  }

  if (!Number.isFinite(amount) || amount <= 0) {
    setSwapPhase("Failed", "Amount must be a valid number greater than 0.");
    showSwapStatus("warn", "Swap preview failed", {
      error: "Invalid amount."
    });
    return;
  }

  if (fromToken === toToken) {
    setSwapPhase("Failed", "From token and to token cannot be the same.");
    showSwapStatus("warn", "Swap preview failed", {
      error: "Choose two different tokens."
    });
    return;
  }

  
  setSwapPhase("Draft", "Requesting backend quote preview...");

  const url =
    "/swap/quote?" +
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

  if (!Array.isArray(quote.route_plan) || !quote.route_plan.length) {
    resetSwapQuoteDisplay();
    setSwapPhase("Failed", "No swap route was found for this request.");
    showSwapStatus("warn", "No route found", {
      quote
    });
    return;
  }






  const estOut =
    quote.estimated_output === null || quote.estimated_output === undefined
      ? "TBD"
      : fmtNum(Number(quote.estimated_output), 6);

  const minReceivedUi = uiAmountFromRaw(
    quote.to_token,
    quote.raw_quote?.otherAmountThreshold
  );

  const minReceived =
    minReceivedUi === null ? "n/a" : fmtNum(minReceivedUi, 6);

  const priceImpact = formatImpactPct(quote.price_impact_pct);
  const slippageSetting = formatSettingPctFromBps(quote.slippage_bps);
  const routeLabel = quote.route_label || "unknown-route";
  const providerLabel =
    (quote.provider || "").toLowerCase() === "jupiter-metis"
      ? "Jupiter"
      : (quote.provider || "current provider");

  const recommendationText =
    "Recommendation: Best value right now is " +
    routeLabel +
    " through " +
    providerLabel +
    " for this request.";

  const swapUsdValue =
    quote.raw_quote?.swapUsdValue === null || quote.raw_quote?.swapUsdValue === undefined
      ? "n/a"
      : "~$" + fmtNum(Number(quote.raw_quote.swapUsdValue), 2);

  $("swapRecommendation").textContent = recommendationText;
  $("swapQuoteSummary").textContent =
    "You pay: " + quote.input_amount + " " + quote.from_token +
    " | You receive (est.): " + estOut + " " + quote.to_token +
    " | Min received: " + minReceived + " " + quote.to_token;

  $("swapProtectionLine").textContent =
    "Protections: minimum received " + minReceived + " " + quote.to_token +
    " | slippage setting " + slippageSetting +
    " | impact " + priceImpact;

  const routeLegs = Array.isArray(quote.route_plan) ? quote.route_plan.length : 0;
  const routeShape =
    routeLegs <= 1 ? "direct/simple route" : (routeLegs + "-leg route");

  const routePathParts = [];

  if (Array.isArray(quote.route_plan) && quote.route_plan.length) {
    for (const leg of quote.route_plan) {
      const info = leg?.swapInfo || {};
      const inLabel = mintLabel(info.inputMint);
      const outLabel = mintLabel(info.outputMint);

      if (!routePathParts.length) {
        routePathParts.push(inLabel);
      } else if (routePathParts[routePathParts.length - 1] !== inLabel) {
        routePathParts.push(inLabel);
      }

      if (routePathParts[routePathParts.length - 1] !== outLabel) {
        routePathParts.push(outLabel);
      }
    }
  }

  const fallbackRoutePath = quote.from_token + " → " + quote.to_token;
  const routePathText = routePathParts.length ? routePathParts.join(" → ") : fallbackRoutePath;
  const stepText = routeLegs === 1 ? "1 step" : (routeLegs + " steps");

  $("swapRoutePath").textContent =
    "Route path: " + routePathText + " | Steps: " + stepText;

  $("swapCompareSummary").textContent =
    "Best value: " + routeLabel +
    " through " + providerLabel +
    " | Route type: " + routeShape +
    " | Cross-provider comparison: not active yet";

  const quoteMs =
    quote.raw_quote?.timeTaken === null || quote.raw_quote?.timeTaken === undefined
      ? "n/a"
      : Math.round(Number(quote.raw_quote.timeTaken) * 1000) + " ms";

  $("swapRoutesText").textContent =
    "Best route right now (within Jupiter): " + routeLabel +
    " | Shape: " + routeShape +
    " | Impact: " + priceImpact +
    " | Slippage setting: " + slippageSetting +
    " | Quote value: " + swapUsdValue +
    " | Quote speed: " + quoteMs +
    " | Why shown: highest output returned by current provider for this request." +
    " | Note: this is not yet a cross-provider comparison.";


  $("swapDebugWrap").style.display = "block";
  $("swapQuotePreview").textContent = JSON.stringify(quote, null, 2);

  setSwapPhase("Quoted", "Backend quote preview ready.");
  showSwapStatus("ok", "Swap preview ready", quote);
}

  function mintLabel(mint) {
    if (!mint) return "unknown";
    if (mint === "So11111111111111111111111111111111111111112") return "SOL";
    if (mint === "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v") return "USDC";
    if (mint === "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB") return "USDT";
    if (mint === "USD1ttGY1N17NEEHLmELoaybftRBUSErhqYiQzvEmuB") return "USD1";
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
    if (t === "SOL") return 9;
    if (t === "USDC") return 6;
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
    return;
  }

  if (!phantomPubkey) {
    pill.textContent = "wallet: not connected";
    pill.className = "pill warn";
    addr.textContent = "address: —";
    return;
  }

  pill.textContent = "wallet: connected";
  pill.className = "pill ok";
  addr.textContent = "address: " + shortenMiddle(phantomPubkey, 8, 8);
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
      setPill("pillBalances", "balances: ?", "warn");
      setPill("pillPrices", "prices: ?", "warn");
      setPill("pillStale", "stale: ?", "warn");
      $("totalValue").textContent = "—";
      return;
    }

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
  }


  function fmtMoney(x) {
    if (x === null || x === undefined) return "—";
    const n = Number(x);
    if (!Number.isFinite(n)) return String(x);
    return n.toFixed(2);
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
    const assets = $("assetsInput").value;
    const showUnpriced = $("showUnpriced").value;

    const r1 = await fetchMaybeJson("/portfolio/latest?" + qs({
      account, currency, assets, show_unpriced: showUnpriced
    }));
    if (!r1.ok) {
      showStatus("err", "GET /portfolio/latest failed", r1.data || r1.text);
      renderReport(null);
      return;
    }
    showStatus("ok", "Loaded latest portfolio", null);
    renderReport(r1.data);

    const r2 = await fetchMaybeJson("/portfolio/history?" + qs({ account, currency, limit: 30 }));
    if (r2.ok) renderHistory(r2.data);
  }

  async function refreshBalances() {
    const account = $("accountSelect").value;
    const force = $("forceSelect").value;
    const r = await fetchMaybeJson("/refresh/balances?" + qs({ account, force }), { method: "POST" });
    if (!r.ok) {
      showStatus("err", "POST /refresh/balances failed", r.data || r.text);
      return;
    }
    showStatus("ok", "Balances refreshed", r.data);
    await loadReportAndHistory();
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

  $("btnLoad").addEventListener("click", loadReportAndHistory);
  $("btnRefreshBalances").addEventListener("click", refreshBalances);
  $("btnRefreshPrices").addEventListener("click", refreshPrices);

  $("btnConnectPhantom").addEventListener("click", () => connectPhantom(false));
  $("btnDisconnectPhantom").addEventListener("click", disconnectPhantom);
  $("btnSignMessage").addEventListener("click", signMessageWithPhantom);
  $("btnValidateSend").addEventListener("click", validateSendSol);
  $("btnSendSol").addEventListener("click", sendSol);
  $("btnAirdropDevnet").addEventListener("click", requestDevnetAirdrop);
  $("btnPreviewSwap").addEventListener("click", previewSwap);
  $("btnClearSwap").addEventListener("click", clearSwapUi);

  // init
  (async () => {
    resetSendStateUi();
    renderActivityLog();
    await loadAccounts();
    await loadReportAndHistory();
    await connectPhantom(true);
    await refreshWalletBalance();
  })();
</script>
</body>
</html>
"""
