#!/usr/bin/env python3

import os
import sys
import socket
import psycopg2
import argparse
import re

class PostgresMetrics():
    
	def __init__(self, user, db, port):
        
		self.user = user
		self.db = db
		self.port = port
		self.users = []
		self.hostname=socket.gethostname()		

		try:
			self.conn = psycopg2.connect(dbname=db, user=user, port=port)
		except:
			pass

	# Number of connections per user
	def connection_per_user(self):
	
		cur = self.conn.cursor()		
		cur.execute("""SELECT usename,count(*) FROM pg_stat_activity WHERE pid != pg_backend_pid() GROUP BY usename ORDER BY 1""")
		rows = cur.fetchall()
		for username,count in rows:
			self.users.insert(len(self.users),username)
			print("connection_per_user,host=%s,database=%s,username=%s value=%s" % (self.hostname, self.db, username, count))

	# Transaction logs, Log Segments
	def wals(self):

		cur = self.conn.cursor()
		cur.execute("""SELECT count(*) AS segments FROM pg_ls_dir('pg_wal') t(fn) WHERE fn ~ '^[0-9A-Z]{24}';""")
		rows = cur.fetchall()
		print ("wals,host=%s,database=%s segments=%s" % (self.hostname, self.db, rows[0][0]))	
	
	# Number of active autovacuum workers
	def autovacuum(self):
		
		cur = self.conn.cursor()
		cur.execute("""SELECT 'active', count(*) FROM pg_stat_activity WHERE query LIKE 'autovacuum: %'""")
		rows = cur.fetchall()
		for state,count in rows:
			print ("autovacuum,host=%s,database=%s value=%s" % (self.hostname, self.db, count))


	# Number of connections per databse
	def connection_per_database(self):

		cur = self.conn.cursor()
		cur.execute("""SELECT pg_database.datname,COALESCE(count,0) AS count FROM pg_database LEFT JOIN (SELECT datname,count(*) FROM \
		pg_stat_activity WHERE pid != pg_backend_pid() GROUP BY datname) AS tmp ON pg_database.datname=tmp.datname WHERE datallowconn \
		ORDER BY 1""")
		rows = cur.fetchall()
		for database,count in rows:
                        print ("connection_per_database,host=%s,database=%s value=%s" % (self.hostname, database, count))

	# Number of checkpoints per minute
	def checkpoints(self):
		
		cur = self.conn.cursor()
		cur.execute("""SELECT checkpoints_timed,checkpoints_req FROM pg_stat_bgwriter""")
		rows = cur.fetchall()
		for timed,requested in rows:
			print ("checkpoints,host=%s,database=%s timed=%s,requested=%s" % (self.hostname, self.db, timed, requested))
	
	# Buffers cache activity, Buffer per second
	# Returns Buffer Read per second, Buffer Hit per second
	# Graph Type = Derive
	def cache(self):
		cur = self.conn.cursor()
		cur.execute("""SELECT sum(blks_read) AS blks_read,sum(blks_hit) AS blks_hit FROM pg_stat_database""")
		rows = cur.fetchall()
		for read,hit in rows:
			print ("cache,host=%s,database=%s blks_read=%s,blks_hits=%s" % (self.hostname, self.db, read, hit))
			
	# Size of Database
 	# Returns the database name and the database size
	# Graph Type = Area	
	def size(self):
		cur = self.conn.cursor()
		cur.execute("""SELECT datname,pg_database_size(oid) FROM pg_database WHERE datname=%s ORDER BY 1""", (self.db, ))
		rows = cur.fetchall()
		for datname,size in rows:
			print ("database_size,host=%s,port=%s,database=%s size=%s" % (self.hostname, self.port, datname, size))

	# Bgwriter buffer statistics
	# Return (Buffers per second):
	# 	Buffers Checkpoint: Buffers written when performing a checkpoint
	# 	Buffers Clean: Buffers cleaned by background bgwriter run
	#	Buffers Backend: Buffers written by backends and not the bgwriter
	# 	Buffers Alloc: Buffers allocated globally
	# Graph Type = Derive
	def bgwriter(self):
		cur = self.conn.cursor()
		cur.execute("""SELECT buffers_checkpoint,buffers_clean,buffers_backend,buffers_alloc FROM pg_stat_bgwriter""")
		rows = cur.fetchall()
		for buffers_checkpoint,buffers_clean,buffers_backend,buffers_alloc in rows:
			print ("bgwriter,host=%s,database=%s buffers_checkpoint=%s,buffers_clean=%s,buffers_backend=%s,buffers_alloc=%s" % \
			(self.hostname, self.db, buffers_checkpoint, buffers_clean, buffers_backend, buffers_alloc))

	# PostgreSQL locks
	# Return (Locks)
	#	accessshareloc: Used by read only queries
	#	rowsharelock: Used by SELECT FOR SHARE and SELECT FOR UPDATE queries
	#	rowexclusivelock: Used by UPDATE, DELETE and INSERT queries
	#	shareupdateexclusivelock: Used by VACUUM, ANALYZE and CREATE INDEX CONCURRENTLY queries
	#	sharelock: Used by CREATE INDEX queries
	#	sharerowexclusivelock: Only issued explicitly from applications
	#	exclusivelock: Infrequently issued on system tables, or by applications
	#	accessexclusivelock: Used by ALTER TABLE, DROP TABLE, TRUNCATE, REINDEX, CLUSTER and VACUUM FULL queries
	# Graph Type = Area
	def locks(self):
		cur = self.conn.cursor()
		cur.execute("""SELECT tmp.mode,COALESCE(count,0) FROM (VALUES ('accesssharelock'),('rowsharelock'),('rowexclusivelock'),\
		('shareupdateexclusivelock'),('sharelock'),('sharerowexclusivelock'),('exclusivelock'),('accessexclusivelock')) AS tmp(mode) \
         	LEFT JOIN (SELECT lower(mode) AS mode,count(*) AS count FROM pg_locks WHERE database IS NOT NULL AND database=(SELECT oid FROM  
		pg_database WHERE datname=%s)GROUP BY lower(mode)) AS tmp2 ON tmp.mode=tmp2.mode ORDER BY 1""", (self.db, ))
		rows = cur.fetchall()
		for lockname,value in rows:
			print ("locks,host=%s,database=%s,lockname=%s value=%s" % (self.hostname, self.db, lockname, value))
		

	# Scan types
	# Resturn, Scans per second
	# Graph Type = Derive
	def scans(self):
		cur = self.conn.cursor()
		cur.execute("""SELECT COALESCE(sum(seq_scan),0) AS sequential, COALESCE(sum(idx_scan),0) AS index FROM pg_stat_user_tables""")
		rows = cur.fetchall()
		for sequential,index in rows:
			print ("scans,host=%s,database=%s sequential=%s,index=%s" % (self.hostname, self.db, sequential, index))

	
	# Most long-running queries and transactions
	# Return Age in seconds
	#	Oldest Transactions 
	#	Oldest Queries
	# Graph Type = Gauge
	def query_length(self):
		cur = self.conn.cursor()
		cur.execute("""SELECT 'query',COALESCE(max(extract(epoch FROM CURRENT_TIMESTAMP-query_start)),0) FROM pg_stat_activity WHERE state \
		<> 'idle' AND query NOT LIKE 'autovacuum%%' AND datname=%s UNION ALL SELECT \
		'transaction',COALESCE(max(extract(epoch FROM CURRENT_TIMESTAMP-xact_start)),0) FROM pg_stat_activity WHERE 1=1 AND query NOT LIKE \
		'autovacuum%%' AND datname=%s """ , (self.db, self.db, ))
		rows = cur.fetchall()
		for name,value in rows:
			print ("query_length,host=%s,database=%s,type=%s value=%s" % (self.hostname, self.db, name, value))

	# Size of database in detail
	# Return Size
	# Graph Type = Gauge
	def size_database_detail(self):
		cur = self.conn.cursor()
		cur.execute("""SELECT CASE WHEN relkind = 'r' OR relkind = 't' THEN 'db_detail_data' WHEN relkind = 'i' THEN 'db_detail_index' WHEN relkind 		    = 'v' THEN 'db_detail_view' WHEN relkind = 'S' THEN 'db_detail_sequence' ELSE 'db_detail_other' END AS state,SUM(relpages::bigint * 8 * 1024		) AS size FROM pg_class pg, pg_namespace pgn WHERE pg.relnamespace = pgn.oid AND pgn.nspname NOT IN ('information_schema', 'pg_catalog') 
		GROUP BY state""")
		rows = cur.fetchall()
		for detail,size in rows:
			print ("database_size_detail,hostname=%s,database=%s,detail=%s size=%s" % (self.hostname, self.db, detail, size))
	

	# Tablespace Size
	# Return Size of Tablespaces
	# Graph Type = Gauge
	def tablespace_size(self):
		cur = self.conn.cursor()
		cur.execute("""SELECT spcname, pg_tablespace_size(oid) FROM pg_tablespace ORDER BY 1""")
		rows = cur.fetchall()
		for tablespace,size in rows:
                        print ("tablespace_size,hostname=%s,database=%s,tablespace=%s size=%s" % (self.hostname, self.db, tablespace, size))
	

	# Tuples access
	# Return Tuples access per second
	# Graph Type = DERIVE
	def tuples(self):
		cur = self.conn.cursor()
		cur.execute("SELECT COALESCE(sum(seq_tup_read),0) AS seqread, COALESCE(sum(idx_tup_fetch),0) AS idxfetch, COALESCE(sum(n_tup_ins),0) \
		AS inserted, COALESCE(sum(n_tup_upd),0) AS updated, COALESCE(sum(n_tup_del),0) AS deleted, COALESCE(sum(n_tup_hot_upd),0) AS hotupdated \
		FROM pg_stat_user_tables")
		rows = cur.fetchall()
		print ("tuples,host=%s,database=%s seqread=%s" % (self.hostname, self.db, rows[0][0]))
		print ("tuples,host=%s,database=%s idxfetch=%s" % (self.hostname, self.db, rows[0][1]))
		print ("tuples,host=%s,database=%s inserted=%s" % (self.hostname, self.db, rows[0][2]))
		print ("tuples,host=%s,database=%s updated=%s" % (self.hostname, self.db, rows[0][3]))
		print ("tuples,host=%s,database=%s deleted=%s" % (self.hostname, self.db, rows[0][4]))
		print ("tuples,host=%s,database=%s hostupdated=%s" % (self.hostname, self.db, rows[0][5]))
		

	# Ratio dead/live tuples of a database
	# Return Live Tup and Dead Tup
	# Graph Type = Gauge
	def tuplesratio(self):
		cur = self.conn.cursor()
		cur.execute("""select sum(n_live_tup) as livetup, sum(n_dead_tup) as deadtup from pg_stat_user_tables""")
		rows = cur.fetchall()
		for livetup,deadtup in rows:
			if not livetup:
				livetup = 0
			if not deadtup:
				deadtup = 0
			print ("tuplesratio,host=%s,database=%s livetup=%s,deadtup=%s" % (self.hostname, self.db, livetup, deadtup))

	# Number of transactions per second
	# Return Transations per second 
	#	Commit = Number of commits per second
	#	Rollback = Number of rollbacks per second
	# Graph Type = Derive
	def transactions(self):
		cur = self.conn.cursor()
		cur.execute("""SELECT 'commit',sum(pg_stat_get_db_xact_commit(oid)) FROM pg_database WHERE datname=%s UNION ALL \
		SELECT 'rollback',sum(pg_stat_get_db_xact_rollback(oid)) FROM pg_database WHERE datname=%s""", (self.db, self.db, ))
		rows = cur.fetchall()
		for transaction,value in rows:
			print ("transactions,host=%s,database=%s,type=%s value=%s" % (self.hostname, self.db, transaction,value))


	# Return the number of connection types for the database
	def connection_db(self):
		cur = self.conn.cursor()
		cur.execute("""SELECT tmp.mstate AS state,COALESCE(count,0) FROM (VALUES ('active'),('waiting'),('idle'),('idletransaction'),('unknown')) \
		AS tmp(mstate) LEFT JOIN (SELECT CASE WHEN wait_event_type IS NOT NULL THEN 'waiting' WHEN state='idle' THEN 'idle' WHEN state LIKE \
                'idle in transaction%%' THEN 'idletransaction' WHEN state='disabled' THEN 'unknown' WHEN query='<insufficient privilege>' THEN 'unknown' \
		ELSE 'active' END AS mstate,count(*) AS count FROM pg_stat_activity WHERE pid != pg_backend_pid() AND datname=%s GROUP BY CASE WHEN \
		wait_event_type IS NOT NULL THEN 'waiting' WHEN state='idle' THEN 'idle' WHEN state LIKE 'idle in transaction%%' THEN 'idletransaction' \
		WHEN state='disabled' THEN 'unknown' WHEN query='<insufficient privilege>' THEN 'unknown' ELSE 'active' END) AS tmp2 ON \
		tmp.mstate=tmp2.mstate ORDER BY 1""", (self.db, ))
		rows = cur.fetchall()
		for type_conn,value in rows:
			print ("connection_db,host=%s,database=%s,type=%s value=%s" % (self.hostname, self.db, type_conn, value))
	
	# Return the count of different states for a given user
	def user_stats(self):
		cur = self.conn.cursor()
		for userdb in self.users:
			cur.execute("""SELECT tmp.mstate AS state,COALESCE(count,0) FROM 
			(VALUES ('active'),('waiting'),('idle'),('idletransaction'),('unknown')) AS tmp(mstate) LEFT JOIN (SELECT CASE WHEN wait_event_type \
			IS NOT NULL THEN 'waiting' WHEN state='idle' THEN 'idle' WHEN state LIKE 'idle in transaction%%' THEN 'idletransaction' \
			WHEN state='disabled' THEN 'unknown' WHEN query='<insufficient privilege>' THEN 'unknown' ELSE 'active' END AS mstate,count(*) \
			AS count FROM pg_stat_activity WHERE pid != pg_backend_pid()  AND usename=%s GROUP BY CASE WHEN wait_event_type IS NOT NULL THEN \
			'waiting' WHEN state='idle' THEN 'idle' WHEN state LIKE 'idle in transaction%%' THEN 'idletransaction' WHEN state='disabled' THEN \
			'unknown' WHEN query='<insufficient privilege>' THEN 'unknown' ELSE 'active' END) AS tmp2 ON tmp.mstate=tmp2.mstate ORDER BY 1;""", \
			(userdb, ))		    
			rows = cur.fetchall()
			for state,value in rows:
				print ("user_state,host=%s,database=%s,user=%s,state=%s value=%s" % (self.hostname, self.db, userdb, state, value))

	def schema_size(self):
		cur = self.conn.cursor()
		cur.execute("""select n.nspname as schema, sum (case when ((pg_table_size(c.oid)::bigint)/1048506) >= 1 then \
		((pg_table_size(c.oid)::bigint)/1048506) else round(((pg_table_size(c.oid)::numeric)/1048506), 2) end) size_mb from pg_class c left \
		join pg_namespace n on n.oid = c.relnamespace group by n.nspname;""")
		rows = cur.fetchall()
		for schema,size in rows:
			print("schema_size,host=%s,database=%s,schema=%s value=%s" % (self.hostname, self.db, schema, size))

	def connection_per_client(self):
		cur = self.conn.cursor()
		cur.execute("""SELECT CASE WHEN length(client_hostname)>0 THEN client_hostname ELSE textin(inet_out(client_addr)) END AS client, \
		count(*) FROM pg_stat_activity p GROUP BY client;""")
		rows = cur.fetchall()
		for client,number in rows:
			print("connection_per_client,host=%s,database=%s,client=%s value=%s" % (self.hostname, self.db, client, number))

	def __del__(self):
		try:
			self.conn.close()
		except:
			pass

if __name__ == "__main__":
	parser = argparse.ArgumentParser()
	parser.add_argument('-u', '--user', help="Username", required=True)
	parser.add_argument('-d', '--db', help="DB", required=True)
	parser.add_argument('-p', '--port', help="Port", required=True)

	args = parser.parse_args()
	stats = PostgresMetrics(args.user, args.db, args.port)

	if hasattr(stats, 'conn'):
		stats.connection_per_user()
		stats.wals()
		stats.autovacuum()
		stats.connection_per_database()
		stats.checkpoints()
		stats.cache()
		stats.size()
		stats.bgwriter()
		stats.locks()
		stats.scans()
		stats.query_length()
		stats.size_database_detail()
		stats.tablespace_size()
		stats.tuples()
		stats.tuplesratio()
		stats.transactions()
		stats.connection_db()
		stats.user_stats()
		stats.schema_size()
		stats.connection_per_client()
