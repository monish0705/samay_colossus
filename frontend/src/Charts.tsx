import { localize } from './i18n';
import { useId } from 'react';
import { Empty } from './ui';
import type { Schema } from './api';
export interface ChartPoint { date: string; value: number }
export function EvaluationChart({ points }: { points: Schema<'EvaluationPoint'>[] }) {
  const id = useId();
  if (!points.length) return null;
  const ordered = [...points].sort((a,b) => a.target_date.localeCompare(b.target_date));
  const start = Date.parse(ordered[0].target_date), end = Date.parse(ordered[ordered.length-1].target_date);
  const values = ordered.flatMap(p => [Number(p.actual_inr_per_quintal),Number(p.prediction_inr_per_quintal)]);
  const minimum = Math.min(...values), maximum = Math.max(...values);
  const low = Math.max(0,minimum-(maximum-minimum)*.1), high = maximum+Math.max((maximum-minimum)*.1,1);
  const x = (day:string) => 64+(Date.parse(day)-start)/Math.max(end-start,1)*646;
  const y = (value:string) => 215-(Number(value)-low)/(high-low)*175;
  const path = (key:'actual_inr_per_quintal'|'prediction_inr_per_quintal') => ordered.map((p,i) => `${i===0 || Date.parse(p.target_date)-Date.parse(ordered[i-1].target_date)>86400000 ? 'M':'L'}${x(p.target_date)},${y(p[key])}`).join(' ');
  return localize(<figure className="chart"><svg viewBox="0 0 760 260" role="img" aria-labelledby={id}>
    <title id={id}>Historical observed and frozen out-of-sample predicted prices, INR/quintal</title>
    {[0,1,2,3].map(i => <g key={i}><line x1="64" x2="710" y1={40+i*58} y2={40+i*58} stroke="#e5e9e3"/><text x="52" y={44+i*58} textAnchor="end">{Math.round(high-i*(high-low)/3).toLocaleString('en-IN')}</text></g>)}
    <path d={path('actual_inr_per_quintal')} fill="none" stroke="#267149" strokeWidth="2.5"/>
    <path d={path('prediction_inr_per_quintal')} fill="none" stroke="#b46d21" strokeWidth="2" strokeDasharray="5 3"/>
    {ordered.map(p => <g key={p.target_date}><circle cx={x(p.target_date)} cy={y(p.actual_inr_per_quintal)} r="2" fill="#267149"/><circle cx={x(p.target_date)} cy={y(p.prediction_inr_per_quintal)} r="2" fill="#b46d21"/></g>)}
    <text x="64" y="245">{ordered[0].target_date}</text><text x="710" y="245" textAnchor="end">{ordered[ordered.length-1].target_date}</text>
  </svg><figcaption>Green: actual observed price. Amber dashed: frozen prediction. Historical evaluation only; unreported dates remain gaps.</figcaption></figure>);
}
export function PriceChart({ points, label = 'Observed modal price', unit = 'INR/quintal' }: { points: ChartPoint[]; label?: string; unit?: string }) {
  const id = useId();
  if (!points.length) return localize(<div className="chart-empty"><Empty title="A clearer picture starts with verified data">No observations for this series yet. A price curve will appear after authentic history is imported.</Empty></div>);
  const sorted = [...points].sort((a, b) => a.date.localeCompare(b.date));
  const start = Date.parse(sorted[0].date), end = Date.parse(sorted[sorted.length - 1].date);
  const minimum = Math.min(...sorted.map(p => p.value)), maximum = Math.max(...sorted.map(p => p.value));
  const pad = Math.max((maximum - minimum) * .15, maximum * .02, 1), low = Math.max(0, minimum - pad), high = maximum + pad;
  const x = (p: ChartPoint) => 64 + (end === start ? .5 : (Date.parse(p.date) - start) / (end - start)) * 646;
  const y = (p: ChartPoint) => 215 - ((p.value - low) / (high - low)) * 175;
  const path = sorted.map((p, i) => `${i === 0 || Date.parse(p.date) - Date.parse(sorted[i - 1].date) > 86400000 ? 'M' : 'L'}${x(p)},${y(p)}`).join(' ');
  return localize(<figure className="chart"><svg viewBox="0 0 760 260" role="img" aria-labelledby={id}><title id={id}>{label}, {sorted.length} observations, {unit}. Gaps are unreported dates.</title>{[0, 1, 2, 3].map(i => <g key={i}><line x1="64" x2="710" y1={40 + i * 58} y2={40 + i * 58} stroke="#e5e9e3" strokeDasharray="4 5"/><text x="52" y={44 + i * 58} textAnchor="end">{Math.round(high - i * (high - low) / 3).toLocaleString('en-IN')}</text></g>)}<path d={path} fill="none" stroke="#267149" strokeWidth="2.5"/>{sorted.map((p, i) => <circle key={`${p.date}-${i}`} cx={x(p)} cy={y(p)} r="3" fill="#267149"><title>{p.date}: {p.value.toLocaleString('en-IN')} {unit}</title></circle>)}<text x="64" y="245">{sorted[0].date}</text><text x="710" y="245" textAnchor="end">{sorted[sorted.length - 1].date}</text></svg><figcaption>{label} · {unit} · unreported days remain gaps.</figcaption></figure>);
}
export function ScenarioChart({ values }: { values: { label: string; value: number }[] }) { const max = Math.max(...values.map(v => Math.abs(v.value)), 1); return localize(<div className="scenario-bars" role="img" aria-label="Backend scenario total net proceeds"><p className="muted small">Total net proceeds · INR</p>{values.map(v => <div className="scenario-bar" key={v.label}><span>{v.label}</span><div className="bar-track"><div className={v.value < 0 ? 'bar-negative' : ''} style={{ width: `${Math.abs(v.value) / max * 100}%` }}/></div><strong>{new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(v.value)}</strong></div>)}</div>); }
