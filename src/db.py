import psycopg
import config

conninfo = f"user={config.DB_USER} password={config.DB_PASS} host={config.DB_HOST} port={config.DB_PORT} dbname={config.DB_NAME}"


def get_conn():
  return psycopg.connect(conninfo=conninfo)
