"""Tiger Town website backend: Flask + MySQL Connector/Python.

Run from VS Code's terminal: python server/server.py
The same HTML frontend is served from frontend/ (download) or dist/ (checkout).
"""
from contextlib import contextmanager
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from pathlib import Path
import hmac
import json
import os
import secrets
import threading
import time
from urllib.parse import urlsplit

from dotenv import load_dotenv
from flask import Flask, abort, g, jsonify, request, send_from_directory, session
import mysql.connector
from werkzeug.exceptions import HTTPException
from werkzeug.security import check_password_hash

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / '.env')
FRONTEND = ROOT / ('frontend' if (ROOT / 'frontend').is_dir() else 'dist')
KINDS = {'business','neighborhood','shopping_area','outdoor_area','library','sports_venue','museum','unspecified_place'}
STATUSES = {'verified','needs_clarification','unverified'}
FIELDS = ['display_name','place_kind','city','street_address','state_code','postal_code',
          'latitude','longitude','website_url','menu_services','hours_summary',
          'student_discount_summary','price_min_usd','price_max_usd','price_basis',
          'verification_status','verification_source_url']
REQUIRED_TABLES = {'places','categories','place_categories','place_aliases','place_mentions','place_reviews'}


def create_app(test_config=None):
    app = Flask(__name__, static_folder=None)
    app.config.update(
        SECRET_KEY=os.getenv('APP_SECRET_KEY') or secrets.token_hex(32),
        ADMIN_PASSWORD_HASH=os.getenv('ADMIN_PASSWORD_HASH',''),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
        SESSION_COOKIE_SECURE=os.getenv('COOKIE_SECURE','false').lower()=='true',
        PERMANENT_SESSION_LIFETIME=timedelta(hours=2),
        MAX_CONTENT_LENGTH=64*1024,
        TRUSTED_HOSTS=[x.strip() for x in os.getenv('ALLOWED_HOSTS','localhost,127.0.0.1,[::1]').split(',')],
        DB_HOST=os.getenv('DB_HOST','127.0.0.1'),
        DB_PORT=int(os.getenv('DB_PORT','3306')),
        DB_USER=os.getenv('DB_USER','tigertown_user'),
        DB_PASSWORD=os.getenv('DB_PASSWORD',''),
        DB_NAME=os.getenv('DB_NAME','tigertown'),
    )
    if test_config:
        app.config.update(test_config)
    attempts = {}
    attempt_lock = threading.Lock()

    def connection():
        if 'db' not in g:
            factory=app.config.get('DB_FACTORY')
            g.db=factory() if factory else mysql.connector.connect(
                host=app.config['DB_HOST'], port=app.config['DB_PORT'],
                user=app.config['DB_USER'], password=app.config['DB_PASSWORD'],
                database=app.config['DB_NAME'], charset='utf8mb4',
                collation='utf8mb4_unicode_ci', connection_timeout=5,
                autocommit=False, use_pure=True,
            )
        return g.db

    def query(sql, params=(), one=False):
        cursor=connection().cursor(dictionary=True, buffered=True)
        try:
            cursor.execute(sql,params)
            rows=cursor.fetchall()
            return (rows[0] if rows else None) if one else rows
        finally:
            cursor.close()

    def execute(sql, params=()):
        cursor=connection().cursor()
        try:
            cursor.execute(sql,params)
            return cursor.lastrowid
        finally:
            cursor.close()

    @contextmanager
    def transaction():
        try:
            yield
            connection().commit()
        except Exception:
            connection().rollback()
            raise

    def tables():
        if 'tables' not in g:
            g.tables={r['table_name'] for r in query(
                'SELECT table_name AS table_name FROM information_schema.tables WHERE table_schema = %s',
                (app.config['DB_NAME'],))}
            if not REQUIRED_TABLES.issubset(g.tables):
                abort(503,description='The Tiger Town tables are missing. Import TigerTown_Jackson_Places.sql in MySQL Workbench first.')
        return g.tables

    def json_ready(value):
        if isinstance(value,dict):return {k:json_ready(v) for k,v in value.items()}
        if isinstance(value,list):return [json_ready(v) for v in value]
        if isinstance(value,Decimal):return str(value)
        if isinstance(value,(date,datetime)):return value.isoformat()
        return value

    def revision(place,categories):
        data={k:v for k,v in place.items() if k not in {'revision'}}
        data['category_ids']=sorted(int(c['category_id']) for c in categories)
        return sha256(json.dumps(json_ready(data),sort_keys=True,separators=(',',':')).encode()).hexdigest()

    def token():
        if 'csrf' not in session:session['csrf']=secrets.token_hex(32)
        return session['csrf']

    @app.before_request
    def protect_writes():
        if request.method in {'POST','PUT','PATCH','DELETE'}:
            supplied=request.headers.get('X-CSRF-Token','')
            expected=session.get('csrf','')
            if not expected or not hmac.compare_digest(supplied,expected):
                abort(403,description='Your session expired. Reload the website and try again.')
            if request.path!='/api/login' and not session.get('admin'):
                abort(401,description='Sign in as an administrator to change the database.')
            if not request.is_json:
                abort(415,description='Send a JSON request.')

    @app.after_request
    def headers(response):
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Referrer-Policy']='strict-origin-when-cross-origin'
        response.headers['X-Frame-Options']='SAMEORIGIN'
        response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'; base-uri 'self'; form-action 'self'; frame-ancestors 'self'"
        if request.path.startswith('/api/') or request.path=='/site-config.json':
            response.headers['Cache-Control']='no-store'
        return response

    @app.teardown_appcontext
    def close_db(error=None):
        db=g.pop('db',None)
        if db:
            try:db.rollback()
            finally:db.close()

    @app.errorhandler(HTTPException)
    def http_error(error):
        return jsonify(error=error.description),error.code

    @app.errorhandler(mysql.connector.Error)
    def db_error(error):
        # Never return SQL, passwords, connection strings, or a traceback to the page.
        if error.errno==1062:
            return jsonify(error='A place with that name already exists. Choose a different name.'),409
        message={1045:'MySQL rejected the login. Check the username and password in .env.',
                 1044:'The MySQL account cannot access tigertown. Check its database permissions.',
                 1049:'The database does not exist. Import the Tiger Town SQL file first.',
                 1146:'A required table is missing. Import the original Tiger Town database SQL file.',
                 2003:'MySQL is unreachable. Start MySQL and check DB_HOST and DB_PORT in .env.',
                 2005:'The MySQL host could not be resolved. Check DB_HOST in .env.'}.get(error.errno,
                 'The database request failed. Check the MySQL server, connection settings and account permissions.')
        app.logger.warning('MySQL request failed (error code %s)',error.errno)
        return jsonify(error=message),503

    @app.get('/')
    def home():return send_from_directory(FRONTEND,'index.html')

    @app.get('/site-config.json')
    def site_config():return jsonify(mode='mysql')

    @app.get('/api/session')
    def session_info():return jsonify(admin=bool(session.get('admin')),csrf=token())

    @app.post('/api/login')
    def login():
        password_hash=app.config['ADMIN_PASSWORD_HASH']
        if not password_hash:
            abort(503,description='Administrator sign-in is not configured. Run python server/setup.py first.')
        data=request.get_json()
        if not isinstance(data,dict) or not isinstance(data.get('password'),str):
            abort(400,description='Enter the administrator password.')
        now=time.monotonic()
        key=request.remote_addr or 'local'
        with attempt_lock:
            # Keep only recent attempts and prevent unbounded growth.
            for old in list(attempts):
                attempts[old]=[t for t in attempts[old] if now-t<300]
                if not attempts[old]:del attempts[old]
            recent=attempts.setdefault(key,[])
            if len(recent)>=8:abort(429,description='Too many sign-in attempts. Wait five minutes and try again.')
            recent.append(now)
        password=data['password']
        if len(password)>200 or not check_password_hash(password_hash,password):
            abort(401,description='The administrator password is incorrect.')
        with attempt_lock:attempts.pop(key,None)
        session.clear();session['admin']=True;session.permanent=True
        return jsonify(admin=True,csrf=token())

    @app.post('/api/logout')
    def logout():
        session.clear()
        return jsonify(admin=False,csrf=token())

    @app.get('/api/catalog')
    def catalog():
        existing=tables()
        places=query('SELECT * FROM places ORDER BY display_name')
        categories=query('SELECT * FROM categories ORDER BY category_id')
        links=query('SELECT pc.place_id, c.category_id, c.category_name FROM place_categories pc JOIN categories c ON c.category_id=pc.category_id ORDER BY c.category_id')
        aliases=query('SELECT place_id, alias FROM place_aliases')
        votes=query("SELECT place_id,COUNT(DISTINCT response_id) AS total FROM place_mentions WHERE response_field=%s GROUP BY place_id",('favorite_place',))
        reviews=query('SELECT place_id,COUNT(*) AS total,ROUND(AVG(rating),1) AS average FROM place_reviews GROUP BY place_id')
        research=query('SELECT * FROM place_research') if 'place_research' in existing else []
        branches=query('SELECT * FROM place_branches ORDER BY branch_name') if 'place_branches' in existing else []
        candidates=query('SELECT * FROM place_identity_candidates ORDER BY candidate_name') if 'place_identity_candidates' in existing else []
        field_notes=query('SELECT * FROM place_research_fields ORDER BY field_name') if 'place_research_fields' in existing else []
        by_id={p['place_id']:p for p in places}
        for p in places:
            p.update(categories=[],aliases=[],branches=[],candidates=[],field_notes=[],survey_votes=0,review_count=0,average_rating=None)
        for row in links:by_id[row['place_id']]['categories'].append({k:row[k] for k in ['category_id','category_name']})
        for row in aliases:by_id[row['place_id']]['aliases'].append(row['alias'])
        for row in votes:by_id[row['place_id']]['survey_votes']=row['total']
        for row in reviews:by_id[row['place_id']].update(review_count=row['total'],average_rating=row['average'])
        for row in research:
            by_id[row['place_id']].update(canonical_name=row['canonical_name'],research_notes=row['research_notes'],primary_source_url=row['primary_source_url'])
        for rows,field in [(branches,'branches'),(candidates,'candidates'),(field_notes,'field_notes')]:
            for row in rows:by_id[row['place_id']][field].append(row)
        # Only administrators receive revision tokens for editing.
        if session.get('admin'):
            for p in places:
                # Same raw place row used by the locked update below.
                raw={k:v for k,v in p.items() if k not in {'categories','aliases','branches','candidates','field_notes','survey_votes','review_count','average_rating','canonical_name','research_notes','primary_source_url'}}
                p['revision']=revision(raw,p['categories'])
        response=jsonify(json_ready({'places':places,'categories':categories}))
        # Manual refreshes can reuse an unchanged catalog without transferring it again.
        response.set_etag(sha256(response.get_data()).hexdigest())
        return response.make_conditional(request)

    def validate(data):
        if not isinstance(data,dict):abort(400,description='Invalid place data.')
        result={}
        limits={'display_name':255,'city':128,'street_address':255,'state_code':2,'postal_code':16,'price_basis':255}
        numbers={'latitude':(-90,90,6),'longitude':(-180,180,6),'price_min_usd':(0,99999999.99,2),'price_max_usd':(0,99999999.99,2)}
        for field in FIELDS:
            raw=data.get(field)
            if raw is not None and not isinstance(raw,(str,int,float)):
                abort(400,description=f'{field.replace("_"," ")} has an invalid value.')
            value=str(raw).strip() if raw is not None else ''
            if not value:result[field]=None;continue
            if field in numbers:
                lo,hi,digits=numbers[field]
                try:
                    number=Decimal(value)
                    if not number.is_finite() or number<Decimal(str(lo)) or number>Decimal(str(hi)):raise InvalidOperation
                    rounded=number.quantize(Decimal(1).scaleb(-digits))
                except (InvalidOperation,ValueError):abort(400,description=f'{field.replace("_"," ")} must be between {lo} and {hi}.')
                result[field]=rounded
            else:
                if len(value)>limits.get(field,4000):abort(400,description=f'{field.replace("_"," ")} is too long.')
                if field.endswith('_url'):
                    try:
                        url=urlsplit(value)
                        valid_host=bool(url.hostname)
                    except ValueError:
                        abort(400,description='Enter a valid website or source URL.')
                    if url.scheme not in {'http','https'} or not valid_host or url.username or url.password:
                        abort(400,description='Website and source links must be valid http or https URLs without embedded credentials.')
                result[field]=value
        if not result['display_name']:abort(400,description='Place name is required.')
        if result['place_kind'] not in KINDS:abort(400,description='Select a valid place type.')
        if result['verification_status'] not in STATUSES:abort(400,description='Select a valid identity status.')
        if result['state_code']:
            if not result['state_code'].isascii() or not result['state_code'].isalpha() or len(result['state_code'])!=2:
                abort(400,description='State must contain exactly two letters, such as MS.')
            result['state_code']=result['state_code'].upper()
        if (result['latitude'] is None)!=(result['longitude'] is None):abort(400,description='Enter both coordinates, or leave both blank.')
        lo,hi=result['price_min_usd'],result['price_max_usd']
        if lo is not None and hi is not None and lo>hi:abort(400,description='Minimum price cannot exceed maximum price.')
        if (lo is not None or hi is not None) and not result['price_basis']:abort(400,description='Explain what the price sample covers.')
        if result['verification_status']=='verified' and not result['verification_source_url']:abort(400,description='A verified identity requires a source URL.')
        ids=data.get('categories',[])
        if not isinstance(ids,list) or any(type(v) is not int for v in ids):abort(400,description='Choose valid categories.')
        allowed={r['category_id'] for r in query('SELECT category_id FROM categories')}
        if not set(ids).issubset(allowed):abort(400,description='A selected category no longer exists.')
        return result,sorted(set(ids))

    def save_categories(place_id,ids):
        # Only catalog category links change; historical survey votes do not.
        old=query('SELECT category_id FROM place_categories WHERE place_id=%s',(place_id,))
        existing={r['category_id'] for r in old}
        for category_id in existing-set(ids):
            execute('DELETE FROM place_categories WHERE place_id=%s AND category_id=%s',(place_id,category_id))
        for category_id in set(ids)-existing:
            execute('INSERT INTO place_categories (place_id,category_id,mapping_basis) VALUES (%s,%s,%s)',(place_id,category_id,'Manual category assignment through Tiger Town website.'))

    @app.post('/api/places')
    def add_place():
        tables()
        data=request.get_json()
        with transaction():
            clean,ids=validate(data)
            note=data.get('identity_notes','')
            if not isinstance(note,str) or len(note)>4000:abort(400,description='Identity notes must be at most 4000 characters.')
            clean['identity_notes']=note.strip() or 'Added manually through the Tiger Town website.'
            clean['verified_at']=datetime.now(timezone.utc).replace(tzinfo=None) if clean['verification_status']=='verified' else None
            cols=list(clean)
            # Column names are fixed by FIELDS above, never supplied as SQL by the client.
            place_id=execute('INSERT INTO places ('+','.join(cols)+') VALUES ('+','.join(['%s']*len(cols))+')',tuple(clean[c] for c in cols))
            save_categories(place_id,ids)
        return jsonify(place_id=place_id,message='Place created.'),201

    @app.put('/api/places/<int:place_id>')
    def update_place(place_id):
        tables()
        data=request.get_json()
        if not isinstance(data,dict):abort(400,description='Invalid place data.')
        with transaction():
            current=query('SELECT * FROM places WHERE place_id=%s FOR UPDATE',(place_id,),one=True)
            if not current:abort(404,description='This place no longer exists.')
            categories=query('SELECT category_id FROM place_categories WHERE place_id=%s',(place_id,))
            provided=data.get('revision','')
            if not isinstance(provided,str) or not hmac.compare_digest(provided,revision(current,categories)):
                abort(409,description='This place changed after you opened it. Close the editor, reload the website, and try again.')
            clean,ids=validate(data)
            # Preserve historical survey text, original identity notes and reported area.
            # Preserve the original name as an alias when renaming a place.
            if current['display_name']!=clean['display_name']:
                old=query('SELECT alias FROM place_aliases WHERE place_id=%s AND alias=%s',(place_id,current['display_name']))
                if not old:execute('INSERT INTO place_aliases (place_id,alias) VALUES (%s,%s)',(place_id,current['display_name']))
            identity_changed=any(clean.get(k)!=current.get(k) for k in ['display_name','street_address','city','verification_source_url'])
            clean['verified_at']=datetime.now(timezone.utc).replace(tzinfo=None) if clean['verification_status']=='verified' and (identity_changed or not current['verified_at']) else current['verified_at']
            execute('UPDATE places SET '+','.join(c+'=%s' for c in clean)+' WHERE place_id=%s',tuple(clean.values())+(place_id,))
            save_categories(place_id,ids)
        return jsonify(place_id=place_id,message='Place updated.')

    @app.get('/<path:name>')
    def assets(name):
        # Explicit allowlist: server code, .env and database credentials are never served.
        if name not in {'style.css','main.js','mark.svg','catalog.json','downloads/TigerTown_Website_MySQL.zip'}:
            abort(404,description='Page not found.')
        return send_from_directory(FRONTEND,name)

    return app


if __name__=='__main__':
    app=create_app()
    port=int(os.getenv('PORT','5000'))
    print(f'Open the Tiger Town website at http://127.0.0.1:{port}')
    app.run(host='127.0.0.1',port=port,debug=False)
