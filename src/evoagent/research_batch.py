from __future__ import annotations
import argparse,json,hashlib,os,re,subprocess,time
from pathlib import Path
from collections import Counter
import requests
from .core import save_json

PAPER_QUERIES=("agentic workflows planning memory", "LLM agents software engineering", "language model tool use", "agent safety prompt injection", "long context retrieval memory", "process supervision reasoning", "multi agent collaboration", "self improving agents", "RAG evaluation", "uncertainty calibration LLM")
GITHUB_QUERIES=("topic:llm stars:>30 archived:false", "topic:agent-framework stars:>20 archived:false", "topic:llmops stars:>20 archived:false", '"language agent" in:name,description stars:>20 archived:false', '"AI agent" in:name,description stars:>20 archived:false', '"function calling" in:name,description stars:>20 archived:false', '"LLM evaluation" in:name,description stars:>20 archived:false')

def abstract(inv):
 if not inv:return ''
 return ' '.join(t for i,t in sorted((i,t) for t,ix in inv.items() for i in ix))

def prior_ids(path):
 try:return {x['work_id'] for x in json.loads(path.read_text(encoding='utf-8-sig')).get('papers',[])}
 except:return set()

def collect_papers(target, prior, timeout=45):
 s=requests.Session();s.headers['User-Agent']='EvoAgent-Research/0.1';out={}
 for q in PAPER_QUERIES:
  try:
   r=s.get('https://api.openalex.org/works',params={'search':q,'per-page':50,'select':'id,display_name,publication_year,doi,open_access,primary_location,authorships,cited_by_count,abstract_inverted_index,type'},timeout=timeout);r.raise_for_status()
   for raw in r.json().get('results',[]):
    wid=raw['id'].rsplit('/',1)[-1]
    if wid in prior:continue
    title=raw.get('display_name') or '';ab=abstract(raw.get('abstract_inverted_index'));text=(title+' '+ab).lower();rel=sum(x in text for x in ('agent','language model','llm','tool','reasoning','benchmark','memory','safety'))
    if rel<2:continue
    loc=raw.get('primary_location') or {};src=loc.get('source') or {}
    row={'work_id':wid,'title':title,'abstract':ab,'year':raw.get('publication_year'),'doi':raw.get('doi'),'url':loc.get('landing_page_url') or raw['id'],'pdf_url':loc.get('pdf_url'),'venue':src.get('display_name'),'authors':[a.get('author',{}).get('display_name') for a in raw.get('authorships',[]) if a.get('author',{}).get('display_name')],'citations':raw.get('cited_by_count',0),'open_access':raw.get('open_access') or {},'type':raw.get('type'),'query':q,'relevance':rel,'source':'openalex'}
    row['content_sha256']=hashlib.sha256((title+'\n'+ab).encode()).hexdigest();out[wid]=row
  except Exception:continue
  if len(out)>=target*2:break
 return sorted(out.values(),key=lambda x:(x['relevance'],x['citations'],x.get('year') or 0),reverse=True)[:target]

def collect_repos(target, prior, timeout=45):
 s=requests.Session();s.headers.update({'Accept':'application/vnd.github+json','User-Agent':'EvoAgent-Research/0.1'});tok=os.getenv('GITHUB_TOKEN')
 if tok:s.headers['Authorization']='Bearer '+tok
 out={}
 for q in GITHUB_QUERIES:
  try:r=s.get('https://api.github.com/search/repositories',params={'q':q,'sort':'stars','order':'desc','per_page':50},timeout=timeout);r.raise_for_status()
  except Exception:continue
  for raw in r.json().get('items',[]):
   name=raw['full_name']
   if name in prior or raw.get('fork') or raw.get('archived'):continue
   text=(name+' '+(raw.get('description') or '')+' '+' '.join(raw.get('topics') or [])).lower();rel=sum(x in text for x in ('agent','llm','language model','prompt','rag','memory','tool','autonomous','benchmark','evaluation'))
   if rel<2:continue
   out[name]={'full_name':name,'description':raw.get('description'),'html_url':raw['html_url'],'clone_url':raw['clone_url'],'default_branch':raw.get('default_branch') or 'main','stars':raw.get('stargazers_count',0),'forks':raw.get('forks_count',0),'language':raw.get('language'),'license':(raw.get('license') or {}).get('spdx_id'),'updated_at':raw.get('updated_at'),'topics':raw.get('topics') or [],'query':q,'relevance':rel}
  if len(out)>=target*2:break
 return sorted(out.values(),key=lambda x:(x['relevance'],x['stars'],x['forks']),reverse=True)[:target]

def tree_hash(p):
 h=hashlib.sha256();n=b=0
 for f in sorted(x for x in p.rglob('*') if x.is_file() and '.git' not in x.parts):
  h.update(f.relative_to(p).as_posix().encode()+b'\0');
  with f.open('rb') as z:
   while c:=z.read(1024*1024):h.update(c);b+=len(c)
  n+=1
 return h.hexdigest(),n,b

def clone(repos,out):
 out.mkdir(parents=True,exist_ok=True);rows=[]
 for i,r in enumerate(repos,1):
  p=out/r['full_name'].replace('/','__');row={**r,'path':str(p),'index':i,'executed':False}
  try:
   if not p.exists():
    z=subprocess.run(['git','clone','--depth','1','--no-tags',r['clone_url'],str(p)],capture_output=True,text=True,timeout=60)
    if z.returncode:raise RuntimeError(z.stderr[-300:])
   c=subprocess.run(['git','-C',str(p),'rev-parse','HEAD'],capture_output=True,text=True,timeout=20,check=True).stdout.strip();h,n,b=tree_hash(p);row.update({'status':'downloaded','commit':c,'tree_sha256':h,'file_count':n,'bytes':b})
  except Exception as e:row.update({'status':'failed','error':f'{type(e).__name__}: {e}'})
  rows.append(row);print(json.dumps({'batch_index':i,'repo':r['full_name'],'status':row['status']}),flush=True)
 return rows

def main():
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path.cwd());p.add_argument('--papers',type=int,default=100);p.add_argument('--repos',type=int,default=100);a=p.parse_args();root=a.root.resolve();base=root/'.evo/research-100x100';batch=base/'batches/batch-002';batch.mkdir(parents=True,exist_ok=True)
 oldp=base/'papers.json';oldr=base/'repository-candidates.json';papers=collect_papers(a.papers,prior_ids(oldp));priorr=set()
 try:priorr={x['full_name'] for x in json.loads((base/'repositories.json').read_text(encoding='utf-8-sig'))['repositories']}
 except:pass
 repos=collect_repos(a.repos,priorr);save_json(batch/'papers.json',{'papers':papers,'count':len(papers)});save_json(batch/'repository-candidates.json',{'repositories':repos,'count':len(repos)});rows=clone(repos,batch/'repositories');save_json(batch/'repositories.json',{'repositories':rows,'count':len(rows)});summary={'batch':2,'papers':len(papers),'repositories':len(rows),'downloaded':sum(x.get('status')=='downloaded' for x in rows),'executed':sum(bool(x.get('executed')) for x in rows),'bytes':sum(x.get('bytes',0) for x in rows),'licenses':dict(Counter(x.get('license') or 'UNKNOWN' for x in rows))};save_json(batch/'summary.json',summary);print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
