#!/usr/bin/env node

import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const DLMM = require("@meteora-ag/dlmm");
const { Connection, PublicKey } = require("@solana/web3.js");
const BN = require("bn.js");

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

async function readStdin() {
  let data = "";
  for await (const chunk of process.stdin) {
    data += chunk;
  }
  return data;
}

function parseInput(raw) {
  if (raw.trim().length === 0) {
    return structuredError("EMPTY_STDIN", "Expected quote request JSON on stdin.");
  }

  try {
    return { ok: true, value: JSON.parse(raw) };
  } catch (err) {
    return structuredError("INVALID_JSON", "Failed to parse quote request JSON.", {
      message: err instanceof Error ? err.message : String(err),
    });
  }
}

function validateRequest(request) {
  if (request === null || typeof request !== "object" || Array.isArray(request)) {
    return structuredError("INVALID_REQUEST", "Quote request must be a JSON object.");
  }

  if (!Array.isArray(request.pool_candidates)) {
    return structuredError("INVALID_POOL_CANDIDATES", "pool_candidates must be an array.");
  }

  for (const [index, candidate] of request.pool_candidates.entries()) {
    if (candidate === null || typeof candidate !== "object" || Array.isArray(candidate)) {
      return structuredError("INVALID_POOL_CANDIDATE", "Pool candidate must be a JSON object.", {
        candidate_index: index,
      });
    }

    const missingFields = ["address", "token_x", "token_y"].filter(
      (field) => typeof candidate[field] !== "string" || candidate[field].trim().length === 0,
    );

    if (missingFields.length > 0) {
      return structuredError(
        "INVALID_POOL_CANDIDATE",
        "Pool candidate is missing required fields.",
        {
          candidate_index: index,
          missing_fields: missingFields,
        },
      );
    }
  }

  return { ok: true, value: request };
}

function summarizeFirstCandidate(candidate) {
  const summary = { address: candidate.address };
  if (typeof candidate.name === "string" && candidate.name.trim().length > 0) {
    summary.name = candidate.name;
  }
  if (candidate.bin_step !== undefined) {
    summary.bin_step = candidate.bin_step;
  }
  return summary;
}

function determineSwapForY(request, candidate) {
  if (request.input_mint === candidate.token_x && request.output_mint === candidate.token_y) {
    return { ok: true, value: true };
  }

  if (request.input_mint === candidate.token_y && request.output_mint === candidate.token_x) {
    return { ok: true, value: false };
  }

  return structuredError(
    "POOL_CANDIDATE_MINT_MISMATCH",
    "Pool candidate does not match input/output mints.",
    {
      input_mint: request.input_mint,
      output_mint: request.output_mint,
      candidate: summarizeFirstCandidate(candidate),
      candidate_token_x: candidate.token_x,
      candidate_token_y: candidate.token_y,
    },
  );
}

function toStringValue(value) {
  return value === undefined || value === null ? null : value.toString();
}

async function quoteMeteoraDlmm(request) {
  if (request.pool_candidates.length === 0) {
    return structuredError(
      "NO_POOL_CANDIDATES",
      "No Meteora DLMM pool candidates provided.",
    );
  }

  const candidate = request.pool_candidates[0];
  const swapForY = determineSwapForY(request, candidate);
  if (!swapForY.ok) {
    return swapForY;
  }

  const connection = new Connection(request.rpc_url);
  const dlmmPool = await DLMM.create(connection, new PublicKey(candidate.address));
  const binArrays = await dlmmPool.getBinArrayForSwap(swapForY.value);
  const quote = dlmmPool.swapQuote(
    new BN(request.amount_raw),
    swapForY.value,
    new BN(request.slippage_bps),
    binArrays,
  );

  return {
    ok: true,
    provider: "meteora_dlmm",
    pool: summarizeFirstCandidate(candidate),
    input_mint: request.input_mint,
    output_mint: request.output_mint,
    in_amount_raw: toStringValue(quote.consumedInAmount),
    out_amount_raw: toStringValue(quote.outAmount),
    min_out_amount_raw: toStringValue(quote.minOutAmount),
    fee_raw: toStringValue(quote.fee),
    protocol_fee_raw: toStringValue(quote.protocolFee),
    price_impact: toStringValue(quote.priceImpact),
    end_price: toStringValue(quote.endPrice),
    bin_arrays: quote.binArraysPubkey.map((pubkey) => pubkey.toString()),
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

  const result = await quoteMeteoraDlmm(validated.value);
  writeJson(result);
  if (!result.ok) {
    process.exitCode = 1;
  }
}

main().catch((err) => {
  writeJson(
    structuredError("UNHANDLED_ERROR", "Unhandled Meteora DLMM quote helper error.", {
      message: err instanceof Error ? err.message : String(err),
    }),
  );
  process.exitCode = 1;
});
