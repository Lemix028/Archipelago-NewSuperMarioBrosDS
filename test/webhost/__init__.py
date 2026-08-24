import unittest
import typing
from uuid import uuid4

from flask import Flask
from flask.testing import FlaskClient


class TestBase(unittest.TestCase):
    app: typing.ClassVar[Flask]
    client: FlaskClient

    @classmethod
    def setUpClass(cls) -> None:
        from WebHostLib import app as raw_app
        from WebHost import get_app

        raw_app.config["PONY"] = {
            "provider": "sqlite",
            "filename": ":memory:",
            "create_db": True,
        }
        raw_app.config.update({
            "TESTING": True,
            "DEBUG": True,
        })
        try:
            cls.app = get_app()
        except (AssertionError, ValueError) as e:
            message = str(e)
            if (
                "register_blueprint" not in message
                and "already registered for this blueprint" not in message
            ):
                raise
            cls.app = raw_app

    def setUp(self) -> None:
        from WebHostLib.models import db
        from pony.orm import db_session
        with db_session:
            for entity in db.entities.values():
                entity.select().delete(bulk=True)
        self.client = self.app.test_client()
