import { createServer } from 'node:http';
import { createReadStream, existsSync, statSync } from 'node:fs';
import path from 'node:path';
import { Readable } from 'node:stream';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const distRoot = path.resolve(__dirname, 'dist');
const indexPath = path.join(distRoot, 'index.html');

const port = Number(process.env.PORT || 3000);
const apiOrigin = process.env.PANOPTIX_API_ORIGIN;

const hopByHopHeaders = new Set([
  'connection',
  'keep-alive',
  'proxy-authenticate',
  'proxy-authorization',
  'te',
  'trailer',
  'transfer-encoding',
  'upgrade',
]);

const mimeTypes = new Map([
  ['.css', 'text/css; charset=utf-8'],
  ['.html', 'text/html; charset=utf-8'],
  ['.ico', 'image/x-icon'],
  ['.js', 'text/javascript; charset=utf-8'],
  ['.json', 'application/json; charset=utf-8'],
  ['.map', 'application/json; charset=utf-8'],
  ['.png', 'image/png'],
  ['.svg', 'image/svg+xml'],
  ['.txt', 'text/plain; charset=utf-8'],
  ['.webp', 'image/webp'],
  ['.woff', 'font/woff'],
  ['.woff2', 'font/woff2'],
]);

function isProxyPath(urlPath) {
  return urlPath === '/health' || urlPath.startsWith('/api/v1/');
}

function copyRequestHeaders(req) {
  const headers = {};
  for (const [name, value] of Object.entries(req.headers)) {
    const lower = name.toLowerCase();
    if (hopByHopHeaders.has(lower) || lower === 'host' || lower === 'content-length') continue;
    if (value !== undefined) headers[name] = Array.isArray(value) ? value.join(', ') : value;
  }
  headers['x-forwarded-host'] = req.headers.host || '';
  headers['x-forwarded-proto'] = req.headers['x-forwarded-proto'] || 'https';
  return headers;
}

function collectRequestBody(req) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    req.on('data', (chunk) => chunks.push(chunk));
    req.on('end', () => resolve(chunks.length > 0 ? Buffer.concat(chunks) : undefined));
    req.on('error', reject);
  });
}

async function proxyRequest(req, res, url) {
  if (!apiOrigin) {
    res.writeHead(503, { 'content-type': 'application/json; charset=utf-8' });
    res.end(JSON.stringify({ detail: 'panoptix-api-origin-not-configured' }));
    return;
  }

  const body = ['GET', 'HEAD'].includes(req.method || 'GET')
    ? undefined
    : await collectRequestBody(req);

  const target = new URL(`${url.pathname}${url.search}`, apiOrigin);
  const upstream = await fetch(target, {
    method: req.method,
    headers: copyRequestHeaders(req),
    body,
    redirect: 'manual',
  });

  const responseHeaders = {};
  upstream.headers.forEach((value, name) => {
    const lower = name.toLowerCase();
    if (hopByHopHeaders.has(lower) || lower === 'set-cookie') return;
    responseHeaders[name] = value;
  });

  const setCookie = typeof upstream.headers.getSetCookie === 'function'
    ? upstream.headers.getSetCookie()
    : [];
  if (setCookie.length > 0) {
    responseHeaders['set-cookie'] = setCookie;
  } else {
    const singleCookie = upstream.headers.get('set-cookie');
    if (singleCookie) responseHeaders['set-cookie'] = singleCookie;
  }

  res.writeHead(upstream.status, responseHeaders);

  if (req.method === 'HEAD' || !upstream.body) {
    res.end();
    return;
  }

  Readable.fromWeb(upstream.body).pipe(res);
}

function resolveStaticPath(urlPath) {
  let decodedPath;
  try {
    decodedPath = decodeURIComponent(urlPath);
  } catch {
    return null;
  }

  const requested = path.resolve(distRoot, `.${decodedPath}`);
  if (!requested.startsWith(`${distRoot}${path.sep}`) && requested !== distRoot) {
    return null;
  }
  return requested;
}

async function serveStatic(req, res, url) {
  const requested = resolveStaticPath(url.pathname);
  const filePath = requested && existsSync(requested) && statSync(requested).isFile()
    ? requested
    : indexPath;

  if (!existsSync(filePath)) {
    res.writeHead(500, { 'content-type': 'text/plain; charset=utf-8' });
    res.end('Frontend build output not found. Run npm run build first.');
    return;
  }

  const ext = path.extname(filePath);
  const contentType = mimeTypes.get(ext) || 'application/octet-stream';
  res.writeHead(200, {
    'content-type': contentType,
    'cache-control': filePath === indexPath ? 'no-store' : 'public, max-age=31536000, immutable',
  });

  if (req.method === 'HEAD') {
    res.end();
    return;
  }

  createReadStream(filePath).pipe(res);
}

const server = createServer(async (req, res) => {
  try {
    const url = new URL(req.url || '/', `http://${req.headers.host || 'localhost'}`);
    if (isProxyPath(url.pathname)) {
      await proxyRequest(req, res, url);
      return;
    }
    await serveStatic(req, res, url);
  } catch (error) {
    console.error('panoptix-web-server-error', error);
    if (!res.headersSent) {
      res.writeHead(502, { 'content-type': 'application/json; charset=utf-8' });
    }
    res.end(JSON.stringify({ detail: 'frontend-proxy-error' }));
  }
});

server.listen(port, '0.0.0.0', () => {
  console.log(`Panoptix web server listening on port ${port}`);
  console.log(`API proxy origin: ${apiOrigin || '(not configured)'}`);
});
