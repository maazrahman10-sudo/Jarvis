import asyncio
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault('JARVIS_DATA_DIR',str(Path(tempfile.gettempdir())/'jarvis-test-import'))
import httpx
from fastapi.testclient import TestClient
from pydantic import ValidationError
from backend.app import create_app
from backend.store import Store
from backend.models import Action, AppShortcut, Website, Settings
from backend.actions import Actions, ActionError
from backend.providers.base import ProviderError
from backend.providers.gemini import GeminiProvider
from backend.providers.speech import FishSpeech

class StoreAndTools(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'db.sqlite3';self.store=Store(self.path);self.actions=Actions(self.store)
    def tearDown(self):self.tmp.cleanup()
    def test_task_persists_across_connections(self):
        t=self.actions.execute('create_task',{'text':'Write a letter'})['task']
        self.assertEqual(Store(self.path).tasks()[0]['text'],'Write a letter')
        self.actions.execute('complete_task',{'id':t['id']})
        self.assertEqual(Store(self.path).tasks()[0]['completed'],1)
        with self.assertRaises(ActionError):self.actions.execute('delete_task',{'id':t['id']})
        self.actions.execute('delete_task',{'id':t['id']},True)
        self.assertEqual(self.store.tasks(),[])
    def test_untrusted_actions_and_arguments(self):
        for name,args in [('shell',{'command':'whoami'}),('time',{'command':'whoami'}),('open_app',{'name':'Unapproved'}),('open_website',{'name':'Unapproved'}),('complete_task',{'id':'../../file'})]:
            with self.subTest(name=name),self.assertRaises(ActionError):self.actions.execute(name,args)
    def test_urls_and_executables(self):
        for url in ['javascript:alert(1)','file:///C:/Windows','http://example.com','https://user:password@example.com','https://example.com:8888','https://example.com\\@evil.com']:
            with self.subTest(url=url),self.assertRaises(ValidationError):Website(name='bad',url=url)
        for path in ['cmd.exe','C:\\a.bat','C:\\a.exe /c whoami','\\\\server\\share\\evil.exe','C:\\a\\..\\b.exe']:
            with self.subTest(path=path),self.assertRaises(ValidationError):AppShortcut(name='bad',path=path)
        AppShortcut(name='Notepad',path='C:\\Windows\\System32\\notepad.exe')
        with self.assertRaises(ValidationError):Settings(apps=[{'name':'X','path':'C:\\x.exe'},{'name':'x','path':'C:\\y.exe'}])
    def test_notes_and_history(self):
        self.store.create_note('Idea','Keep it local')
        c=self.store.new_conversation();self.store.add_messages(c,[('user','hello'),('assistant','hi')]);self.store.rename(c,'Hello')
        self.assertEqual(self.store.conversations()[0]['title'],'Hello')
        self.store.clear_history();self.assertEqual(self.store.messages(c),[]);self.assertEqual(self.store.notes()[0]['content'],'Keep it local')
    def test_launch_failure_never_claims_success(self):
        self.store.save_settings({'apps':[{'name':'test','path':'C:\\test.exe'}]})
        with patch('backend.actions.os.name','nt'),patch('backend.actions.Path') as p,patch('backend.actions.subprocess.Popen',side_effect=OSError):
            p.return_value.is_file.return_value=True;p.return_value.suffix='.exe'
            with self.assertRaisesRegex(ActionError,'could not launch'):self.actions.execute('open_app',{'name':'test'})

class ProviderTests(unittest.IsolatedAsyncioTestCase):
    async def collect(self,p,model='configured-model'):
        return ''.join([x async for x in p.stream([{'role':'user','content':'Hello'}],model)])
    async def test_stream_and_credentials_stay_in_header(self):
        def handle(r):
            self.assertNotIn('test-key',str(r.url));self.assertEqual(r.headers['x-goog-api-key'],'test-key')
            data=json.loads(r.content);self.assertEqual(data['contents'][0]['role'],'user')
            return httpx.Response(200,text='data: {"candidates":[{"content":{"parts":[{"text":"Hello "}]}}]}\n\ndata: {"candidates":[{"content":{"parts":[{"text":"there"}]}}]}\n\n')
        self.assertEqual(await self.collect(GeminiProvider('test-key',httpx.MockTransport(handle))),'Hello there')
    async def test_error_mapping(self):
        for status,code in [(403,'credentials'),(404,'model'),(429,'rate_limit'),(503,'provider_error')]:
            with self.subTest(status=status):
                count=0
                def handle(r):
                    nonlocal count;count+=1;return httpx.Response(status,json={'error':{'message':'sensitive payload'}})
                with self.assertRaises(ProviderError) as error:await self.collect(GeminiProvider('secret',httpx.MockTransport(handle)))
                self.assertEqual(error.exception.code,code);self.assertNotIn('sensitive',str(error.exception));self.assertLessEqual(count,2)
    async def test_missing_model_key_network_and_empty(self):
        with self.assertRaises(ProviderError):await self.collect(GeminiProvider(''))
        with self.assertRaises(ProviderError):await self.collect(GeminiProvider('x'),'../../bad')
        def fail(r):raise httpx.ConnectError('contains private detail',request=r)
        with self.assertRaises(ProviderError) as error:await self.collect(GeminiProvider('x',httpx.MockTransport(fail)))
        self.assertEqual(error.exception.code,'network');self.assertNotIn('private detail',str(error.exception))
        with self.assertRaises(ProviderError):await self.collect(GeminiProvider('x',httpx.MockTransport(lambda r:httpx.Response(200,text='data: {}\n\n'))))
    async def test_fish_transport_and_rejection(self):
        with patch.dict(os.environ,{'FISH_API_KEY':'test-key'}):
            def handle(r):
                self.assertEqual(str(r.url),'https://api.fish.audio/v1/tts');self.assertEqual(r.headers['authorization'],'Bearer test-key');self.assertEqual(json.loads(r.content)['reference_id'],'voice-id')
                return httpx.Response(200,content=b'mocked-mp3',headers={'content-type':'audio/mpeg'})
            self.assertEqual(await FishSpeech(httpx.MockTransport(handle)).synthesize('Hello','voice-id'),b'mocked-mp3')
            with self.assertRaises(ProviderError):await FishSpeech(httpx.MockTransport(lambda r:httpx.Response(401))).synthesize('hi')

class FakeProvider:
    async def stream(self,messages,model):
        yield 'Hello ';yield 'from the test provider.'
class BadProvider:
    async def stream(self,messages,model):
        yield 'Partial '
        raise ProviderError('Test network failure.','network')

class APITests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.app=create_app(self.tmp.name,FakeProvider());self.client=TestClient(self.app,base_url='http://127.0.0.1:8765');self.headers={'Authorization':'Bearer '+self.client.get('/api/session').json()['token']}
    def tearDown(self):self.client.close();self.tmp.cleanup()
    def req(self,method,path,**kwargs):return self.client.request(method,'/api/'+path,headers=self.headers,**kwargs)
    def test_security_and_static(self):
        self.assertEqual(self.client.get('/api/tasks').status_code,401)
        self.assertEqual(self.client.get('/api/session',headers={'Origin':'https://evil.example'}).status_code,403)
        self.assertEqual(self.client.get('/api/session',headers={'Host':'evil.example:8765'}).status_code,400)
        self.assertEqual(self.client.get('/api/session',headers={'Sec-Fetch-Site':'cross-site'}).status_code,403)
        self.assertEqual(self.client.get('/').status_code,200)
        self.assertIn('frame-ancestors',self.client.get('/').headers['content-security-policy'])
        self.assertEqual(self.client.get('/assets/app.js').status_code,200)
        self.assertEqual(self.req('POST','actions',json={'name':'shell','arguments':{}}).status_code,422)
    def test_tasks_notes_stats_and_confirmation(self):
        t=self.req('POST','tasks',json={'text':'Test persistence'}).json()
        self.assertEqual(self.req('GET','tasks').json()[0]['id'],t['id'])
        self.assertEqual(self.req('PATCH','tasks/'+t['id'],json={'completed':True}).status_code,200)
        self.assertEqual(self.req('DELETE','tasks/'+t['id'],json={}).status_code,422)
        self.assertEqual(self.req('DELETE','tasks/'+t['id'],json={'confirmed':True}).status_code,200)
        self.assertEqual(self.req('POST','notes',json={'title':'Test','content':'Local only'}).status_code,200)
        self.assertEqual(self.req('GET','notes').json()[0]['content'],'Local only')
        stats=self.req('GET','stats').json();self.assertTrue(0<=stats['cpu']<=100);self.assertTrue(0<stats['memory']<=100)
    def test_completed_conversation_and_history_off(self):
        r=self.req('POST','chat',json={'text':'Hello'});events=[json.loads(x) for x in r.text.splitlines()]
        self.assertEqual([x['type'] for x in events],['delta','delta','done'])
        ident=events[-1]['conversation_id'];self.assertEqual(len(self.req('GET','conversations/'+ident).json()),2)
        self.assertEqual(self.req('PATCH','conversations/'+ident,json={'title':'Renamed'}).status_code,200)
        settings=self.req('GET','settings').json();settings['history']=False;self.assertEqual(self.req('PUT','settings',json=settings).status_code,200)
        events=[json.loads(x) for x in self.req('POST','chat',json={'text':'Private session'}).text.splitlines()]
        self.assertIsNone(events[-1]['conversation_id']);self.assertEqual(len(self.req('GET','conversations').json()),1)
        self.req('DELETE','conversations',json={'confirmed':True});self.assertEqual(self.req('GET','conversations').json(),[])
    def test_partial_error_does_not_persist(self):
        app=create_app(self.tmp.name,BadProvider())
        with TestClient(app,base_url='http://localhost:8765') as client:
            h={'Authorization':'Bearer '+app.state.token}
            events=[json.loads(x) for x in client.post('/api/chat',headers=h,json={'text':'Fail'}).text.splitlines()]
            self.assertEqual(events[-1]['type'],'error');self.assertEqual(app.state.store.conversations(),[])
    def test_no_secret_in_health_or_settings(self):
        with patch.dict(os.environ,{'GEMINI_API_KEY':'private-test-key','FISH_API_KEY':'private-voice-key'}):
            data=self.req('GET','health').text+self.req('GET','settings').text
            self.assertNotIn('private-test-key',data);self.assertNotIn('private-voice-key',data)
    def test_oversized_request(self):
        r=self.req('POST','tasks',content='x'*1_000_001)
        self.assertEqual(r.status_code,413)


class StreamingLifecycle(unittest.IsolatedAsyncioTestCase):
    async def test_cancel_releases_lock_and_discards_partial(self):
        started=asyncio.Event()
        class Slow:
            async def stream(self,messages,model):
                yield 'Not completed.'
                started.set()
                await asyncio.sleep(60)
        with tempfile.TemporaryDirectory() as directory:
            app=create_app(directory,Slow())
            headers={'Authorization':'Bearer '+app.state.token}
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://127.0.0.1:8765',headers=headers) as client:
                task=asyncio.create_task(client.post('/api/chat',json={'text':'Wait'}))
                await asyncio.wait_for(started.wait(),3)
                busy=await client.post('/api/chat',json={'text':'Second'})
                self.assertEqual(busy.status_code,409)
                task.cancel()
                with self.assertRaises(asyncio.CancelledError):await task
                self.assertEqual(app.state.store.conversations(),[])
                # A following request reaches the provider (not a leaked 409 lock).
                started.clear()
                task=asyncio.create_task(client.post('/api/chat',json={'text':'After cancel'}))
                await asyncio.wait_for(started.wait(),3)
                task.cancel()
                with self.assertRaises(asyncio.CancelledError):await task

if __name__=='__main__':unittest.main()
