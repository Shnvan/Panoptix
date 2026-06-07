import { readdir, readFile } from 'node:fs/promises';
import path from 'node:path';

const root = path.resolve('src');

const forbidden = [
  { name: 'browser media device access', pattern: /\bnavigator\.mediaDevices\b/ },
  { name: 'getUserMedia capture', pattern: /\bgetUserMedia\s*\(/ },
  { name: 'MediaRecorder capture', pattern: /\bnew\s+MediaRecorder\b|\bMediaRecorder\s*\(/ },
  { name: 'LiveKit publishTrack', pattern: /\bpublishTrack\s*\(/ },
  { name: 'LiveKit local track creation', pattern: /\bcreateLocal(?:Audio|Video)?Tracks?\s*\(/ },
  { name: 'sessionStorage token/state storage', pattern: /\bsessionStorage\b/ },
  { name: 'IndexedDB token/state storage', pattern: /\bindexedDB\b|\bIndexedDB\b/ },
  { name: 'gateway-only API route in browser', pattern: /\/api\/v1\/gateways\// },
  { name: 'gateway-control WebSocket route in browser', pattern: /\/api\/v1\/gateway-control/ },
  { name: 'LiveKit webhook route in browser', pattern: /\/api\/v1\/webhooks\/livekit/ },
  { name: 'Gateway Discovery UI route', pattern: /discovery-runs/ },
  { name: 'RTSP URL exposure', pattern: /rtsp:\/\//i },
  { name: 'LiveKit API secret string', pattern: /LIVEKIT_API_SECRET/ },
  { name: 'Cloudflare Access service secret string', pattern: /CF-Access-Client-Secret|CLOUDFLARE_ACCESS_CLIENT_SECRET|PANOPTIX_CF_ACCESS_CLIENT_SECRET/ },
  { name: 'R2 secret string', pattern: /R2_SECRET_ACCESS_KEY/ },
  { name: 'database URL string', pattern: /DATABASE_URL/ },
  { name: 'LLM provider key string', pattern: /AI_ASSISTANT_API_KEY|GROQ_API_KEY|OPENAI_API_KEY/ },
  { name: 'browser LLM provider endpoint', pattern: /api\.groq\.com|api\.openai\.com/ },
  { name: 'raw HTML rendering', pattern: /dangerouslySetInnerHTML/ },
];

const localStorageAllowed = new Set(['src/lib/theme.tsx']);
const serviceTokenAllowed = new Set(['src/lib/types.ts', 'src/app/components/GatewaysSection.tsx']);

function stripComments(source) {
  return source
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/(^|[^:])\/\/.*$/gm, '$1');
}

async function listFiles(dir) {
  const entries = await readdir(dir, { withFileTypes: true });
  const files = await Promise.all(entries.map(async (entry) => {
    const next = path.join(dir, entry.name);
    if (entry.isDirectory()) return listFiles(next);
    if (/\.(ts|tsx|js|jsx|mjs)$/.test(entry.name)) return [next];
    return [];
  }));
  return files.flat();
}

const findings = [];
for (const file of await listFiles(root)) {
  const rel = path.relative(process.cwd(), file).replaceAll(path.sep, '/');
  const source = stripComments(await readFile(file, 'utf8'));

  for (const rule of forbidden) {
    if (rule.pattern.test(source)) {
      findings.push(`${rel}: forbidden ${rule.name}`);
    }
  }

  if (/\blocalStorage\b/.test(source) && !localStorageAllowed.has(rel)) {
    findings.push(`${rel}: localStorage is only allowed for the theme preference`);
  }

  if (/\bservice_token\b/.test(source) && !serviceTokenAllowed.has(rel)) {
    findings.push(`${rel}: service_token may only appear in typed one-time gateway token display paths`);
  }
}

if (findings.length > 0) {
  console.error('Frontend guardrail scan failed:');
  for (const finding of findings) console.error(`- ${finding}`);
  process.exit(1);
}

console.log('Frontend guardrail scan passed.');
