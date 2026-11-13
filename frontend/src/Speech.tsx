import { useEffect, useState, useRef } from 'react';
import { Volume2, Square, Mic, MicOff } from 'lucide-react';
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

// Number words parser for Kannada and English
function parseSpokenNumber(text: string): string | null {
  const cleaned = text.trim().toLowerCase();
  
  // 1. Direct numerals (including Kannada digits ೦-೯)
  const knDigits: Record<string, string> = {
    '೦': '0', '೧': '1', '೨': '2', '೩': '3', '೪': '4',
    '೫': '5', '೬': '6', '೭': '7', '೮': '8', '೯': '9'
  };
  let normalized = cleaned;
  for (const [kn, en] of Object.entries(knDigits)) {
    normalized = normalized.replaceAll(kn, en);
  }
  const match = normalized.match(/\d+(\.\d+)?/);
  if (match) return match[0];

  // 2. Kannada number words
  const knWords: Record<string, number> = {
    'ಒಂದು': 1, 'ಎರಡು': 2, 'ಮೂರು': 3, 'ನಾಲ್ಕು': 4, 'ಐದು': 5,
    'ಆರು': 6, 'ಏಳು': 7, 'ಎಂಟು': 8, 'ಒಂಬತ್ತು': 9, 'ಹತ್ತು': 10,
    'ಹನ್ನೊಂದು': 11, 'ಹನ್ನೆರಡು': 12, 'ಹದಿಮೂರು': 13, 'ಹದಿನಾಲ್ಕು': 14, 'ಹದಿನೈದು': 15,
    'ಇಪ್ಪತ್ತು': 20, 'ಮೂವತ್ತು': 30, 'ನಲವತ್ತು': 40, 'ಐವತ್ತು': 50,
    'ಅರವತ್ತು': 60, 'ಎಪ್ಪತ್ತು': 70, 'ಎಂಬತ್ತು': 80, 'ತೊಂಬತ್ತು': 90,
    'ನೂರು': 100, 'ಇನ್ನೂರು': 200, 'ಮುನ್ನೂರು': 300, 'ನಾನ್ನೂರು': 400, 'ಐನೂರು': 500,
    'ಸಾವಿರ': 1000, 'ಲಕ್ಷ': 100000
  };

  for (const [word, val] of Object.entries(knWords)) {
    if (cleaned.includes(word)) {
      return String(val);
    }
  }

  // 3. English words
  const enWords: Record<string, number> = {
    'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
    'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
    'twenty': 20, 'thirty': 30, 'forty': 40, 'fifty': 50,
    'sixty': 60, 'seventy': 70, 'eighty': 80, 'ninety': 90,
    'hundred': 100, 'thousand': 1000, 'lakh': 100000
  };
  for (const [word, val] of Object.entries(enWords)) {
    if (cleaned.includes(word)) {
      return String(val);
    }
  }

  return null;
}

interface Recognition {
  lang: string; continuous: boolean; interimResults: boolean;
  onstart: (() => void) | null; onend: (() => void) | null; onerror: (() => void) | null;
  onresult: ((event: { results: { [index: number]: { [index: number]: { transcript: string } } } }) => void) | null;
  start: () => void; stop: () => void;
}
type RecognitionWindow = Window & { SpeechRecognition?: new () => Recognition; webkitSpeechRecognition?: new () => Recognition };

export function VoiceInputButton({
  onValue,
  label,
}: {
  onValue: (value: string) => void;
  label?: string;
}) {
  const language = useLanguage();
  const [listening, setListening] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);
  const recognitionRef = useRef<Recognition | null>(null);

  const SpeechRecognition = typeof window !== 'undefined' &&
    ((window as RecognitionWindow).SpeechRecognition || (window as RecognitionWindow).webkitSpeechRecognition);

  const startListening = () => {
    if (!SpeechRecognition) {
      setFeedback(language === 'kn' ? 'ಧ್ವನಿ ಗುರುತಿಸುವಿಕೆ ಬೆಂಬಲಿಸುವುದಿಲ್ಲ' : 'Voice input not supported');
      setTimeout(() => setFeedback(null), 3000);
      return;
    }

    try {
      const recognition = new SpeechRecognition();
      recognition.lang = language === 'kn' ? 'kn-IN' : 'en-IN';
      recognition.continuous = false;
      recognition.interimResults = false;

      recognition.onstart = () => {
        setListening(true);
        setFeedback(language === 'kn' ? 'ಆಲಿಸಲಾಗುತ್ತಿದೆ...' : 'Listening...');
      };

      recognition.onresult = event => {
        const transcript = event.results[0]?.[0]?.transcript || '';
        const parsed = parseSpokenNumber(transcript);
        if (parsed) {
          onValue(parsed);
          setFeedback(`✓ ${parsed}`);
        } else {
          setFeedback(language === 'kn' ? `ತಿಳಿಯಲಿಲ್ಲ: "${transcript}"` : `Heard: "${transcript}"`);
        }
        setTimeout(() => setFeedback(null), 3500);
      };

      recognition.onerror = () => {
        setListening(false);
        setFeedback(null);
      };

      recognition.onend = () => {
        setListening(false);
      };

      recognitionRef.current = recognition;
      recognition.start();
    } catch {
      setListening(false);
    }
  };

  const stopListening = () => {
    if (recognitionRef.current) {
      recognitionRef.current.stop();
      setListening(false);
    }
  };

  return (
    <div style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
      <button
        type="button"
        className={`voice-mic-btn ${listening ? 'is-listening' : ''}`}
        onClick={listening ? stopListening : startListening}
        title={language === 'kn' ? 'ಧ್ವನಿ ಮೂಲಕ ನಮೂದಿಸಿ (Speak value)' : 'Speak value (Voice input)'}
        style={{
          background: listening ? '#dc2626' : 'var(--surface-sunken)',
          color: listening ? '#ffffff' : 'var(--text-muted)',
          border: '1px solid var(--border)',
          borderRadius: '50%',
          width: '32px',
          height: '32px',
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          cursor: 'pointer',
          padding: 0,
          transition: 'all 0.2s ease',
        }}
        aria-label={label || 'Voice input (experimental; manual input available)'}
      >
        {listening ? <MicOff size={15} /> : <Mic size={15} />}
      </button>
      {feedback && (
        <span
          className="small"
          style={{
            fontSize: '0.78rem',
            color: feedback.startsWith('✓') ? '#16a34a' : 'var(--text-muted)',
            fontWeight: 500,
          }}
        >
          {feedback}
        </span>
      )}
    </div>
  );
}
