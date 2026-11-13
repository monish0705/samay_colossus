import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it } from 'vitest';
import { App } from '../src/App';
import { setLanguage } from '../src/i18n';

const show = (path: string) => { setLanguage('en'); return render(<MemoryRouter initialEntries={[path]}><App/></MemoryRouter>); };
afterEach(() => { setLanguage('en'); });

describe('real HTTP end-to-end service integration — synthetic TEST_ONLY temporary database', () => {
  it('loads imported history and source through the actual API', async () => {
    show('/insights');
    expect(await screen.findByText(/HISTORICAL REPLAY — not live market data/)).toBeInTheDocument();
    expect((await screen.findAllByText(/HTTP_E2E_TEST_ONLY_NOT_GOVERNMENT_DATA/)).length).toBeGreaterThan(0);
    expect(screen.getByRole('img', { name: /observations/ })).toBeInTheDocument();
  });
  it('loads a saved baseline and its chronologically calibrated empirical intervals', async () => {
    show('/forecast');
    await screen.findByText('Saved artifact available');
    fireEvent.click(screen.getByRole('button', { name: 'Get forecast' }));
    expect(await screen.findByText(/90% nominal empirical band/)).toBeInTheDocument();
    expect(screen.getByText(/Model .*champion-3d/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'ಕನ್ನಡ' }));
    expect(document.documentElement.lang).toBe('kn');
  });
  it('posts farmer inputs to the real optimizer, preserves amounts in Kannada and tests zero storage', async () => {
    show('/advisor');
    fireEvent.click(screen.getByRole('button', { name: 'Load labeled example' }));
    fireEvent.click(screen.getByRole('button', { name: 'Calculate my sale plan' }));
    expect(await screen.findByRole('heading', { name: 'Keep today’s cash needs covered.' })).toBeInTheDocument();
    expect(screen.getAllByText('₹18,700.00').length).toBeGreaterThan(0);
    fireEvent.click(screen.getByText('Why this recommendation?'));
    expect(screen.getByText(/₹20000.00.*₹1000.00.*₹300.00/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'ಕನ್ನಡ' }));
    expect(screen.getAllByText('₹18,700.00').length).toBeGreaterThan(0);
  });
});
