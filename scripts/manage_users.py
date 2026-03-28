#!/usr/bin/env python3
"""Simple user management CLI for the demo app.

Usage:
  ./scripts/manage_users.py create --email EMAIL --username USER --password PWD [--admin]
  ./scripts/manage_users.py promote --email EMAIL
  ./scripts/manage_users.py list
  ./scripts/manage_users.py delete --email EMAIL

This script writes directly to the same SQLite DB used by the app (`auth.db`).
"""
import argparse
import sqlite3
import time
from passlib.context import CryptContext
from pathlib import Path

from core.config import DB_PATH as DB
pwd = CryptContext(schemes=['pbkdf2_sha256'], deprecated='auto')


def create_user(email: str, username: str, password: str, is_admin: bool = False):
    conn = sqlite3.connect(str(DB))
    try:
        h = pwd.hash(password)
        cur = conn.cursor()
        cur.execute('INSERT INTO users (email, username, password, created_at, is_admin) VALUES (?, ?, ?, ?, ?)',
                    (email, username, h, int(time.time()), 1 if is_admin else 0))
        conn.commit()
        print('created', email)
    except sqlite3.IntegrityError as e:
        print('error:', e)
    finally:
        conn.close()


def promote_user(email: str):
    conn = sqlite3.connect(str(DB))
    try:
        cur = conn.cursor()
        cur.execute('UPDATE users SET is_admin = 1 WHERE email = ?', (email,))
        conn.commit()
        if cur.rowcount:
            print('promoted', email)
        else:
            print('no such user')
    finally:
        conn.close()


def list_users():
    conn = sqlite3.connect(str(DB))
    try:
        cur = conn.cursor()
        cur.execute('SELECT id, email, username, created_at, is_admin FROM users')
        rows = cur.fetchall()
        for r in rows:
            print(r)
    finally:
        conn.close()


def delete_user(email: str):
    conn = sqlite3.connect(str(DB))
    try:
        cur = conn.cursor()
        cur.execute('DELETE FROM users WHERE email = ?', (email,))
        conn.commit()
        print('deleted', cur.rowcount, 'rows')
    finally:
        conn.close()


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest='cmd')
    c = sub.add_parser('create')
    c.add_argument('--email', required=True)
    c.add_argument('--username', required=True)
    c.add_argument('--password', required=True)
    c.add_argument('--admin', action='store_true')

    p2 = sub.add_parser('promote')
    p2.add_argument('--email', required=True)

    p3 = sub.add_parser('list')

    p4 = sub.add_parser('delete')
    p4.add_argument('--email', required=True)

    args = p.parse_args()
    if args.cmd == 'create':
        create_user(args.email, args.username, args.password, is_admin=args.admin)
    elif args.cmd == 'promote':
        promote_user(args.email)
    elif args.cmd == 'list':
        list_users()
    elif args.cmd == 'delete':
        delete_user(args.email)
    else:
        p.print_help()
