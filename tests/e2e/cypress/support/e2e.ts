/**
 * @file e2e.ts
 * @description Cypress E2E 测试支持文件
 * @author YanYuCloudCube Team <admin@0379.email>
 * @version 1.0.0
 * @date 2026-04-08
 * @tags [cypress,support,e2e]
 */

import './commands';

before(() => {
  cy.log('YYC³ E2E 测试开始');
});

after(() => {
  cy.log('YYC³ E2E 测试结束');
});

Cypress.on('uncaught:exception', (err, runnable) => {
  console.error('Uncaught exception:', err);
  return false;
});
