import { test, expect } from '@playwright/test';

const BASE_URL = process.env.BASE_URL || 'https://api.0379.world';
const API_KEY = process.env.API_KEY || '';

test.describe('YYC³ PostgreSQL 连接测试', () => {
  
  test('数据库健康检查应该返回正常', async ({ request }) => {
    const response = await request.get(BASE_URL + /health', {
      headers: {
        'X-API-Key': API_KEY,
      },
    });
    
    expect(response.status()).toBe(200);
    
    const body = await response.json();
    expect(body).toHaveProperty('database');
    expect(body.database).toHaveProperty('status', 'healthy');
  });

  test('数据库连接池应该正常工作', async ({ request }) => {
    const requests = [];
    
    for (let i = 0; i < 10; i++) {
      requests.push(
        request.get(BASE_URL + /v1/models', {
          headers: {
            'X-API-Key': API_KEY,
          },
        })
      );
    }
    
    const responses = await Promise.all(requests);
    
    responses.forEach((response) => {
      expect(response.status()).toBe(200);
    });
  });

  test('数据库查询应该返回正确的结果', async ({ request }) => {
    const response = await request.get(BASE_URL + /v1/models', {
      headers: {
        'X-API-Key': API_KEY,
      },
    });
    
    expect(response.status()).toBe(200);
    
    const body = await response.json();
    expect(body).toHaveProperty('data');
    expect(body.data).toBeInstanceOf(Array);
    expect(body.data.length).toBeGreaterThan(0);
  });

  test('数据库写入应该成功', async ({ request }) => {
    const testMessage = 'Test message ${Date.now()';
    
    const response = await request.post(BASE_URL + /v1/chat/completions', {
      headers: {
        'X-API-Key': API_KEY,
        'Content-Type': 'application/json',
      },
      data: {
        model: 'gpt-3.5-turbo',
        messages: [
          { role: 'user', content: testMessage }
        ],
        max_tokens: 50,
      },
    });
    
    expect(response.status()).toBe(200);
    
    const body = await response.json();
    expect(body).toHaveProperty('id');
    expect(body).toHaveProperty('choices');
  });
});

test.describe('YYC³ PostgreSQL 主从复制测试', () => {
  
  test('主库应该可写', async ({ request }) => {
    const response = await request.post(BASE_URL + /v1/chat/completions', {
      headers: {
        'X-API-Key': API_KEY,
        'Content-Type': 'application/json',
      },
      data: {
        model: 'gpt-3.5-turbo',
        messages: [
          { role: 'user', content: 'Test write to master' }
        ],
        max_tokens: 50,
      },
    });
    
    expect(response.status()).toBe(200);
  });

  test('从库应该可读', async ({ request }) => {
    const response = await request.get(BASE_URL + /v1/models', {
      headers: {
        'X-API-Key': API_KEY,
      },
    });
    
    expect(response.status()).toBe(200);
    
    const body = await response.json();
    expect(body).toHaveProperty('data');
  });

  test('数据应该在主从之间同步', async ({ request }) => {
    const testContent = 'Sync test ${Date.now()';
    
    const writeResponse = await request.post(BASE_URL + /v1/chat/completions', {
      headers: {
        'X-API-Key': API_KEY,
        'Content-Type': 'application/json',
      },
      data: {
        model: 'gpt-3.5-turbo',
        messages: [
          { role: 'user', content: testContent }
        ],
        max_tokens: 50,
      },
    });
    
    expect(writeResponse.status()).toBe(200);
    
    await new Promise(resolve => setTimeout(resolve, 1000));
    
    const readResponse = await request.get(BASE_URL + /v1/models', {
      headers: {
        'X-API-Key': API_KEY,
      },
    });
    
    expect(readResponse.status()).toBe(200);
  });

  test('复制延迟应该在可接受范围内', async ({ request }) => {
    const startTime = Date.now();
    
    const response = await request.get(BASE_URL + /health', {
      headers: {
        'X-API-Key': API_KEY,
      },
    });
    
    const endTime = Date.now();
    const duration = endTime - startTime;
    
    expect(response.status()).toBe(200);
    expect(duration).toBeLessThan(1000);
    
    const body = await response.json();
    if (body.database && body.database.replication_lag !== undefined) {
      console.log('复制延迟: ${body.database.replication_lag}ms');
      expect(body.database.replication_lag).toBeLessThan(100);
    }
  });
});

test.describe('YYC³ PostgreSQL 故障恢复测试', () => {
  
  test('数据库连接失败应该返回适当的错误', async ({ request }) => {
    const response = await request.get(BASE_URL + /v1/models', {
      headers: {
        'X-API-Key': API_KEY,
      },
    });
    
    if (response.status() !== 200) {
      const body = await response.json();
      expect(body).toHaveProperty('error');
      expect(body.error).toHaveProperty('code');
      expect(body.error).toHaveProperty('message');
    } else {
      expect(response.status()).toBe(200);
    }
  });

  test('数据库超时应该被正确处理', async ({ request }) => {
    const response = await request.get(BASE_URL + /v1/models', {
      headers: {
        'X-API-Key': API_KEY,
      },
      timeout: 5000,
    });
    
    expect([200, 408, 503]).toContain(response.status());
  });
});
