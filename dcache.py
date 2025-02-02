# -*- coding:utf-8 -*-
import json
import sqlite3
from time import time
from hashlib import sha256
from lzstring import LZString


class Dinky:
    """
    Todo: Add more docstring
        https://sphinxcontrib-napoleon.readthedocs.io/en/latest/example_google.html

    Todo: add a separate timestamp => possible to set max tables and automatic purge oldest
    Todo: add a method to automatically delete expired and/or purge items in set interval
    Todo:   needs method to purge max
    Todo:       clean oldes / clean least accessed?
    Todo:   would need a separate __dinky_settings database

    example:
        Dinky(autoclean=True, cleanexpired=True, interval=5hrs, maxdbrows=100)
            - 0 values disables
        later runs should be...
        Dinky(autoclean=True).read(id) to invoke and check whether to clean or not
        Dinky().read(id) would skip the check
        another run of
        Dinky(autoclean=True, AutoPurgeOld=True interval=5hrs, maxdbrows=100)
        should update settings, but not reset the timer => shorter and it would run earlier


    """

    def __init__(self, dbfile: str = "dinkycache.db"):
        """
        Checks wheter the database exists, creates it if not.
        Checks for, ande delete expired entries

        Args:
            dbfile (str, optional):  The name (and path) of sqlite3 database.
                Defaults to 'dinkycache.db'
        """
        self.lz = LZString()
        self.db = dbfile
        with self._SQLite(self.db) as cur:
            cur.execute(
                f"CREATE TABLE IF NOT EXISTS 'dinkycache' "
                f"('id' text primary key, 'data' text, 'timestamp' int)"
            )

    def read(self, id: str):
        """
        Does a lookup in the database

        Args:
            id (str):  The id to look for in the database

        Returns:
            The value at the corresponding id if it exists and is not expired,
                False otherwise.
        """
        result = False
        hashed = sha256(id.encode("utf-8")).hexdigest()
        with self._SQLite(self.db) as cur:
            dbdata = cur.execute(
                f"SELECT id, data, timestamp FROM dinkycache WHERE id = '{hashed}'"
            ).fetchone()
        if dbdata is not None:
            now = int(time())
            timestamp = int(dbdata["timestamp"])
            if now < timestamp or timestamp == 0:
                result_str = self.lz.decompressFromBase64(dbdata["data"])
                result = json.loads(result_str)
            else:
                self.delete(id)
        return result

    def write(self, id: str, data: str, ttl: int = 172800):  # 48hours ttl
        """
        todo: really decide what to do with default ttl, thinking 0

        Writes a row to the database

        Args:
            id (str):  The id to store the data under
            data (str): The value to store
            ttl (int, optional): Time to live for the data, specified in seconds.
                Set to 0 for permanent storage. Defaults to 48 hours.

        Returns:
            Hash of the stored id, False otherwise.
        """
        result = hashed = sha256(id.encode("utf-8")).hexdigest()
        if ttl:
            timestamp = int(time()) + int(ttl)
        else:
            timestamp = 0
        str_data = json.dumps(data)
        compressed = self.lz.compressToBase64(str_data)
        with self._SQLite(self.db) as cur:
            cached = cur.execute(
                f"SELECT COUNT() FROM dinkycache WHERE id = '{hashed}'"
            ).fetchone()[0]
            if cached > 0:
                cur.execute(
                    f"UPDATE dinkycache "
                    f"SET data = '{compressed}', timestamp = '{timestamp}' "
                    f"WHERE id = '{hashed}'"
                )
            else:
                cur.execute(
                    f"INSERT INTO dinkycache VALUES "
                    f"('{hashed}', '{compressed}', '{timestamp}')"
                )
        return result

    def delete(self, id: str = False, hash: str = False):
        """
        todo: decide wether we want the hash function here
                ! if so, add it to read as well

        Deletes a row in the database, specified by either id or hash

        Args:
            id (str, optional):  The id of the row to delete, defaults to False
            hash (str, optional): The hash of the row to delete, defaults to False

        Returns:
            True

        Raises:
            TypeError: If neither id nor hash is specified
        """
        if id:
            hashed = sha256(id.encode("utf-8")).hexdigest()
        elif hash:
            hashed = hash
        else:
            raise TypeError("delete() missing 1 required argument: 'id' or 'hash'")
        with self._SQLite(self.db) as cur:
            cur.execute(f"DELETE FROM dinkycache WHERE id = '{hashed}'")
        return True

    def _autoclean(self):
        return False

    def clean(self):
        """
        Cleans the database for expired rows

        Returns:
            True
        """
        with self._SQLite(self.db) as cur:
            cur.execute(
                f"DELETE FROM dinkycache "
                f"WHERE timestamp > 0 AND timestamp < {int(time())}"
            )
        return True

    def purge_max(self, maxrows: int):
        return False

    class _SQLite:
        def __init__(self, file):
            self.file = file

        def __enter__(self):
            self.conn = sqlite3.connect(self.file)
            self.conn.row_factory = sqlite3.Row
            return self.conn.cursor()

        def __exit__(self, type, value, traceback):
            self.conn.commit()
            self.conn.close()
