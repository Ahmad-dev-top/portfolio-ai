import base64, json, urllib.request, urllib.error
from datetime import datetime, timezone
from pathlib import Path

repo = 'Ahmad-dev-top/portfolio-ai'
branch = 'main'
root = Path.home() / 'portfolio-upload'
token = None
for line in (Path.home() / 'dogar-api' / '.env').read_text(encoding='utf-8').splitlines():
    if line.startswith('GITHUB_TOKEN='):
        token = line.split('=', 1)[1].strip().strip("\"'")
        break
if not token:
    raise SystemExit('GITHUB_TOKEN not found in ~/dogar-api/.env')
headers = {
    'Authorization': f'Bearer {token}',
    'Accept': 'application/vnd.github+json',
    'X-GitHub-Api-Version': '2022-11-28',
    'User-Agent': 'dogar-portfolio-sync',
}
files = [p for p in root.rglob('*') if p.is_file()]
created = updated = 0
message = 'add project files from Cursor (' + datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC') + ')'
for path in files:
    rel = path.relative_to(root).as_posix()
    url = f'https://api.github.com/repos/{repo}/contents/{rel}'
    sha = None
    req = urllib.request.Request(url + f'?ref={branch}', headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            sha = json.load(r).get('sha')
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise
    body = {
        'message': message,
        'content': base64.b64encode(path.read_bytes()).decode('ascii'),
        'branch': branch,
    }
    if sha:
        body['sha'] = sha
    put = urllib.request.Request(url, data=json.dumps(body).encode('utf-8'), headers={**headers, 'Content-Type':'application/json'}, method='PUT')
    with urllib.request.urlopen(put, timeout=60):
        if sha:
            updated += 1
        else:
            created += 1
print(json.dumps({'repo': repo, 'branch': branch, 'created': created, 'updated': updated, 'files': len(files)}))
