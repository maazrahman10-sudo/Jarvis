"""Explicit tools only. No shell, arbitrary commands, or model-triggered execution."""
import os
import subprocess
import webbrowser
from datetime import datetime
from pathlib import Path
from pydantic import ValidationError
from .models import Strict, Text, Note
from pydantic import Field

class Named(Strict):
    name: str = Field(min_length=1,max_length=60)
class Ident(Strict):
    id: str = Field(pattern=r'^[a-f0-9]{32}$')
class Empty(Strict):
    pass

TOOL_DEFINITIONS = {
    'open_app': Named, 'open_website':Named, 'search':Text, 'time':Empty,
    'create_task':Text, 'list_tasks':Empty, 'complete_task':Ident,
    'delete_task':Ident, 'create_note':Note, 'list_notes':Empty,
}
class ActionError(Exception):
    pass

class Actions:
    def __init__(self,store):
        self.store=store
    def execute(self,name,args,confirmed=False):
        if name not in TOOL_DEFINITIONS:
            raise ActionError('This action is not supported.')
        try:
            a=TOOL_DEFINITIONS[name](**args)
        except (ValidationError,TypeError):
            raise ActionError('Invalid action arguments.') from None
        if name=='time':
            return {'message':datetime.now().astimezone().strftime('%A, %d %B %Y · %I:%M %p %Z')}
        if name=='list_tasks': return {'tasks':self.store.tasks()}
        if name=='create_task': return {'task':self.store.create_task(a.text),'message':'Task created.'}
        if name in ('complete_task','delete_task'):
            if name=='delete_task' and not confirmed: raise ActionError('Confirm deletion in JARVIS first.')
            if not self.store.task_action(a.id, delete=name=='delete_task'): raise ActionError('Task not found.')
            return {'message':'Task deleted.' if name=='delete_task' else 'Task completed.'}
        if name=='create_note': return {'note':self.store.create_note(a.title,a.content),'message':'Note saved locally.'}
        if name=='list_notes': return {'notes':self.store.notes()}
        if name=='open_app':
            shortcut=next((x for x in self.store.settings()['apps'] if x['name']==a.name),None)
            if not shortcut: raise ActionError('Application is not in your approved shortcuts.')
            if os.name!='nt': raise ActionError('Opening Windows apps is available only on your Windows PC.')
            path=Path(shortcut['path'])
            if not path.is_file() or path.suffix.lower()!='.exe': raise ActionError('The approved executable does not exist.')
            try:
                process=subprocess.Popen([str(path)],shell=False,cwd=str(path.parent))
                # Report only dispatch; process creation does not prove the window opened.
                return {'message':f'Launch request sent to {a.name}.', 'pid':process.pid}
            except OSError:
                raise ActionError('Windows could not launch that application. Check its path and permissions.') from None
        if name=='open_website':
            shortcut=next((x for x in self.store.settings()['websites'] if x['name']==a.name),None)
            if not shortcut: raise ActionError('Website is not approved in Settings.')
            url=shortcut['url']
        else:
            from urllib.parse import urlencode
            url='https://www.google.com/search?'+urlencode({'q':a.text})
        if os.name!='nt': raise ActionError('Browser actions run on the Windows PC hosting JARVIS.')
        try:
            opened=webbrowser.open(url,new=2)
        except (OSError,webbrowser.Error):
            opened=False
        if not opened: raise ActionError('Windows did not accept the browser request. Check your default browser.')
        return {'message':'Browser request accepted. JARVIS has not read the page or search results.'}
