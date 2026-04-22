# -*- coding: UTF-8 -*-
# !/usr/bin/python
# 2020-09-01 fix pool
# 2020-09-03 adding 98 fetchall
# 2020-12-22 inactive module mosql
import psycopg2
from psycopg2.pool import ThreadedConnectionPool
# import mosql
import os
from dotenv import load_dotenv

# Load .env file if it exists
load_dotenv()

import socket
hostname = "mail.itolemma.com"
eikon_token = os.getenv('EIKON_TOKEN', '')
bpipe_host = os.getenv('BPIPE_HOST', "")
bpipe_port = int(os.getenv('BPIPE_PORT', 8194))

pg_host = os.getenv('DB_HOST', "127.0.0.1")
pg_port = int(os.getenv('DB_PORT', 5432))
pg_user = os.getenv('DB_USER', "")
pg_passwd = os.getenv('DB_PASS', "")

pg_host98 = os.getenv('DB_HOST_98', "")
pg_port98 = int(os.getenv('DB_PORT_98', 5432))
pg_user98 = os.getenv('DB_USER_98', "")
pg_passwd98 = os.getenv('DB_PASS_98', "")


conn_pools = {}
conn_pools98 = {}
conn_pools59 = {}

def getconn(database):
    if database not in conn_pools:
        dsn = "host='%s' port='%s' dbname='%s' user='%s' password='%s' " % (
            pg_host, pg_port, database, pg_user, pg_passwd)
        conn_pools[database] = ThreadedConnectionPool(1, 5, dsn=dsn)
    return conn_pools[database].getconn()

def getconn98(database):
    if database not in conn_pools98:
        dsn = "host='%s' port='%s' dbname='%s' user='%s' password='%s'" % (
            pg_host98, pg_port98, database, pg_user98, pg_passwd98)
        conn_pools98[database] = ThreadedConnectionPool(1, 5, dsn=dsn)
    return conn_pools98[database].getconn()

def getconn59(database):
    host59 = os.getenv('DB_HOST_59', "")
    port59 = int(os.getenv('DB_PORT_59', 5432))
    user59 = os.getenv('DB_USER_59', "")
    passwd59 = os.getenv('DB_PASS_59', "")
    if database not in conn_pools59:
        dsn = "host='%s' port='%s' dbname='%s' user='%s' password='%s'" % (
            host59, port59, database, user59, passwd59)
        conn_pools59[database] = ThreadedConnectionPool(1, 5, dsn=dsn)
    return conn_pools59[database].getconn()

def db99Query(database, sqlstring):
    conn = getconn(database)
    cur = conn.cursor()
    try:
        cur.execute(sqlstring)
        r = cur.fetchall()
        cur.close()
    except (Exception, psycopg2.Error) as error:
        r = None
    finally:
        conn_pools[database].putconn(conn)
        return r


def db99fetchall(database, sqlstring):
    conn = getconn(database)
    cur = conn.cursor()
    try:
        cur.execute(sqlstring)
        r = cur.fetchall()
        cur.close()
    except (Exception, psycopg2.Error) as error:
        r = None
    finally:
        conn_pools[database].putconn(conn)
        return r

def db99fetchall_dict(database, sqlstring):
    conn = getconn(database)
    cur = conn.cursor()
    try:
        cur.execute(sqlstring)
        names = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
        out = []
        for row in rows:
            out.append(dict(zip(names, row)))
        cur.close()
    except (Exception, psycopg2.Error) as error:
        out = []
    finally:
        conn_pools[database].putconn(conn)
        return out


def db98fetchall(database, sqlstring):
    conn = getconn98(database)
    cur = conn.cursor()
    try:
        cur.execute(sqlstring)
        r = cur.fetchall()
        cur.close()
    except (Exception, psycopg2.Error) as error:
        r = None
    finally:
        conn_pools98[database].putconn(conn)
        return r
def db98fetchall_dict(database, sqlstring):
    conn = getconn98(database)
    cur = conn.cursor()
    try:
        cur.execute(sqlstring)
        names = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
        out = []
        for row in rows:
            out.append(dict(zip(names, row)))
        cur.close()
    except (Exception, psycopg2.Error) as error:
        out = []
    finally:
        conn_pools98[database].putconn(conn)
        return out
def db59fetchall(database, sqlstring):
    conn = getconn59(database)
    cur = conn.cursor()
    try:
        cur.execute(sqlstring)
        r = cur.fetchall()
        cur.close()
    except (Exception, psycopg2.Error) as error:
        r = None
    finally:
        conn_pools59[database].putconn(conn)
        return r

def db59fetchall_dict(database, sqlstring):
    conn = getconn59(database)
    cur = conn.cursor()
    try:
        cur.execute(sqlstring)
        names = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
        out = []
        for row in rows:
            out.append(dict(zip(names, row)))
        cur.close()
    except (Exception, psycopg2.Error) as error:
        out = []
    finally:
        conn_pools59[database].putconn(conn)
        return out

def db99fetchone(database, sqlstring):
    conn = getconn(database)
    cur = conn.cursor()
    try:
        cur.execute(sqlstring)
        r = cur.fetchone()
        cur.close()
    except (Exception, psycopg2.Error) as error:
        r = None
    finally:
        conn_pools[database].putconn(conn)
        return r


def db99exec(database, sqlstring):
    conn = getconn(database)
    cur = conn.cursor()
    try:
        cur.execute(sqlstring)
        conn.commit()
        cur.close()
    except (Exception, psycopg2.Error) as error:
        conn.rollback()
        cur.close()
        return error
    finally:
        cur.close()
        conn_pools[database].putconn(conn)

def db98exec(database, sqlstring):
    conn = getconn98(database)
    cur = conn.cursor()
    try:
        cur.execute(sqlstring)
        conn.commit()
        cur.close()
    except (Exception, psycopg2.Error) as error:
        conn.rollback()
    finally:
        conn_pools98[database].putconn(conn)


def db59exec(database, sqlstring):
    conn = getconn59(database)
    cur = conn.cursor()
    try:
        cur.execute(sqlstring)
        conn.commit()
        cur.close()
    except (Exception, psycopg2.Error) as error:
        conn.rollback()
    finally:
        conn_pools59[database].putconn(conn)

# def db99insert(database, table, adict):
#     sqlstring = mosql.query.insert(table, adict)
#     db99exec(database, sqlstring)


# import _pg as pg
# import psycopg2
# from config import pg_host, pg_port, pg_user, pg_passwd
#
# def db99(dbname):
#     return pg.connect(dbname=dbname, host=pg_host, port=pg_port, user=pg_user, passwd=pg_passwd)
#
# def db59(dbname):
#     return pg.connect(dbname=dbname, host="192.168.1.59", port=5432, user="postgres", passwd="postgres")
#
# def dblocal(dbname):
#     return pg.connect(dbname=dbname, host="127.0.0.1", port=5432, user="postgres", passwd="postgres")
#     #return pg.connect(dbname=dbname, host="192.168.1.122", port=5432, user="postgres", passwd="postgres")
#
#
# def db99Query(dbname, sqlString):
#     db = db99(dbname)
#     #items = db.query(sqlString).getresult() #This shows 2016-10-10
#     #modify by Michael
#     items = db.query(sqlString).dictresult() #This shows {'da':2016-10-10}
#     return items
#
# def dblocalQuery(dbname, sqlString):
#     db = dblocal(dbname)
#     #items = db.query(sqlString).getresult() #This shows 2016-10-10
#     #modify by Michael
#     items = db.query(sqlString).dictresult() #This shows {'da':2016-10-10}
#     return items
#
# def db99exec(dbname, sqlString):
#     db = db99(dbname)
#     db.query(sqlString)
#
# def dblocalexec(dbname, sqlString):
#     db = dblocal(dbname)
#     db.query(sqlString)
#
#
# class PgDB:
#     def __init__(self, con_string):
#         self.con = psycopg2.connect(con_string)
#         self.cur = self.con.cursor()
#
#     def insertRows(self, qString, rows):
#         self.cur.executemany(qString, rows)
#
#     def execute(self,qString):
#         self.cur.execute(qString)
#
#     def query(self,qString):
#         self.cur.execute(qString)
#         return self.cur.fetchall()
#
#     def close(self):
#         self.cur.close()
#         self.con.close()
#
#     def __del__(self):
#         self.close()
#
#
#
#
#
# def db99b(dbname):
#     conn_string = "host='%s' port='%s' dbname='%s' user='%s' password='%s'" % (pg_host,pg_port,dbname,pg_user,pg_passwd)
#     pgdb = PgDB(conn_string)
#     return pgdb

if __name__ == "__main__":
    sql  ="select * from price limit 1"
    db99exec('daily', sql)
    a=1
