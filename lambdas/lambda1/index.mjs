/**
 * Stock Return Calculator - Alpha Vantage API
 * GET /api/v1/stocks?symbol=AAPL&initialPrice=150.00
 */

import {
  SecretsManagerClient,
  GetSecretValueCommand,
} from "@aws-sdk/client-secrets-manager";

const API_URL = "https://www.alphavantage.co/query";
const MAX_RETRIES = 3;
const SYMBOL_PATTERN = /^[A-Z]{1,5}$/;

let cachedApiKey = null;

/**
 * Structured logger for CloudWatch Logs
 * @param {string} level - Log level (INFO, ERROR, WARN)
 * @param {string} message - Log message
 * @param {Object} metadata - Additional context
 */
const log = (level, message, metadata = {}) => {
  console.log(
    JSON.stringify({
      timestamp: new Date().toISOString(),
      level,
      message,
      function: "NodeFunction",
      ...metadata,
    })
  );
};

/**
 * Retrieves Alpha Vantage API key from AWS Secrets Manager with caching
 * @returns {Promise<string>} API key
 * @throws {Error} If secret retrieval fails
 */
const getApiKey = async () => {
  if (cachedApiKey) {
    return cachedApiKey;
  }

  const client = new SecretsManagerClient();
  const response = await client.send(
    new GetSecretValueCommand({
      SecretId: process.env.SECRET_ARN,
    })
  );

  cachedApiKey = JSON.parse(response.SecretString).apiKey;
  return cachedApiKey;
};

/**
 * Delays execution for specified milliseconds
 * @param {number} ms - Milliseconds to sleep
 * @returns {Promise<void>}
 */
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

/**
 * Constructs API Gateway response object
 * @param {number} statusCode - HTTP status code
 * @param {Object} body - Response body object
 * @returns {{statusCode: number, headers: Object, body: string}}
 */
const response = (statusCode, body) => ({
  statusCode,
  headers: {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
  },
  body: JSON.stringify(body),
});

/**
 * Fetches current stock price from Alpha Vantage API with retry logic
 * @param {string} symbol - Stock symbol (1-5 uppercase letters)
 * @param {string} requestId - Request ID for logging
 * @returns {Promise<number>} Current stock price
 * @throws {Error} With statusCode property (404, 429, 500)
 */
const fetchQuote = async (symbol, requestId) => {
  const API_KEY = await getApiKey();
  const url = `${API_URL}?function=GLOBAL_QUOTE&symbol=${symbol}&apikey=${API_KEY}`;

  for (let attempt = 0; attempt < MAX_RETRIES; attempt++) {
    try {
      const res = await fetch(url);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      const data = await res.json();

      if (data["Error Message"]) {
        const err = new Error(`Invalid symbol: ${symbol}`);
        err.statusCode = 404;
        throw err;
      }

      if (data["Note"]) {
        const err = new Error("Rate limit exceeded");
        err.statusCode = 429;
        throw err;
      }

      const quote = data["Global Quote"];
      if (!quote || !quote["05. price"]) {
        const err = new Error(`No data for symbol: ${symbol}`);
        err.statusCode = 404;
        throw err;
      }

      const price = parseFloat(quote["05. price"]);

      log("INFO", "Alpha Vantage API success", {
        requestId,
        symbol,
        currentPrice: price,
        attempt: attempt + 1,
      });

      return price;
    } catch (error) {
      // Don't retry client errors (404) or rate limits (429)
      if (error.statusCode === 404 || error.statusCode === 429) {
        throw error;
      }

      if (attempt < MAX_RETRIES - 1) {
        await sleep(1000 * Math.pow(2, attempt));
        continue;
      }
      throw error;
    }
  }
};

/**
 * Lambda handler for stock return calculator
 * @param {Object} event - API Gateway event
 * @param {Object} event.queryStringParameters - Query parameters
 * @param {string} event.queryStringParameters.symbol - Stock symbol
 * @param {string} event.queryStringParameters.initialPrice - Initial purchase price
 * @param {Object} context - Lambda context
 * @returns {Promise<Object>} API Gateway response
 */
export const handler = async (event, context) => {
  const requestId = context.awsRequestId;

  log("INFO", "Request received", {
    requestId,
    symbol: event.queryStringParameters?.symbol,
    initialPrice: event.queryStringParameters?.initialPrice,
  });

  try {
    const params = event.queryStringParameters || {};
    const { symbol, initialPrice } = params;

    // Validation
    if (!symbol || !initialPrice) {
      return response(400, {
        success: false,
        error: "Missing required parameters: symbol, initialPrice",
      });
    }

    const upperSymbol = symbol.toUpperCase().trim();
    if (!SYMBOL_PATTERN.test(upperSymbol)) {
      return response(400, {
        success: false,
        error: "Invalid symbol format. Must be 1-5 letters.",
      });
    }

    const price = parseFloat(initialPrice);
    if (isNaN(price) || price <= 0) {
      return response(400, {
        success: false,
        error: "initialPrice must be a positive number",
      });
    }

    // Fetch and calculate
    const currentPrice = await fetchQuote(upperSymbol, requestId);
    const percentageReturn = ((currentPrice - price) / price) * 100;

    log("INFO", "Request completed", {
      requestId,
      symbol: upperSymbol,
      percentageReturn: percentageReturn.toFixed(2),
    });

    return response(200, {
      success: true,
      data: {
        symbol: upperSymbol,
        initialPrice: price,
        currentPrice: currentPrice,
        percentageReturn: parseFloat(percentageReturn.toFixed(2)),
        isProfit: percentageReturn >= 0,
      },
    });
  } catch (error) {
    log("ERROR", "Request failed", {
      requestId,
      error: error.message,
      statusCode: error.statusCode || 500,
      symbol: event.queryStringParameters?.symbol,
    });

    return response(error.statusCode || 500, {
      success: false,
      error: error.message || "Internal server error",
    });
  }
};
