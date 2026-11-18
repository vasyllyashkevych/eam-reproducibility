"""Розгортання еталонного коду PostgreSQL (O2P_GOLDEN_TESTSET_v03) на стенді: кожна одиниця в окремій схемі."""
import re, subprocess, json, sys, os
from concurrent.futures import ThreadPoolExecutor
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DS = os.path.join(ROOT, '..', 'ds', 'O2P_GOLDEN_TESTSET_v03_full.csv')
PSQL = '/opt/homebrew/opt/postgresql@17/bin/psql'
PORT = os.environ.get('PGPORT', '55432')
OUT = os.path.join(ROOT, 'out'); os.makedirs(OUT, exist_ok=True)

def run_sql(sql, db='o2p', timeout=60):
    p = subprocess.run([PSQL, '-p', PORT, '-U', 'postgres', '-d', db, '-X', '-q', '-v', 'ON_ERROR_STOP=0'],
                       input=sql, capture_output=True, text=True, timeout=timeout)
    return p.stdout, p.stderr

def errors(stderr):
    return [l for l in stderr.splitlines() if 'ERROR:' in l]

def deploy(i, code):
    s = f'u{i:04d}'
    pre = f'DROP SCHEMA IF EXISTS {s} CASCADE; CREATE SCHEMA {s}; SET search_path={s},public; SET statement_timeout=\'10s\';\n'
    try:
        _, err = run_sql(pre + code)
    except subprocess.TimeoutExpired:
        return dict(unit=i, n_err=-1, first_err='timeout')
    e = errors(err)
    msg = re.sub(r'^.*ERROR:\s*', '', e[0]) if e else ''
    return dict(unit=i, n_err=len(e), first_err=msg[:200])

if __name__ == '__main__':
    subprocess.run([PSQL, '-p', PORT, '-U', 'postgres', '-Xqc', 'CREATE DATABASE o2p'], capture_output=True)
    d = pd.read_csv(DS)
    with ThreadPoolExecutor(8) as ex:
        res = list(ex.map(lambda t: deploy(*t), enumerate(d['output_db_query'].fillna(''))))
    r = pd.DataFrame(res); r['source'] = d['source']
    r.to_csv(os.path.join(OUT, 'ops_deploy_survey.csv'), index=False)
    print(r.n_err.eq(0).sum(), 'clean of', len(r))
    cat = r.first_err.str.replace(r'"[^"]*"', '"X"', regex=True)
    print(cat[r.n_err > 0].value_counts().head(25))
