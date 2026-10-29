

from contextlib import contextmanager

import mysql.connector

import config


class DBError(Exception):


    def __init__(self, message, technical=""):
        super().__init__(message)
        self.message = message
        self.technical = technical  


class DBConnectionError(DBError):
    pass


class DBInUseError(DBError):
    pass


class DBDuplicateError(DBError):
    pass


ERR_ACCESS_DENIED = 1045
ERR_UNKNOWN_DB = 1049
ERR_NO_SUCH_TABLE = 1146       
ERR_DUPLICATE = 1062
ERR_ROW_IS_REFERENCED = 1451   
ERR_NO_REFERENCED_ROW = 1452   
ERR_CANT_CONNECT = (2002, 2003, 2006, 2013)


def _connection_help(detail):

    return (
        "Could not connect to the MySQL database.\n\n"
        "What to try:\n"
        "1. Open the XAMPP Control Panel and click Start next to MySQL.\n"
        "2. Open the .env file in the project folder and check DB_HOST, "
        "DB_PORT, DB_USER, DB_PASSWORD and DB_NAME.\n"
        "3. If the database or tables are missing, create them with:\n"
        "      python setup_db.py\n\n"
        "Technical detail: " + str(detail)
    )


def translate_error(exc):

    if isinstance(exc, DBError):
        return exc

    errno = getattr(exc, "errno", None)
    detail = str(exc)

    if errno == ERR_UNKNOWN_DB:
        return DBConnectionError(
            "The database '%s' does not exist yet.\n\n"
            "Create it by running:\n    python setup_db.py" % config.DB_NAME,
            detail,
        )
    if errno == ERR_NO_SUCH_TABLE:
        return DBConnectionError(
            "The database exists, but its tables are missing.\n\n"
            "Create them by running:\n    python setup_db.py",
            detail,
        )
    if errno == ERR_ACCESS_DENIED:
        return DBConnectionError(
            "MySQL refused the user name or password.\n\n"
            "Check DB_USER and DB_PASSWORD in the .env file. "
            "(XAMPP default: user root, empty password.)\n\n"
            "Technical detail: " + detail,
            detail,
        )
    if errno in ERR_CANT_CONNECT or isinstance(exc, OSError):
        return DBConnectionError(_connection_help(detail), detail)
    if errno == ERR_ROW_IS_REFERENCED:
        return DBInUseError(
            "This item cannot be deleted because other records still use it.\n"
            "Remove or change those records first, then try again.",
            detail,
        )
    if errno == ERR_NO_REFERENCED_ROW:
        return DBError(
            "The linked item no longer exists. Please refresh the list "
            "and choose again.",
            detail,
        )
    if errno == ERR_DUPLICATE:
        return DBDuplicateError(
            "That value already exists. Please use a different one.", detail
        )
    return DBError("A database error happened:\n" + detail, detail)


_connection = None  


def connect(with_database=True):

    options = dict(
        host=config.DB_HOST,
        port=config.DB_PORT,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        charset="utf8mb4",
        autocommit=True,       
        connection_timeout=5,  
    )
    if with_database:
        options["database"] = config.DB_NAME
    try:
        return mysql.connector.connect(**options)
    except (mysql.connector.Error, OSError) as exc:
        raise translate_error(exc) from exc


def get_connection():

    global _connection
    if _connection is not None:
        try:
            if _connection.is_connected():
                return _connection
        except mysql.connector.Error:
            pass
        _connection = None
    _connection = connect(with_database=True)
    return _connection


def close():

    global _connection
    if _connection is not None:
        try:
            _connection.close()
        except mysql.connector.Error:
            pass
        _connection = None


def check_connection():

    get_connection()


def _run(sql, params, fetch, many=False):

    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        if many:
            cursor.executemany(sql, params)
        else:
            cursor.execute(sql, params)
        if fetch:
            return cursor.fetchall()
        return cursor.lastrowid
    except (mysql.connector.Error, OSError) as exc:
        raise translate_error(exc) from exc
    finally:
        cursor.close()


def like_pattern(text):

    escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return "%" + escaped + "%"


def query(sql, params=None):

    return _run(sql, params, fetch=True)


def query_one(sql, params=None):

    rows = _run(sql, params, fetch=True)
    return rows[0] if rows else None


def execute(sql, params=None):

    return _run(sql, params, fetch=False)


def execute_many(sql, rows):

    return _run(sql, rows, fetch=False, many=True)


@contextmanager
def transaction():

    connection = get_connection()
    connection.start_transaction()
    try:
        yield
        connection.commit()
    except Exception:
        try:
            connection.rollback()
        except mysql.connector.Error:
            pass
        raise
