import sqlite3
from sqlite3 import Error

def create_connection(db_path):
	"""
	Creates the sqlite3 connection

	INTPUT:
		db_path: (str) relative path to sqlite db

	OUTPUT:
		conn: sqlite3 connection
	"""
	try:
		conn = sqlite3.connect(db_path)
	except Error as e:
		print(e)
	return conn

def create_record(conn, table, data):
	"""
	Inserts "data" into "table"

	INTPUT:
		conn: sqlite3 connection
		table: (str) table name
		data: (str) string or iterable of strings containing data

	OUTPUT:
		search_id: (int) returns iff table == "searches", id of newly created record
	"""
	cur = conn.cursor()
	if table == "searches":
		sql = '''
		INSERT INTO searches 
		(root_video, n_splits, depth, date, sample, const_depth)
		VALUES (?,?,?,?,?,?)'''
		cur.execute(sql, data)
		# return the id of the newly created record
		sql = 'SELECT max(search_id) FROM searches'
		search_id = cur.execute(sql).fetchone()[0]
		return search_id
	elif table == "videos":
		sql = '''
		INSERT INTO videos 
		(video_id, search_id, title, postdate, description, category, 
		channel_id, likes, dislikes, views, n_comments)
		VALUES (?,?,?,?,?,?,?,?,?,?,?)'''
	elif table == "channels":
		sql = '''
		INSERT INTO channels
		(channel_id, search_id, name, country, date_created, 
		n_subscribers, n_videos, n_views, categories)
		VALUES (?,?,?,?,?,?,?,?,?)
		'''
	elif table == "recommendations":
		sql = '''
		INSERT INTO recommendations
		(video_id, search_id, recommendations, depth)
		VALUES (?,?,?,?)
		'''
	cur.executemany(sql, data)


def record_exists(conn, table, col, val):
	"""
	Checks whether 'col':'val" exists in 'table'
	
	INPUT:
		conn: sqlite3 connection
		table: (str) table name
		col: (str) column name
		val: value
	
	OUTPUT:
		bool for whether record exsits
	"""
	sql = ("SELECT * FROM {} WHERE {} = {}"
		   .format(table, col, val))
	cur = conn.cursor()
	return bool(cur.execute(sql).fetchall())

