import sqlite3


class MemoryManager:

    def __init__(self):

        self.db = sqlite3.connect(
            "research.db"
        )

        self.create_tables()

    def create_tables(self):

        cur = self.db.cursor()

        cur.execute("""
        CREATE TABLE IF NOT EXISTS findings(

            id INTEGER PRIMARY KEY,
            hypothesis TEXT,
            result TEXT
        )
        """)

        self.db.commit()

    def store_result(
        self,
        hypothesis,
        result
    ):

        cur = self.db.cursor()

        cur.execute(
            """
            INSERT INTO findings
            (
                hypothesis,
                result
            )
            VALUES (?,?)
            """,
            (
                hypothesis,
                str(result)
            )
        )

        self.db.commit()
