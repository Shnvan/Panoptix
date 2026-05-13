#!/usr/bin/env bash
# ct-log-check.sh — Check Certificate Transparency logs for unexpected certificates
# issued for a given domain (default: panoptix.site).
#
# Usage: ./ct-log-check.sh [domain]
#
# Exits 0 if all certs in the last 30 days were issued by Let's Encrypt or Cloudflare.
# Exits 1 if any unexpected issuer is found (possible mis-issuance or rogue cert).
#
# Requires: curl, python3

set -euo pipefail

DOMAIN="${1:-panoptix.site}"

echo "Checking CT logs for: %.${DOMAIN}"

RAW=$(curl -s "https://crt.sh/?q=%.${DOMAIN}&output=json")

if [[ -z "$RAW" || "$RAW" == "[]" ]]; then
    echo "No certificates found for ${DOMAIN}."
    exit 0
fi

python3 -c "
import sys, json, datetime

data = json.loads(sys.argv[1])
cutoff = (datetime.datetime.utcnow() - datetime.timedelta(days=30)).strftime('%Y-%m-%dT%H:%M:%S')

recent = [
    c for c in data
    if c.get('not_before', '') >= cutoff
]

seen = set()
unique = []
for c in recent:
    key = (str(c.get('issuer_ca_id', '')), c.get('name_value', ''))
    if key not in seen:
        seen.add(key)
        unique.append(c)

print(f'Certificates found in last 30 days: {len(unique)}')

unexpected = [
    c for c in unique
    if 'Let\\'s Encrypt' not in c.get('issuer_name', '')
    and 'Cloudflare' not in c.get('issuer_name', '')
]

if unexpected:
    print(f'WARNING: {len(unexpected)} cert(s) from unexpected issuer(s):')
    for c in unexpected:
        print(f'  issuer_ca_id={c.get(\"issuer_ca_id\")} name={c.get(\"name_value\")} issuer={c.get(\"issuer_name\")} not_before={c.get(\"not_before\")}')
    sys.exit(1)
else:
    print('OK: all recent certs issued by trusted CAs (Let\\'s Encrypt / Cloudflare).')
    sys.exit(0)
" "$RAW"
