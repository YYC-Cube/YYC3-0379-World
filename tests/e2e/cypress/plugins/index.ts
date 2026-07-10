/**
 * @file index.ts
 * @description Cypress 插件配置
 * @author YanYuCloudCube Team <admin@0379.email>
 * @version 1.0.0
 * @date 2026-04-08
 * @tags [cypress,plugins]
 */

import { defineConfig } from 'cypress';

export default (on: Cypress.PluginEvents, config: Cypress.PluginConfigOptions) => {
  on('task', {
    log(message: string) {
      console.log(message);
      return null;
    },
  });

  return config;
};
