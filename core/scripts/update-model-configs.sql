-- YYC³ 模型配置更新脚本
-- 更新时间: 2026-04-06
-- 说明: 更新付费模型为 GLM 系列，添加本地 Ollama 模型

BEGIN;

-- 1. 更新智谱 AI 配置 - 添加 GLM-4.7、GLM-5、GLM-5-Turbo
UPDATE api_configs
SET
    model = 'glm-4.7,glm-5,glm-5-turbo,glm-4,codegeex',
    config = jsonb_set(
        config,
        '{models}',
        '["glm-4.7", "glm-5", "glm-5-turbo", "glm-4", "codegeex"]'::jsonb
    ),
    updated_at = CURRENT_TIMESTAMP
WHERE id = '0dc60728-06ad-4ced-a3d2-4cd54e8f5f1b';

-- 2. 添加本地 Ollama 模型配置
INSERT INTO api_configs (
    id,
    name,
    provider,
    api_type,
    endpoint,
    model,
    config,
    enabled,
    category
) VALUES (
    uuid_generate_v4(),
    '本地 Ollama',
    'ollama',
    'chat',
    'http://localhost:11434/v1',
    'codegeex4,llama3.2',
    jsonb_build_object(
        'models', jsonb_build_array('codegeex4', 'llama3.2'),
        'base_url', 'http://localhost:11434',
        'is_local', true
    ),
    true,
    '本地模型'
) ON CONFLICT (name) DO UPDATE SET
    model = EXCLUDED.model,
    config = EXCLUDED.config,
    updated_at = CURRENT_TIMESTAMP;

-- 3. 禁用其他付费模型（保留配置但不启用）
UPDATE api_configs
SET enabled = false, updated_at = CURRENT_TIMESTAMP
WHERE api_type = 'chat'
  AND provider NOT IN ('zhipu', 'ollama');

-- 4. 查看更新后的配置
SELECT
    name as "模型名称",
    provider as "提供商",
    api_type as "类型",
    enabled as "启用",
    model as "模型列表"
FROM api_configs
WHERE api_type = 'chat'
ORDER BY enabled DESC, name;

COMMIT;

-- 输出说明
\echo ''
\echo '========================================'
\echo '模型配置更新完成！'
\echo '========================================'
\echo ''
\echo '已启用的模型:'
\echo '  - 智谱 AI: glm-4.7, glm-5, glm-5-turbo, glm-4, codegeex'
\echo '  - 本地 Ollama: codegeex4, llama3.2'
\echo ''
\echo '已禁用的模型:'
\echo '  - OpenAI (gpt-4, gpt-3.5-turbo)'
\echo '  - Anthropic Claude (claude-3, claude-2)'
\echo '  - Google Gemini (gemini-pro, gemini-ultra)'
\echo '  - DeepSeek (deepseek-coder, deepseek-v2)'
\echo '  - QWEN AI (qwen-max, qwen-plus)'
\echo ''
\echo '提示: 如需启用其他模型，请更新 api_configs 表的 enabled 字段'
\echo '========================================'
