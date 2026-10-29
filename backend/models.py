import re
from typing import Literal
from urllib.parse import urlsplit
from pathlib import PureWindowsPath
from pydantic import BaseModel, ConfigDict, Field, field_validator

class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)

class AppShortcut(Strict):
    name: str = Field(min_length=1,max_length=60)
    path: str = Field(min_length=1,max_length=500)
    @field_validator('path')
    @classmethod
    def valid_path(cls, value):
        p = PureWindowsPath(value)
        if not p.is_absolute() or p.drive.startswith('\\\\') or p.suffix.lower() != '.exe' or '..' in p.parts or '%' in value:
            raise ValueError('Use a full local Windows .exe path without arguments, variables, or parent traversal.')
        return value

class Website(Strict):
    name: str = Field(min_length=1,max_length=60)
    url: str = Field(max_length=2048)
    @field_validator('url')
    @classmethod
    def valid_url(cls, value):
        u = urlsplit(value)
        if u.scheme != 'https' or not u.hostname or u.username or u.password or u.port not in (None,443) or any(ord(c)<33 for c in value) or '\\' in value:
            raise ValueError('Use an HTTPS URL without credentials or custom ports.')
        return value

class Settings(Strict):
    display_name: str = Field(default='',max_length=60)
    provider: Literal['gemini'] = 'gemini'
    model: str = Field(default='',max_length=100)
    speech_provider: Literal['system','fish'] = 'system'
    fish_reference_id: str = Field(default='',max_length=100,pattern=r'^[A-Za-z0-9_-]*$')
    spoken: bool = True
    voice: str = Field(default='',max_length=300)
    rate: float = Field(default=1,ge=.5,le=2)
    microphone: str = Field(default='',max_length=300)
    speaker: str = Field(default='',max_length=300)
    history: bool = True
    apps: list[AppShortcut] = Field(default_factory=list,max_length=30)
    websites: list[Website] = Field(default_factory=list,max_length=30)
    @field_validator('model')
    @classmethod
    def model_id(cls,v):
        if v and not re.fullmatch(r'[A-Za-z0-9._-]+',v):
            raise ValueError('Enter a model ID, not a URL.')
        return v
    @field_validator('apps','websites')
    @classmethod
    def unique_names(cls,v):
        names=[x.name.casefold() for x in v]
        if len(names)!=len(set(names)):
            raise ValueError('Shortcut names must be unique.')
        return v

class Chat(Strict):
    text: str = Field(min_length=1,max_length=12000)
    conversation_id: str | None = Field(default=None,pattern=r'^[a-f0-9]{32}$')
    # Only used when history is off; bounded, validated, never written to disk.
    context: list[dict[Literal['role','content'],str]] = Field(default_factory=list,max_length=40)
    @field_validator('context')
    @classmethod
    def valid_context(cls,v):
        for m in v:
            if set(m)!= {'role','content'} or m['role'] not in ('user','assistant') or len(m['content'])>16000:
                raise ValueError('Invalid chat context.')
        return v

class Text(Strict):
    text: str = Field(min_length=1,max_length=1000)
class Rename(Strict):
    title: str = Field(min_length=1,max_length=100)
class Note(Strict):
    title: str = Field(min_length=1,max_length=100)
    content: str = Field(min_length=1,max_length=20000)
class TaskUpdate(Strict):
    completed: bool
class Confirmation(Strict):
    confirmed: Literal[True]
class Action(Strict):
    name: Literal['open_app','open_website','search','time','list_tasks','create_task','complete_task','delete_task','create_note','list_notes']
    arguments: dict = Field(default_factory=dict)
    confirmed: bool = False

class SpeechRequest(Strict):
    text: str = Field(min_length=1,max_length=12000)
    reference_id: str = Field(default="",max_length=100,pattern=r"^[A-Za-z0-9_-]*$")
