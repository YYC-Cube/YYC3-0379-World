import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate } from 'k6/metrics';

const errorRate = new Rate('errors');

export const options = {
  stages: [
    { duration: '2m', target: 10 },
    { duration: '5m', target: 50 },
    { duration: '2m', target: 100 },
    { duration: '5m', target: 100 },
    { duration: '2m', target: 0 },
  ],
  thresholds: {
    http_req_duration: ['p(95)<500', 'p(99)<1000'],
    errors: ['rate<0.1'],
  },
};

const BASE_URL = __ENV.BASE_URL || 'https://staging-api.0379.world';
const API_KEY = __ENV.API_KEY || '';

export default function () {
  const headers = {
    'X-API-Key': API_KEY,
    'Content-Type': 'application/json',
  };

  const responses = http.batch([
    ['GET', `${BASE_URL}/health`, null, { tags: { name: 'HealthCheck' } }],
    ['GET', `${BASE_URL}/v1/ping`, null, { tags: { name: 'Ping' } }],
    ['GET', `${BASE_URL}/v1/models`, null, { headers, tags: { name: 'ListModels' } }],
  ]);

  check(responses[0], {
    'health check status is 200': (r) => r.status === 200,
    'health check response time < 200ms': (r) => r.timings.duration < 200,
  });

  check(responses[1], {
    'ping status is 200': (r) => r.status === 200,
  });

  check(responses[2], {
    'list models status is 200': (r) => r.status === 200,
    'list models has data': (r) => r.json().length > 0,
  });

  errorRate.add(responses[2].status !== 200);

  const chatPayload = JSON.stringify({
    model: 'qwen2.5:7b',
    messages: [
      { role: 'user', content: 'Hello, this is a performance test.' }
    ],
    max_tokens: 100,
  });

  const chatResponse = http.post(`${BASE_URL}/v1/chat/completions`, chatPayload, {
    headers,
    tags: { name: 'ChatCompletion' },
  });

  check(chatResponse, {
    'chat completion status is 200': (r) => r.status === 200,
    'chat completion has content': (r) => {
      try {
        const body = r.json();
        return body.choices && body.choices.length > 0;
      } catch (e) {
        return false;
      }
    },
  });

  errorRate.add(chatResponse.status !== 200);

  sleep(1);
}

export function handleSummary(data) {
  return {
    'stdout': textSummary(data, { indent: ' ', enableColors: true }),
    'summary.json': JSON.stringify(data, null, 2),
  };
}

function textSummary(data, options) {
  const indent = options.indent || '';
  const colors = options.enableColors || false;
  
  let summary = `${indent}YYC³ API 性能测试报告\n`;
  summary += `${indent}${'='.repeat(50)}\n\n`;
  
  summary += `${indent}总请求数: ${data.metrics.http_reqs.values.count}\n`;
  summary += `${indent}请求速率: ${data.metrics.http_reqs.values.rate.toFixed(2)} req/s\n\n`;
  
  summary += `${indent}响应时间:\n`;
  summary += `${indent}  平均: ${data.metrics.http_req_duration.values.avg.toFixed(2)}ms\n`;
  summary += `${indent}  P95: ${data.metrics.http_req_duration.values['p(95)'].toFixed(2)}ms\n`;
  summary += `${indent}  P99: ${data.metrics.http_req_duration.values['p(99)'].toFixed(2)}ms\n\n`;
  
  summary += `${indent}错误率: ${(data.metrics.errors.values.rate * 100).toFixed(2)}%\n`;
  
  return summary;
}
