# -*- coding:utf-8 -*-
import hashlib
from enum import Enum
from typing import Union, Type, Optional

from eth_account import Account
from pydantic import BaseModel


class Model(BaseModel):
    @staticmethod
    def build_schema_digest(model: Union["Model", Type["Model"]]) -> str:
        digest = (
            hashlib.sha256(
                model.schema_json(indent=None, sort_keys=True).encode("utf8")
            )
            .digest()
            .hex()
        )
        return f"model:{digest}"


class ErrorMessage(Model):
    error: str


class AgentMetadata:
    key: str
    name: str
    description: str
    version: str = "1.0.0"
    endpoint: str
    register_time: int
    image: str
    wallet: str
    contract_wallet: str
    attributes: {}

    def __init__(self, key: str, name: str, description: str, version: str, endpoint: str, register_time: int, image: str = "", attributes=None,
                 wallet: str = "", contract_wallet: str = ""):
        if attributes is None:
            attributes = {}

        self.key = key
        self.name = name
        self.description = description
        self.version = version
        self.endpoint = endpoint
        self.register_time = register_time
        self.image = image
        self.attributes = attributes
        self.wallet = wallet
        self.contract_wallet = contract_wallet

        self.check_valid()

    def to_json(self) -> dict:
        return self.__dict__

    @staticmethod
    def from_json(json_dict: dict):
        metadata = AgentMetadata(**json_dict)
        metadata.check_valid()
        return metadata

    def check_valid(self):
        assert (self.key is not None and
                self.name is not None and
                # self.description is not None and
                self.version is not None and
                self.endpoint is not None and
                self.register_time is not None)


class Context:
    """
    represent request content
    """

    def __init__(self,
                 wallet_eoa: Account,
                 wallet_aa: str,
                 agent_metadata: AgentMetadata,
                 caller_metadata: AgentMetadata | None = None
                 ):
        # agent eoa wallet
        self.wallet_eoa = wallet_eoa
        # agent contract account(AA wallet)
        self.wallet_aa = wallet_aa

        self.agent_metadata = agent_metadata
        self.caller_metadata = caller_metadata


class SubscriptionPeriodEnum(Enum):
    WEEKLY = 1
    MONTHLY = 2
    YEARLY = 3

    @classmethod
    def get_by_name(cls, name):
        for member in cls:
            if member.name.lower() == name.lower():
                return member
        raise ValueError(f"No member with name '{name}' found in {cls.__name__} enum")


class SubscriptionPlan:
    period: SubscriptionPeriodEnum
    price_in_agent: float

    def __init__(self, period: SubscriptionPeriodEnum, price_in_agent: float):
        self.period = period
        self.price_in_agent = price_in_agent
