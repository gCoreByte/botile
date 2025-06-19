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

@dataclass
class Command:
    name: str
    channel_name: str
    keywords: list[str]
    message: str
    id: int | None = None
    dirty: bool = False
    persisted: bool = False

    def __setattr__(self, key, value):
        if getattr(self, key, None) != value:
            if key == "name":
                value = value.lower().strip()
            if key == "channel_name":
                value = value.lower().strip()
            if key == "keywords":
                # Keep as list, normalize individual keywords
                value = [kw.lower().strip() for kw in value]
            if key == "message":
                value = value.strip()
            super().__setattr__(key, value)
            self.dirty = True

    def save(self):
        if not self.persisted:
            Database().create_command(self)
        elif self.dirty:
            Database().update_command(self)
        self.dirty = False

    def delete(self):
        Database().delete_command(self)
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
        cursor.execute("CREATE TABLE IF NOT EXISTS commands (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, channel_name TEXT NOT NULL, keywords TEXT NOT NULL, message TEXT NOT NULL)")

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
    
    def create_command(self, command: Command):
        cursor = self.cursor()
        keywords_str = ", ".join(command.keywords)
        cursor.execute("INSERT INTO commands (name, channel_name, keywords, message) VALUES (?, ?, ?, ?)", (command.name, command.channel_name, keywords_str, command.message))
        last_row_id = cursor.lastrowid
        self.conn.commit()
        command.id = last_row_id
        command.persisted = True
        return command
    
    def delete_command(self, command: Command):
        cursor = self.cursor()
        cursor.execute("DELETE FROM commands WHERE id = ?", (command.id,))
        self.conn.commit()
        return True
    
    def get_command_by_id(self, id: int):
        cursor = self.cursor()
        cursor.execute("SELECT * FROM commands WHERE id = ?", (id,))
        record = cursor.fetchone()
        return Command(id=record["id"], name=record["name"], channel_name=record["channel_name"], keywords=record["keywords"].split(","), message=record["message"], persisted=True) if record else None
    
    def get_all_commands(self):
        cursor = self.cursor()
        cursor.execute("SELECT * FROM commands ORDER BY id DESC")
        records = cursor.fetchall()
        return [Command(id=record["id"], name=record["name"], channel_name=record["channel_name"], keywords=record["keywords"].split(","), message=record["message"], persisted=True) for record in records]
    
    def update_command(self, command: Command):
        cursor = self.cursor()
        keywords_str = ", ".join(command.keywords)
        cursor.execute("UPDATE commands SET name = ?, channel_name = ?, keywords = ?, message = ? WHERE id = ?", (command.name, command.channel_name, keywords_str, command.message, command.id))
        self.conn.commit()
        return command
    
    def get_command_by_channel_name_and_keywords(self, channel_name: str, keywords: list[str]):
        cursor = self.cursor()
        
        # Normalize channel name and keywords
        channel_name = channel_name.lower().strip()
        normalized_keywords = [kw.lower().strip() for kw in keywords]
        keywords_str = ", ".join(normalized_keywords)
        
        cursor.execute("SELECT * FROM commands WHERE channel_name = ? AND keywords = ?", (channel_name, keywords_str))
        record = cursor.fetchone()
        return Command(id=record["id"], name=record["name"], channel_name=record["channel_name"], keywords=record["keywords"].split(","), message=record["message"], persisted=True) if record else None

    def get_command_by_name_and_channel(self, name: str, channel_name: str):
        cursor = self.cursor()
        
        # Normalize name and channel name
        name = name.lower().strip()
        channel_name = channel_name.lower().strip()
        
        cursor.execute("SELECT * FROM commands WHERE name = ? AND channel_name = ?", (name, channel_name))
        record = cursor.fetchone()
        return Command(id=record["id"], name=record["name"], channel_name=record["channel_name"], keywords=record["keywords"].split(","), message=record["message"], persisted=True) if record else None

    def get_commands_by_channel(self, channel_name: str):
        cursor = self.cursor()
        
        # Normalize channel name
        channel_name = channel_name.lower().strip()
        
        cursor.execute("SELECT * FROM commands WHERE channel_name = ? ORDER BY name", (channel_name,))
        records = cursor.fetchall()
        return [Command(id=record["id"], name=record["name"], channel_name=record["channel_name"], keywords=record["keywords"].split(","), message=record["message"], persisted=True) for record in records]

    def find_command_with_most_matching_keywords(self, channel_name: str, search_keywords: list[str]):
        """
        Find the command that has the most matching keywords (case-insensitive).
        Returns the command with the highest number of matching keywords, or None if no matches.
        """
        cursor = self.cursor()
        
        # Get all commands for the channel
        cursor.execute("SELECT * FROM commands WHERE channel_name = ?", (channel_name.lower().strip(),))
        records = cursor.fetchall()
        
        if not records:
            return None
        
        best_match = None
        best_match_count = 0
        
        # Normalize search keywords to lowercase
        search_keywords_lower = [kw.lower().strip() for kw in search_keywords]
        
        for record in records:
            # Get stored keywords and normalize them
            stored_keywords = [kw.strip() for kw in record["keywords"].split(",")]
            stored_keywords_lower = [kw.lower() for kw in stored_keywords]
            
            # Count matching keywords
            match_count = 0
            for search_kw in search_keywords_lower:
                if search_kw in stored_keywords_lower:
                    match_count += 1
            
            # Update best match if this command has more matches
            if match_count > best_match_count:
                best_match_count = match_count
                best_match = Command(
                    id=record["id"], 
                    name=record["name"], 
                    channel_name=record["channel_name"], 
                    keywords=stored_keywords, 
                    message=record["message"], 
                    persisted=True
                )
        
        # Only return a match if at least one keyword matched
        return best_match if best_match_count > 0 else None

