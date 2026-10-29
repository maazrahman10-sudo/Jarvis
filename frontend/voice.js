import {api} from './api.js';
// Browser speech runs asynchronously through the browser/OS audio service.
// No audio is uploaded by our backend or written to disk.
export class Voice {
  constructor({onState,onText,onError,onHint}) {
    Object.assign(this,{onState,onText,onError,onHint});
    this.settings={}; this.held=false; this.recognition=null; this.testStream=null;
    this.Recognition=window.SpeechRecognition || window.webkitSpeechRecognition;
    this.synth=window.speechSynthesis;
    this.testTimer=null; this.generation=0;
  }
  configure(settings) {this.settings=settings;}
  voices() {return this.synth?.getVoices() || [];}
  stopSpeaking() {this.generation++; this.speechRequest?.abort(); this.speechRequest=null; if(this.audio){this.audio.pause();this.audio.src='';this.audio=null;}if(this.audioUrl){URL.revokeObjectURL(this.audioUrl);this.audioUrl=null;} this.synth?.cancel(); this.onState('idle');}
  speak(text,force=false) {
    if ((!this.settings.spoken && !force) || !text.trim()) return;
    if(this.settings.speech_provider==='fish'){this.speakFish(text).catch(e=>{if(e.name!=='AbortError'){this.onState('error');this.onError(e.message);}});return;}
    if (!this.synth) {this.onError('Speech output is unavailable. Try Windows Edge.');return;}
    this.cancelListening(); this.stopSpeaking();
    const generation=this.generation;
    // A single utterance at a time prevents overlapping engine instances. Chunk long responses.
    const chunks=text.slice(0,12000).match(/[^.!?\n]{1,220}[.!?\n]?/g) || [text];
    const next=()=>{
      if(generation!==this.generation) return;
      const chunk=chunks.shift();
      if(!chunk) {this.onState('idle');return;}
      const utterance=new SpeechSynthesisUtterance(chunk);
      utterance.rate=Number(this.settings.rate)||1;
      const selected=this.voices().find(v=>v.voiceURI===this.settings.voice);
      if(selected) utterance.voice=selected;
      utterance.onstart=()=>this.onState('speaking');
      utterance.onend=next;
      utterance.onerror=(e)=>{if(generation!==this.generation) return; this.onState('idle'); if(e.error!=='canceled' && e.error!=='interrupted') this.onError('Speech failed: '+e.error+'. Check your Windows output device, voice, and volume.');};
      this.utterance=utterance;
      this.synth.speak(utterance);
    };
    next();
  }
  async speakFish(text) {
    this.cancelListening(); this.stopSpeaking();
    const generation=this.generation;this.speechRequest=new AbortController();this.onState('processing');
    try {
      const blob=await api('speech','POST',{text:text.slice(0,12000),reference_id:this.settings.fish_reference_id||''},this.speechRequest.signal);
      if(generation!==this.generation)return;
      this.audioUrl=URL.createObjectURL(blob);this.audio=new Audio(this.audioUrl);
      if(this.settings.speaker && typeof this.audio.setSinkId==='function')await this.audio.setSinkId(this.settings.speaker);
      this.audio.onended=()=>{if(generation===this.generation)this.stopSpeaking();};
      this.audio.onerror=()=>{if(generation===this.generation){this.stopSpeaking();this.onError('Cannot play Fish audio. Check your output device or use system voices.');}};
      await this.audio.play();this.onState('speaking');
    }catch(e){if(generation!==this.generation)return;this.stopSpeaking();if(e.name==='NotAllowedError')throw new Error('Browser blocked audio playback. Click Test speech in Settings to allow playback.');throw e;}
  }
  async startListening() {
    if(this.recognition || this.testStream) return;
    if(!this.Recognition) {this.onError('Speech recognition is unsupported in this browser. Use Windows Edge or type your message.');return;}
    this.stopSpeaking(); this.held=true; this.finalText='';let recognitionFailed=false;
    const rec=new this.Recognition(); this.recognition=rec;
    rec.lang=navigator.language || 'en-US'; rec.continuous=true; rec.interimResults=true;
    rec.onstart=()=>{if(!this.held) rec.stop(); else this.onState('listening');};
    rec.onresult=e=>{
      let interim='';
      for(let i=e.resultIndex;i<e.results.length;i++) {
        if(e.results[i].isFinal) this.finalText+=' '+e.results[i][0].transcript;
        else interim+=e.results[i][0].transcript;
      }
      this.onHint((this.finalText+' '+interim).trim() || 'Listening…');
    };
    rec.onerror=e=>{
      const errors={'not-allowed':'Microphone permission denied. Allow it in the address bar and Windows Privacy > Microphone.', 'audio-capture':'No microphone is available. Check Windows input settings.',network:'The browser speech service is unreachable. Check internet access or type instead.', 'service-not-allowed':'Browser speech service is unavailable. Try Windows Edge.'};
      if(e.error!=='aborted' && e.error!=='no-speech') {recognitionFailed=true;this.onError(errors[e.error] || 'Voice recognition failed: '+e.error);}
    };
    rec.onend=()=>{
      if(this.recognition!==rec) return;
      this.recognition=null; this.held=false; clearTimeout(this.listenTimer); this.onState(recognitionFailed?'error':'idle');
      this.onHint('Hold the microphone to talk · Enter to send');
      if(this.finalText.trim()) this.onText(this.finalText.trim());
    };
    try {rec.start(); this.listenTimer=setTimeout(()=>this.stopListening(),30000);}
    catch {this.recognition=null;this.onError('Could not start microphone recognition. Check browser permissions.');}
  }
  cancelListening() {const rec=this.recognition;this.recognition=null;this.held=false;clearTimeout(this.listenTimer);if(rec){rec.onend=null;rec.onresult=null;try{rec.abort();}catch{}}}
  stopListening() {this.held=false;try {this.recognition?.stop();}catch {} }
  async testMicrophone(deviceId,onLevel) {
    this.stopListening();this.stopSpeaking();await this.stopTest();
    if(!navigator.mediaDevices?.getUserMedia) throw new Error('Microphone access needs localhost and a supported browser.');
    try {
      this.testStream=await navigator.mediaDevices.getUserMedia({audio:deviceId?{deviceId:{exact:deviceId}}:true});
      this.audioContext=new AudioContext(); await this.audioContext.resume();
      const source=this.audioContext.createMediaStreamSource(this.testStream);
      const analyser=this.audioContext.createAnalyser(); analyser.fftSize=256;source.connect(analyser);
      const data=new Uint8Array(256);
      const tick=()=>{if(!this.testStream) return;analyser.getByteTimeDomainData(data);let energy=0;for(const n of data) energy+=(n-128)**2;onLevel(Math.min(1,Math.sqrt(energy/256)/35));this.frame=requestAnimationFrame(tick);};tick();
      this.testTimer=setTimeout(()=>{this.stopTest();onLevel(0);},10000);
    } catch(e) {await this.stopTest();throw new Error(e.name==='NotAllowedError'?'Microphone access denied. Allow microphone permission in your browser and Windows settings.':'Cannot use this microphone. Check the selected device and Windows input settings.');}
  }
  async stopTest() {clearTimeout(this.testTimer);cancelAnimationFrame(this.frame);this.testStream?.getTracks().forEach(t=>t.stop());this.testStream=null;await this.audioContext?.close().catch(()=>{});this.audioContext=null;}
}
