import os
from sqlalchemy import *
import datetime

DB = os.environ.get('API_SQL')
engine = create_engine(DB, echo=False)


class DatabaseHandler():
    def __init__(self):
        DB = os.environ.get('API_SQL')
        engine = create_engine(DB, echo=False)
        self.con = engine.connect()

    def add_tempmute(self, user_id: int, guild_id: int, expiration_date: datetime.datetime):
        query = text("INSERT INTO Tempmute (user_id, guild_id, expiration_date) VALUES (:user_id, :guild_id, :expiration_date);")
        self.con.execute(query, {'user_id' : user_id, 'guild_id' : guild_id, 'expiration_date' : expiration_date})
        self.con.close()

    def active_tempmute_to_revoke(self, guild_id: int) -> dict:
        query = text(f"SELECT * FROM Tempmute WHERE guild_id = :guild_id AND active = 1 AND expiration_date < :expiration_date;")
        cursor = self.con.execute(query, {'guild_id' : guild_id, 'expiration_date' : datetime.datetime.utcnow()})
        result = list(map(dict, cursor.fetchall()))
        self.con.close()
        return result

    def revoke_tempmute(self, tempmute_id: int):
        query = text(f"UPDATE Tempmute SET active = 0 WHERE id = :tempmute_id;")
        self.con.execute(query, {'tempmute_id' : tempmute_id})
        self.con.close()

