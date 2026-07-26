from __future__ import annotations
import calendar,re
from datetime import date,timedelta
from itertools import permutations

MONTHS={m.lower():i for i,m in enumerate(calendar.month_name) if m}
MONTHS.update({m.lower():i for i,m in enumerate(calendar.month_abbr) if m})
def options(text): return {k:v.strip() for k,v in re.findall(r'\(([A-F])\)\s*([^\n]+)',text)}
def parse_date(s):
 m=re.search(r'\b(\d{1,2})/(\d{1,2})/(\d{4})\b',s)
 if m:return date(int(m[3]),int(m[1]),int(m[2]))
 m=re.search(r'\b('+ '|'.join(MONTHS) +r')\s+(\d{1,2}),\s*(\d{4})',s,re.I)
 if m:return date(int(m[3]),MONTHS[m[1].lower()],int(m[2]))
def add_months(d,n):
 x=d.month-1+n;y=d.year+x//12;m=x%12+1;return date(y,m,min(d.day,calendar.monthrange(y,m)[1]))
def solve_date(text):
 first=text.split('Options:')[0]
 # Refuse derived-date narratives until their full causal chain is implemented.
 if re.search(r'anniversary|days? have passed|days? away from now|ran out of|visits? the|coming in \d+ hours|actually \w+ years? ago',first,re.I): return None
 holiday=re.search(r'Christmas Eve of (\d{4})',first,re.I)
 if holiday: d=date(int(holiday.group(1)),12,24)
 else: d=None
 # Resolve explicit disagreement when the prompt identifies who is correct.
 cm=re.search(r'John thinks today is ([^,.]+(?:/\d{4})?).*John is correct',first,re.I)
 d=d or (parse_date(cm.group(1)) if cm else parse_date(first))
 if not d:return None
 if re.search(r'delayed by one day to today',first,re.I):d+=timedelta(days=1)
 elif re.search(r'(?:The )?day before yesterday was',first,re.I):d+=timedelta(days=2)
 elif re.search(r'Yesterday(?: was|,)',first,re.I):d+=timedelta(days=1)
 elif re.search(r'Tomorrow (?:will be|is)',first,re.I) or re.search(r'(?:for )?tomorrow\s*[,\(]',first,re.I):d-=timedelta(days=1)
 q=first[first.rfind('?')+1:] if '?' in first else first
 # Use the final question sentence instead of setup statements.
 qm=re.findall(r'(?:What|Which)[^?]+\?',first,re.I); q=qm[-1] if qm else first
 m=re.search(r'(\d+)\s*hours?\s+(later|after|before|earlier)',q,re.I)
 if m:d+=timedelta(hours=int(m[1])*(1 if m[2].lower() in ('later','after') else -1))
 if re.search(r'\bdate yesterday\b',q,re.I): d-=timedelta(days=1)
 if re.search(r'\bdate tomorrow\b',q,re.I): d+=timedelta(days=1)
 m=re.search(r'(?:(\d+)|a|one)\s+(day|week|month|year)s?\s+(ago|before|later|after|from today)',q,re.I)
 if m:
  n=int(m[1] or 1); sign=-1 if m[3].lower() in ('ago','before') else 1;unit=m[2].lower()
  if unit=='day':d+=timedelta(days=sign*n)
  elif unit=='week':d+=timedelta(weeks=sign*n)
  elif unit=='month':d=add_months(d,sign*n)
  else:d=add_months(d,sign*12*n)
 val=d.strftime('%m/%d/%Y')
 return next((k for k,v in options(text).items() if val in v),None)

def solve_logic(text):
 opts=options(text); names=[]
 for v in opts.values():
  m=re.match(r'(?:The )?(.+?) (?:(?:is|are) the|finished) ',v,re.I)
  if m and m.group(1).lower() not in [x.lower() for x in names]:names.append(m.group(1))
 if len(names)!=5:return None
 idx={n.lower():n for n in names}; constraints=[]; body=text.split('Options:')[0]
 def find(raw):
  r=raw.lower().strip();return next((n for k,n in idx.items() if k==r or k.rstrip('s')==r.rstrip('s')),None)
 # Comparative order: cheaper/older/left means smaller rank; expensive/newer/right means larger.
 pat=r'The ([^.]+?) (?:is|are) (more expensive|less expensive|newer|older) than (?:the )?([^.]+?)[.]'
 for a,rel,b in re.findall(pat,body,re.I):
  aa,bb=find(a),find(b)
  if aa and bb:constraints.append(('lt' if rel.lower() in ('less expensive','older','to the left of') else 'gt',aa,bb))
 # Spatial ordering relations.
 for a,rel,b in re.findall(r'The ([^.]+?) (?:is|are) (to the left of|to the right of) (?:the )?([^.]+?)[.]',body,re.I):
  aa,bb=find(a),find(b)
  if aa and bb: constraints.append(('lt' if 'left' in rel.lower() else 'gt',aa,bb))
 # Tournament ranking relations (above/below correspond to better/worse rank).
 for a,rel,b in re.findall(r'([A-Za-z][A-Za-z ]*?) finished (above|below) ([A-Za-z][A-Za-z ]*?)[.]',body,re.I):
  aa,bb=find(a),find(b)
  if aa and bb: constraints.append(('lt' if rel.lower()=='above' else 'gt',aa,bb))
 # Handle "X are more expensive than Y" captured above and fixed ordinal statements.
 ords={'cheapest':0,'oldest':0,'leftmost':0,'newest':4,'most expensive':4,'rightmost':4,'second-cheapest':1,'second-oldest':1,'second from the left':1,'second-most expensive':3,'second-newest':3,'second from the right':3,'third-most expensive':2,'third from the left':2,'third-newest':2,'third-oldest':2,'first':0,'last':4,'second-to-last':3,'second':1,'third':2,'fourth':3}
 for n in names:
  for label,pos in ords.items():
   if re.search(r'(?:The )?'+re.escape(n)+r' (?:(?:is|are) the|finished) '+re.escape(label)+r'(?![-\w])',body,re.I):constraints.append(('eq',n,pos))
 valid=[]
 for perm in permutations(names):
  pos={n:i for i,n in enumerate(perm)};ok=True
  for c in constraints:
   if c[0]=='eq':ok &= pos[c[1]]==c[2]
   elif c[0]=='lt':ok &= pos[c[1]]<pos[c[2]]
   else:ok &= pos[c[1]]>pos[c[2]]
  if ok:valid.append(pos)
 if not valid:return None
 for k,v in opts.items():
  m=re.match(r'(?:The )?(.+?) (?:(?:is|are) the|finished) (.+)',v,re.I)
  if not m:continue
  n=find(m[1]);label=m[2].strip().lower();target=ords.get(label)
  if n and target is not None and all(p[n]==target for p in valid):return k
 return None


