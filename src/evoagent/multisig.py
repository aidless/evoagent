import base64
from datetime import datetime,timezone
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from .signing import canonical_payload
def verify_envelope(envelope,bundle,trusted_keys,now=None):
 if envelope is None:return {'valid':False,'reason':'missing_signature'}
 if envelope.get('algorithm')!='Ed25519':return {'valid':False,'reason':'unsupported_algorithm'}
 if envelope.get('bundle_id')!=bundle.get('bundle_id') or envelope.get('bundle_sha256')!=bundle.get('sha256'):return {'valid':False,'reason':'bundle_mismatch'}
 key=trusted_keys.get(envelope.get('signer'))
 if not key:return {'valid':False,'reason':'untrusted_signer'}
 try:
  now=now or datetime.now(timezone.utc);ex=datetime.fromisoformat(envelope['expires_at']);ex=ex if ex.tzinfo else ex.replace(tzinfo=timezone.utc)
  if now>ex:return {'valid':False,'reason':'signature_expired'}
  payload=canonical_payload(envelope['bundle_id'],envelope['bundle_sha256'],envelope['signer'],envelope['signed_at'],envelope['expires_at']);Ed25519PublicKey.from_public_bytes(key).verify(base64.b64decode(envelope['signature']),payload);return {'valid':True,'reason':'ok','signer':envelope['signer']}
 except Exception:return {'valid':False,'reason':'invalid_signature'}
def verify_multisig(envelopes,bundle,trusted_keys,required_signers,now=None):
 if not envelopes:return {'valid':False,'reason':'no_envelopes','verified':[]}
 results=[(e.get('signer'),verify_envelope(e,bundle,trusted_keys,now)) for e in envelopes]
 valid_sigs=set(s for s,r in results if r['valid'])
 if not set(required_signers).issubset(valid_sigs):return {'valid':False,'reason':'required_signers_missing','verified':results,'unique_signers':sorted(valid_sigs)}
 return {'valid':True,'reason':'ok','verified':results,'unique_signers':sorted(valid_sigs),'valid_count':len(valid_sigs)}
