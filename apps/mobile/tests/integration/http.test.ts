import assert from 'node:assert/strict';
import {
  createServer,
  type IncomingMessage,
  type ServerResponse,
} from 'node:http';
import { once } from 'node:events';
import { after, before, test } from 'node:test';
import { ApiError, requestJson } from '../../src/api/http';

// Exercise the real fetch/AbortController boundary over TCP, without credentials or services.
type Handler = (request: IncomingMessage, response: ServerResponse) => void;
let handler: Handler;
let calls = 0;
const server = createServer((request, response) => {
  calls += 1;
  handler(request, response);
});
const originalAccounts = process.env.EXPO_PUBLIC_ACCOUNTS_API_URL;
const originalPosts = process.env.EXPO_PUBLIC_POSTS_API_URL;

before(async () => {
  server.listen(0, '127.0.0.1');
  await once(server, 'listening');
  const address = server.address();
  assert.ok(address && typeof address !== 'string');
  const base = `http://127.0.0.1:${address.port}`;
  process.env.EXPO_PUBLIC_ACCOUNTS_API_URL = `${base}/accounts/`;
  process.env.EXPO_PUBLIC_POSTS_API_URL = `${base}/posts`;
});

after(async () => {
  server.closeAllConnections();
  await new Promise<void>((resolve, reject) =>
    server.close((err) => (err ? reject(err) : resolve()))
  );
  if (originalAccounts === undefined)
    delete process.env.EXPO_PUBLIC_ACCOUNTS_API_URL;
  else process.env.EXPO_PUBLIC_ACCOUNTS_API_URL = originalAccounts;
  if (originalPosts === undefined) delete process.env.EXPO_PUBLIC_POSTS_API_URL;
  else process.env.EXPO_PUBLIC_POSTS_API_URL = originalPosts;
});

test('sends JSON and bearer headers to the selected service exactly once', async () => {
  const beforeCalls = calls;
  let receivedBody = '';
  handler = (request, response) => {
    assert.equal(request.url, '/posts/api/v1/posts');
    assert.equal(request.method, 'POST');
    assert.equal(request.headers.authorization, 'Bearer synthetic-token');
    assert.match(request.headers['content-type'] ?? '', /application\/json/);
    request.on('data', (chunk: Buffer) => {
      receivedBody += chunk.toString();
    });
    request.on('end', () => {
      response.writeHead(201, { 'content-type': 'application/json' });
      response.end(JSON.stringify({ id: 'synthetic-post' }));
    });
  };
  assert.deepEqual(
    await requestJson('posts', 'api/v1/posts', {
      method: 'POST',
      body: { content: 'Hola' },
      token: 'synthetic-token',
    }),
    { id: 'synthetic-post' }
  );
  assert.deepEqual(JSON.parse(receivedBody), { content: 'Hola' });
  assert.equal(calls - beforeCalls, 1);
});

test('accepts real empty 204 logout responses', async () => {
  handler = (request, response) => {
    assert.equal(request.url, '/accounts/api/v1/sessions/logout');
    response.writeHead(204);
    response.end();
  };
  assert.equal(
    await requestJson('accounts', '/api/v1/sessions/logout', {
      method: 'POST',
      token: 'synthetic-token',
    }),
    undefined
  );
});

test('maps Problem Details safely and never retries a rejected POST', async () => {
  const beforeCalls = calls;
  handler = (_request, response) => {
    response.writeHead(401, { 'content-type': 'application/problem+json' });
    response.end(
      JSON.stringify({
        type: 'https://example.test/problems/invalid-credentials',
        detail: 'private server detail',
      })
    );
  };
  await assert.rejects(
    requestJson('accounts', '/api/v1/sessions', { method: 'POST' }),
    (err: unknown) => {
      assert.ok(err instanceof ApiError);
      assert.equal(err.status, 401);
      assert.equal(err.code, 'invalid-credentials');
      assert.equal(err.message, 'Email, usuario o contraseña incorrectos.');
      assert.ok(!JSON.stringify(err).includes('private server detail'));
      return true;
    }
  );
  assert.equal(calls - beforeCalls, 1);
});

test('normalizes malformed problem types and HTML/empty successes', async () => {
  for (const scenario of [
    {
      status: 503,
      type: 'application/problem+json',
      body: '{"type":{"unexpected":true}}',
      code: 'http-error',
    },
    {
      status: 200,
      type: 'text/html',
      body: '<html>proxy error</html>',
      code: 'malformed-response',
    },
    {
      status: 200,
      type: 'application/json',
      body: '',
      code: 'malformed-response',
    },
  ]) {
    handler = (_request, response) => {
      response.writeHead(scenario.status, { 'content-type': scenario.type });
      response.end(scenario.body);
    };
    await assert.rejects(
      requestJson('accounts', '/check', { method: 'GET' }),
      (err: unknown) => {
        assert.ok(err instanceof ApiError);
        assert.equal(err.status, scenario.status);
        assert.equal(err.code, scenario.code);
        return true;
      }
    );
  }
});

test('preserves a 401 when its response body is truncated', async () => {
  handler = (_request, response) => {
    response.writeHead(401, {
      'content-type': 'application/json',
      'content-length': '100',
    });
    response.flushHeaders();
    response.write('{');
    setTimeout(() => response.destroy(), 30);
  };
  await assert.rejects(
    requestJson('accounts', '/check', { method: 'GET' }),
    (err: unknown) => {
      assert.ok(err instanceof ApiError);
      assert.equal(err.status, 401);
      assert.equal(err.code, 'network-error');
      return true;
    }
  );
});

test(
  'the ten-second deadline covers a body stalled after headers',
  { timeout: 15000 },
  async () => {
    handler = (_request, response) => {
      response.writeHead(200, { 'content-type': 'application/json' });
      response.flushHeaders();
      response.write('{');
    };
    const startedAt = Date.now();
    await assert.rejects(
      requestJson('accounts', '/check', { method: 'GET' }),
      (err: unknown) => {
        assert.ok(err instanceof ApiError);
        assert.equal(err.code, 'timeout-error');
        return true;
      }
    );
    assert.ok(Date.now() - startedAt >= 9500);
    assert.ok(Date.now() - startedAt < 14000);
  }
);
