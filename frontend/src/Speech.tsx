import { useEffect, useState } from 'react';
import { Volume2, Square } from 'lucide-react';
import { useLanguage, localize } from './i18n';
export function ReadAloud({ lines }: { lines: string[] }) {
  const language = useLanguage();
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>([]), [speaking, setSpeaking] = useState(false);
  const supported = typeof window !== 'undefined' && 'speechSynthesis' in window && typeof SpeechSynthesisUtterance !== 'undefined';
  useEffect(() => {
    if (!supported) return;
    const refresh = () => setVoices(window.speechSynthesis.getVoices());
    refresh(); window.speechSynthesis.addEventListener('voiceschanged', refresh);
    return () => { window.speechSynthesis.removeEventListener('voiceschanged', refresh); window.speechSynthesis.cancel(); };
  }, [supported]);
  useEffect(() => { if (supported) window.speechSynthesis.cancel(); setSpeaking(false); }, [language, lines.join('|')]);
  const voice = voices.find(v => v.lang.toLowerCase().startsWith(language === 'kn' ? 'kn' : 'en-in')) || (language === 'en' ? voices.find(v => v.lang.startsWith('en')) : undefined);
  const read = () => { if (!voice || !supported) return; window.speechSynthesis.cancel(); const text = new SpeechSynthesisUtterance(lines.join(' ')); text.voice = voice; text.lang = voice.lang; text.onend = () => setSpeaking(false); text.onerror = () => setSpeaking(false); window.speechSynthesis.speak(text); setSpeaking(true); };
  return localize(<div className="speech-controls"><button className="button button-secondary" disabled={!supported || !voice} onClick={read}><Volume2 size={17}/>Read explanation aloud</button>{speaking && <button className="button button-secondary" onClick={() => { window.speechSynthesis.cancel(); setSpeaking(false); }}><Square size={15}/>Stop reading</button>}<p className="small muted">{!supported ? 'This browser does not support speech. The complete text is available below.' : !voice ? language === 'kn' ? 'A Kannada voice is not available on this device. Read the full Kannada text below.' : 'An English voice is not available yet. Read the full text below.' : 'Optional: your browser’s voice service may process this explanation. Nothing is read until you press the button.'}</p></div>);
}
