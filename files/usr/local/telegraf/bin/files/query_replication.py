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

	def replication_delay_seconds(self):

		cur = self.conn.cursor()
		cur.execute("""SELECT pg_is_in_recovery();""")
		standby = cur.fetchall()
		if standby[0][0] == False:
			cur.execute("""select coalesce(round(extract(epoch from write_lag)), 0) write_lag_sec,
			coalesce(round(extract(epoch from flush_lag)), 0) flush_lag_sec,
			coalesce(round(extract(epoch from replay_lag)), 0) replay_lag_sec
			from pg_stat_replication where application_name = 'standby_hostname';""")
			slot_names = cur.fetchall()
			for slot_name in slot_names:
				cur.execute("""select pg_xlog_location_diff(pg_current_xlog_insert_location(), restart_lsn) AS retained_bytes from pg_replication_slots where slot_name = %s;""", slot_name)
				rows = cur.fetchall()
				if rows:
					print ("query_replication_bytes_delay_logical,host=%s,slot_name=%s,database=%s value=%s" % \
					(self.hostname, slot_name[0], self.db, rows[0][0]))


	def replication_delay_bytes(self):
		cur = self.conn.cursor()
		cur.execute("""SELECT pg_is_in_recovery();""")
		standby = cur.fetchall()
		if standby[0][0] == False:
			cur.execute("""select pg_wal_lsn_diff(pg_current_wal_insert_lsn(), sent_lsn) AS sent_lag_bytes, \
			pg_wal_lsn_diff(pg_current_wal_insert_lsn(), write_lsn) AS write_lag_bytes, \
			pg_wal_lsn_diff(pg_current_wal_insert_lsn(), sent_lsn) AS flush_lag_bytes, \
			pg_wal_lsn_diff(pg_current_wal_insert_lsn(), sent_lsn) AS replay_lag_bytes \
			from pg_stat_replication where application_name = 'standby_hostname';""")
			rows = cur.fetchall()
			if rows:
				print ("query_replication_bytes_delay,host=%s,database=%s value=%s" % (self.hostname, self.db, rows[0][0]))
			else:
				print ("query_replication_bytes_delay,host=%s,database=%s value=0" % (self.hostname, self.db))


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
		query.replication_delay_seconds()
		query.replication_delay_bytes()
