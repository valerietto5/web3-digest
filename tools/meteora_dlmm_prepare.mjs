#!/usr/bin/env node

import { createRequire } from "node:module";
import {
  Connection,
  PublicKey,
  TransactionMessage,
  VersionedTransaction,
} from "@solana/web3.js";
import BN from "bn.js";

const require = createRequire(import.meta.url);
const DLMM = require("@meteora-ag/dlmm");

const DEFAULT_RPC_URL = "https://api.mainnet-beta.solana.com";

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

function structuredError(code, message, detail = undefined) {
  const error = { code, message };
  const safeDetail = safeScalar(detail);
  if (safeDetail !== undefined) {
    error.detail = safeDetail;
  }
  return { ok: false, error };
}

function parseInput(raw) {
  if (raw.trim().length === 0) {
    return structuredError("EMPTY_STDIN", "Expected Meteora DLMM prepare request JSON on stdin.");
  }

  try {
    return { ok: true, value: JSON.parse(raw) };
  } catch (err) {
    return structuredError(
      "INVALID_JSON",
      "Failed to parse Meteora DLMM prepare request JSON.",
      err instanceof Error ? err.message : String(err),
    );
  }
}

function readInputArgOrStdin() {
  if (process.argv[2] && process.argv[2].trim().length > 0) {
    return Promise.resolve(process.argv[2]);
  }

  return new Promise((resolve) => {
    let data = "";
    process.stdin.setEncoding("utf8");
    process.stdin.on("data", (chunk) => {
      data += chunk;
    });
    process.stdin.on("end", () => resolve(data));
  });
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

function validateBinArrays(value) {
  if (!Array.isArray(value) || value.length === 0) {
    return structuredError("METEORA_DLMM_BIN_ARRAYS_REQUIRED", "bin_arrays must be a non-empty array.");
  }

  const out = [];
  for (const [index, item] of value.entries()) {
    const key = validatePublicKey(item, `bin_arrays[${index}]`);
    if (!key.ok) {
      return key;
    }
    out.push(key.value);
  }
  return { ok: true, value: out, valueStrings: value.map((item) => String(item).trim()) };
}

function validateRequest(request) {
  if (request === null || typeof request !== "object" || Array.isArray(request)) {
    return structuredError("INVALID_REQUEST", "Meteora DLMM prepare request must be a JSON object.");
  }

  const routeShape = String(request.route_shape || "").trim();
  if (routeShape !== "single-pool") {
    return structuredError(
      "METEORA_DLMM_UNSUPPORTED_ROUTE",
      "Only single-pool Meteora DLMM routes are supported for prepare V1.",
      routeShape || "missing route_shape",
    );
  }

  const userPublicKey = validatePublicKey(request.user_public_key, "user_public_key");
  if (!userPublicKey.ok) return userPublicKey;

  const poolAddress = validatePublicKey(request.pool_address, "pool_address");
  if (!poolAddress.ok) return poolAddress;

  const inputMint = validatePublicKey(request.input_mint, "input_mint");
  if (!inputMint.ok) return inputMint;

  const outputMint = validatePublicKey(request.output_mint, "output_mint");
  if (!outputMint.ok) return outputMint;

  const amountRaw = validateAmountRaw(request.amount_raw, "amount_raw");
  if (!amountRaw.ok) return amountRaw;

  const minOutAmountRaw = validateAmountRaw(request.min_out_amount_raw, "min_out_amount_raw");
  if (!minOutAmountRaw.ok) return minOutAmountRaw;

  const binArrays = validateBinArrays(request.bin_arrays);
  if (!binArrays.ok) return binArrays;

  const txVersion = String(request.tx_version || "V0").toUpperCase();
  if (txVersion !== "V0") {
    return structuredError("UNSUPPORTED_TX_VERSION", "Only V0 transactions are supported for Meteora DLMM prepare.");
  }

  const slippageBps = request.slippage_bps === undefined || request.slippage_bps === null
    ? 50
    : Number(request.slippage_bps);
  if (!Number.isInteger(slippageBps) || slippageBps < 0 || slippageBps > 10000) {
    return structuredError("INVALID_SLIPPAGE_BPS", "slippage_bps must be an integer from 0 to 10000.");
  }

  return {
    ok: true,
    value: {
      rpcUrl: request.rpc_url || process.env.SOLANA_RPC_URL || DEFAULT_RPC_URL,
      routeShape,
      txVersion,
      slippageBps,
      userPublicKey,
      poolAddress,
      inputMint,
      outputMint,
      amountRaw,
      minOutAmountRaw,
      binArrays,
      includeDiagnostics: request.include_diagnostics === true,
    },
  };
}

function pubkeyString(value) {
  return value && typeof value.toBase58 === "function" ? value.toBase58() : String(value || "");
}

function summarizeInstructionMetas(instructions, bitmapExtensionPubkey) {
  const bitmapExtension = bitmapExtensionPubkey ? pubkeyString(bitmapExtensionPubkey) : null;
  const instructionSummaries = instructions.map((instruction, instructionIndex) => {
    const accounts = Array.isArray(instruction.keys)
      ? instruction.keys.map((meta, accountIndex) => {
        const account = {
          account_index: accountIndex,
          pubkey: pubkeyString(meta.pubkey),
          is_writable: meta.isWritable === true,
          is_signer: meta.isSigner === true,
        };
        if (bitmapExtension && account.pubkey === bitmapExtension) {
          account.role = "bin_array_bitmap_extension";
        }
        return account;
      })
      : [];

    return {
      instruction_index: instructionIndex,
      program_id: pubkeyString(instruction.programId),
      account_count: accounts.length,
      account_metas: accounts,
    };
  });

  const bitmapAccounts = [];
  if (bitmapExtension) {
    for (const instruction of instructionSummaries) {
      for (const account of instruction.account_metas) {
        if (account.pubkey === bitmapExtension) {
          bitmapAccounts.push({
            instruction_index: instruction.instruction_index,
            account_index: account.account_index,
            pubkey: account.pubkey,
            is_writable: account.is_writable,
            is_signer: account.is_signer,
          });
        }
      }
    }
  }

  return {
    instruction_count: instructionSummaries.length,
    program_ids: [...new Set(instructionSummaries.map((item) => item.program_id).filter(Boolean))],
    bin_array_bitmap_extension: bitmapExtension,
    bin_array_bitmap_extension_accounts: bitmapAccounts,
    instructions: instructionSummaries,
  };
}

function ensureBinArrayBitmapExtensionWritable(instructions, dlmmPool) {
  const bitmapExtensionPubkey = dlmmPool?.binArrayBitmapExtension?.publicKey;
  if (!bitmapExtensionPubkey) {
    return {
      bin_array_bitmap_extension_present: false,
      patched: false,
      reason: "Meteora DLMM pool did not expose a bin array bitmap extension account.",
    };
  }

  const bitmapExtension = pubkeyString(bitmapExtensionPubkey);
  const patched_accounts = [];

  for (const [instructionIndex, instruction] of instructions.entries()) {
    if (!Array.isArray(instruction.keys)) {
      continue;
    }
    for (const [accountIndex, meta] of instruction.keys.entries()) {
      if (!meta?.pubkey || !meta.pubkey.equals(bitmapExtensionPubkey)) {
        continue;
      }
      const wasWritable = meta.isWritable === true;
      if (!wasWritable) {
        meta.isWritable = true;
      }
      patched_accounts.push({
        instruction_index: instructionIndex,
        account_index: accountIndex,
        pubkey: bitmapExtension,
        was_writable: wasWritable,
        is_writable: meta.isWritable === true,
      });
    }
  }

  return {
    bin_array_bitmap_extension_present: true,
    pubkey: bitmapExtension,
    patched: patched_accounts.some((item) => item.was_writable === false && item.is_writable === true),
    patched_accounts,
  };
}

async function prepareMeteoraDlmmSwap(request) {
  const connection = new Connection(request.rpcUrl, "confirmed");
  const dlmmPool = await DLMM.create(connection, request.poolAddress.value);

  const legacyTx = await dlmmPool.swap({
    inToken: request.inputMint.value,
    outToken: request.outputMint.value,
    inAmount: request.amountRaw.value,
    minOutAmount: request.minOutAmountRaw.value,
    lbPair: request.poolAddress.value,
    user: request.userPublicKey.value,
    binArraysPubkey: request.binArrays.value,
  });

  if (!legacyTx || !Array.isArray(legacyTx.instructions) || legacyTx.instructions.length === 0) {
    return structuredError("METEORA_DLMM_PREPARE_FAILED", "Meteora DLMM did not return swap instructions.");
  }

  const writablePatch = ensureBinArrayBitmapExtensionWritable(legacyTx.instructions, dlmmPool);
  const warnings = ["legacy_transaction_compiled_to_v0"];
  if (writablePatch.patched) {
    warnings.push("bin_array_bitmap_extension_marked_writable");
  }

  const latestBlockhash = await connection.getLatestBlockhash("confirmed");
  const message = new TransactionMessage({
    payerKey: request.userPublicKey.value,
    recentBlockhash: latestBlockhash.blockhash,
    instructions: legacyTx.instructions,
  }).compileToV0Message();
  const transaction = new VersionedTransaction(message);

  const result = {
    ok: true,
    provider: "meteora-dlmm",
    transaction_format: "versioned",
    transaction_base64: Buffer.from(transaction.serialize()).toString("base64"),
    pool_address: request.poolAddress.valueString,
    input_mint: request.inputMint.valueString,
    output_mint: request.outputMint.valueString,
    amount_raw: request.amountRaw.valueString,
    min_out_amount_raw: request.minOutAmountRaw.valueString,
    route_shape: request.routeShape,
    tx_version: request.txVersion,
    slippage_bps: request.slippageBps,
    bin_arrays_count: request.binArrays.value.length,
    warnings,
  };

  if (request.includeDiagnostics) {
    result.instruction_diagnostics = summarizeInstructionMetas(
      legacyTx.instructions,
      dlmmPool?.binArrayBitmapExtension?.publicKey,
    );
    result.writable_account_patch = writablePatch;
  }

  return result;
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

  try {
    const result = await prepareMeteoraDlmmSwap(validated.value);
    writeJson(result);
    if (!result.ok) {
      process.exitCode = 1;
    }
  } catch (err) {
    writeJson(
      structuredError(
        "METEORA_DLMM_PREPARE_FAILED",
        "Meteora DLMM transaction preparation was not successful.",
        err instanceof Error ? err.message : String(err),
      ),
    );
    process.exitCode = 1;
  }
}

main();
