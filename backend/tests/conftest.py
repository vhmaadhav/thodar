import pytest
from sqlalchemy.orm import sessionmaker

from thodar.db import init_db, make_engine


@pytest.fixture
def session():
    engine = make_engine("sqlite://")
    init_db(engine)
    with sessionmaker(bind=engine, expire_on_commit=False)() as s:
        yield s
