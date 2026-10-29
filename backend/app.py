import asyncio
import json
import os
import secrets
import time
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse, Response
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
import psutil
from .store import Store
from .models import Settings, Chat, Text, Note, Rename, TaskUpdate, Confirmation, Action, SpeechRequest
from .actions import Actions, ActionError, TOOL_DEFINITIONS
from .providers.gemini import GeminiProvider
from .providers.base import ProviderError
from .providers.speech import FishSpeech

ROOT=Path(__file__).resolve().parent.parent
load_dotenv(ROOT/'.env')

def create_app(data_dir=None, provider=None):
    store=Store(Path(data_dir or os.getenv('JARVIS_DATA_DIR', Path.home()/'.jarvis'))/'jarvis.sqlite3')
    actions=Actions(store)
    token=secrets.token_urlsafe(32)
    busy=asyncio.Lock()
    app=FastAPI(docs_url=None,redoc_url=None,openapi_url=None)
    app.state.store=store
    app.state.token=token
    ai=provider or GeminiProvider(os.getenv('GEMINI_API_KEY',''))
    allowed_hosts={'127.0.0.1:8765','localhost:8765'}
    allowed_origins={'http://127.0.0.1:8765','http://localhost:8765'}

    @app.middleware('http')
    async def local_security(request: Request, call_next):
        if request.headers.get('host') not in allowed_hosts:
            return JSONResponse({'detail':'Invalid local host.'},400)
        origin=request.headers.get('origin')
        if (origin and origin not in allowed_origins) or request.headers.get('sec-fetch-site')=='cross-site':
            return JSONResponse({'detail':'Cross-origin requests are blocked.'},403)
        if request.url.path.startswith('/api/') and request.url.path not in ('/api/session','/api/health'):
            if not secrets.compare_digest(request.headers.get('authorization',''),f'Bearer {token}'):
                return JSONResponse({'detail':'Local session expired. Reload JARVIS.'},401)
        # Require a bounded fixed-length JSON request (the browser sets this header).
        # Do not consume the stream in BaseHTTPMiddleware: it must remain available
        # to FastAPI's validated body parser and the streaming disconnect handler.
        if request.method in ('POST','PUT','PATCH','DELETE'):
            try:
                length=int(request.headers.get('content-length','-1'))
            except ValueError:
                length=-1
            if length<0 or request.headers.get('transfer-encoding'):
                return JSONResponse({'detail':'A fixed Content-Length is required.'},411)
            if length>1_000_000:
                return JSONResponse({'detail':'Request is too large.'},413)
        response=await call_next(request)
        response.headers['Cache-Control']='no-store'
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Referrer-Policy']='no-referrer'
        response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; media-src 'self' blob:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        return response

    @app.exception_handler(ActionError)
    async def action_error(request, exc): return JSONResponse({'detail':str(exc)},400)

    @app.get('/api/session')
    def session(): return {'token':token}
    @app.get('/api/health')
    def health():
        settings=store.settings()
        return {'backend':'connected','provider':'gemini','credentials_configured':bool(os.getenv('GEMINI_API_KEY')),
                'fish_configured':bool(os.getenv('FISH_API_KEY')), 'model':settings['model'] or os.getenv('GEMINI_MODEL',''), 'desktop_available':os.name=='nt',
                'cloud_notice':'Chat text is sent to Google Gemini. Audio recognition may use your browser’s speech service.'}
    @app.post('/api/speech')
    async def speech(value:SpeechRequest):
        try:
            audio=await FishSpeech().synthesize(value.text,value.reference_id)
            return Response(audio,media_type='audio/mpeg')
        except ProviderError as exc:
            return JSONResponse({'detail':str(exc)},502)

    @app.get('/api/stats')
    def stats(): return {'cpu':psutil.cpu_percent(interval=.1),'memory':psutil.virtual_memory().percent}
    @app.get('/api/settings')
    def settings(): return store.settings()
    @app.put('/api/settings')
    def save_settings(value:Settings):
        store.save_settings(value.model_dump())
        return store.settings()
    @app.get('/api/tools')
    def tools(): return {k:v.model_json_schema() for k,v in TOOL_DEFINITIONS.items()}
    @app.post('/api/actions')
    def execute(value:Action): return actions.execute(value.name,value.arguments,value.confirmed)
    @app.get('/api/tasks')
    def tasks(): return store.tasks()
    @app.post('/api/tasks')
    def task(value:Text): return store.create_task(value.text)
    @app.patch('/api/tasks/{ident}')
    def task_update(ident:str,value:TaskUpdate):
        if not store.task_action(ident,completed=value.completed): raise HTTPException(404,'Task not found.')
        return {'ok':True}
    @app.delete('/api/tasks/{ident}')
    def task_delete(ident:str,value:Confirmation):
        return actions.execute('delete_task',{'id':ident},value.confirmed)
    @app.get('/api/notes')
    def notes(): return store.notes()
    @app.post('/api/notes')
    def note(value:Note): return store.create_note(value.title,value.content)
    @app.get('/api/conversations')
    def conversations(): return store.conversations()
    @app.get('/api/conversations/{ident}')
    def messages(ident:str): return store.messages(ident)
    @app.patch('/api/conversations/{ident}')
    def rename(ident:str,value:Rename):
        if not store.rename(ident,value.title): raise HTTPException(404,'Conversation not found.')
        return {'ok':True}
    @app.delete('/api/conversations/{ident}')
    def delete_conversation(ident:str,value:Confirmation):
        store.delete_conversation(ident)
        return {'ok':True}
    @app.delete('/api/conversations')
    async def clear_history(value:Confirmation):
        if busy.locked(): raise HTTPException(409,'Stop generation before clearing history.')
        store.clear_history()
        return {'ok':True}
    @app.post('/api/chat')
    async def chat(value:Chat,request:Request):
        if busy.locked(): raise HTTPException(409,'A response is already generating. Stop it first.')
        await busy.acquire()
        settings=store.settings()
        ident=value.conversation_id if settings['history'] else None
        if ident and not any(c['id']==ident for c in store.conversations()):
            busy.release()
            raise HTTPException(404,'Conversation not found. Start a new conversation.')
        context=store.messages(ident)[-40:] if ident else value.context
        context=[*context,{'role':'user','content':value.text}]
        model=settings['model'] or os.getenv('GEMINI_MODEL','')
        async def events():
            nonlocal ident
            output=''
            def event(kind,**data): return json.dumps({'type':kind,**data})+'\n'
            try:
                async with asyncio.timeout(120):
                    async for piece in ai.stream(context,model):
                        output+=piece
                        if len(output)>100000: raise ProviderError('Response exceeded the local length limit.')
                        yield event('delta',text=piece)
                # Only completed responses enter history. Cancellation and failures never persist partial exchanges.
                if settings['history']:
                    if not ident: ident=store.new_conversation(value.text[:60])
                    store.add_messages(ident,[('user',value.text),('assistant',output)])
                yield event('done',conversation_id=ident)
            except ProviderError as exc:
                yield event('error',message=str(exc),code=exc.code)
            except TimeoutError:
                yield event('error',message='Response exceeded two minutes. Try a shorter request.',code='timeout')
            except asyncio.CancelledError:
                raise
            except Exception:
                # Never expose HTTP payloads, API headers, or tracebacks in UI/logs.
                yield event('error',message='The response could not be completed. Please retry.',code='internal')
            finally:
                busy.release()
        return StreamingResponse(events(),media_type='application/x-ndjson',headers={'X-Accel-Buffering':'no'})
    app.mount('/assets',StaticFiles(directory=ROOT/'frontend'),name='assets')
    @app.get('/')
    def index(): return FileResponse(ROOT/'frontend'/'index.html')
    return app

app=create_app()
