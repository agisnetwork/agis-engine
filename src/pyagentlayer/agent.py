# -*- coding:utf-8 -*-
import functools
import hashlib
import json
import logging
import math
import os
import sys
import threading
import types
import uuid
from datetime import datetime
from typing import Type, Optional, Union, Set, List
from urllib.parse import urlparse

import flask
from eth_account import Account
from eth_account.messages import encode_defunct
from flask import Flask, request as flask_request
from flask import Response as FlaskResponse
from web3 import Web3

from .agent_executor import new_smart_wallet_factory, \
    new_smart_wallet, new_agent_token_contract, new_subscription_contract, SmartWallet, Subscription, AgentToken
from .agent_link import AgentLink
from .agent_logger import monitor_new_onchain_log, OnChainLog, record_log, record_log_sync
from .models import AgentMetadata, SubscriptionPlan, SubscriptionPeriodEnum
from .models import Context
from .models import ErrorMessage, Model
from .registry_client import OnChainAgentRegistryClient
from .utils.exceptions import AuthorizationException


class LAgent:
    agent_id: Optional[int]

    # agent related wallet info
    wallet: Account | None
    wallet_address: str
    aa_wallet_address: str
    aa_wallet_contract: SmartWallet

    # component for on-chain operation
    w3: Web3
    agent_token: AgentToken
    agent_client: OnChainAgentRegistryClient
    agent_link: AgentLink
    subscription: Subscription

    # agent subscription plan list
    subscription_plan: list[SubscriptionPlan] | None

    # signature for agent call
    message_hash: str | None
    signature: str | None

    # agent metadata
    metadata: AgentMetadata

    # agent registered message router
    message_route: dict
    # agent icon image
    image: str | None

    _api_list: dict | None

    def __init__(self, name: str, private_key: str = None, message_hash: str = None, signature: str = None,
                 http_endpoint: str = None, agent_id: int | None = None, description: str | None = None, version: str = "1.0.0",
                 image: str | None = None, payable: bool = False, subscription_plan: List[SubscriptionPlan] | None = None):
        try:
            self.agent_id = int(agent_id)
        except:
            self.agent_id = None

        # prepare executors
        if private_key:
            self._init_with_private_key(private_key=private_key)
        else:
            if not message_hash or not signature:
                raise ValueError("message_hash and signature must be provided when initializing without private key.")
            self._init_with_signature(message_hash=message_hash, signature=signature)

        self.subscription_plan = subscription_plan
        if payable and not self.subscription_plan:
            raise ValueError("subscription_plan must be provide when payable is true")

        self.task_id = None

        self.metadata = AgentMetadata(key=str(uuid.uuid4()), name=name, description=description, version=version,
                                      endpoint=http_endpoint, register_time=int(datetime.now().timestamp()))
        self.message_hash = message_hash
        self.signature = signature
        self.message_route = {}
        self.image = image
        self._api_list = None

    def _init_with_private_key(self, private_key: str):
        #  convert private key to wallet
        self.wallet: Account = Web3().eth.account.from_key(private_key)
        self.wallet_address = self.wallet.address
        self.agent_token = new_agent_token_contract(account=self.wallet)
        self.w3 = self.agent_token.w3
        self.agent_client = OnChainAgentRegistryClient(wallet=self.wallet)
        self.agent_link = AgentLink(self.agent_client)

    def _init_with_signature(self, message_hash: str, signature: str):
        recovered_address = Web3().eth.account._recover_hash(message_hash=message_hash, signature=signature)
        self.wallet = None
        self.wallet_address = recovered_address
        self.agent_token = new_agent_token_contract(account_address=self.wallet_address)
        self.w3 = self.agent_token.w3
        self.agent_client = OnChainAgentRegistryClient(wallet_address=self.wallet_address)
        self.agent_link = AgentLink(self.agent_client)

    # check aa_wallet and subscription info before initialize/register/subscribe/wrap_agent
    def _check_aa_wallet_and_subscription(self):
        # init aa wallet
        logging.info("checking smart wallet...")
        aa_wallet_factory = new_smart_wallet_factory(account=self.wallet, account_address=self.wallet_address)
        self.aa_wallet_address = aa_wallet_factory.create_wallet()
        self.aa_wallet_contract = new_smart_wallet(account=self.wallet, eoa_account_address=self.wallet_address, smart_wallet_address=self.aa_wallet_address)

        # set subscription plan
        self.subscription = new_subscription_contract(account=self.wallet, account_address=self.wallet_address)
        if self.subscription_plan:
            logging.info("checking subscription plan...")
            self.subscription.update_subscription_plan(self.aa_wallet_address, self.subscription_plan)

    def initialize(self):
        self._check_aa_wallet_and_subscription()
        if self.agent_id is None:
            logging.error(f"agent_id should be set before initialize, you may want to register with subcommand `register`")
            sys.exit(1)
        # check owner of agent id
        if not self.agent_client.is_owner(self.agent_id):
            raise ValueError(f"owner of agent_id {self.agent_id} mismatch with account {self.wallet.address}")

        self.metadata = self.agent_client.get_agent_meta(self.agent_id)
        logging.info(f"init agent success.\n\n" + self.info())

    def register(self):
        self._check_aa_wallet_and_subscription()
        assert self.metadata.endpoint is not None
        self.metadata.register_time = int(datetime.now().timestamp())
        self.metadata.wallet = self.wallet.address
        self.metadata.contract_wallet = self.aa_wallet_address
        # upload agent icon to ipfs
        if self.image:
            if os.path.exists(self.image) or urlparse(self.image).scheme in ['http', 'https']:
                image_cid = self.agent_client.ipfs_client.upload_file(self.image)
                self.metadata.image = image_cid
            else:
                logging.warning(f"image file not found at {self.image}, skip uploading to ipfs")

        self.agent_id = self.agent_client.register(self.metadata)
        logging.info(f"register agent success.\n\n{self.info()}")
        return self.agent_id

    def subscribe(self, target_agent_id, period: SubscriptionPeriodEnum, auto_renewal=False):
        self._check_aa_wallet_and_subscription()
        target_agent_meta = self.agent_client.get_agent_meta(target_agent_id)

        # checking subscription plan
        weekly_price, monthly_price, yearly_price = self.subscription.get_subscription_plan(target_agent_meta.contract_wallet)
        if weekly_price == 0 and monthly_price == 0 and yearly_price == 0:
            logging.info(f"agent {target_agent_id} is free, no need to subscribe.")
            return

        if self.subscription.is_subscribed(self.aa_wallet_address, target_agent_meta.contract_wallet):
            logging.info("you already subscribed this agent")
            return

        # get provide plans by target agent
        provide_plans = []
        if weekly_price != 0:
            provide_plans.append(SubscriptionPeriodEnum.WEEKLY.name)
        if monthly_price != 0:
            provide_plans.append(SubscriptionPeriodEnum.MONTHLY.name)
        if yearly_price != 0:
            provide_plans.append(SubscriptionPeriodEnum.YEARLY.name)
        if period.name not in provide_plans:
            logging.info(f"agent {target_agent_id} only support plans {' / '.join(provide_plans)}")
            return

        # get charging amount by subscribe plan
        charging_amount = 0
        if period == SubscriptionPeriodEnum.WEEKLY:
            charging_amount = weekly_price
        elif period == SubscriptionPeriodEnum.MONTHLY:
            charging_amount = monthly_price
        elif period == SubscriptionPeriodEnum.YEARLY:
            charging_amount = yearly_price
        logging.info(f"you are subscribing to agent {target_agent_id} for {period.name} plan, "
                     f"{round(charging_amount / math.pow(10, 18), 4)} AgentToken will be deducted from your account({self.aa_wallet_address}), "
                     f"please make sure you have enough wagent in your account.")

        agent_balance = self.agent_token.balance_of(self.aa_wallet_address)
        if agent_balance < charging_amount:
            logging.warning(f"Your account has {round(agent_balance / math.pow(10, 18), 4)} Agent, which is insufficient to cover this subscription.")
            return

        self.aa_wallet_contract.subscribe(target_agent_meta.contract_wallet, period=period, auto_renewal=auto_renewal)
        if not self.subscription.is_subscribed(self.aa_wallet_address, target_agent_meta.contract_wallet):
            raise ValueError(f"subscribe to agent {target_agent_id} failed.")
        logging.info("subscribe success")

    def _register_message(self, key, func, parameters, response):
        self.message_route[key] = {
            "method": func,
            "parameter": parameters,
            "response": response
        }

    def on_message(self, name: str = None, request_type: Type[Model] = None, response_type: Optional[Union[Type[Model], Set[Type[Model]], Type[FlaskResponse]]] = None):

        def decorator(func):
            _name = func.__name__ if name is None else name
            self._register_message(_name, func, request_type, response_type)

            @functools.wraps(func)
            def handler(*args, **kwargs):
                return func(*args, **kwargs)

            return handler

        return decorator

    def send(self, agent_id, method, parameters, sync=True):
        if not self.message_hash or not self.signature:
            if not self.wallet:
                raise ValueError("message hash and signature are required when not provide private key.")
            message = "sign in agentlayer for agent call"
            signed_message = self.wallet.sign_message(encode_defunct(text=message))
            self.message_hash = signed_message.messageHash.hex()
            self.signature = signed_message.signature.hex()

        logging.debug(f"call agent {agent_id}: {method} {parameters}")
        return self.agent_link.call(agent_id, self.task_id, method, parameters, self.metadata, message_hash=self.message_hash, signature=self.signature, sync=sync)

    def _authorized(self, caller_metadata: AgentMetadata | None, caller_message_hash: str = None, caller_signature: str = None) -> bool:
        if not self.subscription_plan:
            return True

        if caller_metadata:
            if not caller_message_hash or not caller_signature:
                logging.warning("client message hash and signature are required when call_metadata is not Noe")
                return False

            if (self.subscription.is_subscribed(caller_metadata.contract_wallet, self.aa_wallet_address) or
                    self.subscription.is_subscribed(caller_metadata.wallet, self.aa_wallet_address)):
                return self.aa_wallet_contract.is_valid_signature(caller_metadata.wallet, message=caller_message_hash, signature=caller_signature)

        return False

    def call_function(self, func, parameter: Model,
                      caller_metadata: AgentMetadata | None = None,
                      caller_message_hash: str = None,
                      caller_signature: str = None,
                      parent_task_id=None, log_onchain=True, with_log_queue=False) -> (bool, int, str):
        if not self._authorized(caller_metadata, caller_message_hash, caller_signature):
            raise AuthorizationException("current agent is payable,you have to subscribe before calling it")

        self.task_id = str(uuid.uuid4())
        ctx = Context(
            wallet_eoa=self.wallet,
            wallet_aa=self.aa_wallet_address,
            agent_metadata=self.metadata,
            caller_metadata=caller_metadata
        )

        start_time = datetime.now()

        res = func(ctx, parameter)

        if log_onchain:
            # record executor log
            time_takes = int((datetime.now().timestamp() - start_time.timestamp()) * 1000)
            logging.info(f"process request <{func.__name__}> from agent {f'{caller_metadata.name}({caller_metadata.key})' if caller_metadata else 'unknown'}, time taken: {time_takes} ms")
            _log = OnChainLog(agent_id=self.agent_id, task_id=self.task_id, parent_task_id=parent_task_id, operation=func.__name__, time_takes=time_takes)
            if with_log_queue:
                record_log(_log)
            else:
                try:
                    record_log_sync(self, _log)
                except Exception as e:
                    logging.warning(f"record log on-chain failed with error message {e}")

        return res

    def _pretty_payment(self):
        if not self.subscription_plan:
            return "Free"
        else:
            plans = []
            for plan in self.subscription_plan:
                if plan.price_in_agent != 0:
                    plans.append(f"{plan.price_in_agent} Agent({str(plan.period.name).lower()})")
            return " / ".join(plans)

    @staticmethod
    def _sha256(defs_json: dict) -> dict:
        if not defs_json:
            return defs_json
        hash_key = hashlib.sha256(json.dumps(defs_json, separators=(',', ':')).encode("utf-8")).hexdigest()
        defs_json["hash"] = hash_key
        return defs_json

    @staticmethod
    def _parse_models(defs_json: dict, response_mode=False) -> (dict, dict):
        method_definition = {
            "name": "body",
            "description": "",
            "type": "object",
            "schema": {
                "$ref": f"#/definitions/{defs_json.get('title')}"
            }
        }
        if not response_mode:
            method_definition["in"] = "body"
            method_definition["required"] = True
        model_definition = {
            defs_json.get("title"): {
                "type": "object",
                "properties": defs_json.get("properties")
            }
        }
        return method_definition, model_definition

    def info(self):
        return f"Name: {self.metadata.name}\n" \
               f"Agent ID: {self.agent_id}\n" \
               f"Wallet Address: {self.wallet_address}\n" \
               f"SmartWallet Address: {self.aa_wallet_address}\n" \
               f"Payments: {self._pretty_payment()}\n" \
               f"Description: {self.metadata.description}\n" \
               f"Endpoint: {self.metadata.endpoint}\n" \
               f"Register Time: {self.metadata.register_time}\n\n"

    def api_list(self):
        if self._api_list:
            return self._api_list
        definitions = {}
        paths = {}
        for k, v in self.message_route.items():
            name = k
            parameter_json_schema = v.get("parameter").schema()
            response_json_schema = v.get("response").schema()

            parameters_schema, definition = self._parse_models(parameter_json_schema)
            definitions.update(definition)

            response_schema, definition = self._parse_models(response_json_schema)
            definitions.update(definition)

            path = {
                "consumes": [
                    "application/json",
                ],
                "produces": [
                    "application/json",
                ],
                "parameters": [parameters_schema],
                "responses": {"200": response_schema}
            }
            paths[f"/{name}"] = {"post": self._sha256(path)}

        self.metadata.endpoint = self.metadata.endpoint.replace("http://", "").replace("https://", "")
        self._api_list = {
            "swagger": "2.0",
            "info": {
                "version": self.metadata.version,
                "name": self.metadata.name,
                "id": self.agent_id,
                "wallet-address": self.wallet_address,
                "contract-wallet-address": self.aa_wallet_address,
                "payment": self._pretty_payment(),
                "title": self.metadata.description,
                "endpoint": self.metadata.endpoint,
                "register-time": self.metadata.register_time
            },
            "host": self.metadata.endpoint,
            "paths": paths,
            "definitions": definitions
        }
        return self._api_list

    def run(self, host="0.0.0.0", port=8000, log_onchain=True):
        http_server = Flask(__name__)
        log = logging.getLogger('werkzeug')
        log.setLevel(logging.ERROR)

        if log_onchain:
            # start a thread for record onchain log
            logging.debug("starting a thread for put agent log on-chain.")
            threading.Thread(target=monitor_new_onchain_log, args=[self]).start()

        @http_server.route("/<method_name>", methods=["POST"])
        def _accept_request(method_name):
            if method_name not in self.message_route:
                msg = f"method {method_name} not found/registered for current agent"
                return ErrorMessage(error=msg).dict()

            parameters = flask_request.json
            caller_metadata = flask_request.headers.get("X-Agent-Meta")
            caller_message_hash = flask_request.headers.get("X-Agent-Message-Hash")
            caller_signature = flask_request.headers.get("X-Agent-Signature")
            if caller_metadata:
                caller_metadata = AgentMetadata.from_json(json.loads(caller_metadata))
                parent_task_id = flask_request.headers.get("X-Agent-Task-Id")
            else:
                caller_metadata = None
                parent_task_id = ""

            func = self.message_route[method_name].get('method')
            parameter_type = self.message_route[method_name].get('parameter')
            response_type = self.message_route[method_name].get('response')

            try:
                res = self.call_function(func, parameter_type(**parameters), caller_metadata, caller_message_hash=caller_message_hash,
                                         caller_signature=caller_signature, parent_task_id=parent_task_id, log_onchain=log_onchain, with_log_queue=True)
            except AuthorizationException:
                return flask.Response(status=401,
                                      response=json.dumps({
                                          "success": False,
                                          "message": "current agent is payable,you have to subscribe before calling it"
                                      }),
                                      mimetype='application/json; charset=utf-8')
            except Exception as e:
                logging.error(e)
                return flask.Response(status=500,
                                      response=json.dumps({
                                          "success": False,
                                          "message": "Internal Server Error"
                                      }),
                                      mimetype='application/json; charset=utf-8')

            if isinstance(res, FlaskResponse):
                return res
            elif isinstance(res, Model):
                return res.dict()
            elif isinstance(res, dict):
                return response_type(**res).dict()
            elif isinstance(res, types.GeneratorType):
                def generator():
                    for chunk in res:
                        if isinstance(chunk, Model):
                            s = chunk.json()
                        else:
                            s = chunk
                        yield s

                return flask.Response(generator(), mimetype='text/event-stream')
            else:
                logging.error(f"invalid response type {type(res)}, should be Model or dict")
                return flask.Response(status=500,
                                      response=json.dumps({
                                          "success": False,
                                          "message": "Internal Server Error"
                                      }),
                                      mimetype='application/json; charset=utf-8')

        @http_server.route("/", methods=["GET"])
        def _api_list():
            return self.api_list()

        logging.info(f"Listening: http://{host}:{port}")
        http_server.run(host=host, port=port)
