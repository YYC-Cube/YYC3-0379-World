/// <reference types="cypress" />

/**
 * YYC³ API E2E 测试
 *
 * 断言已对齐生产 API 实际行为：
 * - /v1/ping 免认证（SKIP_AUTH_PATHS），返回 {status:"ok", timestamp}
 * - /v1/models 需认证，返回裸数组（非 OpenAI {data:[...]} 包装）
 * - /v1/chat/completions 需认证，可用模型如 glm-4-flash
 * - /health 免认证，返回含 services/system 的详情
 */

describe('YYC³ API E2E 测试', () => {

  const API_KEY = Cypress.env('API_KEY') || '';

  // ── 健康检查 ──
  describe('健康检查', () => {

    it('应该返回健康状态', () => {
      cy.request({
        method: 'GET',
        url: '/health',
      }).then((response) => {
        expect(response.status).to.eq(200);
        expect(response.body).to.have.property('status', 'healthy');
      });
    });

    it('/healthz 应该返回存活状态', () => {
      cy.request({
        method: 'GET',
        url: '/healthz',
      }).then((response) => {
        expect(response.status).to.eq(200);
        expect(response.body).to.have.property('status', 'alive');
      });
    });

    it('/v1/ping 应该免认证返回 ok', () => {
      cy.request({
        method: 'GET',
        url: '/v1/ping',
      }).then((response) => {
        expect(response.status).to.eq(200);
        expect(response.body).to.have.property('status', 'ok');
      });
    });
  });

  // ── API 认证 ──
  describe('API 认证', () => {

    it('有效 API Key 应该可以访问受保护端点', () => {
      cy.request({
        method: 'GET',
        url: '/v1/models',
        headers: { 'X-API-Key': API_KEY },
      }).then((response) => {
        expect(response.status).to.eq(200);
      });
    });

    it('缺少 API Key 应该返回 401', () => {
      // /v1/models 不在 SKIP_AUTH_PATHS，无 key 应 401
      cy.request({
        method: 'GET',
        url: '/v1/models',
        failOnStatusCode: false,
      }).then((response) => {
        expect(response.status).to.eq(401);
      });
    });

    it('无效 API Key 应该返回 403', () => {
      cy.request({
        method: 'GET',
        url: '/v1/models',
        headers: { 'X-API-Key': 'invalid_key' },
        failOnStatusCode: false,
      }).then((response) => {
        expect(response.status).to.eq(403);
      });
    });
  });

  // ── 模型列表 ──
  describe('模型列表', () => {

    it('应该返回模型数组', () => {
      cy.request({
        method: 'GET',
        url: '/v1/models',
        headers: { 'X-API-Key': API_KEY },
      }).then((response) => {
        expect(response.status).to.eq(200);
        expect(response.body).to.be.an('array');
        expect(response.body.length).to.be.greaterThan(0);
      });
    });

    it('每个模型应该包含核心字段', () => {
      cy.request({
        method: 'GET',
        url: '/v1/models',
        headers: { 'X-API-Key': API_KEY },
      }).then((response) => {
        expect(response.status).to.eq(200);

        response.body.forEach((model: any) => {
          expect(model).to.have.property('id');
          expect(model).to.have.property('display_name');
          expect(model).to.have.property('backend');
          expect(model).to.have.property('enabled');
        });
      });
    });
  });

  // ── 聊天补全 ──
  describe('聊天补全', () => {

    it('应该成功创建聊天补全', () => {
      cy.request({
        method: 'POST',
        url: '/v1/chat/completions',
        headers: {
          'X-API-Key': API_KEY,
          'Content-Type': 'application/json',
        },
        body: {
          model: 'glm-4-flash',
          messages: [{ role: 'user', content: 'Hello, this is a test message.' }],
          max_tokens: 50,
        },
      }).then((response) => {
        expect(response.status).to.eq(200);
        expect(response.body).to.have.property('choices');
        expect(response.body.choices).to.have.length.at.least(1);
        expect(response.body.choices[0]).to.have.property('message');
      });
    });

    it('响应应该符合 OpenAI API 规范', () => {
      cy.request({
        method: 'POST',
        url: '/v1/chat/completions',
        headers: {
          'X-API-Key': API_KEY,
          'Content-Type': 'application/json',
        },
        body: {
          model: 'glm-4-flash',
          messages: [{ role: 'user', content: 'Hello' }],
          max_tokens: 50,
        },
      }).then((response) => {
        expect(response.status).to.eq(200);

        const body = response.body;

        expect(body).to.have.property('id');
        expect(body).to.have.property('object', 'chat.completion');
        expect(body).to.have.property('created');
        expect(body).to.have.property('model');
        expect(body).to.have.property('choices');
        expect(body).to.have.property('usage');

        expect(body.choices[0].message).to.have.property('role', 'assistant');
        expect(body.choices[0].message).to.have.property('content');

        expect(body.usage).to.have.property('prompt_tokens');
        expect(body.usage).to.have.property('completion_tokens');
        expect(body.usage).to.have.property('total_tokens');
      });
    });

    it('应该支持多轮对话', () => {
      cy.request({
        method: 'POST',
        url: '/v1/chat/completions',
        headers: {
          'X-API-Key': API_KEY,
          'Content-Type': 'application/json',
        },
        body: {
          model: 'glm-4-flash',
          messages: [
            { role: 'system', content: 'You are a helpful assistant.' },
            { role: 'user', content: 'What is the capital of France?' },
          ],
          max_tokens: 100,
        },
      }).then((response) => {
        expect(response.status).to.eq(200);

        const assistantMessage = response.body.choices[0].message.content;

        cy.request({
          method: 'POST',
          url: '/v1/chat/completions',
          headers: {
            'X-API-Key': API_KEY,
            'Content-Type': 'application/json',
          },
          body: {
            model: 'glm-4-flash',
            messages: [
              { role: 'system', content: 'You are a helpful assistant.' },
              { role: 'user', content: 'What is the capital of France?' },
              { role: 'assistant', content: assistantMessage },
              { role: 'user', content: 'What is its population?' },
            ],
            max_tokens: 100,
          },
        }).then((response2) => {
          expect(response2.status).to.eq(200);
        });
      });
    });
  });

  // ── MCP 工具 ──
  describe('MCP 工具', () => {

    it('应该返回工具列表', () => {
      cy.request({
        method: 'GET',
        url: '/mcp/tools',
        headers: { 'X-API-Key': API_KEY },
      }).then((response) => {
        expect(response.status).to.eq(200);
        expect(response.body).to.have.property('tools');
        expect(response.body.tools).to.be.an('array');
      });
    });

    it('应该成功执行工具', () => {
      cy.request({
        method: 'POST',
        url: '/mcp/execute',
        headers: {
          'X-API-Key': API_KEY,
          'Content-Type': 'application/json',
        },
        body: {
          tool: 'yyc3_code_review',
          params: {
            code: 'print("Hello, World!")',
            language: 'python',
          },
        },
      }).then((response) => {
        expect(response.status).to.eq(200);
        expect(response.body).to.have.property('result');
      });
    });
  });

  // ── 错误处理 ──
  describe('错误处理', () => {

    it('无效模型应该返回错误', () => {
      cy.request({
        method: 'POST',
        url: '/v1/chat/completions',
        headers: {
          'X-API-Key': API_KEY,
          'Content-Type': 'application/json',
        },
        body: {
          model: 'invalid-model-xyz',
          messages: [{ role: 'user', content: 'Test' }],
        },
        failOnStatusCode: false,
      }).then((response) => {
        // 模型不存在，期望 4xx 错误
        expect(response.status).to.be.at.least(400).and.be.lessThan(500);
      });
    });

    it('缺少必需字段应该返回 422', () => {
      cy.request({
        method: 'POST',
        url: '/v1/chat/completions',
        headers: {
          'X-API-Key': API_KEY,
          'Content-Type': 'application/json',
        },
        body: {
          model: 'glm-4-flash',
          // 缺少 messages
        },
        failOnStatusCode: false,
      }).then((response) => {
        // FastAPI Pydantic 校验失败返回 422
        expect(response.status).to.eq(422);
      });
    });
  });
});
