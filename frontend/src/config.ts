export const config: Readonly<{ apiBaseUrl: string }> = {
  apiBaseUrl: (import.meta.env.VITE_API_BASE_URL || '/backend').replace(/\/$/, ''),
};
if (!/^https?:\/\//.test(config.apiBaseUrl) && !/^\/(?!\/)[a-zA-Z0-9/_-]+$/.test(config.apiBaseUrl)) throw new Error('VITE_API_BASE_URL must be an HTTP(S) URL or same-origin path');
