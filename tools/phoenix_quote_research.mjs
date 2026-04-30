#!/usr/bin/env node

import { Connection, PublicKey } from "@solana/web3.js";
import {
  Client as PhoenixClient,
  Side,
} from "@ellipsis-labs/phoenix-sdk";

const SOL_MINT = "So11111111111111111111111111111111111111112";
const USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v";
const SOL_DECIMALS = 9;
const USDC_DECIMALS = 6;
const VERIFIED_SOL_USDC_MARKET = {
  address: "4DoNfFBfF7UokCC2FQzriy7yHK6DY6NVdYpuekQ5pRgg",
  name: "SOL/USDC",
  base_mint: SOL_MINT,
  quote_mint: USDC_MINT,
};

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
    return structuredError("EMPTY_STDIN", "Expected Phoenix quote request JSON on stdin.");
  }

  try {
    return { ok: true, value: JSON.parse(raw) };
  } catch (err) {
    return structuredError("INVALID_JSON", "Failed to parse Phoenix quote request JSON.", {
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
    address: candidate.address_string || candidate.address,
  };
  if (index !== undefined) {
    summary.candidate_index = index;
  }
  if (typeof candidate.name === "string" && candidate.name.trim().length > 0) {
    summary.name = candidate.name;
  }
  const baseMint = candidateMint(candidate, ["base_mint", "baseMint", "base_pubkey"]);
  const quoteMint = candidateMint(candidate, ["quote_mint", "quoteMint", "quote_pubkey"]);
  if (baseMint) {
    summary.base_mint = baseMint;
  }
  if (quoteMint) {
    summary.quote_mint = quoteMint;
  }
  return summary;
}

function validateMarketCandidate(candidate, index, request) {
  if (candidate === null || typeof candidate !== "object" || Array.isArray(candidate)) {
    return structuredError("INVALID_MARKET_CANDIDATE", "Market candidate must be a JSON object.", {
      candidate_index: index,
    });
  }

  const addressCheck = validatePublicKey(candidate.address, `market_candidates[${index}].address`);
  if (!addressCheck.ok) {
    return addressCheck;
  }

  const baseMint = candidateMint(candidate, ["base_mint", "baseMint", "base_pubkey"]);
  const quoteMint = candidateMint(candidate, ["quote_mint", "quoteMint", "quote_pubkey"]);

  for (const [field, value] of [
    ["base_mint", baseMint],
    ["quote_mint", quoteMint],
  ]) {
    if (value !== null) {
      const mintCheck = validatePublicKey(value, `market_candidates[${index}].${field}`);
      if (!mintCheck.ok) {
        return mintCheck;
      }
    }
  }

  if (baseMint && quoteMint) {
    if (baseMint !== request.input_mint || quoteMint !== request.output_mint) {
      return structuredError(
        "MARKET_CANDIDATE_MINT_MISMATCH",
        "Phoenix SOL -> USDC expects market base mint SOL and quote mint USDC.",
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

  if (request.input_mint !== SOL_MINT || request.output_mint !== USDC_MINT) {
    return structuredError("UNSUPPORTED_PAIR", "Phoenix quote helper currently supports SOL -> USDC only.", {
      supported_input_mint: SOL_MINT,
      supported_output_mint: USDC_MINT,
      input_mint: request.input_mint,
      output_mint: request.output_mint,
    });
  }

  const amount = validateAmountRaw(request.amount_raw);
  if (!amount.ok) {
    return amount;
  }

  const slippage = validateSlippageBps(request.slippage_bps);
  if (!slippage.ok) {
    return slippage;
  }

  if (!Array.isArray(request.market_candidates)) {
    return structuredError("INVALID_MARKET_CANDIDATES", "market_candidates must be an array.");
  }

  const rawCandidates =
    request.market_candidates.length > 0
      ? request.market_candidates
      : [VERIFIED_SOL_USDC_MARKET];
  const marketCandidates = [];
  for (const [index, candidate] of rawCandidates.entries()) {
    const validated = validateMarketCandidate(candidate, index, request);
    if (!validated.ok) {
      return validated;
    }
    marketCandidates.push(validated.value);
  }

  return {
    ok: true,
    value: {
      rpcUrl: request.rpc_url,
      inputMintString: request.input_mint,
      outputMintString: request.output_mint,
      amountRaw: amount.value,
      amountRawString: request.amount_raw,
      slippageBps: slippage.value,
      marketCandidates,
      usedDefaultMarketCandidate: request.market_candidates.length === 0,
    },
  };
}

function uiAmountFromRaw(rawAmount, decimals) {
  return Number(rawAmount) / 10 ** decimals;
}

function quoteRawFromUi(uiAmount, decimals) {
  if (!Number.isFinite(uiAmount) || uiAmount <= 0) {
    return "0";
  }
  return Math.floor(uiAmount * 10 ** decimals).toString();
}

function minOutRawFromUi(uiAmount, decimals, slippageBps) {
  if (!Number.isFinite(uiAmount) || uiAmount <= 0) {
    return "0";
  }
  return Math.floor(uiAmount * (1 - slippageBps / 10000) * 10 ** decimals).toString();
}

function sumBookQuantity(levels) {
  return levels.reduce((sum, level) => sum + (Number(level.quantity) || 0), 0);
}

function summarizeLevel(level) {
  if (!level) {
    return null;
  }
  return {
    price: level.price,
    quantity: level.quantity,
  };
}

function summarizeMarketState(marketState, candidate) {
  const header = marketState.data.header;
  return {
    address: candidate.address_string,
    name: candidate.name || "SOL/USDC",
    base_mint: header.baseParams.mintKey.toBase58(),
    quote_mint: header.quoteParams.mintKey.toBase58(),
    base_decimals: header.baseParams.decimals,
    quote_decimals: header.quoteParams.decimals,
    base_lot_size: header.baseLotSize.toString(),
    quote_lot_size: header.quoteLotSize.toString(),
    tick_size_in_quote_atoms_per_base_unit: header.tickSizeInQuoteAtomsPerBaseUnit.toString(),
    raw_base_units_per_base_unit: header.rawBaseUnitsPerBaseUnit,
    taker_fee_bps: marketState.data.takerFeeBps,
  };
}

async function quoteMarket(request, client, candidate, index) {
  const marketAddress = candidate.address_string;
  const marketState = client.marketStates.get(marketAddress);
  if (!marketState) {
    return structuredError("MARKET_NOT_LOADED", "Phoenix SDK did not load the candidate market.", {
      candidate: summarizeCandidate(candidate, index),
    });
  }

  const market = summarizeMarketState(marketState, candidate);
  if (market.base_mint !== request.inputMintString || market.quote_mint !== request.outputMintString) {
    return structuredError("MARKET_ONCHAIN_MINT_MISMATCH", "On-chain market mints do not match SOL -> USDC.", {
      candidate: summarizeCandidate(candidate, index),
      market,
    });
  }

  const inputAmountUi = uiAmountFromRaw(request.amountRaw, SOL_DECIMALS);
  const uiLadder = client.getUiLadder(marketAddress, 100);
  const availableBidBaseUi = sumBookQuantity(uiLadder.bids);
  const estimatedOutputUi = client.getMarketExpectedOutAmount({
    marketAddress,
    side: Side.Ask,
    inAmount: inputAmountUi,
  });
  const outAmountRaw = quoteRawFromUi(estimatedOutputUi, USDC_DECIMALS);
  const minOutAmountRaw = minOutRawFromUi(estimatedOutputUi, USDC_DECIMALS, request.slippageBps);
  const fullyFilled = availableBidBaseUi + Number.EPSILON >= inputAmountUi;

  return {
    ok: true,
    provider: "phoenix",
    quote_type: "research_helper",
    execution_status: "quote_only",
    route_shape: "single_clob_market",
    side: "ask",
    candidate_index: index,
    market,
    input_mint: request.inputMintString,
    output_mint: request.outputMintString,
    in_amount_raw: request.amountRawString,
    in_amount_ui: inputAmountUi,
    out_amount_raw: outAmountRaw,
    out_amount_ui: estimatedOutputUi,
    min_out_amount_raw: minOutAmountRaw,
    slippage_bps: request.slippageBps,
    taker_fee_bps: market.taker_fee_bps,
    fully_filled: fullyFilled,
    fill_status: fullyFilled ? "full" : "partial_book_depth",
    available_bid_base_ui: availableBidBaseUi,
    top_bid: summarizeLevel(uiLadder.bids[0]),
    top_ask: summarizeLevel(uiLadder.asks[0]),
    book_depth_checked: {
      bids: uiLadder.bids.length,
      asks: uiLadder.asks.length,
    },
    raw_quote: {
      sdk_method: "Client.getMarketExpectedOutAmount",
      sdk_side: "Side.Ask",
      input_amount_for_sdk: inputAmountUi,
      sdk_output_units: estimatedOutputUi,
    },
  };
}

async function quotePhoenix(request) {
  const connection = new Connection(request.rpcUrl, "confirmed");
  const marketAddresses = request.marketCandidates.map((candidate) => candidate.address);
  const client = await PhoenixClient.createWithMarketAddresses(connection, marketAddresses);

  const quoteResults = [];
  const quoteErrors = [];
  for (const [index, candidate] of request.marketCandidates.entries()) {
    try {
      const result = await quoteMarket(request, client, candidate, index);
      if (result.ok) {
        quoteResults.push(result);
      } else {
        quoteErrors.push({
          candidate_index: index,
          candidate: summarizeCandidate(candidate, index),
          ...result.error,
        });
      }
    } catch (err) {
      quoteErrors.push({
        candidate_index: index,
        candidate: summarizeCandidate(candidate, index),
        code: "MARKET_QUOTE_FAILED",
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
    return structuredError(
      "QUOTE_NOT_IMPLEMENTED",
      "Phoenix SDK path was found, but no candidate market produced a quote.",
      {
        candidates_checked: request.marketCandidates.map((candidate, index) =>
          summarizeCandidate(candidate, index),
        ),
        quote_errors: quoteErrors,
      },
    );
  }

  return {
    ...quoteResults[0],
    candidate_source: request.usedDefaultMarketCandidate
      ? "verified_builtin_sol_usdc_market"
      : "explicit_market_candidates",
    checked_market_count: request.marketCandidates.length,
    successful_quote_count: quoteResults.length,
    market_quote_errors: quoteErrors,
    all_market_quotes: quoteResults,
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

  const result = await quotePhoenix(validated.value);
  writeJson(result);
  if (!result.ok) {
    process.exitCode = 1;
  }
}

main().catch((err) => {
  writeJson(
    structuredError("UNHANDLED_ERROR", "Unhandled Phoenix quote helper error.", {
      message: err instanceof Error ? err.message : String(err),
    }),
  );
  process.exitCode = 1;
});
