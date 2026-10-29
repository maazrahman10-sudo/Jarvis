// Deterministic lifecycle checks; no microphone or speakers are exercised here.
import test from 'node:test';
import assert from 'node:assert/strict';
let spoken=[], canceled=0, recognition;
const synth={cancel(){canceled++},getVoices(){return [{voiceURI:'local',name:'Local',localService:true}]},speak(u){spoken.push(u);u.onstart();queueMicrotask(()=>u.onend());}};
class Recognition {
  constructor(){recognition=this;}
  start(){this.onstart?.();}
  stop(){this.onend?.();}
  abort(){this.aborted=true;this.onend?.();}
}
globalThis.window={speechSynthesis:synth,SpeechRecognition:Recognition};
globalThis.SpeechSynthesisUtterance=class {constructor(text){this.text=text;}};
const {Voice}=await import('../frontend/voice.js');
function makeVoice(){const states=[],texts=[],errors=[];const voice=new Voice({onState:x=>states.push(x),onText:x=>texts.push(x),onError:x=>errors.push(x),onHint:()=>{}});voice.configure({spoken:true,rate:1.2,voice:'local'});return {voice,states,texts,errors};}

test('repeated system responses speak and return to idle',async()=>{
  const {voice,states,errors}=makeVoice();spoken=[];
  for(let i=0;i<3;i++){voice.speak('Hello JARVIS.');await new Promise(resolve=>setTimeout(resolve,0));}
  assert.equal(spoken.length,3);assert.ok(states.includes('speaking'));assert.equal(states.at(-1),'idle');assert.equal(spoken[0].rate,1.2);assert.equal(spoken[0].voice.voiceURI,'local');assert.deepEqual(errors,[]);
});
test('disabled speech stays silent except an explicit test',async()=>{
  const {voice}=makeVoice();voice.configure({spoken:false});spoken=[];voice.speak('Silent');assert.equal(spoken.length,0);voice.speak('Test',true);await new Promise(resolve=>setTimeout(resolve,0));assert.equal(spoken.length,1);
});
test('push-to-talk cancels speech and only returns final transcript on release',async()=>{
  const {voice,texts,states}=makeVoice();const before=canceled;await voice.startListening();assert.ok(canceled>before);assert.equal(states.at(-1),'listening');
  const final=Object.assign([{transcript:'Hello'}],{isFinal:true});recognition.onresult({resultIndex:0,results:[final]});assert.deepEqual(texts,[]);voice.stopListening();assert.deepEqual(texts,['Hello']);assert.equal(states.at(-1),'idle');
});
test('speaking aborts recognition and discards its transcript',async()=>{
  const {voice,texts}=makeVoice();await voice.startListening();recognition.onresult({resultIndex:0,results:[Object.assign([{transcript:'Should discard'}],{isFinal:true})]});const rec=recognition;voice.speak('Output');await new Promise(resolve=>setTimeout(resolve,0));assert.equal(rec.aborted,true);assert.deepEqual(texts,[]);
});
test('stop speaking invalidates queued chunks',async()=>{
  const {voice,states}=makeVoice();spoken=[];voice.speak('A'.repeat(700));voice.stopSpeaking();await new Promise(resolve=>setTimeout(resolve,0));assert.equal(spoken.length,1);assert.equal(states.at(-1),'idle');
});
