#!/usr/bin/env node

import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import { PublicKey } from "@solana/web3.js";

const DEFAULT_RPC_URL = "https://api.mainnet-beta.solana.com";
const HELPER_TIMEOUT_MS = 30000;

const __dirname = dirname(fileURLToPath(import.meta.url));
const quoteHelperPath = resolve(__dirname, "meteora_dlmm_quote.mjs");
const prepareHelperPath = resolve(__dirname, "meteora_dlmm_prepare.mjs");
const nodeBinary = process.env.NODE_BINARY || "node";

function writeJson(value) {
  process.stdout.write(`${JSON.stringify(value)}\n`);
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
  if (!text) {
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

function safeErrorDetails(error) {
  if (!error || typeof error !== "object" || Array.isArray(error)) {
    return undefined;
  }

  const out = {};
  for (const key of ["code", "message", "detail", "details", "provider_code", "provider_message", "provider_detail"]) {
    const value = safeScalar(error[key]);
    if (value !== undefined) {
      out[key] = value;
    }
  }
  return Object.keys(out).length > 0 ? out : undefined;
}

function structuredError(code, message, details = undefined) {
  const error = { code, message };
  const safeDetails = safeErrorDetails(details);
  if (safeDetails !== undefined) {
    error.details = safeDetails;
  } else {
    const safeDetail = safeScalar(details);
    if (safeDetail !== undefined) {
      error.detail = safeDetail;
    }
  }
  return { ok: false, error };
}

async function readInputArgOrStdin() {
  if (process.argv[2] && process.argv[2].trim().length > 0) {
    return process.argv[2];
  }

  let data = "";
  for await (const chunk of process.stdin) {
    data += chunk;
  }
  return data;
}

function parseInput(raw) {
  if (raw.trim().length === 0) {
    return structuredError("EMPTY_STDIN", "Expected Meteora DLMM prepare dry-run request JSON.");
  }

  try {
    return { ok: true, value: JSON.parse(raw) };
  } catch (err) {
    return structuredError(
      "INVALID_JSON",
      "Failed to parse Meteora DLMM prepare dry-run request JSON.",
      err instanceof Error ? err.message : String(err),
    );
  }
}

function validatePublicKey(value, field) {
  if (typeof value !== "string" || value.trim().length === 0) {
    return structuredError("INVALID_PUBLIC_KEY", `${field} must be a non-empty Solana public key string.`);
  }

  try {
    return { ok: true, value: value.trim(), publicKey: new PublicKey(value.trim()) };
  } catch {
    return structuredError("INVALID_PUBLIC_KEY", `${field} is not a valid Solana public key.`);
  }
}

function validateAmountRaw(value) {
  if (typeof value !== "string" || !/^[1-9]\d*$/.test(value)) {
    return structuredError("INVALID_AMOUNT_RAW", "amount_raw must be a positive integer string.");
  }
  return { ok: true, value };
}

function validateRequest(request) {
  if (request === null || typeof request !== "object" || Array.isArray(request)) {
    return structuredError("INVALID_REQUEST", "Meteora DLMM prepare dry-run request must be a JSON object.");
  }

  const userPublicKey = validatePublicKey(request.user_public_key, "user_public_key");
  if (!userPublicKey.ok) return userPublicKey;

  const inputMint = validatePublicKey(request.input_mint, "input_mint");
  if (!inputMint.ok) return inputMint;

  const outputMint = validatePublicKey(request.output_mint, "output_mint");
  if (!outputMint.ok) return outputMint;

  const amountRaw = validateAmountRaw(request.amount_raw);
  if (!amountRaw.ok) return amountRaw;

  const slippageBps = request.slippage_bps === undefined || request.slippage_bps === null
    ? 50
    : Number(request.slippage_bps);
  if (!Number.isInteger(slippageBps) || slippageBps < 0 || slippageBps > 10000) {
    return structuredError("INVALID_SLIPPAGE_BPS", "slippage_bps must be an integer from 0 to 10000.");
  }

  return {
    ok: true,
    value: {
      rpcUrl: typeof request.rpc_url === "string" && request.rpc_url.trim()
        ? request.rpc_url.trim()
        : (process.env.SOLANA_RPC_URL || DEFAULT_RPC_URL),
      userPublicKey: userPublicKey.value,
      inputMint: inputMint.value,
      outputMint: outputMint.value,
      amountRaw: amountRaw.value,
      slippageBps,
      includeTransactionBase64: request.include_transaction_base64 === true,
      includeDiagnostics: request.include_diagnostics === true,
    },
  };
}

function runJsonHelper(helperPath, payload) {
  return new Promise((resolve) => {
    const child = spawn(nodeBinary, [helperPath], { stdio: ["pipe", "pipe", "pipe"] });
    let stdout = "";
    let settled = false;

    const timer = setTimeout(() => {
      if (!settled) {
        settled = true;
        child.kill("SIGTERM");
        resolve(structuredError("HELPER_TIMEOUT", "Meteora DLMM dry-run helper timed out."));
      }
    }, HELPER_TIMEOUT_MS);

    child.stdout.setEncoding("utf8");
    child.stdout.on("data", (chunk) => {
      stdout += chunk;
    });

    child.on("error", (err) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      resolve(structuredError(
        "HELPER_FAILED",
        "Meteora DLMM dry-run helper process failed.",
        err instanceof Error ? err.message : String(err),
      ));
    });

    child.on("close", (code) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);

      const text = stdout.trim();
      if (!text) {
        resolve(structuredError("HELPER_NO_JSON", "Meteora DLMM dry-run helper returned no JSON output."));
        return;
      }

      try {
        const data = JSON.parse(text);
        if (code !== 0 || data?.ok === false) {
          resolve({
            ok: false,
            error: {
              code: data?.error?.code || "HELPER_FAILED",
              message: data?.error?.message || "Meteora DLMM dry-run helper failed.",
              details: safeErrorDetails(data?.error),
            },
          });
          return;
        }
        resolve(data);
      } catch (err) {
        resolve(structuredError(
          "HELPER_INVALID_JSON",
          "Meteora DLMM dry-run helper returned invalid JSON.",
          err instanceof Error ? err.message : String(err),
        ));
      }
    });

    child.stdin.end(JSON.stringify(payload));
  });
}

function quotePayload(request) {
  return {
    rpc_url: request.rpcUrl,
    input_mint: request.inputMint,
    output_mint: request.outputMint,
    amount_raw: request.amountRaw,
    slippage_bps: request.slippageBps,
    pool_candidates: [],
    discover_pools: true,
    enable_two_hop_discovery: true,
  };
}

function rejectUnsupportedQuote(quote) {
  const routeShape = quote.route_shape || (Array.isArray(quote.leg_quotes) ? "two-hop" : "single-pool");
  if (routeShape !== "single-pool") {
    return structuredError(
      "METEORA_DLMM_DRY_RUN_UNSUPPORTED_ROUTE",
      "Only single-pool Meteora DLMM routes are supported for prepare dry-run.",
      routeShape,
    );
  }
  if (!quote?.pool?.address) {
    return structuredError("METEORA_DLMM_DRY_RUN_POOL_MISSING", "Meteora DLMM quote is missing pool address.");
  }
  if (!Array.isArray(quote.bin_arrays) || quote.bin_arrays.length === 0) {
    return structuredError("METEORA_DLMM_DRY_RUN_BIN_ARRAYS_MISSING", "Meteora DLMM quote is missing bin arrays.");
  }
  return { ok: true, routeShape };
}

function preparePayload(request, quote, routeShape) {
  return {
    rpc_url: request.rpcUrl,
    user_public_key: request.userPublicKey,
    pool_address: quote.pool.address,
    input_mint: quote.input_mint,
    output_mint: quote.output_mint,
    amount_raw: quote.in_amount_raw,
    min_out_amount_raw: quote.min_out_amount_raw,
    slippage_bps: request.slippageBps,
    bin_arrays: quote.bin_arrays,
    route_shape: routeShape,
    tx_version: "V0",
    include_diagnostics: request.includeDiagnostics,
  };
}

function summarizeDryRun(request, quote, prepare, routeShape) {
  const transactionBase64 = prepare.transaction_base64;
  const result = {
    ok: true,
    provider: "meteora-dlmm",
    route_shape: routeShape,
    pool_address: quote.pool.address,
    bin_arrays_count: quote.bin_arrays.length,
    quote_summary: {
      input_mint: quote.input_mint,
      output_mint: quote.output_mint,
      in_amount_raw: quote.in_amount_raw,
      out_amount_raw: quote.out_amount_raw,
      min_out_amount_raw: quote.min_out_amount_raw,
      fee_raw: quote.fee_raw,
      protocol_fee_raw: quote.protocol_fee_raw,
      price_impact: quote.price_impact,
    },
    prepare_summary: {
      transaction_format: prepare.transaction_format,
      transaction_base64_present: typeof transactionBase64 === "string" && transactionBase64.length > 0,
      transaction_base64_length: typeof transactionBase64 === "string" ? transactionBase64.length : 0,
      warnings: Array.isArray(prepare.warnings) ? prepare.warnings : [],
    },
    transaction_format: prepare.transaction_format,
    transaction_base64_present: typeof transactionBase64 === "string" && transactionBase64.length > 0,
    transaction_base64_length: typeof transactionBase64 === "string" ? transactionBase64.length : 0,
  };

  if (request.includeDiagnostics === true) {
    result.prepare_diagnostics = {
      instruction_diagnostics: prepare.instruction_diagnostics,
      writable_account_patch: prepare.writable_account_patch,
    };
  }

  if (request.includeTransactionBase64 === true) {
    result.transaction_base64 = transactionBase64;
  }

  return result;
}

async function dryRunMeteoraPrepare(request) {
  const quote = await runJsonHelper(quoteHelperPath, quotePayload(request));
  if (!quote.ok) {
    return structuredError(
      "METEORA_DLMM_DRY_RUN_QUOTE_FAILED",
      "Meteora DLMM dry-run quote failed.",
      quote.error,
    );
  }

  const supported = rejectUnsupportedQuote(quote);
  if (!supported.ok) {
    return supported;
  }

  const prepare = await runJsonHelper(prepareHelperPath, preparePayload(request, quote, supported.routeShape));
  if (!prepare.ok) {
    return structuredError(
      "METEORA_DLMM_DRY_RUN_PREPARE_FAILED",
      "Meteora DLMM dry-run prepare failed.",
      prepare.error,
    );
  }

  return summarizeDryRun(request, quote, prepare, supported.routeShape);
}

async function main() {
  const parsed = parseInput(await readInputArgOrStdin());
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

  const result = await dryRunMeteoraPrepare(validated.value);
  writeJson(result);
  if (!result.ok) {
    process.exitCode = 1;
  }
}

main().catch((err) => {
  writeJson(
    structuredError(
      "METEORA_DLMM_DRY_RUN_FAILED",
      "Unhandled Meteora DLMM prepare dry-run error.",
      err instanceof Error ? err.message : String(err),
    ),
  );
  process.exitCode = 1;
});
