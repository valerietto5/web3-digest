#!/usr/bin/env node

import {
  setNativeMintWrappingStrategy,
  setWhirlpoolsConfig,
  swapInstructions,
} from "@orca-so/whirlpools";
import {
  address,
  appendTransactionMessageInstructions,
  compileTransaction,
  createNoopSigner,
  createSolanaRpc,
  createTransactionMessage,
  getBase64EncodedWireTransaction,
  mainnet,
  pipe,
  setTransactionMessageFeePayer,
  setTransactionMessageLifetimeUsingBlockhash,
} from "@solana/kit";

const DEFAULT_RPC_URL = "https://api.mainnet-beta.solana.com";

function writeJson(value) {
  process.stdout.write(`${JSON.stringify(value)}\n`);
}

function structuredError(code, message, details = undefined) {
  const error = { code, message };
  if (details !== undefined) {
    error.details = details;
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
    return structuredError("EMPTY_STDIN", "Expected Orca Whirlpool prepare request JSON on stdin.");
  }

  try {
    return { ok: true, value: JSON.parse(raw) };
  } catch (err) {
    return structuredError("INVALID_JSON", "Failed to parse Orca Whirlpool prepare request JSON.", {
      message: err instanceof Error ? err.message : String(err),
    });
  }
}

function validateAddress(value, field) {
  if (typeof value !== "string" || value.trim().length === 0) {
    return structuredError("INVALID_PUBLIC_KEY", `${field} must be a non-empty Solana public key string.`, {
      field,
    });
  }

  try {
    return { ok: true, value: address(value.trim()), value_string: value.trim() };
  } catch {
    return structuredError("INVALID_PUBLIC_KEY", `${field} is not a valid Solana public key.`, {
      field,
    });
  }
}

function validateAmountRaw(value) {
  if (typeof value !== "string" || !/^[1-9]\d*$/.test(value)) {
    return structuredError("INVALID_AMOUNT_RAW", "quote_response.in_amount_raw must be a positive integer string.");
  }
  return { ok: true, value: BigInt(value), value_string: value };
}

function validateSlippage(value) {
  const slippage = value === undefined || value === null ? 50 : Number(value);
  if (!Number.isInteger(slippage) || slippage < 0 || slippage > 10000) {
    return structuredError("INVALID_SLIPPAGE_BPS", "quote_response.slippage_bps must be an integer from 0 to 10000.");
  }
  return { ok: true, value: slippage };
}

function validateRequest(request) {
  if (request === null || typeof request !== "object" || Array.isArray(request)) {
    return structuredError("INVALID_REQUEST", "Prepare request must be a JSON object.");
  }

  const wallet = validateAddress(request.user_public_key, "user_public_key");
  if (!wallet.ok) {
    return wallet;
  }

  const quote = request.quote_response;
  if (quote === null || typeof quote !== "object" || Array.isArray(quote)) {
    return structuredError("INVALID_QUOTE_RESPONSE", "quote_response must be a JSON object.");
  }

  if (quote.route_shape === "two-hop" || Array.isArray(quote.leg_quotes)) {
    return structuredError(
      "ORCA_MULTIPLE_TRANSACTIONS_UNSUPPORTED",
      "Orca returned multiple transactions, which are not supported in V1.",
    );
  }

  const poolAddress = validateAddress(quote.pool?.address, "quote_response.pool.address");
  if (!poolAddress.ok) {
    return poolAddress;
  }

  const inputMint = validateAddress(quote.input_mint, "quote_response.input_mint");
  if (!inputMint.ok) {
    return inputMint;
  }

  const amount = validateAmountRaw(quote.in_amount_raw);
  if (!amount.ok) {
    return amount;
  }

  const slippage = validateSlippage(quote.slippage_bps);
  if (!slippage.ok) {
    return slippage;
  }

  const txVersion = request.tx_version || "V0";
  if (txVersion !== "V0") {
    return structuredError("UNSUPPORTED_TX_VERSION", "Only V0 Orca transactions are supported in V1.");
  }

  return {
    ok: true,
    value: {
      quote,
      wallet,
      poolAddress,
      inputMint,
      amount,
      slippage,
      txVersion,
      rpcUrl: request.rpc_url || quote.rpc_url || process.env.SOLANA_RPC_URL || DEFAULT_RPC_URL,
    },
  };
}

async function prepareOrcaWhirlpoolSwap(request) {
  await setWhirlpoolsConfig("solanaMainnet");
  setNativeMintWrappingStrategy("none");

  const rpc = createSolanaRpc(mainnet(request.rpcUrl));
  const signer = createNoopSigner(request.wallet.value);

  const { instructions, quote } = await swapInstructions(
    rpc,
    {
      inputAmount: request.amount.value,
      mint: request.inputMint.value,
    },
    request.poolAddress.value,
    request.slippage.value,
    signer,
  );

  if (!Array.isArray(instructions) || instructions.length === 0) {
    return structuredError("ORCA_PREPARE_FAILED", "Orca did not return swap instructions.");
  }

  const latestBlockhash = await rpc.getLatestBlockhash().send();
  const blockhashLifetime = latestBlockhash.value ?? latestBlockhash;

  const message = pipe(
    createTransactionMessage({ version: 0 }),
    (m) => setTransactionMessageFeePayer(request.wallet.value, m),
    (m) => setTransactionMessageLifetimeUsingBlockhash(blockhashLifetime, m),
    (m) => appendTransactionMessageInstructions(instructions, m),
  );

  const transaction = compileTransaction(message);
  return {
    ok: true,
    transaction_base64: getBase64EncodedWireTransaction(transaction),
    transaction_format: "versioned",
    warnings: [],
    quote_summary: {
      estimated_output_raw: quote.tokenEstOut?.toString?.() ?? null,
      min_received_raw: quote.tokenMinOut?.toString?.() ?? null,
    },
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

  const result = await prepareOrcaWhirlpoolSwap(validated.value);
  writeJson(result);
  if (!result.ok) {
    process.exitCode = 1;
  }
}

main().catch((err) => {
  writeJson(
    prepareFailure(
      "ORCA_PREPARE_FAILED",
      "Orca transaction preparation failed.",
      err instanceof Error ? err.message : String(err),
    ),
  );
  process.exitCode = 1;
});
