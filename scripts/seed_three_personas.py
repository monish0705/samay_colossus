"""Seed and ensure all 3 business personas (APMC Mandi, Private Mandi, Private Buyer) are verified and active for testing."""
import json
import sqlite3
from datetime import datetime, timezone


def run(db_path='samay.db'):
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    now_str = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S.%f')
    # Default password is 'monish1234'
    hashed_pw = 'pbkdf2_sha256$600000$7f16575dc9058fb8f0f642040f6db4ef$b5bcde04aa45bb006767584263af7f6a8d99afa6da39499e7d6d3033411bfd4a'

    # 1. Ensure User 1 exists and has roles
    user = cur.execute('SELECT id, name, email, phone FROM mandi_users WHERE id = 1').fetchone()
    if not user:
        cur.execute(
            'INSERT INTO mandi_users (id, name, email, phone, role, password_hash, language, email_verified, phone_verified, active, created_at) '
            'VALUES (1, ?, ?, ?, ?, ?, ?, 1, 1, 1, ?)',
            ('Monish MR', 'monishmr1986@gmail.com', '+917894561238', 'MANDI_OWNER', hashed_pw, 'en', now_str)
        )
    else:
        cur.execute('UPDATE mandi_users SET role = "MANDI_OWNER", password_hash = ? WHERE id = 1', (hashed_pw,))

    # 2. Create / Upgrade / Verify Private Mandi (ID 1)
    b1 = cur.execute('SELECT id FROM business_accounts WHERE id = 1').fetchone()
    if not b1:
        cur.execute(
            'INSERT INTO business_accounts (id, business_type, name, contact_name, phone, email, address, district, state, registration_details, verification_information, document_references, verification_state, version, created_by, submission_key, payload_hash, created_at) '
            'VALUES (1, "PRIVATE_MANDI", "Monish MR Private Mandi", "Monish MR", "+917894561238", "monishmr1986@gmail.com", "bengaluru, tukur, Karnataka", "tukur", "Karnataka", "PM-REG-2026-001", "Verified Private Mandi", "[]", "VERIFIED", 1, 1, "auto-mandi-key-12345678", "hash-mandi-12345678", ?)',
            (now_str,)
        )
    else:
        cur.execute("UPDATE business_accounts SET verification_state = 'VERIFIED' WHERE id = 1")

    cur.execute(
        "INSERT OR IGNORE INTO business_users (business_id, user_id, can_manage, active) VALUES (1, 1, 1, 1)"
    )
    cur.execute(
        "UPDATE business_users SET can_manage = 1, active = 1 WHERE business_id = 1 AND user_id = 1"
    )
    cur.execute(
        "INSERT OR REPLACE INTO business_roles (business_id, user_id, role, approved_by) VALUES (1, 1, 'PRIVATE_MANDI_OWNER', 1)"
    )
    # Ensure private_mandis entry
    pm = cur.execute('SELECT id FROM private_mandis WHERE business_id = 1').fetchone()
    if not pm:
        cur.execute('INSERT INTO private_mandis (business_id, operating_hours, created_at) VALUES (1, "06:00 - 18:00 Mon-Sat", ?)', (now_str,))
        pm_id = cur.lastrowid
    else:
        pm_id = pm[0]
    
    cur.execute(
        'INSERT OR IGNORE INTO business_market_assignments (business_id, private_mandi_id, approved_by) VALUES (1, ?, 1)',
        (pm_id,)
    )

    # 3. Create / Verify Private Buyer (ID 2)
    b2 = cur.execute('SELECT id FROM business_accounts WHERE id = 2').fetchone()
    if not b2:
        cur.execute(
            'INSERT INTO business_accounts (id, business_type, name, contact_name, phone, email, address, district, state, registration_details, verification_information, document_references, verification_state, version, created_by, submission_key, payload_hash, created_at) '
            'VALUES (2, "PRIVATE_BUYER", "Monish MR Private Buyer", "Monish MR", "+917894561238", "monishmr1986@gmail.com", "bengaluru, tukur, Karnataka", "tukur", "Karnataka", "PB-REG-2026-001", "Verified Direct Buyer", "[]", "VERIFIED", 1, 1, "auto-buyer-key-12345678", "hash-buyer-12345678", ?)',
            (now_str,)
        )
        cur.execute('INSERT INTO private_buyers (business_id, buyer_type, created_at) VALUES (2, "DIRECT_PROCESSOR", ?)', (now_str,))
    else:
        cur.execute("UPDATE business_accounts SET verification_state = 'VERIFIED' WHERE id = 2")

    cur.execute('INSERT OR IGNORE INTO business_users (business_id, user_id, can_manage, active) VALUES (2, 1, 1, 1)')
    cur.execute('UPDATE business_users SET can_manage = 1, active = 1 WHERE business_id = 2 AND user_id = 1')
    cur.execute("INSERT OR REPLACE INTO business_roles (business_id, user_id, role, approved_by) VALUES (2, 1, 'PRIVATE_BUYER', 1)")

    # Ensure crops for both
    for b_id in [1, 2]:
        for c_id in [1, 2, 3, 4, 5]:
            cur.execute('INSERT OR IGNORE INTO business_crop_preferences (business_id, commodity_id) VALUES (?, ?)', (b_id, c_id))

    # 4. APMC Mandi Setup (Kolar APMC - market_id = 1)
    reg = cur.execute('SELECT market_id FROM mandi_registrations WHERE market_id = 1').fetchone()
    if not reg:
        cur.execute(
            'INSERT INTO mandi_registrations (market_id, active, registration_details, approved_by, approved_at, commodity_ids) '
            'VALUES (1, 1, "Official APMC Kolar Market Yard, Karnataka", 1, ?, ?)',
            (now_str, json.dumps([1, 2, 3, 4, 5]))
        )
    else:
        cur.execute('UPDATE mandi_registrations SET active = 1, approved_by = 1 WHERE market_id = 1')

    cur.execute(
        'INSERT OR IGNORE INTO mandi_user_market_assignments (user_id, market_id, can_transact) VALUES (1, 1, 1)'
    )
    cur.execute('UPDATE mandi_user_market_assignments SET can_transact = 1 WHERE user_id = 1 AND market_id = 1')

    # 5. Account roles
    for r in ['FARMER', 'MANDI_OWNER', 'PRIVATE_MANDI_OWNER', 'PRIVATE_BUYER', 'SYSTEM_ADMIN']:
        cur.execute(
            'INSERT OR IGNORE INTO account_roles (user_id, role, approved_by) VALUES (1, ?, 1)',
            (r,)
        )

    # 6. Ensure current active price observations for all 5 crops so Advisor/Selling pages never go stale
    today_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    pilot_observations = [
        (1, 1, 'tomato', 'local', 300, 1000, 2000, 26),
        (3, 3, 'rashi', 'local', 41900, 48009, 48689, 23),
        (4, 4, 'puna', 'local', 1000, 4200, 4700, 24),
        (5, 5, 'copra', 'local', 30000, 31707, 32100, 22),
        (6, 6, 'local', 'medium', 2400, 3000, 3600, 25),
    ]
    for m_id, c_id, v, g, min_p, mod_p, max_p, b_id in pilot_observations:
        exists_row = cur.execute(
            'SELECT id FROM mandi_observations WHERE market_id = ? AND commodity_id = ? AND variety = ? AND grade = ? AND observed_on = ?',
            (m_id, c_id, v, g, today_date)
        ).fetchone()
        if not exists_row:
            cur.execute(
                '''INSERT INTO mandi_observations (
                    market_id, commodity_id, observed_on, variety, grade,
                    min_price_inr_per_quintal, modal_price_inr_per_quintal, max_price_inr_per_quintal,
                    price_unit, data_kind, data_source, latest_batch_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'INR/quintal', 'official', 'Official OGD / AGMARKNET historical APMC observations', ?, ?)''',
                (m_id, c_id, today_date, v, g, min_p, mod_p, max_p, b_id, now_str)
            )

    con.commit()
    con.close()
    print("Successfully seeded and verified all 3 personas: APMC Mandi, Private Mandi, Private Buyer!")

if __name__ == '__main__':
    run()
