"""Build the Kodi repository (GitHub Pages content of the gh-pages branch) from git blobs of a ref.

Usage:
    python tools/build_repo.py <repo> <out_dir> [ref]

    <repo>     path to this git repository (e.g. ".")
    <out_dir>  output directory; everything in it except a ".git" entry is deleted first,
               so it may be a gh-pages worktree (git worktree add ../candre-pages gh-pages)
    [ref]      git ref to package (default: master). Only COMMITTED content of that ref is
               packaged, never the working tree, so commit the version bump first.

Writes: addons.xml, addons.xml.md5, <addon>-<version>.zip at the root, zips/<addon>/ (zip,
addon.xml, art assets, index.html), index.html pages, .nojekyll and .gitattributes.
"""
import hashlib, os, re, shutil, subprocess, sys, zipfile, time
import xml.etree.ElementTree as ET

if len(sys.argv) < 3:
    sys.exit(__doc__)
REPO = sys.argv[1]
OUT = sys.argv[2]
REF = sys.argv[3] if len(sys.argv) > 3 else 'master'
ADDONS = ['repository.candre', 'plugin.video.prism', 'context.prism']
EXCL_DIRS = {'__pycache__', '.git'}

def git(*a, inp=None):
    return subprocess.run(['git', '-C', REPO, *a], input=inp, capture_output=True, check=True).stdout

def blobs(prefix):
    out = git('ls-tree', '-r', '-z', REF, '--', prefix + '/')
    items = []
    for rec in out.split(b'\0'):
        if not rec:
            continue
        meta, path = rec.split(b'\t', 1)
        mode, typ, sha = meta.split()
        path = path.decode('utf-8')
        if typ != b'blob' or mode == b'120000':
            continue
        parts = path.split('/')
        if any(p in EXCL_DIRS for p in parts) or path.endswith(('.pyc', '.pyo')):
            continue
        items.append((path, sha.decode()))
    return items

def read_blob(sha):
    return git('cat-file', 'blob', sha)

if os.path.exists(OUT):
    # keep a ".git" entry so OUT can be a gh-pages worktree/checkout
    for name in os.listdir(OUT):
        if name == '.git':
            continue
        p = os.path.join(OUT, name)
        if os.path.isdir(p) and not os.path.islink(p):
            shutil.rmtree(p)
        else:
            os.remove(p)
os.makedirs(os.path.join(OUT, 'zips'))

link = lambda n: '<a href="%s">%s</a><br>' % (n, n)
def index(path, title, names):
    html = '<!DOCTYPE html>\n<html>\n<head><meta charset="utf-8"><title>%s</title></head>\n<body>\n<h1>%s</h1>\n%s\n</body>\n</html>\n' % (
        title, title, '\n'.join(link(n) for n in names))
    with open(os.path.join(path, 'index.html'), 'w', encoding='utf-8', newline='\n') as f:
        f.write(html)

addon_xmls = []
root_zips = []
dt = time.localtime()[:6]
for aid in ADDONS:
    files = blobs(aid)
    contents = {p: read_blob(s) for p, s in files}
    axml = contents[aid + '/addon.xml']
    root = ET.fromstring(axml)
    assert root.get('id') == aid, (aid, root.get('id'))
    ver = root.get('version')
    zname = '%s-%s.zip' % (aid, ver)
    ddir = os.path.join(OUT, 'zips', aid)
    os.makedirs(ddir)
    zpath = os.path.join(ddir, zname)
    with zipfile.ZipFile(zpath, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for p in sorted(contents):
            zi = zipfile.ZipInfo(p, date_time=dt)
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = 0o644 << 16
            z.writestr(zi, contents[p])
    # addon.xml + art assets next to the zip (Kodi reads art from datadir/<id>/)
    with open(os.path.join(ddir, 'addon.xml'), 'wb') as f:
        f.write(axml)
    listing = [zname, 'addon.xml']
    for a in root.iter('assets'):
        for el in a:
            rel = (el.text or '').strip()
            src = aid + '/' + rel
            if rel and src in contents:
                dst = os.path.join(ddir, *rel.split('/'))
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                with open(dst, 'wb') as f:
                    f.write(contents[src])
    index(ddir, aid, listing)
    shutil.copyfile(zpath, os.path.join(OUT, zname))
    root_zips.append(zname)
    # strip XML declaration, normalise to LF
    txt = axml.decode('utf-8').replace('\r\n', '\n')
    txt = re.sub(r'^\s*<\?xml[^>]*\?>\s*', '', txt).strip()
    addon_xmls.append(txt)
    print(aid, ver, zname, os.path.getsize(zpath))

addons = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<addons>\n' + '\n\n'.join(addon_xmls) + '\n</addons>\n'
data = addons.encode('utf-8')
ET.fromstring(data)  # well-formed check
md5 = hashlib.md5(data).hexdigest()
for d in (OUT,):
    with open(os.path.join(d, 'addons.xml'), 'wb') as f:
        f.write(data)
    with open(os.path.join(d, 'addons.xml.md5'), 'w', newline='') as f:
        f.write(md5)  # upstream convention: no trailing newline
index(os.path.join(OUT, 'zips'), 'zips', [a + '/' for a in ADDONS])
index(OUT, 'Candre Kodi Repository', root_zips + ['zips/', 'addons.xml', 'addons.xml.md5'])
open(os.path.join(OUT, '.nojekyll'), 'w').close()
with open(os.path.join(OUT, '.gitattributes'), 'w', newline='\n') as f:
    f.write('* -text\n')
print('md5', md5)
