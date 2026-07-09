from __future__ import annotations
import hashlib, html, json, os, re, time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup
CONFIG_PATH=Path('config.json'); STATE_PATH=Path('state.json'); RSS_PATH=Path('pokemon_tcg_alerts.xml'); MATCHES_PATH=Path('matches.json')
PRICE_RE=re.compile(r'(?P<price>\d{1,4}(?:[,.]\d{2})?)\s?€'); SPACE_RE=re.compile(r'\s+')
@dataclass(frozen=True)
class Candidate:
    store:str; priority:str; title:str; url:str; source_url:str; score:int; signals:tuple[str,...]; price:str|None=None
def norm_text(v): return SPACE_RE.sub(' ', html.unescape(v or '')).strip()
def load_json(p,d):
    try: return json.loads(p.read_text(encoding='utf-8')) if p.exists() else d
    except Exception: return d
def save_json(p,o): p.write_text(json.dumps(o,ensure_ascii=False,indent=2,sort_keys=True),encoding='utf-8')
def fetch(url,timeout):
    h={'User-Agent':'Mozilla/5.0 PokemonTCGPreorderRSS/2.0 personal alerts','Accept-Language':'fr-FR,fr;q=0.9,en;q=0.7'}
    r=requests.get(url,headers=h,timeout=timeout); r.raise_for_status(); return r.text
def canonical(base,href):
    if not href or href.startswith(('mailto:','tel:','javascript:','#')): return None
    u=urljoin(base,href); p=urlparse(u)
    if p.scheme not in {'http','https'}: return None
    u=p._replace(fragment='').geturl(); u=re.sub(r'([?&])(utm_[^=&]+|srsltid|fbclid|gclid)=[^&]+&?',r'\1',u).rstrip('?&')
    return u
def link_allowed(url, pats):
    if not pats: return True
    path=urlparse(url).path.lower(); return any(x.lower() in path for x in pats)
def context(a):
    nodes=[a,a.parent,a.parent.parent if a.parent else None]
    return norm_text(' '.join(n.get_text(' ',strip=True) for n in nodes if n))
def extract(store, raw, cfg):
    soup=BeautifulSoup(raw,'html.parser')
    for t in soup(['script','style','noscript','svg']): t.decompose()
    kw=cfg['keywords']; must=[x.lower() for x in kw['must_have_any']]; strong=[x.lower() for x in kw['strong_signals']]; excl=[x.lower() for x in kw['exclude']]
    out={}
    for a in soup.find_all('a', href=True):
        url=canonical(store['url'], a.get('href'))
        if not url or not link_allowed(url, store.get('link_allow_patterns',[])): continue
        txt=context(a); low=txt.lower()
        if len(txt)<8 or not any(k in low for k in must) or any(k in low for k in excl): continue
        sig=sorted({k for k in strong if k in low}); score=len(sig)*3
        if any(x in low for x in ['précommande','precommande','pre-order','prochaine sortie']): score+=10
        if any(x in low for x in ['display','elite trainer box','etb','coffret','booster']): score+=4
        if store.get('priority')=='high': score+=2
        if score<2: continue
        title=norm_text(a.get_text(' ',strip=True)) or txt[:160]
        if len(title)<12: title=txt[:180]
        m=PRICE_RE.search(txt); price=(m.group('price').replace(',','.')+' €') if m else None
        c=Candidate(store['name'],store.get('priority','normal'),title[:220],url,store['url'],score,tuple(sig[:12]),price)
        if url not in out or c.score>out[url].score: out[url]=c
    return sorted(out.values(),key=lambda c:(c.score,c.priority=='high'),reverse=True)
def item_id(c): return hashlib.sha256(f'{c.store}|{c.url}|{c.title}'.encode()).hexdigest()
def build_rss(items,cfg):
    now=datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S GMT'); title=cfg['settings'].get('rss_title','Pokemon TCG Alerts')
    parts=[]
    for it in items[:cfg['settings'].get('max_items_per_run',60)]:
        desc=[f"Boutique: {it['store']}",f"Priorité: {it['priority']}",f"Score: {it['score']}"]
        if it.get('price'): desc.append(f"Prix détecté: {it['price']}")
        if it.get('signals'): desc.append('Signaux: '+', '.join(it['signals']))
        desc.append(f"Page source: {it['source_url']}")
        parts.append(f"""    <item>\n      <title>{html.escape(it['title'])}</title>\n      <link>{html.escape(it['url'])}</link>\n      <guid isPermaLink=\"false\">{html.escape(it['id'])}</guid>\n      <pubDate>{html.escape(it['first_seen'])}</pubDate>\n      <description>{html.escape(' | '.join(desc))}</description>\n    </item>""")
    return f"""<?xml version=\"1.0\" encoding=\"UTF-8\" ?>\n<rss version=\"2.0\">\n  <channel>\n    <title>{html.escape(title)}</title>\n    <link>https://github.com/</link>\n    <description>Alertes personnalisées pour précommandes/restocks Pokémon TCG.</description>\n    <lastBuildDate>{now}</lastBuildDate>\n{chr(10).join(parts)}\n  </channel>\n</rss>\n"""
def post_discord(items):
    wh=os.getenv('DISCORD_WEBHOOK_URL','').strip()
    if not wh or not items: return
    lines=[f"**{i['store']}** — [{i['title']}]({i['url']})"+(f" — {i['price']}" if i.get('price') else '') for i in items[:10]]
    requests.post(wh,json={'content':'🎴 **Nouvelles alertes Pokémon TCG**\n'+'\n'.join(lines)},timeout=15).raise_for_status()
def post_telegram(items):
    tok=os.getenv('TELEGRAM_BOT_TOKEN','').strip(); chat=os.getenv('TELEGRAM_CHAT_ID','').strip()
    if not tok or not chat or not items: return
    text='🎴 Nouvelles alertes Pokémon TCG\n\n'+'\n\n'.join([f"{i['store']} — {i['title']}"+(f" — {i['price']}" if i.get('price') else '')+f"\n{i['url']}" for i in items[:10]])
    requests.post(f'https://api.telegram.org/bot{tok}/sendMessage',json={'chat_id':chat,'text':text,'disable_web_page_preview':False},timeout=15).raise_for_status()
def main():
    cfg=load_json(CONFIG_PATH,{}); state=load_json(STATE_PATH,{'seen':{},'items':[]}); seen=state.setdefault('seen',{}); all_items=state.setdefault('items',[]); ids={x['id'] for x in all_items if 'id' in x}; new=[]
    for store in cfg.get('stores',[]):
        try:
            raw=fetch(store['url'], int(cfg['settings'].get('request_timeout_seconds',25)))
            seen.setdefault('page_hashes',{})[store['url']]=hashlib.sha256(raw.encode('utf-8','ignore')).hexdigest()
            cands=extract(store,raw,cfg)
            for c in cands:
                cid=item_id(c)
                if cid in ids: continue
                item={'id':cid,'store':c.store,'priority':c.priority,'title':c.title,'url':c.url,'source_url':c.source_url,'score':c.score,'signals':list(c.signals),'price':c.price,'first_seen':datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S GMT')}
                all_items.insert(0,item); ids.add(cid); new.append(item)
            print(f"OK {store['name']}: {len(cands)} candidate(s).")
            time.sleep(float(cfg['settings'].get('sleep_between_requests_seconds',1.5)))
        except Exception as e: print(f"ERROR {store.get('name',store.get('url'))}: {e}")
    state['items']=all_items[:300]
    MATCHES_PATH.write_text(json.dumps(new,ensure_ascii=False,indent=2),encoding='utf-8')
    RSS_PATH.write_text(build_rss(state['items'],cfg),encoding='utf-8')
    save_json(STATE_PATH,state)
    try: post_discord(new)
    except Exception as e: print(f'Discord notification failed: {e}')
    try: post_telegram(new)
    except Exception as e: print(f'Telegram notification failed: {e}')
    print(f'Done. New items: {len(new)}. RSS: {RSS_PATH}')
if __name__=='__main__': main()
