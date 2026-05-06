#!/usr/bin/env node

import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const DLMM = require("@meteora-ag/dlmm");
const { Connection, PublicKey } = require("@solana/web3.js");
const BN = require("bn.js");

const DEFAULT_DISCOVERY_API_URL = "https://dlmm.datapi.meteora.ag/pools";
const DEFAULT_DISCOVERY_MIN_TVL_USD = 1000;
const DEFAULT_DISCOVERY_MIN_VOLUME_24H_USD = 1;
const DEFAULT_DISCOVERY_PAGE_SIZE = 20;
const DISCOVERY_REQUEST_TIMEOUT_MS = 8000;
const SOL_MINT = "So11111111111111111111111111111111111111112";

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

function numberOrZero(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function exactPairMatches(pool, inputMint, outputMint) {
  const tokenX = pool?.token_x?.address;
  const tokenY = pool?.token_y?.address;
  return (
    (tokenX === inputMint && tokenY === outputMint) ||
    (tokenX === outputMint && tokenY === inputMint)
  );
}

function candidateFromDiscoveredPool(pool) {
  return {
    address: pool.address,
    name: pool.name,
    token_x: pool.token_x.address,
    token_y: pool.token_y.address,
    bin_step: pool.pool_config?.bin_step,
    discovery_source: "meteora_dlmm_data_api",
    tvl: numberOrZero(pool.tvl),
    volume_24h: numberOrZero(pool.volume?.["24h"]),
  };
}

function discoveryConfig(request) {
  const discovery = request.discovery && typeof request.discovery === "object"
    ? request.discovery
    : {};

  return {
    apiUrl: typeof discovery.api_url === "string" && discovery.api_url.trim()
      ? discovery.api_url.trim()
      : DEFAULT_DISCOVERY_API_URL,
    minTvlUsd: numberOrZero(discovery.min_tvl_usd) || DEFAULT_DISCOVERY_MIN_TVL_USD,
    minVolume24hUsd:
      discovery.min_volume_24h_usd === 0
        ? 0
        : (numberOrZero(discovery.min_volume_24h_usd) || DEFAULT_DISCOVERY_MIN_VOLUME_24H_USD),
    pageSize: Math.max(1, Math.min(100, Number.parseInt(discovery.page_size, 10) || DEFAULT_DISCOVERY_PAGE_SIZE)),
    sortBy: typeof discovery.sort_by === "string" && discovery.sort_by.trim()
      ? discovery.sort_by.trim()
      : "tvl:desc",
  };
}

async function fetchDiscoveryPage(config, tokenX, tokenY) {
  const url = new URL(config.apiUrl);
  url.searchParams.set("page_size", String(config.pageSize));
  url.searchParams.set("sort_by", config.sortBy);
  url.searchParams.set("filter_by", `token_x=${tokenX} && token_y=${tokenY}`);

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), DISCOVERY_REQUEST_TIMEOUT_MS);

  try {
    const response = await fetch(url, {
      headers: {
        "Accept": "application/json",
        "User-Agent": "web3-digest/0.1 meteora-dlmm-discovery",
      },
      signal: controller.signal,
    });

    const text = await response.text();
    if (!response.ok) {
      return structuredError("DISCOVERY_API_ERROR", "Meteora DLMM pool discovery API returned an error.", {
        status: response.status,
        body: text.slice(0, 500),
        url: url.toString(),
      });
    }

    try {
      return { ok: true, value: JSON.parse(text), url: url.toString() };
    } catch (err) {
      return structuredError("DISCOVERY_INVALID_JSON", "Meteora DLMM pool discovery API returned invalid JSON.", {
        message: err instanceof Error ? err.message : String(err),
        body: text.slice(0, 500),
        url: url.toString(),
      });
    }
  } catch (err) {
    return structuredError("DISCOVERY_REQUEST_FAILED", "Meteora DLMM pool discovery request failed.", {
      message: err instanceof Error ? err.message : String(err),
      url: url.toString(),
    });
  } finally {
    clearTimeout(timer);
  }
}

async function discoverPoolCandidates(request) {
  if (request.discover_pools !== true) {
    return structuredError(
      "NO_POOL_CANDIDATES",
      "No Meteora DLMM pool candidates provided.",
    );
  }

  const config = discoveryConfig(request);
  const queries = [
    [request.input_mint, request.output_mint],
    [request.output_mint, request.input_mint],
  ];
  const poolsByAddress = new Map();
  const requestedUrls = [];

  for (const [tokenX, tokenY] of queries) {
    const result = await fetchDiscoveryPage(config, tokenX, tokenY);
    if (!result.ok) {
      return result;
    }
    requestedUrls.push(result.url);
    const pools = Array.isArray(result.value?.data) ? result.value.data : [];
    for (const pool of pools) {
      if (typeof pool?.address === "string" && !poolsByAddress.has(pool.address)) {
        poolsByAddress.set(pool.address, pool);
      }
    }
  }

  const stats = {
    requested_urls: requestedUrls,
    discovered_pool_count: poolsByAddress.size,
    rejected_mint_mismatch_count: 0,
    rejected_blacklisted_count: 0,
    rejected_low_tvl_count: 0,
    rejected_low_volume_count: 0,
    usable_pool_count: 0,
    min_tvl_usd: config.minTvlUsd,
    min_volume_24h_usd: config.minVolume24hUsd,
  };

  const usable = [];
  for (const pool of poolsByAddress.values()) {
    if (!exactPairMatches(pool, request.input_mint, request.output_mint)) {
      stats.rejected_mint_mismatch_count += 1;
      continue;
    }
    if (pool.is_blacklisted === true) {
      stats.rejected_blacklisted_count += 1;
      continue;
    }

    const tvl = numberOrZero(pool.tvl);
    const volume24h = numberOrZero(pool.volume?.["24h"]);
    if (tvl < config.minTvlUsd) {
      stats.rejected_low_tvl_count += 1;
      continue;
    }
    if (volume24h < config.minVolume24hUsd) {
      stats.rejected_low_volume_count += 1;
      continue;
    }

    usable.push(pool);
  }

  usable.sort((a, b) => {
    const tvlDiff = numberOrZero(b.tvl) - numberOrZero(a.tvl);
    if (tvlDiff !== 0) return tvlDiff;
    return numberOrZero(b.volume?.["24h"]) - numberOrZero(a.volume?.["24h"]);
  });

  stats.usable_pool_count = usable.length;
  if (poolsByAddress.size === 0) {
    return structuredError("NO_DISCOVERED_POOL", "No Meteora DLMM pools were discovered for this pair.", stats);
  }
  if (usable.length === 0) {
    return structuredError("NO_USABLE_DISCOVERED_POOL", "Discovered Meteora DLMM pools did not pass quality filters.", stats);
  }

  return {
    ok: true,
    value: usable.map(candidateFromDiscoveredPool),
    metadata: {
      ...stats,
      selected_pool: candidateFromDiscoveredPool(usable[0]),
    },
  };
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

async function quoteCandidate(request, candidate, discoveryMetadata = null) {
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
    discovery: discoveryMetadata,
  };
}

async function quoteDiscoveredSinglePool(request) {
  const discovered = await discoverPoolCandidates(request);
  if (!discovered.ok) {
    return discovered;
  }

  const failures = [];
  for (const candidate of discovered.value) {
    try {
      const quote = await quoteCandidate(request, candidate, {
        ...discovered.metadata,
        selected_pool: candidate,
        quote_attempted_pool_count: failures.length + 1,
      });
      if (failures.length > 0) {
        quote.discovery.quote_failures = failures;
      }
      return quote;
    } catch (err) {
      failures.push({
        pool: summarizeFirstCandidate(candidate),
        message: err instanceof Error ? err.message : String(err),
      });
    }
  }

  return structuredError("DISCOVERED_POOL_QUOTE_FAILED", "Discovered Meteora DLMM pools could not be quoted.", {
    discovery: discovered.metadata,
    quote_failures: failures,
  });
}

function shouldAttemptTwoHop(request, directResult) {
  if (request.enable_two_hop_discovery !== true) {
    return false;
  }
  if (request.input_mint === SOL_MINT || request.output_mint === SOL_MINT) {
    return false;
  }

  const code = directResult?.error?.code;
  return (
    code === "NO_DISCOVERED_POOL" ||
    code === "NO_USABLE_DISCOVERED_POOL" ||
    code === "DISCOVERED_POOL_QUOTE_FAILED"
  );
}

function twoHopLegRequest(request, inputMint, outputMint, amountRaw) {
  return {
    ...request,
    input_mint: inputMint,
    output_mint: outputMint,
    amount_raw: String(amountRaw),
    pool_candidates: [],
    discover_pools: true,
    enable_two_hop_discovery: false,
  };
}

function routeStepFromLeg(leg, label) {
  const pool = leg.pool || {};
  return {
    label,
    pool_address: pool.address,
    pool_name: pool.name,
    bin_step: pool.bin_step,
    input_mint: leg.input_mint,
    output_mint: leg.output_mint,
    in_amount_raw: leg.in_amount_raw,
    out_amount_raw: leg.out_amount_raw,
    min_out_amount_raw: leg.min_out_amount_raw,
    fee_raw: leg.fee_raw,
    protocol_fee_raw: leg.protocol_fee_raw,
    bin_arrays: leg.bin_arrays || [],
    discovery: leg.discovery,
  };
}

async function quoteTwoHopViaSol(request, directResult) {
  const leg1Request = twoHopLegRequest(request, request.input_mint, SOL_MINT, request.amount_raw);
  const leg1 = await quoteDiscoveredSinglePool(leg1Request);
  if (!leg1.ok) {
    return structuredError("TWO_HOP_LEG_1_FAILED", "Meteora DLMM two-hop quote failed on the input-to-SOL leg.", {
      intermediate_mint: SOL_MINT,
      direct_error: directResult?.error,
      leg_1_error: leg1.error,
    });
  }

  const leg2Request = twoHopLegRequest(request, SOL_MINT, request.output_mint, leg1.out_amount_raw);
  const leg2 = await quoteDiscoveredSinglePool(leg2Request);
  if (!leg2.ok) {
    return structuredError("TWO_HOP_LEG_2_FAILED", "Meteora DLMM two-hop quote failed on the SOL-to-output leg.", {
      intermediate_mint: SOL_MINT,
      direct_error: directResult?.error,
      leg_1: {
        pool: leg1.pool,
        out_amount_raw: leg1.out_amount_raw,
      },
      leg_2_error: leg2.error,
    });
  }

  const routeSteps = [
    routeStepFromLeg(leg1, "Meteora DLMM leg 1"),
    routeStepFromLeg(leg2, "Meteora DLMM leg 2"),
  ];

  return {
    ok: true,
    provider: "meteora_dlmm",
    route_shape: "two-hop",
    route_steps: routeSteps,
    pool: leg1.pool,
    input_mint: request.input_mint,
    output_mint: request.output_mint,
    intermediate_mint: SOL_MINT,
    in_amount_raw: leg1.in_amount_raw,
    out_amount_raw: leg2.out_amount_raw,
    min_out_amount_raw: leg2.min_out_amount_raw,
    fee_raw: null,
    protocol_fee_raw: null,
    price_impact: leg2.price_impact,
    bin_arrays: [],
    discovery: {
      route_type: "venue_restricted_two_hop",
      direct_error: directResult?.error,
      intermediate_mint: SOL_MINT,
      legs: [
        {
          input_mint: leg1.input_mint,
          output_mint: leg1.output_mint,
          selected_pool: leg1.discovery?.selected_pool || leg1.pool,
        },
        {
          input_mint: leg2.input_mint,
          output_mint: leg2.output_mint,
          selected_pool: leg2.discovery?.selected_pool || leg2.pool,
        },
      ],
    },
    leg_quotes: [leg1, leg2],
  };
}

async function quoteMeteoraDlmm(request) {
  if (request.pool_candidates.length > 0) {
    return quoteCandidate(request, request.pool_candidates[0], null);
  }

  const directResult = await quoteDiscoveredSinglePool(request);
  if (directResult.ok || !shouldAttemptTwoHop(request, directResult)) {
    return directResult;
  }

  return quoteTwoHopViaSol(request, directResult);
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
