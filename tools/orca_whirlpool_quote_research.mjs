#!/usr/bin/env node

import {
  fetchWhirlpoolsByTokenPair,
  setNativeMintWrappingStrategy,
  setWhirlpoolsConfig,
  swapInstructions,
} from "@orca-so/whirlpools";
import {
  address,
  createNoopSigner,
  createSolanaRpc,
  isAddress,
  mainnet,
} from "@solana/kit";

const SOL_MINT = "So11111111111111111111111111111111111111112";
const DEFAULT_QUOTE_OWNER = "11111111111111111111111111111111";
const DEFAULT_DISCOVERY_API_URL = "https://api.orca.so/v2/solana/pools";
const DEFAULT_DISCOVERY_MIN_TVL_USDC = 10000;
const DEFAULT_DISCOVERY_MIN_VOLUME_24H_USDC = 1;
const DEFAULT_DISCOVERY_PAGE_SIZE = 10;
const DISCOVERY_REQUEST_TIMEOUT_MS = 8000;

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
    return structuredError("EMPTY_STDIN", "Expected Orca Whirlpool quote request JSON on stdin.");
  }

  try {
    return { ok: true, value: JSON.parse(raw) };
  } catch (err) {
    return structuredError("INVALID_JSON", "Failed to parse Orca Whirlpool quote request JSON.", {
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

  if (!isAddress(value)) {
    return structuredError("INVALID_PUBLIC_KEY", `${field} is not a valid Solana public key.`, {
      field,
      value,
    });
  }

  return { ok: true, value: address(value) };
}

function validateAmountRaw(value) {
  if (typeof value !== "string" || !/^[1-9]\d*$/.test(value)) {
    return structuredError("INVALID_AMOUNT_RAW", "amount_raw must be a positive integer string.", {
      amount_raw: value,
    });
  }

  return { ok: true, value: BigInt(value) };
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

function candidateMint(candidate, names) {
  for (const name of names) {
    if (typeof candidate[name] === "string" && candidate[name].trim().length > 0) {
      return candidate[name].trim();
    }
  }
  return null;
}

function summarizeCandidate(candidate, index = undefined) {
  const summary = {
    address: candidate.address,
  };
  if (index !== undefined) {
    summary.candidate_index = index;
  }
  if (typeof candidate.name === "string" && candidate.name.trim().length > 0) {
    summary.name = candidate.name;
  }
  if (candidate.tick_spacing !== undefined) {
    summary.tick_spacing = candidate.tick_spacing;
  }
  if (candidate.tickSpacing !== undefined) {
    summary.tick_spacing = candidate.tickSpacing;
  }
  const tokenMintA = candidateMint(candidate, ["token_mint_a", "tokenMintA", "token_a", "tokenA"]);
  const tokenMintB = candidateMint(candidate, ["token_mint_b", "tokenMintB", "token_b", "tokenB"]);
  if (tokenMintA) {
    summary.token_mint_a = tokenMintA;
  }
  if (tokenMintB) {
    summary.token_mint_b = tokenMintB;
  }
  return summary;
}

function validateCandidate(candidate, index, request) {
  if (candidate === null || typeof candidate !== "object" || Array.isArray(candidate)) {
    return structuredError("INVALID_POOL_CANDIDATE", "Pool candidate must be a JSON object.", {
      candidate_index: index,
    });
  }

  const addressCheck = validatePublicKey(candidate.address, `pool_candidates[${index}].address`);
  if (!addressCheck.ok) {
    return addressCheck;
  }

  const tokenMintA = candidateMint(candidate, ["token_mint_a", "tokenMintA", "token_a", "tokenA"]);
  const tokenMintB = candidateMint(candidate, ["token_mint_b", "tokenMintB", "token_b", "tokenB"]);
  for (const [field, value] of [
    ["token_mint_a", tokenMintA],
    ["token_mint_b", tokenMintB],
  ]) {
    if (value !== null) {
      const mintCheck = validatePublicKey(value, `pool_candidates[${index}].${field}`);
      if (!mintCheck.ok) {
        return mintCheck;
      }
    }
  }

  if (tokenMintA && tokenMintB) {
    const candidateMints = new Set([tokenMintA, tokenMintB]);
    if (!candidateMints.has(request.input_mint) || !candidateMints.has(request.output_mint)) {
      return structuredError(
        "POOL_CANDIDATE_MINT_MISMATCH",
        "Pool candidate token mints do not match input/output mints.",
        {
          input_mint: request.input_mint,
          output_mint: request.output_mint,
          candidate: summarizeCandidate(candidate, index),
        },
      );
    }
  }

  return {
    ok: true,
    value: {
      ...candidate,
      address: addressCheck.value,
      address_string: candidate.address,
    },
  };
}

function validateRequest(request) {
  if (request === null || typeof request !== "object" || Array.isArray(request)) {
    return structuredError("INVALID_REQUEST", "Quote request must be a JSON object.");
  }

  if (typeof request.rpc_url !== "string" || request.rpc_url.trim().length === 0) {
    return structuredError("INVALID_RPC_URL", "rpc_url must be a non-empty string.");
  }

  const inputMint = validatePublicKey(request.input_mint, "input_mint");
  if (!inputMint.ok) {
    return inputMint;
  }

  const outputMint = validatePublicKey(request.output_mint, "output_mint");
  if (!outputMint.ok) {
    return outputMint;
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

  const candidates = [];
  for (const [index, candidate] of request.pool_candidates.entries()) {
    const validated = validateCandidate(candidate, index, request);
    if (!validated.ok) {
      return validated;
    }
    candidates.push(validated.value);
  }

  return {
    ok: true,
    value: {
      rpcUrl: request.rpc_url,
      inputMint: inputMint.value,
      outputMint: outputMint.value,
      inputMintString: request.input_mint,
      outputMintString: request.output_mint,
      amountRaw: amount.value,
      amountRawString: request.amount_raw,
      slippageBps: slippage.value,
      poolCandidates: candidates,
      discoverPools: request.discover_pools === true,
      enableTwoHopDiscovery: request.enable_two_hop_discovery === true,
      discovery: request.discovery && typeof request.discovery === "object" && !Array.isArray(request.discovery)
        ? request.discovery
        : {},
    },
  };
}

function numberOrZero(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function isBlockedPool(pool) {
  return Boolean(
    pool?.isBlocked ||
      pool?.is_blocked ||
      pool?.blocked ||
      pool?.hasWarning ||
      pool?.has_warning ||
      pool?.isBlacklisted ||
      pool?.is_blacklisted ||
      pool?.blacklisted,
  );
}

function discoveryConfig(request) {
  const config = request.discovery || {};
  const minTvl = Number(config.min_tvl_usdc ?? config.min_tvl_usd ?? DEFAULT_DISCOVERY_MIN_TVL_USDC);
  const minVolume = Number(
    config.min_volume_24h_usdc ?? config.min_volume_24h_usd ?? config.min_volume_usdc ?? DEFAULT_DISCOVERY_MIN_VOLUME_24H_USDC,
  );
  const pageSize = Number(config.page_size ?? DEFAULT_DISCOVERY_PAGE_SIZE);
  return {
    apiUrl: typeof config.api_url === "string" && config.api_url.trim() ? config.api_url.trim() : DEFAULT_DISCOVERY_API_URL,
    minTvlUsdc: Number.isFinite(minTvl) && minTvl >= 0 ? minTvl : DEFAULT_DISCOVERY_MIN_TVL_USDC,
    minVolume24hUsdc: Number.isFinite(minVolume) && minVolume >= 0 ? minVolume : DEFAULT_DISCOVERY_MIN_VOLUME_24H_USDC,
    pageSize: Number.isInteger(pageSize) && pageSize > 0 ? Math.min(pageSize, 25) : DEFAULT_DISCOVERY_PAGE_SIZE,
    sortBy: typeof config.sort_by === "string" && config.sort_by.trim() ? config.sort_by.trim() : "tvl",
  };
}

function poolTvlUsdc(pool) {
  return numberOrZero(pool?.tvlUsdc ?? pool?.tvl_usdc ?? pool?.tvl);
}

function poolVolume24hUsdc(pool) {
  return numberOrZero(pool?.stats?.["24h"]?.volume ?? pool?.volume24h ?? pool?.volume_24h ?? pool?.volume24hUsdc);
}

function poolInfoToCandidate(pool, index = undefined) {
  return {
    address: address(pool.address.toString()),
    address_string: pool.address.toString(),
    candidate_index: index,
    initialized: pool.initialized,
    price: pool.price,
    tick_spacing: pool.tickSpacing,
    fee_rate: pool.feeRate,
    protocol_fee_rate: pool.protocolFeeRate,
    liquidity: pool.liquidity === undefined || pool.liquidity === null ? null : pool.liquidity.toString(),
    token_mint_a: pool.tokenMintA?.toString?.() ?? pool.tokenMintA,
    token_mint_b: pool.tokenMintB?.toString?.() ?? pool.tokenMintB,
    source: "orca_sdk_fetchWhirlpoolsByTokenPair",
  };
}

function apiPoolToCandidate(pool, index = undefined) {
  return {
    address: address(pool.address),
    address_string: pool.address,
    candidate_index: index,
    initialized: true,
    price: pool.price,
    tick_spacing: pool.tickSpacing,
    fee_rate: pool.feeRate,
    protocol_fee_rate: pool.protocolFeeRate,
    liquidity: pool.liquidity === undefined || pool.liquidity === null ? null : pool.liquidity.toString(),
    token_mint_a: pool.tokenMintA,
    token_mint_b: pool.tokenMintB,
    tvl_usdc: pool.tvlUsdc,
    volume_24h: pool.stats?.["24h"]?.volume ?? null,
    source: "orca_public_api_pools_search",
  };
}

function discoveryMetadata(config, discoveredPools, usablePools, rejected, selectedPool = null, lookupError = null) {
  return {
    source: "orca_public_api_pools_search",
    api_url: config.apiUrl,
    min_tvl_usdc: config.minTvlUsdc,
    min_volume_24h_usdc: config.minVolume24hUsdc,
    discovered_pool_count: discoveredPools.length,
    usable_pool_count: usablePools.length,
    rejected_blocked_count: rejected.blocked,
    rejected_mint_mismatch_count: rejected.mintMismatch,
    rejected_low_tvl_count: rejected.lowTvl,
    rejected_low_volume_count: rejected.lowVolume,
    selected_pool: selectedPool
      ? {
          address: selectedPool.address,
          name: selectedPool.name,
          tick_spacing: selectedPool.tickSpacing,
          fee_rate: selectedPool.feeRate,
          tvl_usdc: poolTvlUsdc(selectedPool),
          volume_24h: poolVolume24hUsdc(selectedPool),
          token_mint_a: selectedPool.tokenMintA,
          token_mint_b: selectedPool.tokenMintB,
        }
      : null,
    lookup_error: lookupError,
  };
}

function quoteToJson(quote) {
  return {
    token_in_raw: quote.tokenIn?.toString() ?? null,
    token_est_out_raw: quote.tokenEstOut?.toString() ?? null,
    token_min_out_raw: quote.tokenMinOut?.toString() ?? null,
    trade_fee_raw: quote.tradeFee?.toString() ?? null,
    trade_fee_rate_min: quote.tradeFeeRateMin ?? null,
    trade_fee_rate_max: quote.tradeFeeRateMax ?? null,
  };
}

async function resolvePoolCandidates(request, rpc) {
  if (request.poolCandidates.length > 0) {
    return {
      ok: true,
      source: "explicit_pool_candidates",
      candidates: request.poolCandidates,
      discovery: null,
    };
  }

  if (request.discoverPools) {
    return resolveApiDiscoveredPoolCandidates(request);
  }

  let pools = [];
  let sdkLookupError = null;
  try {
    pools = await fetchWhirlpoolsByTokenPair(rpc, request.inputMint, request.outputMint);
  } catch (err) {
    sdkLookupError = err instanceof Error ? err.message : String(err);
  }

  let candidates = pools
    .filter((pool) => pool.initialized)
    .map((pool, index) => poolInfoToCandidate(pool, index));

  if (candidates.length === 0) {
    let apiCandidates = [];
    let apiLookupError = null;
    try {
      apiCandidates = await fetchOrcaApiPoolCandidates(request);
    } catch (err) {
      apiLookupError = err instanceof Error ? err.message : String(err);
    }
    if (apiCandidates.length > 0) {
      return {
        ok: true,
        source: "orca_public_api_pools_search",
        candidates: apiCandidates,
        sdk_lookup_error: sdkLookupError,
        discovery: null,
      };
    }
    if (apiLookupError) {
      sdkLookupError = [sdkLookupError, `Orca API lookup failed: ${apiLookupError}`]
        .filter(Boolean)
        .join(" | ");
    }
  }

  if (candidates.length === 0) {
    return structuredError(
      "NO_POOL_CANDIDATES",
      "No initialized Orca Whirlpool pool candidates were found for the requested pair.",
      {
        input_mint: request.inputMintString,
        output_mint: request.outputMintString,
        lookup_source: "fetchWhirlpoolsByTokenPair",
        pools_returned: pools.length,
        sdk_lookup_error: sdkLookupError,
      },
    );
  }

  return {
    ok: true,
    source: "orca_sdk_fetchWhirlpoolsByTokenPair",
    candidates,
    discovery: null,
  };
}

async function resolveApiDiscoveredPoolCandidates(request) {
  const config = discoveryConfig(request);
  let discoveredPools = [];
  try {
    discoveredPools = await fetchOrcaApiPools(request, config);
  } catch (err) {
    return structuredError("DISCOVERY_REQUEST_FAILED", "Orca pool discovery request failed.", {
      message: err instanceof Error ? err.message : String(err),
      source: "orca_public_api_pools_search",
    });
  }

  const rejected = {
    blocked: 0,
    mintMismatch: 0,
    lowTvl: 0,
    lowVolume: 0,
  };
  const usablePools = [];

  for (const pool of discoveredPools) {
    if (!pool || typeof pool !== "object") {
      continue;
    }

    const mints = new Set([pool.tokenMintA, pool.tokenMintB]);
    if (!mints.has(request.inputMintString) || !mints.has(request.outputMintString)) {
      rejected.mintMismatch += 1;
      continue;
    }
    if (isBlockedPool(pool)) {
      rejected.blocked += 1;
      continue;
    }
    if (poolTvlUsdc(pool) < config.minTvlUsdc) {
      rejected.lowTvl += 1;
      continue;
    }
    if (poolVolume24hUsdc(pool) < config.minVolume24hUsdc) {
      rejected.lowVolume += 1;
      continue;
    }
    usablePools.push(pool);
  }

  usablePools.sort((left, right) => {
    const tvlDiff = poolTvlUsdc(right) - poolTvlUsdc(left);
    if (tvlDiff !== 0) {
      return tvlDiff;
    }
    return poolVolume24hUsdc(right) - poolVolume24hUsdc(left);
  });

  if (discoveredPools.length === 0) {
    return structuredError("NO_DISCOVERED_POOL", "No Orca Whirlpool pools were discovered for the requested pair.", {
      input_mint: request.inputMintString,
      output_mint: request.outputMintString,
      discovery: discoveryMetadata(config, discoveredPools, usablePools, rejected),
    });
  }

  if (usablePools.length === 0) {
    return structuredError(
      "NO_USABLE_DISCOVERED_POOL",
      "Discovered Orca Whirlpool pools did not pass quality filters.",
      {
        input_mint: request.inputMintString,
        output_mint: request.outputMintString,
        discovery: discoveryMetadata(config, discoveredPools, usablePools, rejected),
      },
    );
  }

  return {
    ok: true,
    source: "orca_public_api_pools_search",
    candidates: usablePools.map((pool, index) => apiPoolToCandidate(pool, index)),
    discovery: discoveryMetadata(config, discoveredPools, usablePools, rejected, usablePools[0]),
  };
}

async function fetchOrcaApiPools(request, config) {
  const url = new URL(config.apiUrl);
  url.search = new URLSearchParams({
    tokensBothOf: `${request.inputMintString},${request.outputMintString}`,
    minTvl: config.minTvlUsdc.toString(),
    minVolume: config.minVolume24hUsdc.toString(),
    size: config.pageSize.toString(),
    sortBy: config.sortBy,
    sortDirection: "desc",
    stats: "24h",
  }).toString();

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), DISCOVERY_REQUEST_TIMEOUT_MS);
  try {
    const response = await fetch(url, {
      headers: {
        Accept: "application/json",
        "User-Agent": "web3-digest-orca-quote-research",
      },
      signal: controller.signal,
    });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const payload = await response.json();
    return Array.isArray(payload?.data) ? payload.data : [];
  } finally {
    clearTimeout(timeout);
  }
}

async function fetchOrcaApiPoolCandidates(request) {
  const url = new URL("https://api.orca.so/v2/solana/pools/search");
  url.search = new URLSearchParams({
    q: `${request.inputMintString}-${request.outputMintString}`,
    minTvl: "50000",
    size: "10",
    sortBy: "tvl",
    sortDirection: "desc",
  }).toString();

  const response = await fetch(url, {
    headers: {
      Accept: "application/json",
      "User-Agent": "web3-digest-orca-quote-research",
    },
  });
  if (!response.ok) {
    return [];
  }

  const payload = await response.json();
  const pools = Array.isArray(payload?.data) ? payload.data : [];
  return pools
    .filter((pool) => {
      if (!pool || typeof pool !== "object") {
        return false;
      }
      const mints = new Set([pool.tokenMintA, pool.tokenMintB]);
      return mints.has(request.inputMintString) && mints.has(request.outputMintString);
    })
    .map((pool, index) => apiPoolToCandidate(pool, index));
}

async function quoteCandidate(request, rpc, candidate, index, discovery = null) {
  const signer = createNoopSigner(address(DEFAULT_QUOTE_OWNER));
  const { quote, instructions, tradeEnableTimestamp } = await swapInstructions(
    rpc,
    {
      inputAmount: request.amountRaw,
      mint: request.inputMint,
    },
    candidate.address,
    request.slippageBps,
    signer,
  );

  const quoteJson = quoteToJson(quote);
  if (discovery) {
    quoteJson.discovery = discovery;
  }
  return {
    ok: true,
    provider: "orca_whirlpool",
    quote_type: "research_helper",
    execution_status: "quote_only",
    candidate_index: index,
    pool: summarizeCandidate(candidate, index),
    input_mint: request.inputMintString,
    output_mint: request.outputMintString,
    in_amount_raw: request.amountRawString,
    out_amount_raw: quoteJson.token_est_out_raw,
    min_out_amount_raw: quoteJson.token_min_out_raw,
    fee_raw: quoteJson.trade_fee_raw,
    trade_fee_rate_min: quoteJson.trade_fee_rate_min,
    trade_fee_rate_max: quoteJson.trade_fee_rate_max,
    slippage_bps: request.slippageBps,
    trade_enable_timestamp: tradeEnableTimestamp.toString(),
    instructions_count: instructions.length,
    discovery,
    raw_quote: quoteJson,
  };
}

async function quoteSinglePoolRoute(request, rpc) {
  const resolved = await resolvePoolCandidates(request, rpc);
  if (!resolved.ok) {
    return resolved;
  }

  const quoteResults = [];
  const quoteErrors = [];
  for (const [index, candidate] of resolved.candidates.entries()) {
    try {
      quoteResults.push(await quoteCandidate(request, rpc, candidate, index, resolved.discovery ?? null));
    } catch (err) {
      quoteErrors.push({
        candidate_index: index,
        pool: summarizeCandidate(candidate, index),
        code: "POOL_QUOTE_FAILED",
        message: err instanceof Error ? err.message : String(err),
      });
    }
  }

  quoteResults.sort((left, right) => {
    const leftOut = BigInt(left.out_amount_raw ?? "-1");
    const rightOut = BigInt(right.out_amount_raw ?? "-1");
    if (rightOut > leftOut) {
      return 1;
    }
    if (rightOut < leftOut) {
      return -1;
    }
    return 0;
  });

  if (quoteResults.length === 0) {
    const details = {
      candidate_source: resolved.source,
      candidates_checked: resolved.candidates.length,
      quote_errors: quoteErrors,
    };
    if (resolved.discovery) {
      details.discovery = resolved.discovery;
    }
    return structuredError(
      resolved.source === "orca_public_api_pools_search" ? "DISCOVERED_POOL_QUOTE_FAILED" : "QUOTE_NOT_IMPLEMENTED",
      "Orca SDK path was found, but no candidate pool produced a quote.",
      details,
    );
  }

  return {
    ...quoteResults[0],
    candidate_source: resolved.source,
    checked_pool_count: resolved.candidates.length,
    successful_quote_count: quoteResults.length,
    pool_quote_errors: quoteErrors,
    all_pool_quotes: quoteResults,
  };
}

function shouldAttemptTwoHop(request, directResult) {
  if (request.enableTwoHopDiscovery !== true) {
    return false;
  }
  if (request.inputMintString === SOL_MINT || request.outputMintString === SOL_MINT) {
    return false;
  }

  const code = directResult?.error?.code;
  return (
    code === "NO_DISCOVERED_POOL" ||
    code === "NO_USABLE_DISCOVERED_POOL" ||
    code === "DISCOVERED_POOL_QUOTE_FAILED"
  );
}

function twoHopLegRequest(request, inputMintString, outputMintString, amountRawString) {
  return {
    ...request,
    inputMint: address(inputMintString),
    outputMint: address(outputMintString),
    inputMintString,
    outputMintString,
    amountRaw: BigInt(amountRawString),
    amountRawString: String(amountRawString),
    poolCandidates: [],
    discoverPools: true,
    enableTwoHopDiscovery: false,
  };
}

function routeStepFromLeg(leg, label) {
  const pool = leg.pool || {};
  return {
    label,
    pool_address: pool.address,
    pool_name: pool.name,
    tick_spacing: pool.tick_spacing ?? pool.tickSpacing,
    fee_rate: pool.fee_rate ?? pool.feeRate,
    input_mint: leg.input_mint,
    output_mint: leg.output_mint,
    in_amount_raw: leg.in_amount_raw,
    out_amount_raw: leg.out_amount_raw,
    min_out_amount_raw: leg.min_out_amount_raw,
    fee_raw: leg.fee_raw,
    trade_fee_rate_min: leg.trade_fee_rate_min,
    trade_fee_rate_max: leg.trade_fee_rate_max,
    discovery: leg.discovery,
  };
}

async function quoteTwoHopViaSol(request, rpc, directResult) {
  const leg1Request = twoHopLegRequest(request, request.inputMintString, SOL_MINT, request.amountRawString);
  const leg1 = await quoteSinglePoolRoute(leg1Request, rpc);
  if (!leg1.ok) {
    return structuredError("TWO_HOP_LEG_1_FAILED", "Orca Whirlpool two-hop quote failed on the input-to-SOL leg.", {
      intermediate_mint: SOL_MINT,
      direct_error: directResult?.error,
      leg_1_error: leg1.error,
    });
  }

  const leg2Request = twoHopLegRequest(request, SOL_MINT, request.outputMintString, leg1.out_amount_raw);
  const leg2 = await quoteSinglePoolRoute(leg2Request, rpc);
  if (!leg2.ok) {
    return structuredError("TWO_HOP_LEG_2_FAILED", "Orca Whirlpool two-hop quote failed on the SOL-to-output leg.", {
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
    routeStepFromLeg(leg1, "Orca Whirlpool leg 1"),
    routeStepFromLeg(leg2, "Orca Whirlpool leg 2"),
  ];

  return {
    ok: true,
    provider: "orca_whirlpool",
    quote_type: "research_helper",
    execution_status: "quote_only",
    route_shape: "two-hop",
    route_steps: routeSteps,
    pool: leg1.pool,
    input_mint: request.inputMintString,
    output_mint: request.outputMintString,
    intermediate_mint: SOL_MINT,
    in_amount_raw: leg1.in_amount_raw,
    out_amount_raw: leg2.out_amount_raw,
    min_out_amount_raw: leg2.min_out_amount_raw,
    fee_raw: null,
    trade_fee_rate_min: null,
    trade_fee_rate_max: null,
    slippage_bps: request.slippageBps,
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
    checked_pool_count: (leg1.checked_pool_count || 0) + (leg2.checked_pool_count || 0),
    successful_quote_count: (leg1.successful_quote_count || 0) + (leg2.successful_quote_count || 0),
  };
}

async function quoteOrcaWhirlpool(request) {
  await setWhirlpoolsConfig("solanaMainnet");
  setNativeMintWrappingStrategy("none");

  const rpc = createSolanaRpc(mainnet(request.rpcUrl));
  const directResult = await quoteSinglePoolRoute(request, rpc);
  if (directResult.ok || !shouldAttemptTwoHop(request, directResult)) {
    return directResult;
  }

  return quoteTwoHopViaSol(request, rpc, directResult);
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

  const result = await quoteOrcaWhirlpool(validated.value);
  writeJson(result);
  if (!result.ok) {
    process.exitCode = 1;
  }
}

main().catch((err) => {
  writeJson(
    structuredError("UNHANDLED_ERROR", "Unhandled Orca Whirlpool quote helper error.", {
      message: err instanceof Error ? err.message : String(err),
    }),
  );
  process.exitCode = 1;
});
