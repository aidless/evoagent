import json
from datetime import datetime,timezone
from pathlib import Path
def audit(self):
  rows=[]
  for bid,rec in (self.data.get('signatures') or {}).items():
   if isinstance(rec,dict) and 'envelope' in rec:env=rec['envelope']
   elif isinstance(rec,dict) and 'signer' in rec:env=rec
   else:env=rec
   expired=False
   try:ex=datetime.fromisoformat(env['expires_at']);ex=ex if ex.tzinfo else ex.replace(tzinfo=timezone.utc);expired=datetime.now(timezone.utc)>ex
   except Exception:expired=None
   rows.append({'bundle_id':bid,'signer':env.get('signer'),'signed_at':env.get('signed_at'),'expires_at':env.get('expires_at'),'expired':expired,'signed_by_trusted_key':env.get('signer') in self.trusted_keys})
  return {'trusted_signers':sorted(self.trusted_keys),'signatures':rows,'history':self.data.get('history',[])}
