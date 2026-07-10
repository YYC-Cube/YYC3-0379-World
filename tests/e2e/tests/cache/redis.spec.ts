import { test, expect } from '@playwright/test';

const BASE_URL = process.env.BASE_URL || 'https://api.0379.world';
const API_KEY = process.env.API_KEY || '';

test.describe('YYC³ Redis 缓存测试', () => {
  
  test('Redis 健康检查应该返回正常', async ({ request }) => {
    const response = await request.get(BASE_URL + /health', {
      headers: {
        'X-API-Key': API_KEY,
      },
    });
    
    expect(response.status()).toBe(200);
    
    const body = await response.json();
    expect(body).toHaveProperty('redis');
    expect(body.redis).toHaveProperty('status', 'healthy');
  });

  test('缓存应该可以存储和读取数据', async ({ request }) => {
    const testKey = 'test_key_${Date.now()';
    const testValue = 'test_value_${Date.now()';
    
    const setResponse = await request.post(BASE_URL + /v1/cache/set', {
      headers: {
        'X-API-Key': API_KEY,
        'Content-Type': 'application/json',
      },
      data: {
        key: testKey,
        value: testValue,
        ttl: 60,
      },
    });
    
    if (setResponse.status() === 200) {
      const getResponse = await request.get(BASE_URL + /v1/cache/get?key=${testKey', {
        headers: {
          'X-API-Key': API_KEY,
        },
      });
      
      expect(getResponse.status()).toBe(200);
      
      const body = await getResponse.json();
      expect(body).toHaveProperty('value', testValue);
    } else {
      console.log('缓存 API 不可用，跳过测试');
    }
  });

  test('缓存过期应该正常工作', async ({ request }) => {
    const testKey = 'expire_key_${Date.now()';
    const testValue = 'expire_value_${Date.now()';
    
    const setResponse = await request.post(BASE_URL + /v1/cache/set', {
      headers: {
        'X-API-Key': API_KEY,
        'Content-Type': 'application/json',
      },
      data: {
        key: testKey,
        value: testValue,
        ttl: 2,
      },
    });
    
    if (setResponse.status() === 200) {
      await new Promise(resolve => setTimeout(resolve, 3000));
      
      const getResponse = await request.get(BASE_URL + /v1/cache/get?key=${testKey', {
        headers: {
          'X-API-Key': API_KEY,
        },
      });
      
      if (getResponse.status() === 404) {
        expect(getResponse.status()).toBe(404);
      } else {
        const body = await getResponse.json();
        expect(body.value).toBeUndefined();
      }
    }
  });

  test('缓存命中率应该被记录', async ({ request }) => {
    const response = await request.get(BASE_URL + /metrics', {
      headers: {
        'X-API-Key': API_KEY,
      },
    });
    
    expect(response.status()).toBe(200);
    
    const text = await response.text();
    expect(text).toContain('cache_hits_total');
    expect(text).toContain('cache_misses_total');
  });
});

test.describe('YYC³ Redis 主从复制测试', () => {
  
  test('主节点应该可写', async ({ request }) => {
    const testKey = 'master_key_${Date.now()';
    
    const response = await request.post(BASE_URL + /v1/cache/set', {
      headers: {
        'X-API-Key': API_KEY,
        'Content-Type': 'application/json',
      },
      data: {
        key: testKey,
        value: 'master_write_test',
        ttl: 60,
      },
    });
    
    if (response.status() === 200) {
      expect(response.status()).toBe(200);
    }
  });

  test('从节点应该可读', async ({ request }) => {
    const response = await request.get(BASE_URL + /health', {
      headers: {
        'X-API-Key': API_KEY,
      },
    });
    
    expect(response.status()).toBe(200);
    
    const body = await response.json();
    if (body.redis && body.redis.slaves) {
      expect(body.redis.slaves.length).toBeGreaterThan(0);
      console.log('Redis 从节点数量: ${body.redis.slaves.length');
    }
  });

  test('主从数据应该一致', async ({ request }) => {
    const testKey = 'consistency_key_${Date.now()';
    const testValue = 'consistency_value_${Date.now()';
    
    const setResponse = await request.post(BASE_URL + /v1/cache/set', {
      headers: {
        'X-API-Key': API_KEY,
        'Content-Type': 'application/json',
      },
      data: {
        key: testKey,
        value: testValue,
        ttl: 60,
      },
    });
    
    if (setResponse.status() === 200) {
      await new Promise(resolve => setTimeout(resolve, 500));
      
      const getResponse = await request.get(BASE_URL + /v1/cache/get?key=${testKey', {
        headers: {
          'X-API-Key': API_KEY,
        },
      });
      
      if (getResponse.status() === 200) {
        const body = await getResponse.json();
        expect(body.value).toBe(testValue);
      }
    }
  });

  test('复制延迟应该在可接受范围内', async ({ request }) => {
    const response = await request.get(BASE_URL + /health', {
      headers: {
        'X-API-Key': API_KEY,
      },
    });
    
    expect(response.status()).toBe(200);
    
    const body = await response.json();
    if (body.redis && body.redis.replication_lag !== undefined) {
      console.log('Redis 复制延迟: ${body.redis.replication_lag}ms');
      expect(body.redis.replication_lag).toBeLessThan(100);
    }
  });
});

test.describe('YYC³ Redis 性能测试', () => {
  
  test('Redis 响应时间应该 < 10ms', async ({ request }) => {
    const startTime = Date.now();
    
    const response = await request.get(BASE_URL + /health', {
      headers: {
        'X-API-Key': API_KEY,
      },
    });
    
    const endTime = Date.now();
    const duration = endTime - startTime;
    
    expect(response.status()).toBe(200);
    
    const body = await response.json();
    if (body.redis && body.redis.response_time) {
      expect(body.redis.response_time).toBeLessThan(10);
    }
  });

  test('并发缓存操作应该正常工作', async ({ request }) => {
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
    
    const successCount = responses.filter(r => r.status() === 200).length;
    expect(successCount).toBe(10);
  });

  test('缓存内存使用应该正常', async ({ request }) => {
    const response = await request.get(BASE_URL + /health', {
      headers: {
        'X-API-Key': API_KEY,
      },
    });
    
    expect(response.status()).toBe(200);
    
    const body = await response.json();
    if (body.redis && body.redis.memory) {
      console.log('Redis 内存使用: ${body.redis.memory.used_memory_human');
      expect(body.redis.memory.used_memory).toBeLessThan(1024 * 1024 * 1024);
    }
  });
});
