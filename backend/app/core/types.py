"""Column types that match the ER diagram exactly on MySQL.

Each type falls back to a plain type on other databases, so the models can
also be loaded without MySQL (for example to export the OpenAPI file). The
site, the tests and CI always use MySQL.
"""

from sqlalchemy import BigInteger, DateTime, Enum, Integer, LargeBinary, SmallInteger
from sqlalchemy.dialects import mysql

# BIGINT UNSIGNED ids. SQLite needs a plain INTEGER for auto-increment.
ID = BigInteger().with_variant(mysql.BIGINT(unsigned=True), "mysql").with_variant(Integer(), "sqlite")

# DATETIME(3): UTC, millisecond precision, no time zone stored.
TIMESTAMP = DateTime().with_variant(mysql.DATETIME(fsp=3), "mysql")

TINY_UINT = SmallInteger().with_variant(mysql.TINYINT(unsigned=True), "mysql")
SMALL_UINT = SmallInteger().with_variant(mysql.SMALLINT(unsigned=True), "mysql")
UINT = Integer().with_variant(mysql.INTEGER(unsigned=True), "mysql")

# VARBINARY(16): an IPv4 or IPv6 address in packed form.
IP_ADDRESS = LargeBinary(16).with_variant(mysql.VARBINARY(16), "mysql")


def enum(name: str, *values: str) -> Enum:
    """A MySQL ENUM column with these values."""
    return Enum(*values, name=name, native_enum=True, validate_strings=True)
