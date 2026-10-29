"""Behavioral tests with a SQLite adapter for the MySQL DB-API boundary.

Actual MySQL settings remain private to the user's computer. These tests exercise
the real Flask routes and SQL, translating only parameter markers, metadata and locks.
"""
from datetime import datetime
from decimal import Decimal
import json
from pathlib import Path
import sqlite3
import sys

import mysql.connector
import pytest
from werkzeug.security import generate_password_hash

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from server.server import create_app, FIELDS

PASSWORD='test-password-for-tests-only'


class Cursor:
    def __init__(self,owner,dictionary=False):
        self.owner=owner;self.dictionary=dictionary;self.cursor=owner.db.cursor();self.rows=None

    def execute(self,sql,params=()):
        self.owner.statements.append((sql,params))
        if 'information_schema.tables' in sql:
            self.rows=[{'table_name':r[0]} for r in self.owner.db.execute("SELECT name FROM sqlite_master WHERE type='table'")];return
        if self.owner.fail_categories and sql.startswith('INSERT INTO place_categories'):
            raise mysql.connector.Error(msg='simulated write failure',errno=1205)
        sql=sql.replace(' FOR UPDATE','').replace('%s','?')
        params=tuple(str(v) if isinstance(v,Decimal) else v.isoformat() if isinstance(v,datetime) else v for v in params)
        try:self.cursor.execute(sql,params)
        except sqlite3.IntegrityError as error:
            raise mysql.connector.IntegrityError(msg='constraint failure',errno=1062) from error

    def fetchall(self):
        if self.rows is not None:return self.rows
        return [dict(r) if self.dictionary else tuple(r) for r in self.cursor.fetchall()]

    @property
    def lastrowid(self):return self.cursor.lastrowid

    def close(self):self.cursor.close()


class Connection:
    def __init__(self,path,state):
        self.db=sqlite3.connect(path);self.db.row_factory=sqlite3.Row
        self.db.execute('PRAGMA foreign_keys=ON')
        self.statements=state['statements'];self.fail_categories=state.get('fail_categories',False)
    def cursor(self,dictionary=False,buffered=False):return Cursor(self,dictionary)
    def commit(self):self.db.commit()
    def rollback(self):self.db.rollback()
    def close(self):self.db.close()


@pytest.fixture
def site(tmp_path):
    path=tmp_path/'test.sqlite';db=sqlite3.connect(path)
    db.executescript('''
    CREATE TABLE places (
      place_id INTEGER PRIMARY KEY AUTOINCREMENT, display_name TEXT NOT NULL COLLATE NOCASE UNIQUE,
      place_kind TEXT NOT NULL, reported_area TEXT, identity_notes TEXT NOT NULL,
      verification_status TEXT NOT NULL DEFAULT 'unverified', street_address TEXT, city TEXT,
      state_code TEXT, postal_code TEXT, latitude NUMERIC, longitude NUMERIC, website_url TEXT,
      hours_summary TEXT, menu_services TEXT, student_discount_summary TEXT, price_min_usd NUMERIC,
      price_max_usd NUMERIC, price_basis TEXT, verification_source_url TEXT, verified_at TEXT,
      CHECK ((latitude IS NULL AND longitude IS NULL) OR (latitude IS NOT NULL AND longitude IS NOT NULL)),
      CHECK (price_min_usd IS NULL OR price_max_usd IS NULL OR price_min_usd<=price_max_usd),
      CHECK (verification_status<>'verified' OR (verification_source_url IS NOT NULL AND verified_at IS NOT NULL))
    );
    CREATE TABLE categories (category_id INTEGER PRIMARY KEY,category_name TEXT,is_survey_option INTEGER);
    CREATE TABLE place_categories (place_id INTEGER REFERENCES places(place_id),category_id INTEGER REFERENCES categories(category_id),mapping_basis TEXT,PRIMARY KEY(place_id,category_id));
    CREATE TABLE place_aliases (place_id INTEGER REFERENCES places(place_id),alias TEXT COLLATE NOCASE,PRIMARY KEY(place_id,alias));
    CREATE TABLE place_mentions (place_id INTEGER REFERENCES places(place_id),response_id INTEGER,response_field TEXT);
    CREATE TABLE place_reviews (review_id INTEGER PRIMARY KEY,place_id INTEGER REFERENCES places(place_id),rating INTEGER);
    ''')
    data=json.loads((ROOT/('frontend' if (ROOT/'frontend').exists() else 'dist')/'catalog.json').read_text())
    cols=[r[1] for r in db.execute('PRAGMA table_info(places)')]
    for cat in data['categories']:db.execute('INSERT INTO categories VALUES (?,?,?)',(cat['category_id'],cat['category_name'],cat['is_survey_option']))
    for p in data['places']:
        db.execute('INSERT INTO places ('+','.join(cols)+') VALUES ('+','.join('?' for _ in cols)+')',tuple(p.get(c) for c in cols))
        for c in p['categories']:db.execute('INSERT INTO place_categories VALUES (?,?,?)',(p['place_id'],c['category_id'],'original survey category'))
        for a in p['aliases']:db.execute('INSERT INTO place_aliases VALUES (?,?)',(p['place_id'],a))
        for i in range(p['survey_votes']):db.execute('INSERT INTO place_mentions VALUES (?,?,?)',(p['place_id'],i+1,'favorite_place'))
    db.commit();db.close()
    state={'statements':[]}
    app=create_app({'TESTING':True,'SECRET_KEY':'test-only-secret','ADMIN_PASSWORD_HASH':generate_password_hash(PASSWORD),'DB_FACTORY':lambda:Connection(path,state)})
    return app,app.test_client(),path,state


def sign_in(client):
    csrf=client.get('/api/session').json['csrf']
    response=client.post('/api/login',json={'password':PASSWORD},headers={'X-CSRF-Token':csrf})
    assert response.status_code==200
    return {'X-CSRF-Token':response.json['csrf']}


def payload(p=None):
    data={k:p.get(k) for k in FIELDS} if p else dict(display_name='Test place',place_kind='business',state_code='MS',verification_status='unverified')
    data['categories']=[c['category_id'] for c in p['categories']] if p else [1]
    if p:data['revision']=p['revision']
    return data


def test_preview_assets_and_no_secret_files(site):
    _,client,_,_=site
    assert client.get('/').status_code==200
    assert client.get('/style.css').status_code==200
    assert client.get('/site-config.json').json['mode']=='mysql'
    assert client.get('/.env').status_code==404
    assert client.get('/server/server.py').status_code==404


def test_reads_original_database_without_optional_research_tables(site):
    _,client,_,_=site
    response=client.get('/api/catalog')
    assert response.status_code==200
    assert len(response.json['places'])==27
    assert len(response.json['categories'])==8
    assert 'revision' not in response.json['places'][0]
    assert response.json['places'][0]['branches']==[]


def test_csrf_and_admin_required(site):
    _,client,_,_=site
    assert client.post('/api/places',json=payload()).status_code==403
    csrf=client.get('/api/session').json['csrf']
    assert client.post('/api/places',json=payload(),headers={'X-CSRF-Token':csrf}).status_code==401
    assert client.post('/api/login',json={'password':'wrong'},headers={'X-CSRF-Token':csrf}).status_code==401


def test_create_edit_rename_categories_and_preserve_survey(site):
    _,client,path,state=site;headers=sign_in(client)
    before=sqlite3.connect(path).execute('SELECT * FROM place_mentions ORDER BY place_id,response_id').fetchall()
    result=client.post('/api/places',json=payload(),headers=headers)
    assert result.status_code==201
    place_id=result.json['place_id']
    p=next(p for p in client.get('/api/catalog').json['places'] if p['place_id']==place_id)
    data=payload(p);data.update(display_name='Renamed place',hours_summary='Updated hours',categories=[2],verification_status='verified',verification_source_url='https://example.com/place')
    result=client.put(f'/api/places/{place_id}',json=data,headers=headers)
    assert result.status_code==200
    updated=next(p for p in client.get('/api/catalog').json['places'] if p['place_id']==place_id)
    assert updated['display_name']=='Renamed place'
    assert updated['aliases']==['Test place']
    assert [c['category_id'] for c in updated['categories']]==[2]
    assert updated['verified_at']
    assert any('FOR UPDATE' in s for s,_ in state['statements'])
    assert before==sqlite3.connect(path).execute('SELECT * FROM place_mentions ORDER BY place_id,response_id').fetchall()


@pytest.mark.parametrize('values',[
    {'display_name':''},{'state_code':'MISS'},{'state_code':'M1'},
    {'latitude':'NaN','longitude':'-90'},{'latitude':'32'},
    {'latitude':'91','longitude':'-90'},{'price_min_usd':'-1'},
    {'price_min_usd':'20','price_max_usd':'10','price_basis':'Sample'},
    {'price_min_usd':'5'},{'verification_status':'verified'},
    {'website_url':'javascript:alert(1)'},{'place_kind':'made_up'},
    {'website_url':'https://['},
    {'categories':[99999]},{'categories':['1']},{'city':'x'*129},
])
def test_server_rejects_invalid_input(site,values):
    _,client,path,_=site;headers=sign_in(client);data=payload();data.update(values)
    result=client.post('/api/places',json=data,headers=headers)
    assert result.status_code==400,result.json
    assert sqlite3.connect(path).execute('SELECT COUNT(*) FROM places').fetchone()[0]==27


def test_sql_injection_is_stored_as_a_value(site):
    _,client,path,state=site;headers=sign_in(client);data=payload();name="Robert'); DROP TABLE places; --";data['display_name']=name
    response=client.post('/api/places',json=data,headers=headers)
    assert response.status_code==201
    db=sqlite3.connect(path)
    assert db.execute('SELECT display_name FROM places WHERE place_id=?',(response.json['place_id'],)).fetchone()[0]==name
    assert any('%s' in sql and name in params for sql,params in state['statements'])
    assert db.execute('SELECT COUNT(*) FROM places').fetchone()[0]==28


def test_duplicate_name_rolls_back(site):
    _,client,path,_=site;headers=sign_in(client);data=payload();data['display_name']='Foundation Burger'
    response=client.post('/api/places',json=data,headers=headers)
    assert response.status_code==409
    assert sqlite3.connect(path).execute('SELECT COUNT(*) FROM places').fetchone()[0]==27


def test_related_write_failure_rolls_back_parent(site):
    _,client,path,state=site;headers=sign_in(client);state['fail_categories']=True
    response=client.post('/api/places',json=payload(),headers=headers)
    assert response.status_code==503
    assert sqlite3.connect(path).execute('SELECT COUNT(*) FROM places').fetchone()[0]==27


def test_stale_edit_cannot_overwrite_newer_values(site):
    _,client,_,_=site;headers=sign_in(client)
    p=client.get('/api/catalog').json['places'][0];data=payload(p);data['hours_summary']='First edit'
    assert client.put(f"/api/places/{p['place_id']}",json=data,headers=headers).status_code==200
    data['hours_summary']='Stale second edit'
    assert client.put(f"/api/places/{p['place_id']}",json=data,headers=headers).status_code==409


def test_logout_clears_admin_permission(site):
    _,client,_,_=site;headers=sign_in(client)
    r=client.post('/api/logout',json={},headers=headers)
    assert r.status_code==200
    assert client.post('/api/places',json=payload(),headers={'X-CSRF-Token':r.json['csrf']}).status_code==401


def test_missing_admin_password_disabled(site):
    app,client,_,_=site;app.config['ADMIN_PASSWORD_HASH']=''
    csrf=client.get('/api/session').json['csrf']
    assert client.post('/api/login',json={'password':PASSWORD},headers={'X-CSRF-Token':csrf}).status_code==503


def test_missing_base_schema_clear_error(site):
    _,client,path,_=site
    db=sqlite3.connect(path);db.execute('DROP TABLE place_reviews');db.close()
    r=client.get('/api/catalog')
    assert r.status_code==503 and 'tables are missing' in r.json['error']


def test_login_rate_limit(site):
    _,client,_,_=site;csrf=client.get('/api/session').json['csrf']
    for _ in range(8):assert client.post('/api/login',json={'password':'wrong'},headers={'X-CSRF-Token':csrf}).status_code==401
    assert client.post('/api/login',json={'password':PASSWORD},headers={'X-CSRF-Token':csrf}).status_code==429


def test_external_database_insert_changes_etag_and_catalog(site):
    _,client,path,_=site
    first=client.get('/api/catalog')
    etag=first.headers['ETag']
    assert client.get('/api/catalog',headers={'If-None-Match':etag}).status_code==304
    # Simulates an INSERT made outside the website, such as from MySQL Workbench.
    db=sqlite3.connect(path)
    db.execute("INSERT INTO places (display_name,place_kind,identity_notes,verification_status,city) VALUES (?,?,?,?,?)",('New Workbench place','business','Added outside website','unverified','Jackson'))
    db.commit();db.close()
    latest=client.get('/api/catalog',headers={'If-None-Match':etag})
    assert latest.status_code==200
    assert latest.headers['ETag']!=etag
    assert any(p['display_name']=='New Workbench place' for p in latest.json['places'])
    assert len(latest.json['places'])==28


def test_original_notes_and_survey_area_are_preserved(site):
    _,client,path,_=site;headers=sign_in(client)
    p=client.get('/api/catalog').json['places'][0]
    data=payload(p);data.update(identity_notes='Do not replace historical context',reported_area='Do not replace reported area')
    assert client.put(f"/api/places/{p['place_id']}",json=data,headers=headers).status_code==200
    row=sqlite3.connect(path).execute('SELECT identity_notes,reported_area FROM places WHERE place_id=?',(p['place_id'],)).fetchone()
    assert row==(p['identity_notes'],p['reported_area'])


def test_optional_research_tables_attach_to_places(site):
    _,client,path,_=site
    data=json.loads((ROOT/('frontend' if (ROOT/'frontend').exists() else 'dist')/'catalog.json').read_text())
    db=sqlite3.connect(path)
    db.execute('CREATE TABLE place_research (place_id INTEGER,canonical_name TEXT,research_notes TEXT,primary_source_url TEXT)')
    for p in data['places']:
        db.execute('INSERT INTO place_research VALUES (?,?,?,?)',(p['place_id'],p['canonical_name'],p['research_notes'],p['primary_source_url']))
    for field,table in [('branches','place_branches'),('candidates','place_identity_candidates'),('field_notes','place_research_fields')]:
        rows=[row for p in data['places'] for row in p[field]]
        cols=list(dict.fromkeys(k for row in rows for k in row))
        db.execute('CREATE TABLE '+table+' ('+','.join(k+(' INTEGER' if k=='place_id' else ' TEXT') for k in cols)+')')
        for row in rows:db.execute('INSERT INTO '+table+' VALUES ('+','.join('?' for _ in cols)+')',tuple(row.get(k) for k in cols))
    db.commit();db.close()
    result=client.get('/api/catalog')
    assert result.status_code==200
    places=result.json['places']
    assert sum(len(p['branches']) for p in places)==14
    assert sum(len(p['candidates']) for p in places)==5
    assert sum(len(p['field_notes']) for p in places)==351
    assert next(p for p in places if p['place_id']==6)['canonical_name']=='Dogmud Tavern'
