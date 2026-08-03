#!/usr/bin/env python3
"""cordia_email.py CLI — setup helper for Agentic Mail.

Usage:
  python3 /opt/cordia/backend/cordia_email.py --health       # show provider state
  python3 /opt/cordia/backend/cordia_email.py --setup        # GET /api/v1/me → print resourceId
  python3 /opt/cordia/backend/cordia_email.py <to> <subject> <textfile>   # one-shot send
"""
import json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cordia_email as em


def cmd_health():
    print(json.dumps(em.health(), indent=2))


def cmd_setup():
    """Call GET /api/v1/me and print the mailboxes so you can copy the resourceId."""
    if not os.environ.get('AGENTIC_MAIL_TOKEN'):
        print('AGENTIC_MAIL_TOKEN not set in environment.', file=sys.stderr)
        print('Add it to /etc/cordia/cordia.env, then run with:', file=sys.stderr)
        print('  set -a && source /etc/cordia/cordia.env && set +a && python3 cordia_email.py --setup', file=sys.stderr)
        sys.exit(1)
    result = em.list_mailboxes()
    print(json.dumps(result, indent=2, default=str))
    if result.get('ok'):
        data = result.get('data', {})
        mailboxes = data.get('data', {}).get('mailboxes', [])
        if mailboxes:
            print('\n=== Copy the resourceId into AGENTIC_MAIL_RESOURCE_ID ===')
            for mb in mailboxes:
                print(f"  {mb.get('resourceId')}  {mb.get('address')}")
        else:
            print('\nNo mailboxes found for this token.')


def main():
    if '--health' in sys.argv:
        return cmd_health()
    if '--setup' in sys.argv:
        return cmd_setup()
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(2)
    text = open(sys.argv[3]).read()
    print(json.dumps(em.send(sys.argv[1], sys.argv[2], text), indent=2))


if __name__ == '__main__':
    main()
