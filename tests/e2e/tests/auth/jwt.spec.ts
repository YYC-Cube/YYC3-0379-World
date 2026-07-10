import { test, expect } from '@playwright/test';

const BASE_URL = process.env.BASE_URL || 'https://api.0379.world';
const API_KEY = process.env.API_KEY || '';

test.describe('YYC³ JWT 认证测试', () => {
  
  test('JWT Token 应该可以获取', async ({ request }) => {
    const response = await request.post(BASE_URL + /v1/auth/token', {
      headers: {
        'Content-Type': 'application/json',
      },
      data: {
        api_key: API_KEY,
      },
    });
    
    expect(response.status()).toBe(200);
    
    const body = await response.json();
    expect(body).toHaveProperty('access_token');
    expect(body).toHaveProperty('token_type', 'Bearer');
    expect(body).toHaveProperty('expires_in');
  });

  test('JWT Token 应该可以访问受保护的端点', async ({ request }) => {
    const tokenResponse = await request.post(BASE_URL + /v1/auth/token', {
      headers: {
        'Content-Type': 'application/json',
      },
      data: {
        api_key: API_KEY,
      },
    });
    
    expect(tokenResponse.status()).toBe(200);
    
    const tokenBody = await tokenResponse.json();
    const token = tokenBody.access_token;

    const apiResponse = await request.get(BASE_URL + /v1/models', {
      headers: {
        'Authorization': 'Bearer ${token',
      },
    });
    
    expect(apiResponse.status()).toBe(200);
  });

  test('无效 JWT Token 应该返回 401', async ({ request }) => {
    const response = await request.get(BASE_URL + /v1/models', {
      headers: {
        'Authorization': 'Bearer invalid_token',
      },
    });
    
    expect(response.status()).toBe(401);
  });

  test('过期的 JWT Token 应该返回 401', async ({ request }) => {
    const expiredToken = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyLCJleHAiOjE1MTYyMzkwMjJ9.4Adcj3UFYzP5aU0qVW9z5Z6Z7Z8Z9Z0Z1Z2Z3Z4Z5Z6';
    
    const response = await request.get(BASE_URL + /v1/models', {
      headers: {
        'Authorization': 'Bearer ${expiredToken',
      },
    });
    
    expect(response.status()).toBe(401);
  });
});

test.describe('YYC³ API Key 认证测试', () => {
  
  test('有效 API Key 应该可以访问', async ({ request }) => {
    const response = await request.get(BASE_URL + /v1/models', {
      headers: {
        'X-API-Key': API_KEY,
      },
    });
    
    expect(response.status()).toBe(200);
  });

  test('缺少 API Key 应该返回 401', async ({ request }) => {
    const response = await request.get(BASE_URL + /v1/models');
    
    expect(response.status()).toBe(401);
  });

  test('无效 API Key 应该返回 403', async ({ request }) => {
    const response = await request.get(BASE_URL + /v1/models', {
      headers: {
        'X-API-Key': 'invalid_key_12345',
      },
    });
    
    expect(response.status()).toBe(403);
  });

  test('API Key 格式错误应该返回 400', async ({ request }) => {
    const response = await request.get(BASE_URL + /v1/models', {
      headers: {
        'X-API-Key': '',
      },
    });
    
    expect(response.status()).toBe(400);
  });
});

test.describe('YYC³ 双重认证测试', () => {
  
  test('同时使用 JWT 和 API Key 应该优先使用 JWT', async ({ request }) => {
    const tokenResponse = await request.post(BASE_URL + /v1/auth/token', {
      headers: {
        'Content-Type': 'application/json',
      },
      data: {
        api_key: API_KEY,
      },
    });
    
    const tokenBody = await tokenResponse.json();
    const token = tokenBody.access_token;

    const response = await request.get(BASE_URL + /v1/models', {
      headers: {
        'Authorization': 'Bearer ${token',
        'X-API-Key': 'invalid_key',
      },
    });
    
    expect(response.status()).toBe(200);
  });

  test('JWT Token 过期后应该可以使用 API Key', async ({ request }) => {
    const expiredToken = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.expired';
    
    const response = await request.get(BASE_URL + /v1/models', {
      headers: {
        'Authorization': 'Bearer ${expiredToken',
        'X-API-Key': API_KEY,
      },
    });
    
    expect(response.status()).toBe(200);
  });
});
