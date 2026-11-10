from pathlib import Path
from ssl import SSLSocket, create_default_context

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.registration.models import IntakeBase


def factory(settings, *, initialise=False):
    url = make_url(settings.registration_database_url.get_secret_value())
    production = settings.registration_environment != "development"
    if url.drivername.startswith("sqlite"):
        if production or not url.database or url.database == ":memory:":
            raise ValueError(
                "SQLite intake is available for explicit local development files only."
            )
        engine = create_engine(url, connect_args={"check_same_thread": False})

        @event.listens_for(engine, "connect")
        def sqlite_setup(connection, _):
            connection.execute("PRAGMA journal_mode=WAL")
    elif url.drivername == "mysql+pymysql" and url.database == "smvs_registration":
        # TLS identity verification is mandatory for the isolated public intake DB.
        ca = url.query.get("ssl_ca")
        if not ca or not Path(ca).is_file():
            raise ValueError("Configure the intake database CA certificate.")
        ctx = create_default_context(cafile=ca)
        engine = create_engine(
            url.difference_update_query(["ssl_ca"]),
            connect_args={"ssl": ctx},
            pool_pre_ping=True,
        )

        @event.listens_for(engine, "connect")
        def require_tls(connection, _):
            if not getattr(connection, "_sock", None) or not isinstance(
                connection._sock, SSLSocket
            ):
                raise ValueError("An encrypted intake database connection is required.")

        with engine.connect() as connection:
            if (
                connection.execute(text("SELECT DATABASE()")).scalar_one()
                != "smvs_registration"
            ):
                raise ValueError("Unexpected intake database.")
    else:
        raise ValueError("The intake requires a separate smvs_registration database.")
    if initialise:
        IntakeBase.metadata.create_all(engine)
    return sessionmaker(engine, expire_on_commit=False)
