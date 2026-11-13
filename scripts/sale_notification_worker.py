"""Run beside the API against the same durable database; one worker recommended."""
import argparse
import time

from app.db import SessionLocal
from app.sale_notifications import deliver_pending, refresh_provider_status


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    while True:
        deliver_pending(SessionLocal)
        refresh_provider_status(SessionLocal)
        if args.once:
            break
        time.sleep(5)


if __name__ == '__main__':
    main()
