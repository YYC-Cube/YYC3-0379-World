import { test, expect } from '@playwright/test';

const BASE_URL = process.env.BASE_URL || 'https://api.0379.world';
const API_KEY = process.env.API_KEY || '';

test.describe('YYC³ API 回归测试', () => {
  
  test('完整聊天流程应该正常工作', async ({ request }) => {
    // 1. 创建聊天会话
    const createResponse = await request.post(BASE_URL + /v1/chat/completions', {
      headers: {
        'X-API-Key': API_KEY,
        'Content-Type': 'application/json',
      },
      data: {
        model: 'gpt-3.5-turbo',
        messages: [
          { role: 'system', content: 'You are a helpful assistant.' },
          { role: 'user', content: 'What is the capital of France?' }
        ],
        max_tokens: 100,
      },
    });
    
    expect(createResponse.status()).toBe(200);
    
    const createBody = await createResponse.json();
    expect(createBody).toHaveProperty('choices');
    expect(createBody.choices[0].message.content).toContain('Paris');

    // 2. 继续对话
    const continueResponse = await request.post(BASE_URL + /v1/chat/completions', {
      headers: {
        'X-API-Key': API_KEY,
        'Content-Type': 'application/json',
      },
      data: {
        model: 'gpt-3.5-turbo',
        messages: [
          { role: 'system', content: 'You are a helpful assistant.' },
          { role: 'user', content: 'What is the capital of France?' },
          { role: 'assistant', content: createBody.choices[0].message.content },
          { role: 'user', content: 'What is its population?' }
        ],
        max_tokens: 100,
      },
    });
    
    expect(continueResponse.status()).toBe(200);
    
    const continueBody = await continueResponse.json();
    expect(continueBody).toHaveProperty('choices');
  });

  test('错误处理应该正确', async ({ request }) => {
    // 1. 测试无效模型
    const invalidModelResponse = await request.post(BASE_URL + /v1/chat/completions', {
      headers: {
        'X-API-Key': API_KEY,
        'Content-Type': 'application/json',
      },
      data: {
        model: 'invalid-model',
        messages: [
          { role: 'user', content: 'Test' }
        ],
      },
    });
    
    expect(invalidModelResponse.status()).toBe(400);

    // 2. 测试缺少必需字段
    const missingFieldsResponse = await request.post(BASE_URL + /v1/chat/completions', {
      headers: {
        'X-API-Key': API_KEY,
        'Content-Type': 'application/json',
      },
      data: {
        model: 'gpt-3.5-turbo',
      },
    });
    
    expect(missingFieldsResponse.status()).toBe(400);

    // 3. 测试无效参数
    const invalidParamsResponse = await request.post(BASE_URL + /v1/chat/completions', {
      headers: {
        'X-API-Key': API_KEY,
        'Content-Type': 'application/json',
      },
      data: {
        model: 'gpt-3.5-turbo',
        messages: [
          { role: 'user', content: 'Test' }
        ],
        max_tokens: -1,
      },
    });
    
    expect(invalidParamsResponse.status()).toBe(400);
  });

  test('速率限制应该正常工作', async ({ request }) => {
    const requests = [];
    
    // 发送 100 个并发请求
    for (let i = 0; i < 100; i++) {
      requests.push(
        request.get(BASE_URL + /v1/ping', {
          headers: {
            'X-API-Key': API_KEY,
          },
        })
      );
    }
    
    const responses = await Promise.all(requests);
    
    // 至少应该有一些请求成功
    const successCount = responses.filter(r => r.status() === 200).length;
    expect(successCount).toBeGreaterThan(50);
    
    // 可能有一些请求被限流
    const rateLimitedCount = responses.filter(r => r.status() === 429).length;
    console.log('成功: ${successCount}, 限流: ${rateLimitedCount');
  });

  test('并发请求应该正常处理', async ({ request }) => {
    const requests = [];
    
    // 发送 10 个并发聊天请求
    for (let i = 0; i < 10; i++) {
      requests.push(
        request.post(BASE_URL + /v1/chat/completions', {
          headers: {
            'X-API-Key': API_KEY,
            'Content-Type': 'application/json',
          },
          data: {
            model: 'gpt-3.5-turbo',
            messages: [
              { role: 'user', content: 'Test message ${i' }
            ],
            max_tokens: 50,
          },
        })
      );
    }
    
    const responses = await Promise.all(requests);
    
    // 所有请求都应该成功
    responses.forEach(response => {
      expect(response.status()).toBe(200);
    });
  });
});

test.describe('YYC³ API 数据验证', () => {
  
  test('响应格式应该符合 OpenAI API 规范', async ({ request }) => {
    const response = await request.post(BASE_URL + /v1/chat/completions', {
      headers: {
        'X-API-Key': API_KEY,
        'Content-Type': 'application/json',
      },
      data: {
        model: 'gpt-3.5-turbo',
        messages: [
          { role: 'user', content: 'Hello' }
        ],
        max_tokens: 50,
      },
    });
    
    expect(response.status()).toBe(200);
    
    const body = await response.json();
    
    // 验证响应结构
    expect(body).toHaveProperty('id');
    expect(body).toHaveProperty('object', 'chat.completion');
    expect(body).toHaveProperty('created');
    expect(body).toHaveProperty('model');
    expect(body).toHaveProperty('choices');
    expect(body).toHaveProperty('usage');
    
    // 验证 choices 结构
    expect(body.choices).toBeInstanceOf(Array);
    expect(body.choices[0]).toHaveProperty('index', 0);
    expect(body.choices[0]).toHaveProperty('message');
    expect(body.choices[0]).toHaveProperty('finish_reason');
    
    // 验证 message 结构
    expect(body.choices[0].message).toHaveProperty('role', 'assistant');
    expect(body.choices[0].message).toHaveProperty('content');
    
    // 验证 usage 结构
    expect(body.usage).toHaveProperty('prompt_tokens');
    expect(body.usage).toHaveProperty('completion_tokens');
    expect(body.usage).toHaveProperty('total_tokens');
  });

  test('模型列表应该包含必需字段', async ({ request }) => {
    const response = await request.get(BASE_URL + /v1/models', {
      headers: {
        'X-API-Key': API_KEY,
      },
    });
    
    expect(response.status()).toBe(200);
    
    const body = await response.json();
    
    // 验证响应结构
    expect(body).toHaveProperty('object', 'list');
    expect(body).toHaveProperty('data');
    
    // 验证每个模型的结构
    body.data.forEach((model: any) => {
      expect(model).toHaveProperty('id');
      expect(model).toHaveProperty('object', 'model');
      expect(model).toHaveProperty('created');
      expect(model).toHaveProperty('owned_by');
    });
  });
});
