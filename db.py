import os
import psycopg2

def get_db_connection():

    database_url = os.getenv("DATABASE_URL")

    if database_url:
        return psycopg2.connect(database_url)

    return psycopg2.connect(
        host="localhost",
        database="api_gateway_db",
        user="postgres",
        password="finance123"
    )