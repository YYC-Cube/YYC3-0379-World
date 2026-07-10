/**
 * @file commands.ts
 * @description Cypress 自定义命令
 * @author YanYuCloudCube Team <admin@0379.email>
 * @version 1.0.0
 * @date 2026-04-08
 * @tags [cypress,commands]
 */

Cypress.Commands.add('login', (apiKey: string) => {
  cy.setCookie('api_key', apiKey);
  window.localStorage.setItem('api_key', apiKey);
});

Cypress.Commands.add('logout', () => {
  cy.clearCookie('api_key');
  window.localStorage.removeItem('api_key');
});

Cypress.Commands.add('waitForApi', (timeout: number = 10000) => {
  cy.request({
    method: 'GET',
    url: '/health',
    timeout,
    retryOnStatusCodeFailure: true,
  }).then((response) => {
    expect(response.status).to.eq(200);
  });
});

declare global {
  namespace Cypress {
    interface Chainable {
      login(apiKey: string): Chainable<void>;
      logout(): Chainable<void>;
      waitForApi(timeout?: number): Chainable<void>;
    }
  }
}

export {};
