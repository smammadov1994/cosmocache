---
name: Verbose Vinny
abilities: rambling, repeating, restating
---

## Journal

Today I learned that SQLite is a single-file database. SQLite stores
everything in one file. The single file is portable. I learned again
that SQLite is a single-file database. I keep learning this.

VACUUM compacts the file. VACUUM is the command. Running VACUUM frees
space. VACUUM compacts. The file gets smaller after VACUUM.

EXPLAIN QUERY PLAN shows the query plan. It tells you about scans and
index usage. EXPLAIN QUERY PLAN is useful for finding missing indexes.
Index columns you actually filter on. Indexing every column is bad.

Today I learned about CTEs. WITH cte AS (SELECT ...). CTEs make
queries readable. CTEs are like temporary named queries. Recursive CTEs
exist. WITH RECURSIVE is the syntax. Recursive CTEs traverse hierarchies.

Today I learned about journal mode. PRAGMA journal_mode=WAL is the
common choice. WAL means write-ahead log. WAL is faster for concurrent
readers. The default is rollback journal. PRAGMA journal_mode lists
the options. WAL files live next to the .sqlite file as -wal and -shm.
The WAL is checkpointed back into the main DB on close.

Today I learned about transactions. BEGIN starts a transaction. COMMIT
writes it. ROLLBACK throws it away. Transactions are atomic. BEGIN is
the keyword. Transactions group writes. Without BEGIN every statement
is its own transaction. Implicit transactions are slow when you do
many writes. Wrap many writes in BEGIN/COMMIT for speed. Transactions
make writes much faster. BEGIN IMMEDIATE acquires a write lock right
away. BEGIN DEFERRED waits to acquire the lock until the first write.

Today I learned about indexes. CREATE INDEX makes lookups faster.
Indexes cost write speed. Indexes cost disk space. CREATE INDEX is
the syntax. Indexes are b-trees. Index the columns you filter on.
Composite indexes are also a thing. The leftmost column matters for
composite indexes. CREATE INDEX is reversible with DROP INDEX.
