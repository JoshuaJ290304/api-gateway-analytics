import psycopg2

conn = psycopg2.connect(
    host="localhost",
    database="api_gateway_db",
    user="postgres",
    password="finance123"
)

print("Connected Successfully")

conn.close()