import { test, expect } from '@playwright/test';

const BASE_URL = process.env.BASE_URL || 'https://api.0379.world';
const API_KEY = process.env.API_KEY || '';

test.describe('YYC³ API 烟雾测试', () => {
  
  test('健康检查端点应该返回 200', async ({ request }) => {
    const response = await request.get(BASE_URL + '/health');
    
    expect(response.status()).toBe(200);
    
    const body = await response.json();
    expect(body).toHaveProperty('status', 'healthy');
  });

  test('API 应该可以访问', async ({ request }) => {
    const response = await request.get(BASE_URL + '/v1/ping', {
      headers: {
        'X-API-Key': API_KEY,
      },
    });
    
    expect(response.status()).toBe(200);
    
    const body = await response.json();
    expect(body).toHaveProperty('message', 'pong');
  });

  test('模型列表应该可以获取', async ({ request }) => {
    const response = await request.get(BASE_URL + '/v1/models', {
      headers: {
        'X-API-Key': API_KEY,
      },
    });
    
    expect(response.status()).toBe(200);
    
    const body = await response.json();
    expect(body).toHaveProperty('data');
    expect(Array.isArray(body.data)).toBeTruthy();
  });

  test('未授权请求应该返回 401', async ({ request }) => {
    const response = await request.get(BASE_URL + '/v1/models');
    
    expect(response.status()).toBe(401);
  });

  test('无效 API Key 应该返回 403', async ({ request }) => {
    const response = await request.get(BASE_URL + '/v1/models', {
      headers: {
        'X-API-Key': 'invalid_key',
      },
    });
    
    expect(response.status()).toBe(403);
  });
});

test.describe('YYC³ API 功能测试', () => {
  
  test('聊天补全应该正常工作', async ({ request }) => {
    const response = await request.post(BASE_URL + '/v1/chat/completions', {
      headers: {
        'X-API-Key': API_KEY,
        'Content-Type': 'application/json',
      },
      data: {
        model: 'gpt-3.5-turbo',
        messages: [
          { role: 'user', content: 'Hello, this is a test message.' }
        ],
        max_tokens: 50,
      },
    });
    
    expect(response.status()).toBe(200);
    
    const body = await response.json();
    expect(body).toHaveProperty('choices');
    expect(body.choices).toHaveLength(1);
    expect(body.choices[0]).toHaveProperty('message');
  });

  test('MCP 工具列表应该可以获取', async ({ request }) => {
    const response = await request.get(BASE_URL + '/mcp/tools', {
      headers: {
        'X-API-Key': API_KEY,
      },
    });
    
    expect(response.status()).toBe(200);
    
    const body = await response.json();
    expect(body).toHaveProperty('tools');
    expect(Array.isArray(body.tools)).toBeTruthy();
  });

  test('MCP 工具执行应该正常工作', async ({ request }) => {
    const response = await request.post(BASE_URL + '/mcp/execute', {
      headers: {
        'X-API-Key': API_KEY,
        'Content-Type': 'application/json',
      },
      data: {
        tool: 'yyc3_code_review',
        params: {
          code: 'print("Hello, World!")',
          language: 'python',
        },
      },
    });
    
    expect(response.status()).toBe(200);
    
    const body = await response.json();
    expect(body).toHaveProperty('result');
  });

  test('Prometheus 指标应该可以获取', async ({ request }) => {
    const response = await request.get(BASE_URL + '/metrics');
    
    expect(response.status()).toBe(200);
    
    const text = await response.text();
    expect(text).toContain('http_requests_total');
  });
});

test.describe('YYC³ API 性能测试', () => {
  
  test('健康检查响应时间应该 < 100ms', async ({ request }) => {
    const startTime = Date.now();
    
    const response = await request.get(BASE_URL + '/health');
    
    const endTime = Date.now();
    const duration = endTime - startTime;
    
    expect(response.status()).toBe(200);
    expect(duration).toBeLessThan(100);
  });

  test('API 响应时间应该 < 500ms', async ({ request }) => {
    const startTime = Date.now();
    
    const response = await request.get(BASE_URL + '/v1/ping', {
      headers: {
        'X-API-Key': API_KEY,
      },
    });
    
    const endTime = Date.now();
    const duration = endTime - startTime;
    
    expect(response.status()).toBe(200);
    expect(duration).toBeLessThan(500);
  });
});
