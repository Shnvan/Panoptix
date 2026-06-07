import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { createServer, get as httpGet } from 'node:http';
import { brotliCompressSync, gzipSync } from 'node:zlib';
import { after, before, test } from 'node:test';

const fixtures = {
  plain: JSON.stringify({ encoding: 'identity' }),
  gzip: JSON.stringify({ encoding: 'gzip' }),
  br: JSON.stringify({ encoding: 'br' }),
};

let upstream;
let upstreamOrigin;
let proxy;
let proxyOrigin;
const upstreamAcceptEncodings = new Map();

function listen(server) {
  return new Promise((resolve, reject) => {
    server.once('error', reject);
    server.listen(0, '127.0.0.1', () => {
      server.off('error', reject);
      resolve(server.address().port);
    });
  });
}

function close(server) {
  return new Promise((resolve, reject) => {
    server.close((error) => error ? reject(error) : resolve());
  });
}

function request(path) {
  return new Promise((resolve, reject) => {
    httpGet(`${proxyOrigin}${path}`, (response) => {
      const chunks = [];
      response.on('data', (chunk) => chunks.push(chunk));
      response.on('end', () => {
        resolve({
          status: response.statusCode,
          headers: response.headers,
          body: Buffer.concat(chunks),
        });
      });
    }).on('error', reject);
  });
}

before(async () => {
  upstream = createServer((req, res) => {
    const path = new URL(req.url, 'http://upstream.test').pathname;
    upstreamAcceptEncodings.set(path, req.headers['accept-encoding']);

    if (path === '/api/v1/plain') {
      res.writeHead(200, {
        'content-type': 'application/json',
        'content-length': Buffer.byteLength(fixtures.plain),
        'x-upstream-security': 'preserved',
      });
      res.end(fixtures.plain);
      return;
    }

    if (path === '/api/v1/gzip') {
      const body = gzipSync(fixtures.gzip);
      res.writeHead(200, {
        'content-type': 'application/json',
        'content-encoding': 'gzip',
        'content-length': body.length,
      });
      res.end(body);
      return;
    }

    if (path === '/api/v1/br') {
      const body = brotliCompressSync(fixtures.br);
      res.writeHead(200, {
        'content-type': 'application/json',
        'content-encoding': 'br',
        'content-length': body.length,
      });
      res.end(body);
      return;
    }

    if (path === '/api/v1/redirect') {
      res.writeHead(302, {
        location: '/api/v1/plain',
        'set-cookie': ['session=one; HttpOnly; Secure', 'theme=dark; Secure'],
      });
      res.end();
      return;
    }

    res.writeHead(404);
    res.end();
  });

  const upstreamPort = await listen(upstream);
  upstreamOrigin = `http://127.0.0.1:${upstreamPort}`;

  const portProbe = createServer();
  const proxyPort = await listen(portProbe);
  await close(portProbe);
  proxyOrigin = `http://127.0.0.1:${proxyPort}`;

  proxy = spawn(process.execPath, ['server.mjs'], {
    cwd: new URL('..', import.meta.url),
    env: {
      ...process.env,
      PORT: String(proxyPort),
      PANOPTIX_API_ORIGIN: upstreamOrigin,
    },
    stdio: ['ignore', 'pipe', 'pipe'],
  });

  let output = '';
  proxy.stdout.setEncoding('utf8');
  proxy.stderr.setEncoding('utf8');
  proxy.stdout.on('data', (chunk) => {
    output += chunk;
  });
  proxy.stderr.on('data', (chunk) => {
    output += chunk;
  });

  let startupTimer;
  try {
    await Promise.race([
      new Promise((resolve) => {
        proxy.stdout.on('data', () => {
          if (output.includes('Panoptix web server listening')) resolve();
        });
      }),
      once(proxy, 'exit').then(([code]) => {
        throw new Error(`proxy exited before startup with code ${code}: ${output}`);
      }),
      new Promise((_, reject) => {
        startupTimer = setTimeout(
          () => reject(new Error(`proxy startup timed out: ${output}`)),
          5_000,
        );
      }),
    ]);
  } finally {
    clearTimeout(startupTimer);
  }
});

after(async () => {
  if (proxy && proxy.exitCode === null) {
    proxy.kill();
    await once(proxy, 'exit');
  }
  if (upstream) await close(upstream);
});

test('requests identity encoding and preserves ordinary response headers', async () => {
  const response = await request('/api/v1/plain');

  assert.equal(response.status, 200);
  assert.equal(upstreamAcceptEncodings.get('/api/v1/plain'), 'identity');
  assert.equal(response.headers['x-upstream-security'], 'preserved');
  assert.equal(response.headers['content-encoding'], undefined);
  assert.equal(response.headers['content-length'], undefined);
  assert.deepEqual(JSON.parse(response.body.toString('utf8')), { encoding: 'identity' });
});

for (const encoding of ['gzip', 'br']) {
  test(`does not forward stale ${encoding} representation headers`, async () => {
    const response = await request(`/api/v1/${encoding}`);

    assert.equal(response.status, 200);
    assert.equal(upstreamAcceptEncodings.get(`/api/v1/${encoding}`), 'identity');
    assert.equal(response.headers['content-encoding'], undefined);
    assert.equal(response.headers['content-length'], undefined);
    assert.deepEqual(JSON.parse(response.body.toString('utf8')), { encoding });
  });
}

test('preserves redirects and multiple set-cookie headers', async () => {
  const response = await request('/api/v1/redirect');

  assert.equal(response.status, 302);
  assert.equal(response.headers.location, '/api/v1/plain');
  assert.deepEqual(response.headers['set-cookie'], [
    'session=one; HttpOnly; Secure',
    'theme=dark; Secure',
  ]);
});
