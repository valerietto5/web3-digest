#!/usr/bin/env node

import {
  Connection,
  PublicKey,
  TransactionMessage,
  VersionedTransaction,
} from "@solana/web3.js";
import {
  OnlinePumpAmmSdk,
  PUMP_AMM_SDK,
} from "@pump-fun/pump-swap-sdk";
import BN from "bn.js";

const DEFAULT_RPC_URL = "https://api.mainnet-beta.solana.com";

function writeJson(value) {
  process.stdout.write(`${JSON.stringify(value)}\n`);
}

function structuredError(code, message, detail = undefined) {
  const error = { code, message };
  if (detail !== undefined) {
    error.detail = detail;
  }
  return { ok: false, error };
}

function safeScalar(value) {
  if (
    value === undefined
    || value === null
    || (typeof value !== "string" && typeof value !== "number" && typeof value !== "boolean")
  ) {
    return undefined;
  }

  let text = String(value).trim();
  if (text.length === 0) {
    return undefined;
  }

  const lower = text.toLowerCase();
  const unsafeMarkers = [
    "http://",
    "https://",
    "api-key",
    "api_key",
    "access_token",
    "key=",
    "token=",
    "auth=",
    "signature=",
    "password",
    "secret",
    "transaction_base64",
    "transactionbase64",
    "signed_transaction",
    "signedtransaction",
    "swaptransaction",
  ];
  if (unsafeMarkers.some((marker) => lower.includes(marker))) {
    return undefined;
  }

  if (text.length > 240) {
    text = `${text.slice(0, 237)}...`;
  }
  return text;
}

function prepareFailure(code, message, detail = undefined) {
  const error = { code, message };
  const safeDetail = safeScalar(detail);
  if (safeDetail !== undefined) {
    error.detail = safeDetail;
  }
  return { ok: false, error };
}

async function readStdin() {
  let data = "";
  for await (const chunk of process.stdin) {
    data += chunk;
  }
  return data;
}

function parseInput(raw) {
  if (raw.trim().length === 0) {
    return structuredError("EMPTY_STDIN", "Expected PumpSwap prepare request JSON on stdin.");
  }

  try {
    return { ok: true, value: JSON.parse(raw) };
  } catch (err) {
    return prepareFailure(
      "INVALID_JSON",
      "Failed to parse PumpSwap prepare request JSON.",
      err instanceof Error ? err.message : String(err),
    );
  }
}

function validatePublicKey(value, field) {
  if (typeof value !== "string" || value.trim().length === 0) {
    return structuredError("INVALID_PUBLIC_KEY", `${field} must be a non-empty Solana public key string.`);
  }

  try {
    return { ok: true, value: new PublicKey(value.trim()), valueString: value.trim() };
  } catch {
    return structuredError("INVALID_PUBLIC_KEY", `${field} is not a valid Solana public key.`);
  }
}

function validateAmountRaw(value, field) {
  if (typeof value !== "string" || !/^[1-9]\d*$/.test(value)) {
    return structuredError("INVALID_AMOUNT_RAW", `${field} must be a positive integer string.`);
  }
  return { ok: true, value: new BN(value), valueString: value };
}

function validateSlippage(value) {
  const slippageBps = value === undefined || value === null ? 50 : Number(value);
  if (!Number.isInteger(slippageBps) || slippageBps < 0 || slippageBps > 10000) {
    return structuredError("INVALID_SLIPPAGE_BPS", "quote_response.slippage_bps must be an integer from 0 to 10000.");
  }
  return { ok: true, value: slippageBps / 100 };
}

function normalizePumpSwapDirection(direction) {
  if (direction === "buy_base_with_quote") {
    return "buy_base_with_quote";
  }
  if (direction === "sell_base_for_quote") {
    return "sell_base_for_quote";
  }
  return null;
}

function expectedPoolMints(quote) {
  const direction = normalizePumpSwapDirection(quote.direction);
  if (direction === "buy_base_with_quote") {
    return {
      baseMint: quote.output_mint,
      quoteMint: quote.input_mint,
    };
  }
  if (direction === "sell_base_for_quote") {
    return {
      baseMint: quote.input_mint,
      quoteMint: quote.output_mint,
    };
  }
  return null;
}

function validateRequest(request) {
  if (request === null || typeof request !== "object" || Array.isArray(request)) {
    return structuredError("INVALID_REQUEST", "PumpSwap prepare request must be a JSON object.");
  }

  const wallet = validatePublicKey(request.user_public_key, "user_public_key");
  if (!wallet.ok) {
    return wallet;
  }

  const quote = request.quote_response;
  if (quote === null || typeof quote !== "object" || Array.isArray(quote)) {
    return structuredError("INVALID_QUOTE_RESPONSE", "quote_response must be a JSON object.");
  }

  if (quote.route_shape === "two-hop" || Array.isArray(quote.leg_quotes)) {
    return structuredError(
      "PUMPSWAP_MULTIPLE_TRANSACTIONS_UNSUPPORTED",
      "PumpSwap returned multiple transactions, which are not supported in V1.",
    );
  }

  const normalizedDirection = normalizePumpSwapDirection(quote.direction);
  if (!normalizedDirection) {
    return structuredError("PUMPSWAP_UNSUPPORTED_ROUTE", "PumpSwap quote direction is not supported for prepare.");
  }

  const poolAddress = validatePublicKey(quote.pool?.address, "quote_response.pool.address");
  if (!poolAddress.ok) {
    return poolAddress;
  }

  const inputMint = validatePublicKey(quote.input_mint, "quote_response.input_mint");
  if (!inputMint.ok) {
    return inputMint;
  }

  const outputMint = validatePublicKey(quote.output_mint, "quote_response.output_mint");
  if (!outputMint.ok) {
    return outputMint;
  }

  const amount = validateAmountRaw(quote.in_amount_raw, "quote_response.in_amount_raw");
  if (!amount.ok) {
    return amount;
  }

  const slippage = validateSlippage(quote.slippage_bps);
  if (!slippage.ok) {
    return slippage;
  }

  const txVersion = request.tx_version || "V0";
  if (txVersion !== "V0") {
    return structuredError("UNSUPPORTED_TX_VERSION", "Only V0 transactions are supported for PumpSwap prepare.");
  }

  return {
    ok: true,
    value: {
      quote,
      normalizedDirection,
      wallet,
      poolAddress,
      inputMint,
      outputMint,
      amount,
      slippage,
      txVersion,
      rpcUrl: request.rpc_url || quote.rpc_url || process.env.SOLANA_RPC_URL || DEFAULT_RPC_URL,
    },
  };
}

function assertOnchainPoolMatchesQuote(swapState, quote) {
  const expected = expectedPoolMints(quote);
  if (!expected) {
    return structuredError("PUMPSWAP_UNSUPPORTED_ROUTE", "PumpSwap quote direction is not supported for prepare.");
  }

  const onchainBaseMint = swapState.pool.baseMint.toString();
  const onchainQuoteMint = swapState.pool.quoteMint.toString();
  if (onchainBaseMint !== expected.baseMint || onchainQuoteMint !== expected.quoteMint) {
    return structuredError("POOL_ONCHAIN_MINT_MISMATCH", "On-chain pool mints do not match the quote response.");
  }

  return { ok: true };
}

async function preparePumpSwap(request) {
  const connection = new Connection(request.rpcUrl, "confirmed");
  const onlineSdk = new OnlinePumpAmmSdk(connection);
  const swapState = await onlineSdk.swapSolanaState(request.poolAddress.value, request.wallet.value);
  const onchainMatch = assertOnchainPoolMatchesQuote(swapState, request.quote);
  if (!onchainMatch.ok) {
    return onchainMatch;
  }

  let instructions;
  if (request.normalizedDirection === "buy_base_with_quote") {
    instructions = await PUMP_AMM_SDK.buyQuoteInput(
      swapState,
      request.amount.value,
      request.slippage.value,
    );
  } else if (request.normalizedDirection === "sell_base_for_quote") {
    instructions = await PUMP_AMM_SDK.sellBaseInput(
      swapState,
      request.amount.value,
      request.slippage.value,
    );
  } else {
    return structuredError("PUMPSWAP_UNSUPPORTED_ROUTE", "PumpSwap quote direction is not supported for prepare.");
  }

  if (!Array.isArray(instructions) || instructions.length === 0) {
    return structuredError("PUMPSWAP_PREPARE_FAILED", "PumpSwap did not return swap instructions.");
  }

  const latestBlockhash = await connection.getLatestBlockhash("confirmed");
  const message = new TransactionMessage({
    payerKey: request.wallet.value,
    recentBlockhash: latestBlockhash.blockhash,
    instructions,
  }).compileToV0Message();

  const transaction = new VersionedTransaction(message);
  return {
    ok: true,
    transaction_base64: Buffer.from(transaction.serialize()).toString("base64"),
    transaction_format: "versioned",
    warnings: [],
  };
}

async function main() {
  const parsed = parseInput(await readStdin());
  if (!parsed.ok) {
    writeJson(parsed);
    process.exitCode = 1;
    return;
  }

  const validated = validateRequest(parsed.value);
  if (!validated.ok) {
    writeJson(validated);
    process.exitCode = 1;
    return;
  }

  const result = await preparePumpSwap(validated.value);
  writeJson(result);
  if (!result.ok) {
    process.exitCode = 1;
  }
}

main().catch((err) => {
  writeJson(
    prepareFailure(
      "PUMPSWAP_PREPARE_FAILED",
      "PumpSwap transaction preparation failed.",
      err instanceof Error ? err.message : String(err),
    ),
  );
  process.exitCode = 1;
});
