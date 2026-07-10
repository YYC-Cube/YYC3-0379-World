import http from 'k6/http';
import { check, sleep, group } from 'k6';
import { Rate, Trend, Counter } from 'k6/metrics';

// 自定义指标
const errorRate = new Rate('errors');
const responseTime = new Trend('response_time');
const requestCount = new Counter('requests');

// 测试配置
export const options = {
  // 场景配置
  scenarios: {
    // 场景 1: 烟雾测试
    smoke_test: {
      executor: 'constant-vus',
      vus: 10,
      duration: '5m',
      tags: { test_type: 'smoke' },
    },
    
    // 场景 2: 负载测试
    load_test: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '2m', target: 50 },
        { duration: '5m', target: 100 },
        { duration: '5m', target: 100 },
        { duration: '2m', target: 0 },
      ],
      tags: { test_type: 'load' },
    },
    
    // 场景 3: 压力测试
    stress_test: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '2m', target: 100 },
        { duration: '5m', target: 200 },
        { duration: '5m', target: 300 },
        { duration: '2m', target: 0 },
      ],
      tags: { test_type: 'stress' },
    },
    
    // 场景 4: 峰值测试
    spike_test: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '10s', target: 100 },
        { duration: '1m', target: 100 },
        { duration: '10s', target: 0 },
      ],
      tags: { test_type: 'spike' },
    },
    
    // 场景 5: 浸泡测试
    soak_test: {
      executor: 'constant-vus',
      vus: 50,
      duration: '1h',
      tags: { test_type: 'soak' },
    },
  },
  
  // 阈值配置
  thresholds: {
    http_req_duration: ['p(95)<500', 'p(99)<1000'],
    errors: ['rate<0.1'],
    http_req_failed: ['rate<0.05'],
  },
};

// 环境配置
const BASE_URL = __ENV.BASE_URL || 'https://api.0379.world';
const API_KEY = __ENV.API_KEY || '';

// 默认导出函数
export default function () {
  // 请求头
  const headers = {
    'X-API-Key': API_KEY,
    'Content-Type': 'application/json',
  };

  group('健康检查', () => {
    const response = http.get(`${BASE_URL}/health`, {
      headers,
      tags: { name: 'HealthCheck' },
    });
    
    check(response, {
      '健康检查状态码为 200': (r) => r.status === 200,
      '健康检查响应时间 < 100ms': (r) => r.timings.duration < 100,
    });
    
    errorRate.add(response.status !== 200);
    responseTime.add(response.timings.duration);
    requestCount.add(1);
  });

  sleep(1);

  group('API 端点测试', () => {
    // 测试 Ping 端点
    const pingResponse = http.get(`${BASE_URL}/v1/ping`, {
      headers,
      tags: { name: 'Ping' },
    });
    
    check(pingResponse, {
      'Ping 状态码为 200': (r) => r.status === 200,
      'Ping 响应时间 < 200ms': (r) => r.timings.duration < 200,
    });
    
    errorRate.add(pingResponse.status !== 200);
    responseTime.add(pingResponse.timings.duration);
    requestCount.add(1);

    sleep(0.5);

    // 测试模型列表
    const modelsResponse = http.get(`${BASE_URL}/v1/models`, {
      headers,
      tags: { name: 'ListModels' },
    });
    
    check(modelsResponse, {
      '模型列表状态码为 200': (r) => r.status === 200,
      '模型列表响应时间 < 500ms': (r) => r.timings.duration < 500,
      '模型列表包含数据': (r) => r.json('data') !== undefined,
    });
    
    errorRate.add(modelsResponse.status !== 200);
    responseTime.add(modelsResponse.timings.duration);
    requestCount.add(1);

    sleep(0.5);

    // 测试聊天补全
    const chatPayload = JSON.stringify({
      model: 'gpt-3.5-turbo',
      messages: [
        { role: 'user', content: 'Hello, this is a test message.' }
      ],
      max_tokens: 50,
    });
    
    const chatResponse = http.post(`${BASE_URL}/v1/chat/completions`, chatPayload, {
      headers,
      tags: { name: 'ChatCompletion' },
    });
    
    check(chatResponse, {
      '聊天补全状态码为 200': (r) => r.status === 200,
      '聊天补全响应时间 < 3000ms': (r) => r.timings.duration < 3000,
      '聊天补全包含选择': (r) => r.json('choices') !== undefined,
    });
    
    errorRate.add(chatResponse.status !== 200);
    responseTime.add(chatResponse.timings.duration);
    requestCount.add(1);
  });

  sleep(1);

  group('MCP 端点测试', () => {
    // 测试 MCP 工具列表
    const toolsResponse = http.get(`${BASE_URL}/mcp/tools`, {
      headers,
      tags: { name: 'MCPTools' },
    });
    
    check(toolsResponse, {
      'MCP 工具列表状态码为 200': (r) => r.status === 200,
      'MCP 工具列表响应时间 < 500ms': (r) => r.timings.duration < 500,
    });
    
    errorRate.add(toolsResponse.status !== 200);
    responseTime.add(toolsResponse.timings.duration);
    requestCount.add(1);

    sleep(0.5);

    // 测试 MCP 工具调用
    const toolPayload = JSON.stringify({
      tool: 'yyc3_code_review',
      params: {
        code: 'print("Hello, World!")',
        language: 'python',
      },
    });
    
    const toolResponse = http.post(`${BASE_URL}/mcp/execute`, toolPayload, {
      headers,
      tags: { name: 'MCPExecute' },
    });
    
    check(toolResponse, {
      'MCP 执行状态码为 200': (r) => r.status === 200,
      'MCP 执行响应时间 < 5000ms': (r) => r.timings.duration < 5000,
    });
    
    errorRate.add(toolResponse.status !== 200);
    responseTime.add(toolResponse.timings.duration);
    requestCount.add(1);
  });

  sleep(2);
}

// 测试结束后的处理
export function handleSummary(data) {
  return {
    'stdout': textSummary(data, { indent: ' ', enableColors: true }),
    'tests/performance/results/summary.json': JSON.stringify(data, null, 2),
    'tests/performance/results/report.html': htmlReport(data),
  };
}

// 文本摘要
function textSummary(data, options) {
  const indent = options.indent || ' ';
  const enableColors = options.enableColors || false;
  
  let summary = '\n' + indent + '='.repeat(60) + '\n';
  summary += indent + '性能测试报告\n';
  summary += indent + '='.repeat(60) + '\n\n';
  
  summary += indent + '测试概览:\n';
  summary += indent + `  总请求数: ${data.state.metrics.http_reqs.values.count}\n`;
  summary += indent + `  失败请求: ${data.state.metrics.http_req_failed.values.passes}\n`;
  summary += indent + `  错误率: ${(data.state.metrics.http_req_failed.values.rate * 100).toFixed(2)}%\n\n`;
  
  summary += indent + '响应时间:\n';
  summary += indent + `  平均: ${data.state.metrics.http_req_duration.values.avg.toFixed(2)}ms\n`;
  summary += indent + `  P95: ${data.state.metrics.http_req_duration.values['p(95)'].toFixed(2)}ms\n`;
  summary += indent + `  P99: ${data.state.metrics.http_req_duration.values['p(99)'].toFixed(2)}ms\n`;
  summary += indent + `  最大: ${data.state.metrics.http_req_duration.values.max.toFixed(2)}ms\n\n`;
  
  summary += indent + '吞吐量:\n';
  summary += indent + `  请求/秒: ${data.state.metrics.http_reqs.values.rate.toFixed(2)}\n`;
  summary += indent + `  数据接收: ${(data.state.metrics.data_received.values.rate / 1024).toFixed(2)} KB/s\n`;
  summary += indent + `  数据发送: ${(data.state.metrics.data_sent.values.rate / 1024).toFixed(2)} KB/s\n\n`;
  
  return summary;
}

// HTML 报告
function htmlReport(data) {
  return `
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>YYC³ 性能测试报告</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background: #f5f5f5;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h1 {
            color: #333;
            border-bottom: 3px solid #4CAF50;
            padding-bottom: 10px;
        }
        .metrics {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin: 30px 0;
        }
        .metric-card {
            background: #f9f9f9;
            padding: 20px;
            border-radius: 8px;
            border-left: 4px solid #4CAF50;
        }
        .metric-card h3 {
            margin: 0 0 10px 0;
            color: #666;
        }
        .metric-card .value {
            font-size: 2em;
            font-weight: bold;
            color: #333;
        }
        .status-good {
            color: #4CAF50;
        }
        .status-warning {
            color: #FF9800;
        }
        .status-bad {
            color: #F44336;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🚀 YYC³ 性能测试报告</h1>
        
        <div class="metrics">
            <div class="metric-card">
                <h3>总请求数</h3>
                <div class="value">${data.state.metrics.http_reqs.values.count}</div>
            </div>
            <div class="metric-card">
                <h3>错误率</h3>
                <div class="value ${(data.state.metrics.http_req_failed.values.rate * 100) < 5 ? 'status-good' : 'status-bad'}">
                    ${(data.state.metrics.http_req_failed.values.rate * 100).toFixed(2)}%
                </div>
            </div>
            <div class="metric-card">
                <h3>平均响应时间</h3>
                <div class="value">${data.state.metrics.http_req_duration.values.avg.toFixed(2)}ms</div>
            </div>
            <div class="metric-card">
                <h3>P95 响应时间</h3>
                <div class="value ${data.state.metrics.http_req_duration.values['p(95)'] < 500 ? 'status-good' : 'status-warning'}">
                    ${data.state.metrics.http_req_duration.values['p(95)'].toFixed(2)}ms
                </div>
            </div>
            <div class="metric-card">
                <h3>P99 响应时间</h3>
                <div class="value ${data.state.metrics.http_req_duration.values['p(99)'] < 1000 ? 'status-good' : 'status-warning'}">
                    ${data.state.metrics.http_req_duration.values['p(99)'].toFixed(2)}ms
                </div>
            </div>
            <div class="metric-card">
                <h3>吞吐量</h3>
                <div class="value">${data.state.metrics.http_reqs.values.rate.toFixed(2)} req/s</div>
            </div>
        </div>
        
        <p><small>测试时间: ${new Date().toLocaleString('zh-CN')}</small></p>
    </div>
</body>
</html>
  `;
}
