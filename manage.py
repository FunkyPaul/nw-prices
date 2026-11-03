#!/usr/bin/env python3
"""Command line for the price database (output language: NWP_LANG=en|de).

  python manage.py import capture.zip [weitere.zip ...] --server Nysa [--name "Name"]
  python manage.py servers
  python manage.py list
  python manage.py delete <capture-id>
  python manage.py export shop.json
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import db, decoder, i18n  # noqa: E402

DB_PATH = os.environ.get('NWP_DB', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'prices.db'))


def main():
    ap = argparse.ArgumentParser(description='New World trading post price database')
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('import', help='import capture ZIP or ledger.bin')
    p.add_argument('files', nargs='+')
    p.add_argument('--name')
    p.add_argument('--server', required=True, help='server name, e.g. Nysa')
    sub.add_parser('list', help='list captures')
    sub.add_parser('servers', help='list servers')
    p = sub.add_parser('delete', help='delete a capture')
    p.add_argument('id', type=int)
    p = sub.add_parser('export', help='export shop prices as JSON')
    p.add_argument('out')
    a = ap.parse_args()
    con = db.connect(DB_PATH)
    L = i18n.cli_lang()

    if a.cmd == 'import':
        srv = db.find_server(con, a.server)
        if not srv:
            sys.exit(i18n.t('cli.unknown_server', L, name=a.server,
                            known=', '.join(s['name'] for s in db.list_servers(con))))
        for f in a.files:
            blob = open(f, 'rb').read()
            try:
                decoded, meta = decoder.decode_upload(blob, f)
            except decoder.DecodeError as e:
                print(i18n.t('cli.error', L, file=f, msg=e.message(L)))
                continue
            r = db.import_decoded(con, decoded, meta, a.name, os.path.basename(f), blob, server_id=srv['id'])
            if r['duplicate']:
                print(i18n.t('cli.dup', L, file=f, id=r['capture_id'], name=r['name']))
            else:
                print(i18n.t('cli.ok', L, file=f, id=r['capture_id'], name=r['name'], s=r['searches'],
                             c=r['contracts'], e=r['errors']))
    elif a.cmd == 'servers':
        for s in db.list_servers(con):
            print(f"#{s['id']:<3} {s['name']:<16} {s['region'] or '':<14} {s['captures']} captures")
    elif a.cmd == 'list':
        for c in db.list_captures(con):
            print(f"#{c['id']:<4} {c['started_at'] or '':<28} {c['server'] or '?':<12} {c['name']:<30} "
                  + i18n.t('cli.row', L, s=c['searches'], c=c['contracts']))
    elif a.cmd == 'delete':
        db.delete_capture(con, a.id)
        print(i18n.t('cli.deleted', L))
    elif a.cmd == 'export':
        json.dump(db.export_shop(con), open(a.out, 'w'), indent=2, ensure_ascii=False)
        print(i18n.t('cli.written', L, file=a.out))


if __name__ == '__main__':
    main()
