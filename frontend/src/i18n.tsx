import { cloneElement, isValidElement, useSyncExternalStore, type ReactElement, type ReactNode } from 'react';
import { kannada } from './locales/kn';
export type Language = 'en' | 'kn';
let language: Language = 'en';
try { if (localStorage.getItem('samay-language') === 'kn') language = 'kn'; } catch { /* Storage is optional. */ }
const listeners = new Set<() => void>();
const dictionary = new Map(Object.entries(kannada).map(([key, value]) => [key.toLowerCase(), value]));
export function setLanguage(value: Language) { language = value; try { localStorage.setItem('samay-language', value); } catch { /* No financial data is stored. */ } listeners.forEach(listener => listener()); }
export const getLanguage = () => language;
export function useLanguage() { return useSyncExternalStore(callback => { listeners.add(callback); return () => { listeners.delete(callback); }; }, getLanguage, () => 'en' as Language); }
export function t(text: string, values: Record<string, string | number> = {}, locale: Language = language): string {
  const key = text.trim();
  let translated = locale === 'kn' ? dictionary.get(key.toLowerCase()) || key : key;
  if (locale === 'kn' && translated === key) {
    const patterns: [RegExp, string][] = [
      [/^(\d+) calendar days since report$/, '$1 ಕ್ಯಾಲೆಂಡರ್ ದಿನಗಳ ಹಿಂದಿನ ವರದಿ'],
      [/^(\d+) calendar days; loss still applies$/, '$1 ಕ್ಯಾಲೆಂಡರ್ ದಿನಗಳು; ಪ್ರಮಾಣ ನಷ್ಟ ಇನ್ನೂ ಅನ್ವಯಿಸುತ್ತದೆ'],
      [/^(\d+)d:(.*)$/, '$1 ದಿನಗಳು: $2'],
    ];
    for (const [pattern, replacement] of patterns) if (pattern.test(key)) { translated = key.replace(pattern, replacement); break; }
    if (/[·/]/.test(translated) && !translated.startsWith('http') && !translated.startsWith('{')) translated = translated.split(/(\s*·\s*|\s*\/\s*)/).map(part => dictionary.get(part.trim().toLowerCase()) || part).join('');
    // Stable backend warning codes remain machine-readable in exports; the UI explains them.
    for (const [code, explanation] of Object.entries(warningMessages)) translated = translated.replaceAll(code, dictionary.get(explanation.toLowerCase()) || explanation);
  }
  for (const [name, value] of Object.entries(values)) translated = translated.replaceAll(`{${name}}`, String(value));
  return `${text.match(/^\s*/)?.[0] || ''}${translated}${text.match(/\s*$/)?.[0] || ''}`;
}
export const warningMessages: Record<string, string> = {
  extended_horizon_no_new_final_test: 'This horizon has no new untouched final test; research evidence only.',
  predeclared_persistence_baseline_not_trained_ml: 'Predeclared last-price baseline; not trained ML',
  insufficient_horizon_evidence: 'Insufficient evidence for this date. No future price will be invented.',
  fewer_than_60_exact_dated_development_pairs: 'Fewer than 60 exact dated development pairs.',
  less_than_90_calendar_days_of_origins: 'Less than 90 calendar days of decision history.',
  fewer_than_3_nonoverlapping_forecast_cases: 'Fewer than three nonoverlapping forecast cases.',
  insufficient_separated_train_validation_folds_for_model_selection: 'Insufficient separated folds for model selection; fixed baseline only.',
  context_not_available_at_decision: "External evidence was captured after this decision and has been excluded.",
  weather_context_stale: "The captured weather forecast is stale.",
  weather_does_not_cover_entire_holding_period: "Weather forecasts do not cover the entire holding period.",
  festival_calendar_coverage_incomplete: "The calendar does not cover every year in this holding period.",
  news_context_stale: "The captured news feed is stale.",
  no_matching_recent_news_in_collected_feeds: "No matching recent news was found in the collected feeds.",
  weather_context_unavailable: "Weather evidence is unavailable for this decision.",
  context_archive_unavailable_or_invalid: "External evidence is unavailable or failed its integrity checks.",
  user_outdoor_rainfall_constraint_blocks_holding: "Your outdoor-storage rain rule blocks holding, or required weather coverage is missing.",
  cash_requirement_not_achievable: "The immediate cash requirement cannot be achieved under these inputs.",
  holding_cannot_be_assessed_without_future_scenarios: "A usable forecast or explicit future-price assumption is needed to compare holding.",
  mandatory_cash_and_storage_constraints_satisfied: "This plan meets your immediate cash, storage and sale-lot constraints.",
  risk_adjusted_net_exceeds_immediate_sale: "This plan has a higher risk-adjusted net result under the supplied scenarios.",
  holding_does_not_improve_risk_adjusted_net_or_is_infeasible: "Holding is infeasible or does not improve the risk-adjusted net result under these assumptions.",
  flat_reference_not_a_forecast: "A flat dated-price reference is being used as a scenario, not a trained long-horizon forecast.",

  retrospective_research_only: 'Research forecast only; not validated farmer advice.',
  historical_publication_unverified: 'Original historical publication and revision times are unverified.',
  interval_coverage_not_guaranteed: 'Empirical interval coverage is not guaranteed.',
  empirical_interval_unavailable: 'Not enough separated residuals to estimate a reliable empirical interval.',
  short_history_baseline_only: 'History supports baseline forecasts only; advanced model training is not justified.',
  research_forecast_unavailable: 'No usable research forecast is available for this series and date.',
  scenario_only_simulation: 'User-entered future price assumption; not a model forecast.',

  invalid_request: 'Please check the submitted values and required fields.', scenario_assumptions_invalid: 'The adverse price or realization factor conflicts with the forecast bounds. Review those assumptions.',
  economic_assumptions_invalid: 'Economic assumptions conflict with the available forecast. Review costs and price mapping.', future_decision: 'The decision date cannot be in the future.',
  unsupported_series: 'This market, crop, variety or grade is unsupported.', market_source_unavailable: 'The market source evidence is unavailable.',
  missing_model: 'No saved model is available.', forecast_unavailable: 'A usable forecast is unavailable.', stale_market_data: 'Market observations are stale.',
  insufficient_calibration: 'Not enough residual evidence for an empirical interval.', limited_unseen_interval_evidence: 'Too little unseen interval evidence.',
  no_official_observations: 'No official observations are available.', sparse_history: 'Historical observations are sparse.',
  prediction_service_unavailable: 'The saved prediction service is unavailable.', registry_unavailable: 'The model registry is unavailable.',
  excessive_volatility: 'Recent observed price changes are unusually large.', model_drift: 'Recent forecast errors suggest a changing market.',
  large_recent_forecast_errors: 'Recent forecasts had large errors.', stale_calibration: 'Interval calibration is old.', stale_error_evidence: 'Recent error evidence is old.',
  wide_empirical_interval: 'The empirical price band is very wide.', unsupported_horizon: 'This forecast horizon is unsupported.',
  invalid_reliability_evidence: 'Reliability evidence failed its checks.', database_unavailable: 'The database is unavailable.',
};
export function warningText(value: string, locale: Language = language) {
  const [prefix, ...tail] = value.split(':');
  const code = tail.length ? tail.join(':') : prefix;
  const message = warningMessages[code] || (code.includes('no_official_market_observations') ? 'No official observation; farmer-entered quote used' : code.replaceAll('_', ' '));
  return `${tail.length ? `${prefix.replace('d', locale === 'kn' ? ' ದಿನಗಳು' : ' days')}: ` : ''}${t(message, {}, locale)}`;
}
/** Translate declared React text/labels, never input values, identifiers, prices or DOM state. */
export function localize(node: ReactNode): ReactNode {
  if (typeof node === 'string') return t(node);
  if (Array.isArray(node)) return node.map((child, index) => { const translated = localize(child); return isValidElement(translated) && translated.key == null ? cloneElement(translated, { key: `static-${index}` }) : translated; });
  if (!isValidElement(node)) return node;
  const element = node as ReactElement<Record<string, unknown>>;
  const props: Record<string, unknown> = {};
  for (const name of ['title', 'label', 'eyebrow', 'note', 'placeholder', 'aria-label']) if (typeof element.props[name] === 'string') props[name] = t(element.props[name] as string);
  if (element.props.children !== undefined) props.children = localize(element.props.children as ReactNode);
  return cloneElement(element, props);
}
