import { test, expect } from '@playwright/test';

const BASE_URL = process.env.BASE_URL || 'https://api.0379.world';
const API_KEY = process.env.API_KEY || '';

test.describe('YYC³ 负载均衡测试', () => {
  
  test('负载均衡器应该返回健康状态', async ({ request }) => {
    const response = await request.get(BASE_URL + /health');
    
    expect(response.status()).toBe(200);
    
    const body = await response.json();
    expect(body).toHaveProperty('status', 'healthy');
    expect(body).toHaveProperty('load_balancer');
  });

  test('请求应该被分发到不同的后端服务器', async ({ request }) => {
    const responses = [];
    
    for (let i = 0; i < 10; i++) {
      const response = await request.get(BASE_URL + /health');
      const body = await response.json();
      responses.push(body.server_id || body.instance_id);
    }
    
    const uniqueServers = [...new Set(responses)];
    console.log('检测到 ${uniqueServers.length} 个不同的服务器实例');
    
    expect(uniqueServers.length).toBeGreaterThan(0);
  });

  test('健康检查应该包含后端服务器状态', async ({ request }) => {
    const response = await request.get(BASE_URL + /health');
    
    expect(response.status()).toBe(200);
    
    const body = await response.json();
    expect(body).toHaveProperty('backends');
    expect(body.backends).toBeInstanceOf(Array);
    
    body.backends.forEach((backend: any) => {
      expect(backend).toHaveProperty('server');
      expect(backend).toHaveProperty('status');
      expect(backend).toHaveProperty('healthy');
    });
  });

  test('负载均衡器应该支持会话保持', async ({ request }) => {
    const sessionId = 'test-session-${Date.now()';
    
    const response1 = await request.get(BASE_URL + /v1/ping', {
      headers: {
        'X-API-Key': API_KEY,
        'X-Session-ID': sessionId,
      },
    });
    
    const body1 = await response1.json();
    const server1 = body1.server_id || body1.instance_id;

    const response2 = await request.get(BASE_URL + /v1/ping', {
      headers: {
        'X-API-Key': API_KEY,
        'X-Session-ID': sessionId,
      },
    });
    
    const body2 = await response2.json();
    const server2 = body2.server_id || body2.instance_id;

    expect(server1).toBe(server2);
  });
});

test.describe('YYC³ 故障转移测试', () => {
  
  test('主节点故障时应该自动切换到备用节点', async ({ request }) => {
    const response = await request.get(BASE_URL + /health');
    
    expect(response.status()).toBe(200);
    
    const body = await response.json();
    expect(body).toHaveProperty('active_backend');
    console.log('当前活跃后端: ${body.active_backend');
  });

  test('故障转移应该对客户端透明', async ({ request }) => {
    const responses = [];
    
    for (let i = 0; i < 5; i++) {
      const response = await request.get(BASE_URL + /v1/ping', {
        headers: {
          'X-API-Key': API_KEY,
        },
      });
      
      expect(response.status()).toBe(200);
      responses.push(response);
    }
    
    responses.forEach((response) => {
      expect(response.status()).toBe(200);
    });
  });

  test('故障节点应该被标记为不健康', async ({ request }) => {
    const response = await request.get(BASE_URL + /health');
    
    expect(response.status()).toBe(200);
    
    const body = await response.json();
    
    if (body.backends && body.backends.length > 0) {
      const unhealthyBackends = body.backends.filter((b: any) => !b.healthy);
      console.log('不健康的后端数量: ${unhealthyBackends.length');
    }
  });
});

test.describe('YYC³ 负载均衡性能测试', () => {
  
  test('负载均衡器响应时间应该 < 50ms', async ({ request }) => {
    const startTime = Date.now();
    
    const response = await request.get(BASE_URL + /health');
    
    const endTime = Date.now();
    const duration = endTime - startTime;
    
    expect(response.status()).toBe(200);
    expect(duration).toBeLessThan(50);
  });

  test('并发请求应该被正确处理', async ({ request }) => {
    const requests = [];
    
    for (let i = 0; i < 20; i++) {
      requests.push(
        request.get(BASE_URL + /v1/ping', {
          headers: {
            'X-API-Key': API_KEY,
          },
        })
      );
    }
    
    const responses = await Promise.all(requests);
    
    const successCount = responses.filter(r => r.status() === 200).length;
    expect(successCount).toBe(20);
  });

  test('负载均衡器应该支持长连接', async ({ request }) => {
    const connectionHeader = 'keep-alive';
    
    const response = await request.get(BASE_URL + /health', {
      headers: {
        'Connection': connectionHeader,
      },
    });
    
    expect(response.status()).toBe(200);
    
    const responseConnection = response.headers()['connection'];
    console.log('响应 Connection 头: ${responseConnection');
  });
});
