#!/usr/bin/env python3

import psycopg2
import socket
import argparse

class PostgresQuerys():

	def __init__(self, user, db, port):

		self.user = user
		self.db = db
		self.port = port
		self.users = []

		self.hostname = socket.gethostname()

		try:
        	    	self.conn = psycopg2.connect(dbname=db, user=user, port=port)
		except:
			pass


	def application_delay_seconds(self):
        	cur = self.conn.cursor()
	        cur.execute("""SELECT pg_is_in_recovery();""")
        	result = cur.fetchall()
	        if result[0][0] == True:
        	        cur.execute("""select COALESCE(ROUND(EXTRACT(epoch FROM now() - pg_last_xact_replay_timestamp())),0) AS lag_sec;""")
                	rows = cur.fetchall()
	                print ("query_application,type=%s,host=%s,database=%s value=%s" % ("delay_seconds", self.hostname, self.db, rows[0][0]))

	def application_delay_bytes(self):
		cur = self.conn.cursor()
		cur.execute("""SELECT pg_is_in_recovery();""")
		result = cur.fetchall()
		if result[0][0] == True:
			cur.execute("""select pg_wal_lsn_diff(pg_last_wal_receive_lsn(), pg_last_wal_replay_lsn()) as lag_bytes;""")
			rows = cur.fetchall()
			if rows[0][0] == None:
				print ("query_application,type=%s,host=%s,database=%s value=0" % ("delay_bytes", self.hostname, self.db))
			else:
				print ("query_application,type=%s,host=%s,database=%s value=%s" % ("delay_bytes", self.hostname, self.db, rows[0][0]))


	def __del__(self):
		try:
			self.conn.close()
		except:
			pass


if __name__ == "__main__":

	parser = argparse.ArgumentParser()
	parser.add_argument('-u', '--user', help="Username", required=True)
	parser.add_argument('-d', '--db', help="DB", required=True)
	parser.add_argument('-p', '--port', help="PORT", required=True)

	args = parser.parse_args()
	query = PostgresQuerys(args.user, args.db, args.port)


	if hasattr(query, 'conn'):
		query.application_delay_seconds()
		query.application_delay_bytes()

