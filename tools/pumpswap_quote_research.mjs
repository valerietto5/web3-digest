#!/usr/bin/env node

import { Connection, PublicKey } from "@solana/web3.js";
import {
  OnlinePumpAmmSdk,
  PUMP_AMM_PROGRAM_ID,
  buyQuoteInput,
  sellBaseInput,
  canonicalPumpPoolPda,
} from "@pump-fun/pump-swap-sdk";
import BN from "bn.js";

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
    return structuredError("EMPTY_STDIN", "Expected PumpSwap quote request JSON on stdin.");
  }

  try {
    return { ok: true, value: JSON.parse(raw) };
  } catch (err) {
    return structuredError("INVALID_JSON", "Failed to parse PumpSwap quote request JSON.", {
      message: err instanceof Error ? err.message : String(err),
    });
  }
}

function validatePublicKey(value, field) {
  if (typeof value !== "string" || value.trim().length === 0) {
    return structuredError("INVALID_PUBLIC_KEY", `${field} must be a non-empty public key string.`, {
      field,
    });
  }

  try {
    return { ok: true, value: new PublicKey(value) };
  } catch (err) {
    return structuredError("INVALID_PUBLIC_KEY", `${field} is not a valid Solana public key.`, {
      field,
      value,
      message: err instanceof Error ? err.message : String(err),
    });
  }
}

function validateAmountRaw(value) {
  if (typeof value !== "string" || !/^[1-9]\d*$/.test(value)) {
    return structuredError("INVALID_AMOUNT_RAW", "amount_raw must be a positive integer string.", {
      amount_raw: value,
    });
  }

  return { ok: true, value: new BN(value) };
}

function validateSlippageBps(value) {
  const slippageBps = value === undefined || value === null ? 0 : Number(value);
  if (!Number.isInteger(slippageBps) || slippageBps < 0 || slippageBps > 10000) {
    return structuredError("INVALID_SLIPPAGE_BPS", "slippage_bps must be an integer between 0 and 10000.", {
      slippage_bps: value,
    });
  }

  return { ok: true, value: slippageBps };
}

function summarizeCandidate(candidate, index = undefined) {
  const summary = {
    address: candidate.address,
    base_mint: candidate.base_mint,
    quote_mint: candidate.quote_mint,
  };
  if (index !== undefined) {
    summary.candidate_index = index;
  }
  if (typeof candidate.name === "string" && candidate.name.trim().length > 0) {
    summary.name = candidate.name;
  }
  return summary;
}

function validateCandidate(candidate, index) {
  if (candidate === null || typeof candidate !== "object" || Array.isArray(candidate)) {
    return structuredError("INVALID_POOL_CANDIDATE", "Pool candidate must be a JSON object.", {
      candidate_index: index,
    });
  }

  const missingFields = ["address", "base_mint", "quote_mint"].filter(
    (field) => typeof candidate[field] !== "string" || candidate[field].trim().length === 0,
  );
  if (missingFields.length > 0) {
    return structuredError("INVALID_POOL_CANDIDATE", "Pool candidate is missing required fields.", {
      candidate_index: index,
      missing_fields: missingFields,
    });
  }

  for (const field of ["address", "base_mint", "quote_mint"]) {
    const validated = validatePublicKey(candidate[field], `pool_candidates[${index}].${field}`);
    if (!validated.ok) {
      return validated;
    }
  }

  return { ok: true, value: candidate };
}

function directionForCandidate(request, candidate) {
  if (request.input_mint === candidate.quote_mint && request.output_mint === candidate.base_mint) {
    return "buy_base_with_quote";
  }

  if (request.input_mint === candidate.base_mint && request.output_mint === candidate.quote_mint) {
    return "sell_base_for_quote";
  }

  return null;
}

function discoverableCanonicalMint(request) {
  const solMint = "So11111111111111111111111111111111111111112";
  if (request.input_mint === solMint && request.output_mint !== solMint) {
    return request.output_mint;
  }
  if (request.output_mint === solMint && request.input_mint !== solMint) {
    return request.input_mint;
  }
  return null;
}

function canonicalPoolNotFoundError({ mint, poolKey, accountInfo, knownPoolDiagnostics = [], message }) {
  const details = {
    mint,
    discovery_mode: "canonical_pumpswap_pool",
    candidate_pool_address: poolKey.toString(),
    candidate_pool_addresses: [poolKey.toString()],
    account_exists: accountInfo !== null,
    account_owner: accountInfo?.owner?.toString?.() || null,
    expected_program_id: PUMP_AMM_PROGRAM_ID.toString(),
    rejection_reason: accountInfo === null ? "ACCOUNT_NOT_FOUND" : "UNSUPPORTED_POOL_LAYOUT",
    pair_constraint: "direct SOL <-> pump-token canonical pool",
    message,
    note: "No direct canonical PumpSwap pool was found for this token. Jupiter may still route through Pump.fun Amm as one leg of a multi-hop route.",
  };
  if (knownPoolDiagnostics.length > 0) {
    details.known_pool_diagnostics = knownPoolDiagnostics;
  }
  if (accountInfo !== null && !accountInfo.owner.equals(PUMP_AMM_PROGRAM_ID)) {
    details.rejection_reason = "NOT_CANONICAL_POOL";
  }
  return structuredError("NO_PUMPSWAP_POOL", "No direct canonical PumpSwap pool was found for this token.", details);
}

function validateRequest(request) {
  if (request === null || typeof request !== "object" || Array.isArray(request)) {
    return structuredError("INVALID_REQUEST", "Quote request must be a JSON object.");
  }

  if (typeof request.rpc_url !== "string" || request.rpc_url.trim().length === 0) {
    return structuredError("INVALID_RPC_URL", "rpc_url must be a non-empty string.");
  }

  for (const field of ["input_mint", "output_mint", "user_public_key"]) {
    const validated = validatePublicKey(request[field], field);
    if (!validated.ok) {
      return validated;
    }
  }

  const amount = validateAmountRaw(request.amount_raw);
  if (!amount.ok) {
    return amount;
  }

  const slippage = validateSlippageBps(request.slippage_bps);
  if (!slippage.ok) {
    return slippage;
  }

  if (!Array.isArray(request.pool_candidates)) {
    return structuredError("INVALID_POOL_CANDIDATES", "pool_candidates must be an array.");
  }

  const knownPoolAddresses = [];
  if (Array.isArray(request.known_amm_pool_addresses)) {
    for (const [index, address] of request.known_amm_pool_addresses.entries()) {
      const validated = validatePublicKey(address, `known_amm_pool_addresses[${index}]`);
      if (!validated.ok) {
        return validated;
      }
      knownPoolAddresses.push(validated.value);
    }
  }

  if (request.pool_candidates.length === 0) {
    if (request.discover_canonical_pool === true && discoverableCanonicalMint(request)) {
      return {
        ok: true,
        value: {
          request,
          amountRaw: amount.value,
          slippageBps: slippage.value,
          match: null,
          discoverCanonicalMint: discoverableCanonicalMint(request),
          knownPoolAddresses,
        },
      };
    }

    return structuredError("NO_POOL_CANDIDATES", "pool_candidates must contain at least one explicit PumpSwap pool candidate.");
  }

  const candidates = [];
  for (const [index, candidate] of request.pool_candidates.entries()) {
    const validated = validateCandidate(candidate, index);
    if (!validated.ok) {
      return validated;
    }
    candidates.push(validated.value);
  }

  const matches = candidates
    .map((candidate, index) => ({
      candidate,
      index,
      direction: directionForCandidate(request, candidate),
    }))
    .filter((match) => match.direction !== null);

  if (matches.length === 0) {
    return structuredError(
      "POOL_CANDIDATE_MINT_MISMATCH",
      "No pool candidate matches the input/output mint direction.",
      {
        input_mint: request.input_mint,
        output_mint: request.output_mint,
        pool_candidates: candidates.map((candidate, index) => summarizeCandidate(candidate, index)),
      },
    );
  }

  return {
    ok: true,
    value: {
      request,
      amountRaw: amount.value,
      slippageBps: slippage.value,
      match: matches[0],
      knownPoolAddresses,
    },
  };
}

function bnToString(value) {
  return value === undefined || value === null ? null : value.toString();
}

function assertOnchainPoolMatchesCandidate(swapState, candidate) {
  const onchainBaseMint = swapState.pool.baseMint.toString();
  const onchainQuoteMint = swapState.pool.quoteMint.toString();

  if (onchainBaseMint !== candidate.base_mint || onchainQuoteMint !== candidate.quote_mint) {
    return structuredError("POOL_ONCHAIN_MINT_MISMATCH", "On-chain pool mints do not match the selected pool candidate.", {
      candidate: summarizeCandidate(candidate),
      onchain_base_mint: onchainBaseMint,
      onchain_quote_mint: onchainQuoteMint,
    });
  }

  return { ok: true };
}

async function inspectKnownPumpAmmPools({ request, sdk, knownPoolAddresses }) {
  const diagnostics = [];
  for (const [index, poolKey] of knownPoolAddresses.entries()) {
    const item = {
      candidate_index: index,
      address: poolKey.toString(),
      source: "known_amm_pool_addresses",
    };
    try {
      const pool = await sdk.fetchPool(poolKey);
      const candidate = {
        address: poolKey.toString(),
        name: "known-pump-amm-pool",
        base_mint: pool.baseMint.toString(),
        quote_mint: pool.quoteMint.toString(),
        discovery_mode: "known_amm_pool_address",
      };
      const direction = directionForCandidate(request, candidate);
      const includesInput = candidate.base_mint === request.input_mint || candidate.quote_mint === request.input_mint;
      const includesOutput = candidate.base_mint === request.output_mint || candidate.quote_mint === request.output_mint;
      const includesEitherRequestedMint = includesInput || includesOutput;
      diagnostics.push({
        ...item,
        account_exists: true,
        account_owner: PUMP_AMM_PROGRAM_ID.toString(),
        decode_ok: true,
        base_mint: candidate.base_mint,
        quote_mint: candidate.quote_mint,
        direction,
        matches_requested_pair: direction !== null,
        rejection_reason: direction
          ? null
          : includesEitherRequestedMint
            ? "TOKEN_NOT_DIRECT_SOL_PAIR"
            : "POOL_DOES_NOT_MATCH_REQUESTED_PAIR",
      });
      if (direction) {
        return {
          match: {
            candidate,
            index,
            direction,
          },
          diagnostics,
        };
      }
    } catch (err) {
      diagnostics.push({
        ...item,
        account_exists: null,
        decode_ok: false,
        rejection_reason: "UNSUPPORTED_POOL_LAYOUT",
        message: err instanceof Error ? err.message : String(err),
      });
    }
  }
  return { match: null, diagnostics };
}

async function quotePumpSwap(validated) {
  const { request, amountRaw, slippageBps } = validated;
  const connection = new Connection(request.rpc_url);
  const sdk = new OnlinePumpAmmSdk(connection);
  let match = validated.match;
  let knownPoolDiagnostics = [];

  if (!match && Array.isArray(validated.knownPoolAddresses) && validated.knownPoolAddresses.length > 0) {
    const knownPoolResult = await inspectKnownPumpAmmPools({
      request,
      sdk,
      knownPoolAddresses: validated.knownPoolAddresses,
    });
    knownPoolDiagnostics = knownPoolResult.diagnostics;
    if (knownPoolResult.match) {
      match = knownPoolResult.match;
    }
  }

  if (!match && validated.discoverCanonicalMint) {
    const baseMint = new PublicKey(validated.discoverCanonicalMint);
    const poolKey = canonicalPumpPoolPda(baseMint);
    const accountInfo = await connection.getAccountInfo(poolKey);
    if (accountInfo === null || !accountInfo.owner.equals(PUMP_AMM_PROGRAM_ID)) {
      return canonicalPoolNotFoundError({
        mint: validated.discoverCanonicalMint,
        poolKey,
        accountInfo,
        knownPoolDiagnostics,
        message: accountInfo === null
          ? "Canonical PumpSwap pool account does not exist."
          : "Canonical PumpSwap pool account is not owned by the PumpSwap AMM program.",
      });
    }
    try {
      const pool = await sdk.fetchPool(poolKey);
      match = {
        candidate: {
          address: poolKey.toString(),
          name: "canonical-pumpswap-pool",
          base_mint: pool.baseMint.toString(),
          quote_mint: pool.quoteMint.toString(),
          discovery_mode: "canonical_pumpswap_pool",
        },
        index: 0,
        direction: directionForCandidate(request, {
          base_mint: pool.baseMint.toString(),
          quote_mint: pool.quoteMint.toString(),
        }),
      };
    } catch (err) {
      return canonicalPoolNotFoundError({
        mint: validated.discoverCanonicalMint,
        poolKey,
        accountInfo,
        knownPoolDiagnostics,
        message: err instanceof Error ? err.message : String(err),
      });
    }
  }

  if (!match || !match.direction) {
    return structuredError("NO_PUMPSWAP_POOL", "No PumpSwap pool matches the requested pair.", {
      input_mint: request.input_mint,
      output_mint: request.output_mint,
      known_pool_diagnostics: knownPoolDiagnostics,
    });
  }

  const { candidate, index, direction } = match;
  const poolKey = new PublicKey(candidate.address);
  const user = new PublicKey(request.user_public_key);
  const swapState = await sdk.swapSolanaState(poolKey, user);
  const onchainMatch = assertOnchainPoolMatchesCandidate(swapState, candidate);
  if (!onchainMatch.ok) {
    return onchainMatch;
  }

  const quoteArgs = {
    slippage: slippageBps / 100,
    baseReserve: swapState.poolBaseAmount,
    quoteReserve: swapState.poolQuoteAmount,
    globalConfig: swapState.globalConfig,
    baseMintAccount: swapState.baseMintAccount,
    baseMint: swapState.pool.baseMint,
    coinCreator: swapState.pool.coinCreator,
    creator: swapState.pool.creator,
    feeConfig: swapState.feeConfig,
  };

  if (direction === "buy_base_with_quote") {
    const quote = buyQuoteInput({
      ...quoteArgs,
      quote: amountRaw,
    });

    return {
      ok: true,
      provider: "pumpswap",
      quote_type: "research_helper",
      direction,
      pool: summarizeCandidate(candidate, index),
      input_mint: request.input_mint,
      output_mint: request.output_mint,
      in_amount_raw: amountRaw.toString(),
      out_amount_raw: bnToString(quote.base),
      max_in_amount_raw: bnToString(quote.maxQuote),
      internal_quote_without_fees_raw: bnToString(quote.internalQuoteWithoutFees),
      base_reserve_raw: bnToString(swapState.poolBaseAmount),
      quote_reserve_raw: bnToString(swapState.poolQuoteAmount),
      slippage_bps: slippageBps,
    };
  }

  if (direction === "sell_base_for_quote") {
    const quote = sellBaseInput({
      ...quoteArgs,
      base: amountRaw,
    });

    return {
      ok: true,
      provider: "pumpswap",
      quote_type: "research_helper",
      direction,
      pool: summarizeCandidate(candidate, index),
      input_mint: request.input_mint,
      output_mint: request.output_mint,
      in_amount_raw: amountRaw.toString(),
      out_amount_raw: bnToString(quote.uiQuote),
      min_out_amount_raw: bnToString(quote.minQuote),
      internal_quote_amount_out_raw: bnToString(quote.internalQuoteAmountOut),
      base_reserve_raw: bnToString(swapState.poolBaseAmount),
      quote_reserve_raw: bnToString(swapState.poolQuoteAmount),
      slippage_bps: slippageBps,
    };
  }

  return structuredError("QUOTE_NOT_IMPLEMENTED", "PumpSwap quote direction is not implemented.", {
    direction,
    candidate: summarizeCandidate(candidate, index),
  });
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

  const result = await quotePumpSwap(validated.value);
  writeJson(result);
  if (!result.ok) {
    process.exitCode = 1;
  }
}

main().catch((err) => {
  writeJson(
    structuredError("UNHANDLED_ERROR", "Unhandled PumpSwap quote helper error.", {
      message: err instanceof Error ? err.message : String(err),
    }),
  );
  process.exitCode = 1;
});
