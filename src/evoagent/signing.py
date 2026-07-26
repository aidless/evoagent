import json,base64
from datetime import datetime,timezone
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey,Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding,PrivateFormat,PublicFormat,NoEncryption
def canonical_payload(bundle_id,bundle_sha256,signer,signed_at,expires_at):return json.dumps({'bundle_id':bundle_id,'bundle_sha256':bundle_sha256,'signer':signer,'signed_at':signed_at,'expires_at':expires_at},sort_keys=True,separators=(',',':')).encode()
def generate_keypair():
 k=Ed25519PrivateKey.generate()
 return k.private_bytes(Encoding.Raw,PrivateFormat.Raw,NoEncryption()),k.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)
def sign_bundle(bundle,private_key,signer,expires_at,signed_at=None):
 signed_at=signed_at or datetime.now(timezone.utc).isoformat()
 payload=canonical_payload(bundle['bundle_id'],bundle['sha256'],signer,signed_at,expires_at)
 sig=Ed25519PrivateKey.from_private_bytes(private_key).sign(payload)
 return {'bundle_id':bundle['bundle_id'],'bundle_sha256':bundle['sha256'],'signer':signer,'signed_at':signed_at,'expires_at':expires_at,'signature':base64.b64encode(sig).decode(),'algorithm':'Ed25519'}
def verify_envelope(envelope,bundle,trusted_keys,now=None):
 if envelope is None: return {'valid':False,'reason':'missing_signature'}
 if envelope.get('algorithm')!='Ed25519': return {'valid':False,'reason':'unsupported_algorithm'}
 if envelope.get('bundle_id')!=bundle.get('bundle_id') or envelope.get('bundle_sha256')!=bundle.get('sha256'): return {'valid':False,'reason':'bundle_mismatch'}
 key=trusted_keys.get(envelope.get('signer'))
 if not key: return {'valid':False,'reason':'untrusted_signer'}
 try:
  now=now or datetime.now(timezone.utc)
  ex=datetime.fromisoformat(envelope['expires_at'])
  ex=ex if ex.tzinfo else ex.replace(tzinfo=timezone.utc)
  if now>ex: return {'valid':False,'reason':'signature_expired'}
  payload=canonical_payload(envelope['bundle_id'],envelope['bundle_sha256'],envelope['signer'],envelope['signed_at'],envelope['expires_at'])
  Ed25519PublicKey.from_public_bytes(key).verify(base64.b64decode(envelope['signature']),payload)
  return {'valid':True,'reason':'ok','signer':envelope['signer'],'expires_at':envelope['expires_at']}
 except Exception: return {'valid':False,'reason':'invalid_signature'}
class SignatureRegistry:
 def __init__(self,path,trusted_keys):
  self.path=path
  self.trusted_keys=trusted_keys
  self.data=json.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else {'signatures':{}, 'history':[]}
 def _save(self):
  self.path.parent.mkdir(parents=True,exist_ok=True)
  tmp=self.path.with_suffix('.tmp')
  tmp.write_text(json.dumps(self.data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
  tmp.replace(self.path)
 def add(self,envelope,bundle):
  v=verify_envelope(envelope,bundle,self.trusted_keys)
  if not v['valid']: raise ValueError('signature rejected: '+v['reason'])
  self.data['signatures'][envelope['bundle_id']]={'envelope':envelope,'bundle_sha256':bundle['sha256']}
  self.data['history'].append({'action':'add','bundle_id':envelope['bundle_id'],'signer':envelope['signer'],'at':datetime.now(timezone.utc).isoformat()})
  self._save()
 def verify(self,bundle):
  rec=self.data['signatures'].get(bundle['bundle_id'])
  return verify_envelope(rec['envelope'] if rec else None,bundle,self.trusted_keys)
 def audit(self):
  rows=[]
  for bid,rec in (self.data.get('signatures') or {}).items():
   if isinstance(rec,dict) and 'envelope' in rec: env=rec['envelope']
   elif isinstance(rec,dict) and 'signer' in rec: env=rec
   else: env=rec
   expired=False
   try:
    ex=datetime.fromisoformat(env['expires_at'])
    ex=ex if ex.tzinfo else ex.replace(tzinfo=timezone.utc)
    expired=datetime.now(timezone.utc)>ex
   except Exception: expired=None
   rows.append({'bundle_id':bid,'signer':env.get('signer'),'signed_at':env.get('signed_at'),'expires_at':env.get('expires_at'),'expired':expired,'signed_by_trusted_key':env.get('signer') in self.trusted_keys})
  return {'trusted_signers':sorted(self.trusted_keys),'signatures':rows,'history':self.data.get('history',[])}
