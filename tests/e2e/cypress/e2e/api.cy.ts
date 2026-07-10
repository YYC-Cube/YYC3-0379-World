/// <reference types="cypress" />

describe('YYC³ API E2E 测试', () => {
  
  const API_KEY = Cypress.env('API_KEY') || '';
  
  beforeEach(() => {
    cy.request({
      method: 'GET',
      url: '/health',
    }).then((response) => {
      expect(response.status).to.eq(200);
    });
  });

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

    it('响应时间应该 < 100ms', () => {
      const startTime = Date.now();
      
      cy.request({
        method: 'GET',
        url: '/health',
      }).then((response) => {
        const endTime = Date.now();
        const duration = endTime - startTime;
        
        expect(response.status).to.eq(200);
        expect(duration).to.be.lessThan(100);
      });
    });
  });

  describe('API 认证', () => {
    
    it('有效 API Key 应该可以访问', () => {
      cy.request({
        method: 'GET',
        url: '/v1/ping',
        headers: {
          'X-API-Key': API_KEY,
        },
      }).then((response) => {
        expect(response.status).to.eq(200);
        expect(response.body).to.have.property('message', 'pong');
      });
    });

    it('缺少 API Key 应该返回 401', () => {
      cy.request({
        method: 'GET',
        url: '/v1/ping',
        failOnStatusCode: false,
      }).then((response) => {
        expect(response.status).to.eq(401);
      });
    });

    it('无效 API Key 应该返回 403', () => {
      cy.request({
        method: 'GET',
        url: '/v1/ping',
        headers: {
          'X-API-Key': 'invalid_key',
        },
        failOnStatusCode: false,
      }).then((response) => {
        expect(response.status).to.eq(403);
      });
    });
  });

  describe('模型列表', () => {
    
    it('应该返回模型列表', () => {
      cy.request({
        method: 'GET',
        url: '/v1/models',
        headers: {
          'X-API-Key': API_KEY,
        },
      }).then((response) => {
        expect(response.status).to.eq(200);
        expect(response.body).to.have.property('data');
        expect(response.body.data).to.be.an('array');
      });
    });

    it('每个模型应该包含必需字段', () => {
      cy.request({
        method: 'GET',
        url: '/v1/models',
        headers: {
          'X-API-Key': API_KEY,
        },
      }).then((response) => {
        expect(response.status).to.eq(200);
        
        response.body.data.forEach((model: any) => {
          expect(model).to.have.property('id');
          expect(model).to.have.property('object', 'model');
          expect(model).to.have.property('created');
          expect(model).to.have.property('owned_by');
        });
      });
    });
  });

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
          model: 'gpt-3.5-turbo',
          messages: [
            { role: 'user', content: 'Hello, this is a test message.' }
          ],
          max_tokens: 50,
        },
      }).then((response) => {
        expect(response.status).to.eq(200);
        expect(response.body).to.have.property('choices');
        expect(response.body.choices).to.have.length(1);
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
          model: 'gpt-3.5-turbo',
          messages: [
            { role: 'user', content: 'Hello' }
          ],
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
          model: 'gpt-3.5-turbo',
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
            model: 'gpt-3.5-turbo',
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

  describe('MCP 工具', () => {
    
    it('应该返回工具列表', () => {
      cy.request({
        method: 'GET',
        url: '/mcp/tools',
        headers: {
          'X-API-Key': API_KEY,
        },
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

  describe('错误处理', () => {
    
    it('无效模型应该返回 400', () => {
      cy.request({
        method: 'POST',
        url: '/v1/chat/completions',
        headers: {
          'X-API-Key': API_KEY,
          'Content-Type': 'application/json',
        },
        body: {
          model: 'invalid-model',
          messages: [
            { role: 'user', content: 'Test' }
          ],
        },
        failOnStatusCode: false,
      }).then((response) => {
        expect(response.status).to.eq(400);
      });
    });

    it('缺少必需字段应该返回 400', () => {
      cy.request({
        method: 'POST',
        url: '/v1/chat/completions',
        headers: {
          'X-API-Key': API_KEY,
          'Content-Type': 'application/json',
        },
        body: {
          model: 'gpt-3.5-turbo',
        },
        failOnStatusCode: false,
      }).then((response) => {
        expect(response.status).to.eq(400);
      });
    });
  });
});
