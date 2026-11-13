"""Real Chromium → production React → HTTP → SQLite marketplace lifecycle.

Uses only a disposable TEST_ONLY database and identities. Never seeds runtime accounts.
Requires: python -m pip install playwright; python -m playwright install chromium
"""
import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]


def free_port():
    with socket.socket() as connection:
        connection.bind(('127.0.0.1', 0))
        return connection.getsockname()[1]


def ready(url, process):
    for _ in range(240):
        try:
            with urlopen(url, timeout=1):
                return
        except OSError:
            if process.poll() is not None:
                raise RuntimeError('Fixture process exited; inspect reports/sale-e2e-server.log') from None
            time.sleep(.25)
    raise RuntimeError('Fixture readiness timeout')


def run():
    from playwright.sync_api import expect, sync_playwright
    backend_port, frontend_port = free_port(), free_port()
    password = 'TEST_ONLY-' + secrets.token_urlsafe(16)
    env = {**os.environ, 'SAMAY_SALE_E2E_ADMIN_PASSWORD': password,
           'SAMAY_BACKEND_URL': f'http://127.0.0.1:{backend_port}', 'VITE_API_BASE_URL': '/backend'}
    report_dir = ROOT / 'reports'
    browser_errors = []
    steps = []
    with tempfile.TemporaryDirectory(prefix='samay-sale-TEST_ONLY-') as directory, (report_dir / 'sale-e2e-server.log').open('w', encoding='utf-8') as log:
        backend = subprocess.Popen([sys.executable, 'tests/http_fixture_server.py', '--folder', directory, '--port', str(backend_port)], cwd=ROOT, env=env, stdout=log, stderr=log)
        frontend = None
        try:
            ready(f'http://127.0.0.1:{backend_port}/api/health', backend)
            frontend = subprocess.Popen([shutil.which('node'), str(ROOT / 'frontend/node_modules/vite/bin/vite.js'), 'preview', '--host', '127.0.0.1', '--port', str(frontend_port), '--strictPort'], cwd=ROOT / 'frontend', env=env, stdout=log, stderr=log)
            base = f'http://127.0.0.1:{frontend_port}'
            ready(base, frontend)
            with sync_playwright() as p:
                options = {'headless': True}
                if os.getenv('SAMAY_E2E_CHROMIUM'):
                    options['executable_path'] = os.environ['SAMAY_E2E_CHROMIUM']
                browser = p.chromium.launch(**options)
                farmer_context = browser.new_context(viewport={'width': 390, 'height': 844})
                owner_context = browser.new_context(viewport={'width': 1440, 'height': 1000})
                farmer_context.add_init_script("localStorage.setItem('samay-language', 'en')")
                owner_context.add_init_script("localStorage.setItem('samay-language', 'en')")
                farmer, owner = farmer_context.new_page(), owner_context.new_page()
                farmer.on('pageerror', lambda e: browser_errors.append(str(e)))
                owner.on('pageerror', lambda e: browser_errors.append(str(e)))
                api = p.request.new_context(base_url=f'http://127.0.0.1:{backend_port}', extra_http_headers={'X-SAMAY-Action': '1'})
                assert api.post('/api/v1/auth/login', data={'email': 'admin@example.test', 'password': password}).ok
                market = api.get('/api/v1/markets').json()[0]
                crop = api.get('/api/v1/commodities').json()[0]
                assert api.post('/api/v1/admin/mandis', data={'market_id': market['id'], 'active': True,
                    'registration_details': 'TEST_ONLY independently verified operator', 'commodity_ids': [crop['id']]}).ok
                invitation = api.post('/api/v1/admin/mandi-invitations', data={'email': 'owner@example.test', 'role': 'MANDI_OWNER',
                    'market_id': market['id'], 'identity_evidence': 'TEST_ONLY independent identity verification'}).json()['invitation_token']
                steps.append('administrator registers existing mandi and invites owner')
                owner.goto(base + '/mandi')
                owner.get_by_role('button', name='Redeem authorized invitation').click()
                owner.get_by_label('Full name', exact=True).fill('TEST_ONLY mandi operator')
                owner.get_by_label('Email', exact=True).fill('owner@example.test')
                owner.get_by_label('Password (at least 12 characters)', exact=True).fill(password)
                owner.get_by_label('Administrator invitation code').fill(invitation)
                owner.get_by_role('button', name='Create account', exact=True).click()
                expect(owner.get_by_text('No sale requests in this view')).to_be_visible()
                steps.append('owner redeems invitation through actual portal')
                farmer.goto(base + '/advisor')
                farmer.get_by_role('button', name='Load labeled example').click()
                farmer.get_by_role('button', name='Calculate my sale plan', exact=True).click()
                expect(farmer.get_by_role('link', name='Sell to This Mandi')).to_be_visible(timeout=30000)
                farmer.get_by_role('link', name='Sell to This Mandi').click()
                farmer.get_by_role('button', name='Create farmer account').click()
                farmer.get_by_label('Full name', exact=True).fill('TEST_ONLY farmer')
                farmer.get_by_label('Email', exact=True).fill('farmer@example.test')
                farmer.get_by_label('Password (at least 12 characters)', exact=True).fill(password)
                farmer.get_by_role('button', name='Create account', exact=True).click()
                expect(farmer.get_by_label('Quantity to sell (quintals)', exact=True)).to_be_visible()
                farmer.get_by_label('Quantity to sell (quintals)', exact=True).fill('12')
                farmer.get_by_label('Expected selling price (INR/quintal)', exact=True).fill('1000')
                farmer.get_by_label('Estimated selling costs (INR)', exact=True).fill('300')
                arrival = (datetime.now(UTC) + timedelta(days=2)).strftime('%Y-%m-%dT%H:%M')
                expiry = (datetime.now(UTC) + timedelta(hours=12)).strftime('%Y-%m-%dT%H:%M')
                farmer.get_by_label('Preferred arrival (your local time)', exact=True).fill(arrival)
                farmer.get_by_role('button', name='Review request', exact=True).click()
                expect(farmer.get_by_role('heading', name='Confirm request summary')).to_be_visible()
                farmer.get_by_role('button', name='Confirm and send request', exact=True).click()
                expect(farmer.get_by_role('heading', name='Request timeline')).to_be_visible()
                public = farmer.url.rsplit('/', 1)[1]
                steps.append('real recommendation leads to confirmed partial-quantity request')
                # No manual refresh: polling must reveal the newly created request to the owner.
                expect(owner.get_by_role('link', name=public, exact=True)).to_be_visible(timeout=20000)
                owner.screenshot(path=str(report_dir / 'sale-owner-incoming.png'), full_page=True)
                owner.get_by_role('link', name=public, exact=True).click()
                owner.get_by_label('Accepted quantity (quintals)', exact=True).fill('10')
                owner.get_by_label('Offered price (INR/quintal)', exact=True).fill('1050')
                owner.get_by_label('Offered arrival slot (your local time)', exact=True).fill(arrival)
                owner.get_by_label('Offer expiry (your local time)', exact=True).fill(expiry)
                owner.get_by_role('button', name='Send terms to farmer', exact=True).click()
                expect(owner.get_by_text('₹1,050.00/quintal', exact=False)).to_be_visible()
                steps.append('owner receives automatic in-app notification and counteroffers partial quantity')
                farmer.goto(base + '/sale-requests/notifications')
                expect(farmer.get_by_role('button', name='Open request').first).to_be_visible()
                farmer.get_by_role('button', name='Open request').first.click()
                farmer.once('dialog', lambda dialog: dialog.accept())
                farmer.get_by_role('button', name='Confirm offer and book arrival', exact=True).click()
                expect(farmer.get_by_role('heading', name='Arrival booking')).to_be_visible()
                steps.append('farmer reviews notification, accepts offer and creates arrival booking')
                owner.reload()
                owner.get_by_label('Received quantity (quintals)', exact=True).fill('9.8')
                owner.get_by_role('button', name='Record arrival', exact=True).click()
                owner.get_by_label('Weighed quantity (quintals)', exact=True).fill('9.725')
                owner.get_by_label('Final actual price (INR/quintal)', exact=True).fill('1049.95')
                owner.get_by_label('Actual deductions (INR)', exact=True).fill('250.75')
                owner.get_by_label('Actual quality assessment', exact=True).fill('TEST_ONLY inspected')
                owner.get_by_role('button', name='Record weighment and final terms', exact=True).click()
                owner.get_by_role('button', name='Complete sale record', exact=True).click()
                expect(owner.locator('.sale-status')).to_have_text('COMPLETED')
                farmer.reload()
                expect(farmer.get_by_role('heading', name='Recorded actual transaction')).to_be_visible()
                expect(farmer.get_by_text('9960.01', exact=True)).to_be_visible()
                farmer.screenshot(path=str(report_dir / 'sale-farmer-completed-en.png'), full_page=True)
                farmer.get_by_role('button', name='ಕನ್ನಡ', exact=True).first.click()
                expect(farmer.get_by_role('heading', name='ದಾಖಲಾದ ನೈಜ ವ್ಯವಹಾರ')).to_be_visible()
                expect(farmer.get_by_text('9960.01', exact=True)).to_be_visible()
                farmer.screenshot(path=str(report_dir / 'sale-farmer-completed-kn.png'), full_page=True)
                assert farmer.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
                steps.append('owner records arrival, weighment and completion; farmer sees identical amounts in English/Kannada on mobile')
                assert not browser_errors, browser_errors
                browser.close()
                api.dispose()
            result = {'status': 'passed', 'scope': 'Isolated TEST_ONLY fixtures, actual Chromium and HTTP services',
                      'steps': steps, 'browser_errors': browser_errors, 'external_channels_tested': []}
            (report_dir / 'sale-browser-e2e.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
            print(json.dumps(result, indent=2))
        finally:
            for process in [frontend, backend]:
                if process:
                    process.terminate()
                    process.wait(timeout=20)


if __name__ == '__main__':
    run()
