"""Optional Chromium integration check: pip install playwright, then run this file.
Start JARVIS separately on its normal loopback address before running.
"""
from pathlib import Path
import time
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':1672,'height':941},reduced_motion='reduce')
    page.set_default_timeout(8000)
    note_title='Browser smoke note '+str(time.time_ns())
    failures=[]
    page.on('pageerror',lambda e:failures.append(str(e)))
    page.goto('http://127.0.0.1:8765')
    page.get_by_text('LOCAL ONLINE',exact=True).wait_for()
    # Use only an expendable server: reset cosmetic settings for repeatability.
    page.evaluate("""async () => {
      const token=(await (await fetch('/api/session')).json()).token;
      const headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'};
      const settings=await (await fetch('/api/settings',{headers})).json();
      await fetch('/api/settings',{method:'PUT',headers,body:JSON.stringify({...settings,display_name:'',spoken:false,speech_provider:'system'})});
    }""")
    page.reload();page.get_by_text('LOCAL ONLINE',exact=True).wait_for()
    page.get_by_role('heading',name='How can I help you?').wait_for()
    shots=Path('.jarvis/screenshots');shots.mkdir(parents=True,exist_ok=True)
    page.screenshot(path=str(shots/'home.png'),full_page=True)
    page.get_by_role('button',name='My tasks',exact=True).first.click()
    page.get_by_label('New task').fill('Browser smoke task')
    page.get_by_role('button',name='Add task').click()
    page.get_by_label('Complete Browser smoke task').check()
    page.wait_for_timeout(200)
    assert page.locator('.list-row.completed').count()==1
    page.reload()
    page.get_by_text('LOCAL ONLINE',exact=True).wait_for()
    page.get_by_role('button',name='My tasks',exact=True).first.click()
    assert page.get_by_label('Complete Browser smoke task').is_checked()
    page.get_by_role('button',name='Delete',exact=True).click()
    page.get_by_role('dialog').get_by_role('button',name='Cancel').click()
    assert page.get_by_text('Browser smoke task',exact=True).count()==1
    page.get_by_role('button',name='Delete',exact=True).click()
    page.get_by_role('dialog').get_by_role('button',name='Delete').click()
    page.get_by_text('A clear mind. No tasks yet.').wait_for()
    page.get_by_role('button',name='Notes',exact=True).click()
    page.get_by_label('Note title',exact=True).fill(note_title)
    page.get_by_label('Note content',exact=True).fill('SQLite stores this note.')
    page.get_by_role('button',name='Save note',exact=True).click()
    page.get_by_role('heading',name=note_title).wait_for()
    page.get_by_role('button',name='Settings',exact=True).first.click()
    page.get_by_label('Your display name').fill('Alex')
    page.get_by_label('Speech provider',exact=True).select_option('fish')
    page.get_by_role('button',name='Save settings',exact=True).click()
    page.get_by_text('Settings saved locally.',exact=True).wait_for()
    page.get_by_role('button',name='Home',exact=True).click()
    page.get_by_role('heading',name='How can I help, Alex?').wait_for()
    page.get_by_label('Message JARVIS').fill('Hello')
    page.get_by_role('button',name='Send message',exact=True).click()
    page.locator('#messages').get_by_text('Add GEMINI_API_KEY to the backend .env file and restart JARVIS.',exact=True).wait_for()
    page.screenshot(path=str(shots/'chat-error.png'),full_page=True)
    # A transport fixture tests rendering; provider integration is separately unit-tested.
    page.route('**/api/chat',lambda route:route.fulfill(status=200,content_type='application/x-ndjson',body='{"type":"delta","text":"A browser test response."}\n{"type":"done","conversation_id":null}\n'))
    page.get_by_label('Message JARVIS').fill('Browser fixture')
    page.get_by_role('button',name='Send message',exact=True).click()
    page.get_by_text('A browser test response.',exact=True).wait_for()
    page.get_by_role('button',name='Collapse',exact=True).click()
    assert page.locator('#messages').is_hidden()
    page.get_by_role('button',name='Expand',exact=True).click()
    assert page.locator('#messages').is_visible()
    page.set_viewport_size({'width':390,'height':844})
    page.get_by_role('button',name='＋ New',exact=True).click()
    page.screenshot(path=str(shots/'mobile.png'),full_page=True)
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
    assert not failures,failures
    browser.close()
    print('Browser smoke passed: real API task persistence, confirmations, notes, settings, missing-key errors; fixture streaming; mobile overflow; no JS errors.')
