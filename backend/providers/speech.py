"""Optional Fish Audio REST adapter. Credentials stay in the backend."""
import os
import httpx
from .base import ProviderError

class FishSpeech:
    def __init__(self, transport=None):
        self.transport=transport
    async def synthesize(self,text,reference_id=''):
        key=os.getenv('FISH_API_KEY','')
        if not key: raise ProviderError('Set FISH_API_KEY in the backend .env file and restart JARVIS.','credentials')
        body={'text':text,'format':'mp3'}
        reference=reference_id or os.getenv('FISH_REFERENCE_ID','')
        if reference: body['reference_id']=reference
        headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'}
        if os.getenv('FISH_MODEL'): headers['model']=os.environ['FISH_MODEL']
        async with httpx.AsyncClient(timeout=httpx.Timeout(60,connect=10),transport=self.transport) as client:
            try:
                async with client.stream('POST','https://api.fish.audio/v1/tts',json=body,headers=headers) as r:
                    if r.status_code in (401,403): raise ProviderError('Fish Audio rejected the key or permissions.','credentials')
                    if r.status_code==429: raise ProviderError('Fish Audio quota or rate limit reached.','rate_limit')
                    if r.status_code>=400: raise ProviderError('Fish Audio rejected speech synthesis. Check the voice reference, model, and account.','voice')
                    if not r.headers.get('content-type','').split(';')[0] in ('audio/mpeg','audio/mp3','application/octet-stream'):
                        raise ProviderError('Fish Audio did not return an MP3 response.','voice')
                    audio=bytearray()
                    async for chunk in r.aiter_bytes():
                        audio.extend(chunk)
                        if len(audio)>15_000_000: raise ProviderError('Speech response exceeded the local size limit.','voice')
                    if not audio: raise ProviderError('Fish Audio returned empty audio.','voice')
                    return bytes(audio)
            except httpx.TimeoutException:
                raise ProviderError('Fish Audio timed out. Try system voices or retry later.','timeout') from None
            except httpx.RequestError:
                raise ProviderError('Cannot reach Fish Audio. Check internet access or use system voices.','network') from None
