let token = '';
export async function connect() {
  const r = await fetch('/api/session', {cache:'no-store'});
  if (!r.ok) throw new Error('Cannot create a local session.');
  token = (await r.json()).token;
}
export async function api(path, method='GET', body, signal) {
  let r;
  try {r = await fetch('/api/'+path, {method,signal,headers:{'Authorization':'Bearer '+token,...(body !== undefined ? {'Content-Type':'application/json'} : {})},body:body === undefined ? undefined : JSON.stringify(body)});}
  catch(e) {if(e.name==='AbortError') throw e; throw new Error('The local backend is disconnected. Check the launcher, then reload JARVIS.');}
  if (!r.ok) {
    const data = await r.json().catch(()=>({}));
    throw new Error(typeof data.detail==='string' ? data.detail : 'Please check the entered values.');
  }
  if (path==='chat') return r;
  if (path==='speech') return r.blob();
  return r.json();
}
export async function* streamEvents(response) {
  const reader=response.body.getReader();
  const decoder=new TextDecoder();
  let buffer='';
  try {
    while(true) {
      const {value,done}=await reader.read();
      buffer+=decoder.decode(value || new Uint8Array(),{stream:!done});
      const lines=buffer.split('\n'); buffer=lines.pop();
      for(const line of lines) if(line.trim()) yield JSON.parse(line);
      if(done) {if(buffer.trim()) yield JSON.parse(buffer); break;}
    }
  } finally {reader.releaseLock();}
}
