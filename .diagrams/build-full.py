# 拼装 DeepSeek Harness 单文件图集:5 视图 + hash 路由 + 下钻
# 输入:5 个 archify 交付 HTML
# 输出:harness-full.html(纯图集,无文字解读)
import re, os

BASE = r'D:\AI-Projects\deepseek-harness\.diagrams'
REPO = 'D:/AI-Projects/deepseek-harness'

def srcdoc(path):
    h = open(path, encoding='utf-8').read()
    # archify 证据链接默认指向 GitHub blob;改写为本机 VS Code 导航
    h = re.sub(
        r'https://github\.com/deepseek-ai/deepseek-harness/blob/[0-9a-f]+/([^"#]+)#L(\d+)',
        lambda m: f'vscode://file/{REPO}/{m.group(1)}:{m.group(2)}',
        h)
    h = h.replace('https://github.com/deepseek-ai/deepseek-harness',
                  f'vscode://file/{REPO}')
    return h.replace('&', '&amp;').replace('"', '&quot;')

DIAGRAMS = {
    'tu':     ('harness-architecture.html', '主架构图'),
    'cordis': ('cordis-kernel.html',        'Cordis 内核'),
    'eco':    ('plugin-ecosystem.html',     '插件生态'),
    'collab': ('collaboration-patterns.html', '协作模式'),
    'pano':   ('panorama.html',             '全景回顾'),
    'sess':   ('session-log.html',          '会话日志'),
    'seam':   ('capability-seam.html',      '能力接缝'),
    'scope':  ('scope-shadowing.html',      '作用域遮蔽'),
    'crash':  ('crash-recovery.html',       '崩溃恢复'),
    'turn':   ('turn-step.html',            'Turn/Step 时序'),
    'tool':   ('tool-pipeline.html',        '工具三道关口'),
    'life':   ('plugin-lifecycle.html',     '插件生命周期'),
}

# ---------- 视图装配 ----------
views_html = []
for key, (fname, label) in DIAGRAMS.items():
    sd = srcdoc(f'{BASE}\\{fname}')
    back = '' if key == 'tu' else '<div class="drill"><a href="#/tu">← 返回主架构图</a></div>'
    views_html.append(f'<section class="view" id="view-{key}">{back}<iframe title="{label}" srcdoc="{sd}"></iframe></section>')

drill_tu = ('<div class="drill"><b>下钻:</b> '
            '<a href="#/cordis">Cordis 内核(六概念)</a>'
            '<a href="#/eco">插件生态(一切皆插件)</a>'
            '<a href="#/collab">协作模式(接缝/日志/作用域/恢复)</a>'
            '<a href="#/pano">全景回顾(四层结构)</a>'
            '<a href="#/sess">会话日志(模型可见即可重建)</a>'
            '<a href="#/seam">能力接缝(三角色)</a>'
            '<a href="#/scope">作用域遮蔽(两层查找)</a>'
            '<a href="#/crash">崩溃恢复(两种场景)</a>'
            '<a href="#/turn">agent-loop → Turn/Step 时序</a>'
            '<a href="#/tool">core/tools → 三道关口</a>'
            '<a href="#/life">插件 → 生命周期</a></div>')
views_html[0] = views_html[0].replace('<section class="view" id="view-tu">',
    '<section class="view" id="view-tu">' + drill_tu)

nav = ''.join(
    f'<a href="#/{k}" data-r="{k}">{l}</a>' for k, (_, l) in DIAGRAMS.items()
)

ROUTES = list(DIAGRAMS.keys())

route_css = '\n'.join(f'body.route-{k} #view-{k}{{display:block}}' for k in ROUTES)

html = f'''<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<title>DeepSeek Harness 架构图集(单文件)</title>
<style>
:root{{--ink:#1c1917;--sub:#78716c;--line:#e7e5e4;--bg:#fafaf9;--accent:#0f766e}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--ink);font:16px/1.8 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif}}
nav.router{{position:sticky;top:0;z-index:50;display:flex;gap:2px;background:#1c1917;padding:0 1em;font-size:.92em;flex-wrap:wrap}}
nav.router a{{color:#a8a29e;text-decoration:none;padding:.65em .9em;border-bottom:2px solid transparent}}
nav.router a.on{{color:#fff;border-bottom-color:#14b8a6;font-weight:600}}
nav.router .hint{{margin-left:auto;color:#78716c;align-self:center;font-size:.82em}}
section.view{{display:none}}
section.view iframe{{width:100%;height:calc(100vh - 82px);border:0;display:block}}
.drill{{display:flex;gap:1.2em;align-items:center;background:#f0fdfa;border-bottom:1px solid #99f6e4;padding:.35em 1em;font-size:.86em}}
.drill a{{color:#0f766e;text-decoration:none}}
.drill a:hover{{text-decoration:underline}}
{route_css}
</style>
</head>
<body class="route-tu">
<nav class="router">{nav}<span class="hint">单文件图集 · 按 1-9 切换前 9 个视图 · 文字解读见 docs/architecture-map.md</span></nav>
{''.join(views_html)}
<script>
var ROUTES = {ROUTES!r}.map(String);
function route() {{
  var key = (location.hash || '#/tu').replace('#/', '');
  if (ROUTES.indexOf(key) < 0) key = 'tu';
  document.body.className = 'route-' + key;
  var links = document.querySelectorAll('nav.router a');
  for (var i = 0; i < links.length; i++) links[i].className = links[i].getAttribute('data-r') === key ? 'on' : '';
}}
addEventListener('hashchange', route);
addEventListener('keydown', function(e) {{
  if (/^(INPUT|TEXTAREA)$/.test(e.target.tagName)) return;
  var n = parseInt(e.key, 10);
  if (n >= 1 && n <= ROUTES.length) location.hash = '#/' + ROUTES[n - 1];
}});
route();
</script>
</body>
</html>
'''

out = f'{BASE}\\harness-full.html'
open(out, 'w', encoding='utf-8').write(html)
print('写出:', out, '| %.1f KB' % (os.path.getsize(out) / 1024))
