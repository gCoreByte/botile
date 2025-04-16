import sqlite3
from dataclasses import dataclass


@dataclass
class Account:
    name: str
    tag: str
    puuid: str | None = None
    id: int | None = None
    dirty: bool = False
    persisted: bool = False

    def full_name(self):
        return f"{self.name}#{self.tag}"

    def __setattr__(self, key, value):
        if getattr(self, key, None) != value:
            if key == "name" or key == "tag":
                # Normalize name and tag
                value = value.lower().strip()
            super().__setattr__(key, value)
            self.dirty = True

    def save(self):
        if not self.persisted:
            Database().create_account(self)
        elif self.dirty:
            Database().update_account(self)
        self.dirty = False


    def delete(self):
        Database().delete_account(self)
        self.persisted = False
        self.id = None


class Database:
    def __init__(self):
        self.conn = sqlite3.connect("database.db")
        self.conn.row_factory = sqlite3.Row

    def cursor(self):
        return self.conn.cursor()

    def create_tables(self):
        cursor = self.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS accounts (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, tag TEXT NOT NULL, puuid TEXT)")

    def create_account(self, account: Account):
        cursor = self.cursor()
        cursor.execute("INSERT INTO accounts (name, tag, puuid) VALUES (?, ?, ?)", (account.name, account.tag, account.puuid))
        last_row_id = cursor.lastrowid
        self.conn.commit()
        account.id = last_row_id
        account.persisted = True
        return account

    def delete_account(self, account: Account):
        cursor = self.cursor()
        cursor.execute("DELETE FROM accounts WHERE id = ?", (account.id,))
        self.conn.commit()
        return True

    def get_account_by_id(self, id: int):
        cursor = self.cursor()
        cursor.execute("SELECT * FROM accounts WHERE id = ?", (id,))
        record = cursor.fetchone()
        return Account(id=record["id"], name=record["name"], tag=record["tag"], puuid=record["puuid"], persisted=True) if record else None

    def get_account_by_name_and_tag(self, name: str, tag: str):
        # Normalize
        name = name.lower().strip()
        tag = tag.lower().strip()
        cursor = self.cursor()
        cursor.execute("SELECT * FROM accounts WHERE name = ? AND tag = ?", (name, tag))
        record = cursor.fetchone()
        return Account(id=record["id"], name=record["name"], tag=record["tag"], puuid=record["puuid"], persisted=True) if record else None

    def get_all_accounts(self):
        cursor = self.cursor()
        cursor.execute("SELECT * FROM accounts ORDER BY id DESC")
        records = cursor.fetchall()
        return [Account(id=record["id"], name=record["name"], tag=record["tag"], puuid=record["puuid"], persisted=True) for record in records]

    def update_account(self, account: Account):
        cursor = self.cursor()
        cursor.execute("UPDATE accounts SET puuid = ?, name = ? WHERE id = ?", (account.puuid, account.name, account.id))
        self.conn.commit()
        return account
    

