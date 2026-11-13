import { createContext, useContext, useState, type ReactNode } from 'react';
import { api, defaultScope, type Scope, type Prediction, type Recommendation } from './api';
import { blankAdvisor, type AdvisorValues } from './advisor';
import { useResource } from './ui';
import { useLanguage } from './i18n';

function useAppState() {
  const language = useLanguage();
  const [scope, setScope] = useState<Scope>(defaultScope);
  const [draft, setDraft] = useState<AdvisorValues>(blankAdvisor);
  const [result, setResultState] = useState<Recommendation | null>(null);
  const [priorResult, setPriorResult] = useState<Recommendation | null>(null);
  const setResult = (next: Recommendation) => { setPriorResult(result); setResultState(next); };
  const [predictionHistory, setPredictionHistory] = useState<Prediction[]>([]);
  const connection = useResource(api.health, 'health');
  const catalog = useResource(async () => { const [markets, commodities, data, models] = await Promise.all([api.markets(), api.commodities(), api.data(), api.models()]); return { markets, commodities, data, models }; }, 'catalog');
  const rememberPrediction = (p: Prediction) => setPredictionHistory(old => [p, ...old.filter(x => x.request_id !== p.request_id)].slice(0, 10));
  return { language, scope, setScope, draft, setDraft, result, priorResult, setResult, predictionHistory, rememberPrediction, connection, catalog };
}
type State = ReturnType<typeof useAppState>;
const Context = createContext<State | null>(null);
export function AppProvider({ children }: { children: ReactNode }) { const state = useAppState(); return <Context.Provider value={state}>{children}</Context.Provider>; }
export function useApp() { const state = useContext(Context); if (!state) throw new Error('SAMAY context is missing'); return state; }
