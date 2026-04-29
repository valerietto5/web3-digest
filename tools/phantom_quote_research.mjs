#!/usr/bin/env node

const DEFAULT_PHANTOM_API_BASE_URL = "https://api.phantom.app";
const SOLANA_MAINNET_SWAPPER_CHAIN_ID = "solana:101";
const SOLANA_MAINNET_ALIASES = new Set([
  "solana:mainnet",
  "solana:mainnet-beta",
  "solana:5eykt4UsFv8P8NJdTREpY1vzqKqZKvdp".toLowerCase(),
  SOLANA_MAINNET_SWAPPER_CHAIN_ID,
]);

const TOKEN_DECIMALS = {
  SOL: 9,
};

function writeJson(value) {
  process.stdout.write(`${JSON.stringify(value, null, 2)}\n`);
}

function structuredError(code, message, detail = {}) {
  return {
    ok: false,
    error: {
      code,
      message,
      ...detail,
    },
  };
}

async function readStdinJson() {
  const chunks = [];
  for await (const chunk of process.stdin) {
    chunks.push(chunk);
  }

  const raw = Buffer.concat(chunks).toString("utf8").trim();
  if (!raw) {
    throw structuredError("EMPTY_STDIN", "Expected a JSON request on stdin.");
  }

  try {
    return JSON.parse(raw);
  } catch (error) {
    throw structuredError("INVALID_JSON", "Stdin did not contain valid JSON.", {
      detail: error instanceof Error ? error.message : String(error),
    });
  }
}

function normalizeSolanaSwapperChainId(chainId) {
  const normalized = String(chainId || "").trim();
  if (!normalized) {
    return SOLANA_MAINNET_SWAPPER_CHAIN_ID;
  }

  if (SOLANA_MAINNET_ALIASES.has(normalized.toLowerCase())) {
    return SOLANA_MAINNET_SWAPPER_CHAIN_ID;
  }

  return normalized;
}

function buildTokenObject(chainId, mint, isNative) {
  if (isNative) {
    if (chainId !== SOLANA_MAINNET_SWAPPER_CHAIN_ID) {
      throw structuredError(
        "UNSUPPORTED_NATIVE_CHAIN",
        "This research helper currently supports native SOL on Solana mainnet only.",
        { chain_id: chainId },
      );
    }

    return {
      chainId,
      resourceType: "nativeToken",
      slip44: "501",
    };
  }

  if (!mint || typeof mint !== "string") {
    throw structuredError("MISSING_TOKEN_MINT", "Token mint is required for non-native tokens.");
  }

  return {
    chainId,
    resourceType: "address",
    address: mint,
  };
}

function parseUiAmountToBaseUnits(amount, decimals) {
  const raw = String(amount ?? "").trim();
  if (!/^\d+(\.\d+)?$/.test(raw)) {
    throw structuredError("INVALID_AMOUNT", "Amount must be a positive decimal string.", {
      amount,
    });
  }

  const [wholePart, fractionalPart = ""] = raw.split(".");
  if (fractionalPart.length > decimals) {
    throw structuredError("AMOUNT_TOO_PRECISE", "Amount has more decimals than the token supports.", {
      amount,
      decimals,
    });
  }

  const paddedFraction = fractionalPart.padEnd(decimals, "0");
  const baseUnits = BigInt(wholePart) * 10n ** BigInt(decimals) + BigInt(paddedFraction || "0");
  if (baseUnits <= 0n) {
    throw structuredError("INVALID_AMOUNT", "Amount must convert to positive base units.", {
      amount,
      decimals,
    });
  }

  return baseUnits.toString();
}

function amountToBaseUnits({ amount, amountUnit, sellTokenIsNative }) {
  const unit = String(amountUnit || "base").toLowerCase();
  if (unit === "base") {
    if (!/^\d+$/.test(String(amount ?? ""))) {
      throw structuredError("INVALID_BASE_AMOUNT", "Base-unit amount must be a positive integer string.", {
        amount,
      });
    }
    return String(amount);
  }

  if (unit !== "ui") {
    throw structuredError("UNSUPPORTED_AMOUNT_UNIT", "amount_unit must be either 'ui' or 'base'.", {
      amount_unit: amountUnit,
    });
  }

  if (!sellTokenIsNative) {
    throw structuredError(
      "UNSUPPORTED_UI_DECIMALS",
      "This research helper only knows UI decimals for native SOL in its initial path.",
    );
  }

  return parseUiAmountToBaseUnits(amount, TOKEN_DECIMALS.SOL);
}

function slippageBpsToPercent(slippageBps) {
  if (slippageBps === undefined || slippageBps === null || slippageBps === "") {
    return undefined;
  }

  const bps = Number(slippageBps);
  if (!Number.isFinite(bps) || bps < 0 || bps > 10000) {
    throw structuredError("INVALID_SLIPPAGE_BPS", "slippage_bps must be between 0 and 10000.", {
      slippage_bps: slippageBps,
    });
  }

  return bps / 100;
}

function buildQuoteRequest(input) {
  const sellChainId = normalizeSolanaSwapperChainId(input.sell_chain_id);
  const buyChainId = normalizeSolanaSwapperChainId(input.buy_chain_id || input.sell_chain_id);
  const sellTokenIsNative = input.sell_token_is_native !== false;

  if (sellChainId !== SOLANA_MAINNET_SWAPPER_CHAIN_ID || buyChainId !== SOLANA_MAINNET_SWAPPER_CHAIN_ID) {
    throw structuredError(
      "UNSUPPORTED_CHAIN",
      "This first research helper supports same-chain Solana mainnet quotes only.",
      {
        sell_chain_id: sellChainId,
        buy_chain_id: buyChainId,
      },
    );
  }

  if (!input.taker_address || typeof input.taker_address !== "string") {
    throw structuredError(
      "MISSING_TAKER_ADDRESS",
      "Phantom's quote request shape requires a taker address. Pass taker_address in the stdin JSON.",
    );
  }

  const sellAmount = amountToBaseUnits({
    amount: input.amount,
    amountUnit: input.amount_unit,
    sellTokenIsNative,
  });

  const body = {
    taker: {
      chainId: sellChainId,
      resourceType: "address",
      address: input.taker_address,
    },
    buyToken: buildTokenObject(buyChainId, input.buy_token_mint, input.buy_token_is_native === true),
    sellToken: buildTokenObject(sellChainId, input.sell_token_mint, sellTokenIsNative),
    sellAmount,
    exactOut: false,
    autoSlippage: input.auto_slippage !== false,
    base64EncodedTx: input.base64_encoded_tx === true,
  };

  const slippageTolerance = slippageBpsToPercent(input.slippage_bps);
  if (slippageTolerance !== undefined) {
    body.slippageTolerance = slippageTolerance;
  }

  return body;
}

function buildHeaders() {
  const appId = process.env.PHANTOM_APP_ID || process.env.PHANTOM_CLIENT_ID;
  const accessToken = process.env.PHANTOM_ACCESS_TOKEN;
  const headers = {
    accept: "application/json",
    "content-type": "application/json",
    "user-agent": "web3-digest-phantom-quote-research/0.1",
    "x-phantom-version": "0.0.0-dev",
  };

  if (appId) {
    headers["x-api-key"] = appId;
    headers["x-phantom-app-id"] = appId;
  }

  if (accessToken) {
    headers.authorization = accessToken.toLowerCase().startsWith("bearer ")
      ? accessToken
      : `Bearer ${accessToken}`;
  }

  return headers;
}

async function readResponseBody(response) {
  const text = await response.text();
  if (!text) {
    return { text: "", json: null };
  }

  try {
    return { text, json: JSON.parse(text) };
  } catch {
    return { text, json: null };
  }
}

function extractRouteMetadata(firstQuote) {
  if (!firstQuote || typeof firstQuote !== "object") {
    return null;
  }

  const metadata = {};
  const fields = [
    "provider",
    "baseProvider",
    "route",
    "routes",
    "sources",
    "fees",
    "tool",
    "steps",
    "exchangeAddress",
    "allowanceTarget",
    "priceImpact",
    "simulationFailed",
    "simulationTipAmount",
    "simulationPriorityFee",
    "gaslessSwapFeeResult",
  ];
  for (const field of fields) {
    if (Object.prototype.hasOwnProperty.call(firstQuote, field)) {
      metadata[field] = firstQuote[field];
    }
  }

  if (Array.isArray(firstQuote.steps)) {
    metadata.step_tools = firstQuote.steps
      .map((step) => step && typeof step === "object" ? step.tool : null)
      .filter(Boolean);
  }

  return Object.keys(metadata).length ? metadata : null;
}

async function main() {
  try {
    const input = await readStdinJson();
    const quoteRequest = buildQuoteRequest(input);
    const apiBaseUrl = (process.env.PHANTOM_API_BASE_URL || DEFAULT_PHANTOM_API_BASE_URL).replace(/\/+$/, "");
    const url = `${apiBaseUrl}/swap/v2/quotes`;

    const response = await fetch(url, {
      method: "POST",
      headers: buildHeaders(),
      body: JSON.stringify(quoteRequest),
    });
    const responseBody = await readResponseBody(response);
    const quoteResponse = responseBody.json;
    const firstQuote = Array.isArray(quoteResponse?.quotes) ? quoteResponse.quotes[0] : null;

    writeJson({
      ok: response.ok,
      status_code: response.status,
      status_text: response.statusText,
      endpoint: url,
      quoteRequest,
      quoteResponse,
      first_quote_buyAmount: firstQuote?.buyAmount ?? null,
      route_metadata: extractRouteMetadata(firstQuote),
      raw_response_text: quoteResponse ? undefined : responseBody.text,
    });
  } catch (error) {
    if (error && typeof error === "object" && error.ok === false && error.error) {
      writeJson(error);
      process.exitCode = 1;
      return;
    }

    writeJson(structuredError("UNHANDLED_ERROR", "Unhandled Phantom quote research helper error.", {
      detail: error instanceof Error ? error.message : String(error),
    }));
    process.exitCode = 1;
  }
}

await main();
