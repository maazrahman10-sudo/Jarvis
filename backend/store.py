"""Small transactional SQLite store. Secrets never enter this database."""
import json
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path

DEFAULTS = {'display_name': '', 'provider': 'gemini', 'model': '', 'spoken': True,
            'speech_provider': 'system', 'fish_reference_id': '', 'voice': '', 'rate': 1.0, 'microphone': '', 'speaker': '', 'history': True,
            'apps': [], 'websites': [ {'name': 'Google', 'url': 'https://www.google.com'},
                                      {'name': 'YouTube', 'url': 'https://www.youtube.com'}]}

class Store:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.db() as c:
            c.executescript('''
            CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS conversations (id TEXT PRIMARY KEY, title TEXT NOT NULL, created TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY, conversation_id TEXT REFERENCES conversations(id) ON DELETE CASCADE, role TEXT NOT NULL, content TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS tasks (id TEXT PRIMARY KEY, text TEXT NOT NULL, completed INTEGER DEFAULT 0);
            CREATE TABLE IF NOT EXISTS notes (id TEXT PRIMARY KEY, title TEXT NOT NULL, content TEXT NOT NULL, created TEXT DEFAULT CURRENT_TIMESTAMP);
            ''')
    @contextmanager
    def db(self):
        c = sqlite3.connect(self.path, timeout=10)
        c.row_factory = sqlite3.Row
        c.execute('PRAGMA foreign_keys=ON')
        try:
            with c:
                yield c
        finally:
            c.close()
    def settings(self):
        with self.db() as c:
            return {**DEFAULTS, **{r['key']: json.loads(r['value']) for r in c.execute('SELECT * FROM settings')}}
    def save_settings(self, values):
        with self.db() as c:
            c.executemany('INSERT OR REPLACE INTO settings VALUES (?,?)', [(k,json.dumps(v)) for k,v in values.items()])
    def conversations(self):
        with self.db() as c:
            return [dict(r) for r in c.execute('SELECT * FROM conversations ORDER BY created DESC, rowid DESC')]
    def new_conversation(self, title='New conversation'):
        ident = uuid.uuid4().hex
        with self.db() as c:
            c.execute('INSERT INTO conversations(id,title) VALUES (?,?)', (ident,title[:100]))
        return ident
    def messages(self, ident):
        with self.db() as c:
            return [dict(r) for r in c.execute('SELECT role,content FROM messages WHERE conversation_id=? ORDER BY id', (ident,))]
    def add_messages(self, ident, pairs):
        with self.db() as c:
            c.executemany('INSERT INTO messages(conversation_id,role,content) VALUES (?,?,?)', [(ident,r,t) for r,t in pairs])
    def rename(self, ident, title):
        with self.db() as c:
            return c.execute('UPDATE conversations SET title=? WHERE id=?', (title,ident)).rowcount
    def delete_conversation(self, ident):
        with self.db() as c:
            c.execute('DELETE FROM conversations WHERE id=?', (ident,))
    def clear_history(self):
        with self.db() as c:
            c.execute('DELETE FROM conversations')
    def tasks(self):
        with self.db() as c:
            return [dict(r) for r in c.execute('SELECT * FROM tasks ORDER BY rowid DESC')]
    def create_task(self, text):
        ident = uuid.uuid4().hex
        with self.db() as c:
            c.execute('INSERT INTO tasks(id,text) VALUES (?,?)',(ident,text))
        return {'id':ident,'text':text,'completed':0}
    def task_action(self, ident, delete=False, completed=True):
        with self.db() as c:
            if delete:
                return c.execute('DELETE FROM tasks WHERE id=?', (ident,)).rowcount
            return c.execute('UPDATE tasks SET completed=? WHERE id=?', (completed,ident)).rowcount
    def notes(self):
        with self.db() as c:
            return [dict(r) for r in c.execute('SELECT * FROM notes ORDER BY rowid DESC')]
    def create_note(self, title, content):
        ident = uuid.uuid4().hex
        with self.db() as c:
            c.execute('INSERT INTO notes(id,title,content) VALUES (?,?,?)', (ident,title,content))
        return {'id':ident,'title':title,'content':content}
