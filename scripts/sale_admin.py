"""Local trusted administration; never seeds marketplace accounts or sample sales."""
import argparse
import getpass

from app.db import SessionLocal
from app.sale_auth import password_hash
from app.sale_models import SaleUser
from sqlalchemy import select


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['bootstrap-admin', 'verify-phone'])
    parser.add_argument('--email', required=True)
    parser.add_argument('--name')
    parser.add_argument('--phone')
    parser.add_argument('--evidence', help='Required reference to independently completed phone ownership verification')
    args = parser.parse_args()
    with SessionLocal() as db:
        user = db.scalar(select(SaleUser).where(SaleUser.email == args.email.lower()))
        if args.command == 'bootstrap-admin':
            if user or db.scalar(select(SaleUser).where(SaleUser.role == 'SYSTEM_ADMIN')):
                raise SystemExit('An administrator already exists; use authorized account administration.')
            if not args.name or '@' not in args.email:
                raise SystemExit('Provide real --email and --name.')
            password = getpass.getpass('New administrator password (12–128 characters): ')
            if not 12 <= len(password) <= 128 or password != getpass.getpass('Repeat password: '):
                raise SystemExit('Password invalid or mismatch')
            db.add(SaleUser(email=args.email.lower(), name=args.name, password_hash=password_hash(password), role='SYSTEM_ADMIN'))
        else:
            import re
            if not user or not args.phone or not re.fullmatch(r'\+[1-9]\d{7,14}', args.phone) or not args.evidence:
                raise SystemExit('Existing account, E.164 phone and independent verification evidence required.')
            # Trusted host operator only. Evidence is retained in a protected administration audit.
            import json
            from datetime import UTC, datetime
            from pathlib import Path
            audit = Path('.local-data/phone-verification-audit.jsonl')
            audit.parent.mkdir(exist_ok=True)
            with audit.open('a', encoding='utf-8') as stream:
                stream.write(json.dumps({'user_id': user.id, 'at': datetime.now(UTC).isoformat(), 'evidence': args.evidence}) + '\n')
            user.phone, user.phone_verified = args.phone, True
        db.commit()
    print('Saved. No external notification was sent.')


if __name__ == '__main__':
    main()
