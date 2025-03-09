import os
from sqlalchemy import *
from datetime import datetime, timezone
import pytz

class DatabaseHandler():
    def __init__(self):
        DB = os.environ.get('API_SQL')
        self.engine = create_engine(DB, echo=False)

    def add_tempmute(self,
                     user_id: int,
                     guild_id: int,
                     expiration_date: datetime):
        con = self.engine.connect()
        query = text(
            "INSERT INTO Tempmute (user_id, guild_id, expiration_date) VALUES (:user_id, :guild_id, :expiration_date);")
        con.execute(query, {
                    'user_id': user_id, 'guild_id': guild_id, 'expiration_date': expiration_date})
        con.close()

    def active_tempmute_to_revoke(self, guild_id: int) -> dict:
        con = self.engine.connect()
        query = text(
            f"SELECT * FROM Tempmute WHERE guild_id = :guild_id AND active = true AND expiration_date < :expiration_date;")
        cursor = con.execute(
            query, {'guild_id': guild_id, 'expiration_date': datetime.now(pytz.timezone('Europe/Paris'))})
        result = list(map(dict, cursor.fetchall()))
        con.close()
        return result

    def revoke_tempmute(self, tempmute_id: int):
        con = self.engine.connect()
        query = text(
            f"UPDATE Tempmute SET active = false WHERE id = :tempmute_id;")
        con.execute(query, {'tempmute_id': tempmute_id})
        con.close()
