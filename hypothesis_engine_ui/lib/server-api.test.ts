import assert from 'node:assert/strict';
import test from 'node:test';
import { proxyApiRequest } from './server-api.ts';

const base = 'https://research.example/api/v1';

test('proxy preserves API method, query, streamed body and error while stripping credentials and caching', async () => {
  const request = new Request('https://ui.example/api/v1/hypotheses?limit=5', {
    method: 'POST', body: '{"title":"Research"}', headers: {
      'X-API-Key': 'synthetic-workspace-key', Cookie: 'private=session', Authorization: 'Bearer private',
      'Content-Type': 'application/json', 'Idempotency-Key': 'operation-1', 'X-Forwarded-For': 'spoofed',
    },
  });
  const response = await proxyApiRequest(request, ['hypotheses'], base, async (input, init) => {
    assert.equal(String(input), `${base}/hypotheses?limit=5`);
    assert.equal(init?.method, 'POST');
    assert.equal(init?.cache, 'no-store');
    assert.equal(init?.redirect, 'manual');
    assert.equal(init?.credentials, 'omit');
    const headers = new Headers(init?.headers);
    assert.equal(headers.get('x-api-key'), 'synthetic-workspace-key');
    assert.equal(headers.get('idempotency-key'), 'operation-1');
    for (const name of ['cookie', 'authorization', 'x-forwarded-for']) assert.equal(headers.get(name), null);
    assert.equal(await new Response(init?.body).text(), '{"title":"Research"}');
    return new Response('{"detail":"Denied"}', { status: 403, headers: { 'Content-Type': 'application/json', 'Set-Cookie': 'bad=value', 'Cache-Control': 'public,max-age=3600' } });
  });
  assert.equal(response.status, 403);
  assert.equal(await response.text(), '{"detail":"Denied"}');
  assert.equal(response.headers.get('set-cookie'), null);
  assert.match(response.headers.get('cache-control')!, /private, no-store/);
  assert.equal(response.headers.get('cdn-cache-control'), 'no-store');
  assert.equal(response.headers.get('vercel-cdn-cache-control'), 'no-store');
});

test('production rejects cleartext or credential-bearing configuration before any fetch', async () => {
  const environment: Record<string, string | undefined> = process.env;
  const previous = environment.NODE_ENV;
  environment.NODE_ENV = 'production';
  try {
    for (const upstream of ['http://research.example/api/v1', 'https://user:password@research.example/api/v1', `${base}?key=private`, `${base}#private`]) {
      const response = await proxyApiRequest(new Request('https://ui.example/'), ['hypotheses'], upstream, async () => { assert.fail('must not fetch'); });
      assert.equal(response.status, 502);
    }
    for (const status of [200, 401]) {
      const response = await proxyApiRequest(new Request('https://ui.example/'), ['hypotheses'], base, async () => new Response('{}', { status }));
      assert.equal(response.status, status);
      assert.match(response.headers.get('cache-control')!, /private, no-store/);
      assert.equal(response.headers.get('cdn-cache-control'), 'no-store');
      assert.equal(response.headers.get('vercel-cdn-cache-control'), 'no-store');
    }
  } finally {
    if (previous === undefined) delete environment.NODE_ENV;
    else environment.NODE_ENV = previous;
  }
});

test('proxy rejects path escapes and never follows off-origin redirects', async () => {
  for (const part of ['..', '.', '../docs', '\\docs']) {
    const response = await proxyApiRequest(new Request('https://ui.example/'), [part], base, async () => { throw new Error('must not fetch'); });
    assert.equal(response.status, 400);
  }
  const response = await proxyApiRequest(new Request('https://ui.example/'), ['hypotheses'], base, async () => new Response(null, { status: 307, headers: { location: 'https://elsewhere.example/' } }));
  assert.equal(response.status, 502);
  assert.equal(response.headers.get('location'), null);
});

test('same-origin API redirects remain on UI origin and upstream failures disclose no input', async () => {
  const request = new Request('https://ui.example/');
  const response = await proxyApiRequest(request, ['hypotheses'], base, async () => new Response(null, { status: 307, headers: { location: `${base}/hypotheses/?limit=5` } }));
  assert.equal(response.status, 307);
  assert.equal(response.headers.get('location'), '/api/v1/hypotheses/?limit=5');
  const error = await proxyApiRequest(request, ['hypotheses'], base, async () => { throw new Error('synthetic-private-key'); });
  assert.equal(error.status, 502);
  assert.doesNotMatch(await error.text(), /synthetic-private-key/);
});
