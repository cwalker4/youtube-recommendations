import os
import fnmatch

import sqlite3
from sqlite3 import Error


def credentials():
	"""
	Set up credentials folder and empty api key text file
	"""
	if not os.path.exists('credentials'):
		os.mkdir('credentials')
	open('credentials/api_key.txt', 'w').close()


def execute_sql_script(cur, path):
	"""
	Executes the script at path. Handles multiple commands per file.

	"""
	f = open(path, 'r')
	all_cmds = f.read()
	f.close()

	all_cmds = all_cmds.split(';')
	for sql in all_cmds:
		cur.execute(sql)


def database():
	"""
	set up the data directory

	"""
	if not os.path.exists('data'):
		os.mkdir('data')
	try:
		con = sqlite3.connect('data/crawl.sqlite')
	except Error as e:
		print(e)
	else:
		cur = con.cursor()
		for file in os.listdir('scripts/data_preparation'):
			if fnmatch.fnmatch(file, '*.sql'):
				path = os.path.join('scripts/data_preparation', file)
				execute_sql_script(cur, path)
	finally:
		con.commit()
		con.close()


if __name__ == "__main__":
	database()
	credentials()
	print("Done.\n")
	print("Copy your YouTube API key into `credentials/api_key.txt`")

