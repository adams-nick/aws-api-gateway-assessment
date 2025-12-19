/**
 * Unit tests for Stock Return Calculator Lambda
 * Minimal essential tests covering critical paths
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { handler } from './index.mjs';

// Mock AWS SDK
vi.mock('@aws-sdk/client-secrets-manager', () => ({
  SecretsManagerClient: vi.fn(() => ({
    send: vi.fn().mockResolvedValue({
      SecretString: JSON.stringify({ apiKey: 'TEST_API_KEY' })
    })
  })),
  GetSecretValueCommand: vi.fn()
}));

describe('Stock Calculator Lambda', () => {
  const mockContext = { awsRequestId: 'test-123' };

  beforeEach(() => {
    vi.spyOn(console, 'log').mockImplementation(() => {});
  });

  it('should return 400 for missing parameters', async () => {
    const event = { queryStringParameters: {} };
    const result = await handler(event, mockContext);

    expect(result.statusCode).toBe(400);
    expect(JSON.parse(result.body).error).toContain('Missing required parameters');
  });

  it('should return 400 for invalid symbol format', async () => {
    const event = {
      queryStringParameters: { symbol: 'INVALID123', initialPrice: '100' }
    };
    const result = await handler(event, mockContext);

    expect(result.statusCode).toBe(400);
    expect(JSON.parse(result.body).error).toContain('Invalid symbol format');
  });

  it('should return 400 for invalid price', async () => {
    const event = {
      queryStringParameters: { symbol: 'AAPL', initialPrice: '-50' }
    };
    const result = await handler(event, mockContext);

    expect(result.statusCode).toBe(400);
    expect(JSON.parse(result.body).error).toContain('must be a positive number');
  });

  it('should return 200 with correct calculation for valid request', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        'Global Quote': { '05. price': '200.00' }
      })
    });

    const event = {
      queryStringParameters: { symbol: 'AAPL', initialPrice: '150.00' }
    };
    const result = await handler(event, mockContext);

    expect(result.statusCode).toBe(200);
    const body = JSON.parse(result.body);
    expect(body.success).toBe(true);
    expect(body.data.percentageReturn).toBe(33.33);
    expect(body.data.isProfit).toBe(true);
  });

  it('should return 404 for invalid symbol from API', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ 'Error Message': 'Invalid API call' })
    });

    const event = {
      queryStringParameters: { symbol: 'BAD', initialPrice: '150.00' }
    };
    const result = await handler(event, mockContext);

    expect(result.statusCode).toBe(404);
    expect(JSON.parse(result.body).error).toContain('Invalid symbol');
  });

  it('should return 429 for rate limit without retry', async () => {
    const fetchSpy = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ 'Note': 'API call frequency exceeded' })
    });
    global.fetch = fetchSpy;

    const event = {
      queryStringParameters: { symbol: 'AAPL', initialPrice: '150.00' }
    };
    const result = await handler(event, mockContext);

    expect(result.statusCode).toBe(429);
    expect(fetchSpy).toHaveBeenCalledTimes(1); // No retry
  });
});
