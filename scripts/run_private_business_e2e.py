"""Chromium private onboarding/verification/role persistence against isolated TEST_ONLY services."""
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile

from run_sale_e2e import ROOT, free_port, ready


def main():
    from playwright.sync_api import expect, sync_playwright
    backend_port, frontend_port = free_port(), free_port()
    password = 'TEST_ONLY-' + secrets.token_urlsafe(18)
    env = {**os.environ, 'SAMAY_SALE_E2E_ADMIN_PASSWORD': password,
           'SAMAY_BACKEND_URL': f'http://127.0.0.1:{backend_port}', 'VITE_API_BASE_URL': '/backend'}
    reports = ROOT / 'reports'
    errors, steps = [], []
    with tempfile.TemporaryDirectory(prefix='samay-private-TEST_ONLY-') as directory, (reports / 'private-business-browser-server.log').open('w', encoding='utf-8') as log:
        backend = subprocess.Popen([sys.executable, 'tests/http_fixture_server.py', '--folder', directory, '--port', str(backend_port)], cwd=ROOT, env=env, stdout=log, stderr=log)
        frontend = None
        try:
            ready(f'http://127.0.0.1:{backend_port}/api/health', backend)
            frontend = subprocess.Popen([shutil.which('node'), str(ROOT / 'frontend/node_modules/vite/bin/vite.js'), 'preview', '--host', '127.0.0.1', '--port', str(frontend_port), '--strictPort'], cwd=ROOT / 'frontend', env=env, stdout=log, stderr=log)
            base = f'http://127.0.0.1:{frontend_port}'
            ready(base, frontend)
            with sync_playwright() as p:
                launch = {'headless': True}
                if os.getenv('SAMAY_E2E_CHROMIUM'):
                    launch['executable_path'] = os.environ['SAMAY_E2E_CHROMIUM']
                browser = p.chromium.launch(**launch)
                member_context = browser.new_context(viewport={'width': 1440, 'height': 1000})
                admin_context = browser.new_context(viewport={'width': 1440, 'height': 1000})
                for context in [member_context, admin_context]:
                    context.add_init_script("localStorage.setItem('samay-language','en')")
                member, admin = member_context.new_page(), admin_context.new_page()
                for page in [member, admin]:
                    page.on('pageerror', lambda error: errors.append(str(error)))
                admin.goto(base + '/business/register')
                admin.get_by_label('Email', exact=True).fill('admin@example.test')
                admin.get_by_label('Password (at least 12 characters)', exact=True).fill(password)
                admin.get_by_role('button', name='Sign in', exact=True).click()
                expect(admin.get_by_role('link', name='Review pending businesses')).to_be_visible()
                member.goto(base + '/business/register')
                member.get_by_role('button', name='Create farmer account', exact=True).click()
                member.get_by_label('Full name', exact=True).fill('TEST_ONLY multi-role applicant')
                member.get_by_label('Email', exact=True).fill('multi@example.test')
                member.get_by_label('Password (at least 12 characters)', exact=True).fill(password)
                member.get_by_role('button', name='Create account', exact=True).click()
                expect(member.get_by_label('Registered private mandi name')).to_be_visible()
                expect(member.get_by_role('button', name='Business Mode', exact=True)).to_be_disabled()

                def apply(kind):
                    if kind == 'PRIVATE_BUYER':
                        member.get_by_role('group', name='Business type').get_by_role('button', name=re.compile('Private buyer')).click()
                    fields = {
                        'Registered private mandi name' if kind == 'PRIVATE_MANDI' else 'Buyer or business name': f'TEST_ONLY {kind} business',
                        'Owner name' if kind == 'PRIVATE_MANDI' else 'Authorized contact person': 'TEST_ONLY authorized applicant',
                        'Business phone in international format': '+919000000000', 'Business email': 'business@example.test',
                        'Business address': 'TEST_ONLY protected business address', 'District': 'Kolar', 'State': 'Karnataka',
                        'Business registration details or applicability': 'TEST_ONLY registration evidence',
                        'Verification information': 'TEST_ONLY independently supplied identity and registration',
                        'Protected verification document references (one per line)': 'TEST_ONLY protected document reference',
                    }
                    if kind == 'PRIVATE_MANDI':
                        fields['Operating hours'] = 'TEST_ONLY 09:00–17:00'
                    for label, value in fields.items():
                        member.get_by_label(label, exact=True).fill(value)
                    member.get_by_role('checkbox', name='Tomato', exact=True).check()
                    member.get_by_role('button', name='Submit for verification', exact=True).click()
                    expect(member.get_by_role('heading', name='Application saved for verification')).to_be_visible()
                    response = member_context.request.get(base + '/backend/api/v1/business/profile')
                    assert response.ok
                    return next(b for b in response.json() if b['business_type'] == kind)

                def approve(business):
                    admin.goto(base + '/business/admin')
                    expect(admin.get_by_role('heading', name=business['name'], exact=True)).to_be_visible()
                    admin.get_by_label('Verification evidence and decision reason', exact=True).fill('TEST_ONLY reviewer independently verified supplied identity, contact and registration')
                    admin.get_by_role('checkbox', name='Contact ownership verified independently', exact=True).check()
                    admin.get_by_role('checkbox', name='Business registration checked', exact=True).check()
                    admin.get_by_role('checkbox', name='Verification documents required', exact=True).check()
                    admin.get_by_role('button', name='Save verification decision', exact=True).click()
                    expect(admin.get_by_text('No pending business applications.', exact=True)).to_be_visible()

                mandi = apply('PRIVATE_MANDI')
                assert mandi['verification_state'] == 'PENDING_VERIFICATION' and not mandi['can_publish']
                expect(member.get_by_role('button', name='Business Mode', exact=True)).to_be_disabled()
                approve(mandi)
                member.reload()
                expect(member.get_by_role('button', name='Business Mode', exact=True)).to_be_enabled()
                member.get_by_role('button', name='Business Mode', exact=True).click()
                expect(member.get_by_role('heading', name='Private Mandi Dashboard', exact=True)).to_be_visible()
                assert member.locator('.scope-bar').count() == 0
                expect(member.get_by_text('Not an APMC market operator', exact=False)).to_be_visible()
                member.reload()
                expect(member.get_by_role('heading', name='Private Mandi Dashboard', exact=True)).to_be_visible()
                steps.append('private mandi application stays pending, administrator verifies, authorized workspace persists after reload')
                member.get_by_role('button', name='Farmer Mode', exact=True).click()
                expect(member.get_by_role('heading', name='Should I sell or wait?', exact=True)).to_be_visible()
                member.goto(base + '/business/register')
                buyer = apply('PRIVATE_BUYER')
                approve(buyer)
                member.reload()
                member.get_by_role('combobox', name='Authorized business workspace', exact=True).select_option(f'{buyer["id"]}:PRIVATE_BUYER')
                expect(member.get_by_role('heading', name='Private Buyer Dashboard', exact=True)).to_be_visible()
                member.reload()
                expect(member.get_by_role('heading', name='Private Buyer Dashboard', exact=True)).to_be_visible()
                member.screenshot(path=str(reports / 'private-buyer-dashboard.png'), full_page=True, animations='disabled')
                role_data = member_context.request.get(base + '/backend/api/v1/business/roles').json()
                assert {'FARMER', 'PRIVATE_MANDI_OWNER', 'PRIVATE_BUYER'} <= set(role_data['roles'])
                denied = member_context.request.post(base + '/backend/api/v1/business/active-role', headers={'X-SAMAY-Action': '1'}, data={'mode': 'BUSINESS', 'business_id': 999999, 'role': 'PRIVATE_BUYER'})
                assert denied.status == 403
                steps.append('one account has farmer and both private roles; buyer workspace restores and forged scope is denied')
                admin.goto(base + '/business/admin')
                admin.get_by_label('Find business by ID', exact=True).fill(str(buyer['id']))
                admin.get_by_role('button', name='Open business review', exact=True).click()
                expect(admin.get_by_role('heading', name=buyer['name'], exact=True)).to_be_visible()
                admin.get_by_label('Review decision', exact=True).select_option('SUSPENDED')
                admin.get_by_label('Verification evidence and decision reason', exact=True).fill('TEST_ONLY authority suspended access pending further independent review')
                admin.get_by_role('button', name='Save verification decision', exact=True).click()
                expect(admin.get_by_text('No pending business applications.', exact=True)).to_be_visible()
                member.goto(base + '/')
                expect(member.get_by_role('button', name='Farmer Mode', exact=True)).to_have_attribute('aria-pressed', 'true')
                role_data = member_context.request.get(base + '/backend/api/v1/business/roles').json()
                assert 'PRIVATE_BUYER' not in role_data['roles'] and 'PRIVATE_MANDI_OWNER' in role_data['roles']
                steps.append('administrator suspension immediately denies backend buyer powers and refresh falls back to farming')
                member.get_by_role('combobox', name='Authorized business workspace', exact=True).select_option(f'{mandi["id"]}:PRIVATE_MANDI_OWNER')
                expect(member.get_by_role('heading', name='Private Mandi Dashboard', exact=True)).to_be_visible()
                member.get_by_role('button', name='ಕನ್ನಡ', exact=True).click()
                expect(member.get_by_role('heading', name='ಖಾಸಗಿ ಮಂಡಿ ಕಾರ್ಯಕ್ಷೇತ್ರ', exact=True)).to_be_visible()
                member.set_viewport_size({'width': 390, 'height': 844})
                member.wait_for_function("document.querySelector('.sidebar').getBoundingClientRect().right <= 0")
                assert member.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
                member.screenshot(path=str(reports / 'private-mandi-mobile-kn.png'), full_page=True, animations='disabled')
                assert not errors, errors
                browser.close()
            result = {'status': 'passed', 'scope': 'Prompt 1 foundation only, isolated TEST_ONLY accounts and documents',
                      'steps': steps, 'browser_page_errors': errors, 'purchase_offers_implemented': True, 'external_identity_verification_claimed': False}
            (reports / 'private-business-browser.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
            print(json.dumps(result, indent=2))
        finally:
            for process in [frontend, backend]:
                if process:
                    process.terminate()
                    process.wait(timeout=20)


if __name__ == '__main__':
    main()
