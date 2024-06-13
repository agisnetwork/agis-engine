# -*- coding:utf-8 -*-
import abc
import json
import logging
import math
import os.path
import time
from typing import List

from eth_account import Account
from web3 import Web3
from web3.contract import Contract
from web3.exceptions import TransactionNotFound

from .models import SubscriptionPlan, SubscriptionPeriodEnum

logging.basicConfig(format='%(asctime)s: t-%(thread)d: %(levelname)s: %(message)s')
logging.getLogger().setLevel(logging.INFO)

rpc_endpoint = os.environ.get("CHAIN_RPC", "https://testnet-rpc.agentlayer.xyz/")
if not rpc_endpoint:
    raise ValueError("missing rpc endpoint environment: CHAIN_RPC")

agent_nft_address = Web3.to_checksum_address('0xB6B3ef5eA5e94796E43fE126626fa555C6919265')
smart_wallet_factory_address = Web3.to_checksum_address('0xCd64Fa42F7f27D2b7cC1F58BED61B86EB1C9586d')
agent_address = Web3.to_checksum_address('0x1E6ed7b03939903EE95d57AAc1FA08869585Fe2a')
subscription_address = Web3.to_checksum_address('0x8fD8AEFc6e97Ce1C9F49834265656A77629f3243')
with open(os.path.join(os.path.dirname(__file__), "abi/AgentNFT.json"), "r") as f:
    agent_nft_abi = json.loads("".join(f.readlines()))
with open(os.path.join(os.path.dirname(__file__), "abi/SmartWalletFactory.json"), "r") as f:
    smart_wallet_factory_abi = json.loads("".join(f.readlines()))
with open(os.path.join(os.path.dirname(__file__), "abi/SmartWallet.json"), "r") as f:
    smart_wallet_abi = json.loads("".join(f.readlines()))
with open(os.path.join(os.path.dirname(__file__), "abi/AGENT.json"), "r") as f:
    agent_abi = json.loads("".join(f.readlines()))
with open(os.path.join(os.path.dirname(__file__), "abi/Subscription.json"), "r") as f:
    subscription_abi = json.loads("".join(f.readlines()))


class AbstractExecutor(metaclass=abc.ABCMeta):
    account: Account | None
    contract: Contract
    account_address: str

    def __init__(self, contract: Contract, account: Account = None, account_address=None):
        self.contract = contract
        self.account = account
        if account:
            self.account_address = account.address
        else:
            self.account_address = account_address

        self.w3 = contract.w3
        self.chain_id = self.w3.eth.chain_id

    def waiting_for_confirmation(self, tx_hash):
        logging.info(f"waiting tx: {tx_hash.hex()}")
        while True:
            try:
                receipt = self.contract.w3.eth.get_transaction_receipt(tx_hash)
                logging.info(f"tx: {tx_hash.hex()} confirmed at block {receipt.blockNumber}\tstatus: {'success' if receipt.get('status') == 1 else 'fail'}")
                if receipt.contractAddress:
                    return receipt.contractAddress
                return
            except TransactionNotFound:
                time.sleep(1)


class AgentNft(AbstractExecutor):
    def owner_of(self, token_id: int):
        return self.contract.functions.ownerOf(int(token_id)).call()

    def token_uri(self, token_id: int):
        return self.contract.functions.tokenURI(token_id).call()

    def safe_mint_sync(self, token_uri):
        if not self.account:
            raise ValueError("Agent without private key cannot mint nft with sdk.")
        tx = self.contract.functions.safeMint(token_uri).build_transaction({
            "from": self.account.address,
            "nonce": self.contract.w3.eth.get_transaction_count(self.account.address, "pending")
        })
        signed_tx = self.account.sign_transaction(tx)

        # broadcast tx and wait for confirmation
        tx_hash = self.contract.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
        logging.info(f"mint agent nft\ttx hash: {tx_hash.hex()}")
        self.waiting_for_confirmation(tx_hash)

        # decode token_id from receipt
        receipt = self.contract.w3.eth.get_transaction_receipt(tx_hash)
        token_id = list(self.contract.w3.codec.decode(["uint256"], receipt.logs[1].topics[3]))[0]
        return token_id


class SmartWalletFactory(AbstractExecutor):

    def create_wallet(self):
        owned_aa_wallet = self.contract.functions.eoaOwnedWallet(self.account_address).call()
        if owned_aa_wallet == '0x0000000000000000000000000000000000000000':
            if not self.account:
                raise ValueError("Agent without private key cannot crate aa wallet.")
            # create
            tx = self.contract.functions.createWallet().build_transaction({
                "from": self.account.address,
                "nonce": self.contract.w3.eth.get_transaction_count(self.account.address)
            })
            signed_tx = self.account.sign_transaction(tx)

            # broadcast tx and wait for confirmation
            tx_hash = self.contract.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            logging.info(f"contract call: createWallet\ttx hash: {tx_hash.hex()}")
            self.waiting_for_confirmation(tx_hash)
            return self.contract.functions.eoaOwnedWallet(self.account.address).call()
        else:
            return owned_aa_wallet


class SmartWallet(AbstractExecutor):

    def is_valid_signature(self, address, message, signature):
        try:
            recover_address = self.contract.w3.eth.account._recover_hash(message_hash=message, signature=signature)
            return recover_address.lower() == address.lower()
        except Exception as e:
            logging.warning(f"check signature error with message {str(e)}\taddress:{address}\tmessage:{message}\tsignature:{signature}")
        return False

    def subscribe(self, target_address, period: SubscriptionPeriodEnum, auto_renewal=False):
        if not self.account:
            raise ValueError("Agent without private key cannot subscribe to other agent.")

        logging.info(f"subscribe to address: {target_address} with period: {str(period.name).lower()}\tauto renewal: {auto_renewal}")
        tx = self.contract.functions.subscribeOtherAgent(period.value, target_address, auto_renewal).build_transaction({
            "from": self.account.address,
            "nonce": self.contract.w3.eth.get_transaction_count(self.account.address)
        })
        signed_tx = self.account.sign_transaction(tx)
        # broadcast tx and wait for confirmation
        tx_hash = self.contract.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
        logging.info(f"subscribing\ttx hash: {tx_hash.hex()}")
        self.waiting_for_confirmation(tx_hash)


class AgentToken(AbstractExecutor):
    def balance_of(self, address):
        return self.contract.functions.balanceOf(address).call()


class Subscription(AbstractExecutor):
    def is_subscribed(self, subscriber, target_agent_address):
        return self.contract.functions.isSubscribed(subscriber, target_agent_address).call()

    def is_auto_renewal(self, subscriber, target_agent_address):
        return self.contract.functions.isAutoRenewal(subscriber, target_agent_address).call()

    def get_subscription_left_time(self, subscriber, target_agent_address):
        return self.contract.functions.getSubscriptionLeftTime(subscriber, target_agent_address).call()

    def get_subscription_plan(self, wallet) -> (int, int, int):
        weekly_price = self.contract.functions.getSubscriptionPrice(SubscriptionPeriodEnum.WEEKLY.value, wallet).call()
        monthly_price = self.contract.functions.getSubscriptionPrice(SubscriptionPeriodEnum.MONTHLY.value, wallet).call()
        yearly_price = self.contract.functions.getSubscriptionPrice(SubscriptionPeriodEnum.YEARLY.value, wallet).call()
        return weekly_price, monthly_price, yearly_price

    def update_subscription_plan(self, wallet, subscription_plans: List[SubscriptionPlan] | None):
        new_weekly_price = 0
        new_monthly_price = 0
        new_yearly_price = 0

        if subscription_plans is not None:
            for plan in subscription_plans:
                if plan.period == SubscriptionPeriodEnum.WEEKLY:
                    new_weekly_price = int(plan.price_in_agent * math.pow(10, 18))
                elif plan.period == SubscriptionPeriodEnum.MONTHLY:
                    new_monthly_price = int(plan.price_in_agent * math.pow(10, 18))
                elif plan.period == SubscriptionPeriodEnum.YEARLY:
                    new_yearly_price = int(plan.price_in_agent * math.pow(10, 18))

        # get exist subscription plan
        exists_weekly_price, exists_monthly_price, exists_yearly_price = self.get_subscription_plan(wallet)
        if new_weekly_price != exists_weekly_price:
            logging.info(f"set weekly subscription plan with price {round(new_weekly_price / math.pow(10, 18), 4)} WAGENT")
            self._update_subscription_price(SubscriptionPeriodEnum.WEEKLY, wallet, new_weekly_price)
        if new_monthly_price != exists_monthly_price:
            logging.info(f"set monthly subscription plan with price {round(new_monthly_price / math.pow(10, 18), 4)} WAGENT")
            self._update_subscription_price(SubscriptionPeriodEnum.MONTHLY, wallet, new_monthly_price)
        if new_yearly_price != exists_yearly_price:
            logging.info(f"set yearly subscription plan with price {round(new_yearly_price / math.pow(10, 18), 4)} WAGENT")
            self._update_subscription_price(SubscriptionPeriodEnum.YEARLY, wallet, new_yearly_price)

    def _update_subscription_price(self, period, wallet, price):
        if not self.account:
            raise ValueError("Agent without private key cannot update subscribe info.")

        tx = self.contract.functions.setSubscriptionPrice(period.value, wallet, price).build_transaction({
            "from": self.account.address,
            "nonce": self.contract.w3.eth.get_transaction_count(self.account.address)
        })
        signed_tx = self.account.sign_transaction(tx)
        # broadcast tx and wait for confirmation
        tx_hash = self.contract.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
        logging.info(f"tx hash: {tx_hash.hex()}")
        self.waiting_for_confirmation(tx_hash)


def new_agent_nft(account: Account = None, account_address: str = None) -> AgentNft:
    web3 = Web3(Web3.HTTPProvider(rpc_endpoint))
    contract = web3.eth.contract(address=agent_nft_address, abi=agent_nft_abi)
    return AgentNft(contract=contract, account=account, account_address=account_address)


def new_smart_wallet_factory(account: Account = None, account_address: str = None) -> SmartWalletFactory:
    web3 = Web3(Web3.HTTPProvider(rpc_endpoint))
    contract = web3.eth.contract(address=smart_wallet_factory_address, abi=smart_wallet_factory_abi)
    return SmartWalletFactory(contract=contract, account=account, account_address=account_address)


def new_smart_wallet(account: Account = None, eoa_account_address=None, smart_wallet_address: str = None) -> SmartWallet:
    web3 = Web3(Web3.HTTPProvider(rpc_endpoint))
    contract = web3.eth.contract(address=smart_wallet_address, abi=smart_wallet_abi)
    return SmartWallet(contract=contract, account=account, account_address=eoa_account_address)


def new_agent_token_contract(account: Account = None, account_address=None) -> AgentToken:
    web3 = Web3(Web3.HTTPProvider(rpc_endpoint))
    contract = web3.eth.contract(address=agent_address, abi=agent_abi)
    return AgentToken(contract=contract, account=account, account_address=account_address)


def new_subscription_contract(account=None, account_address=None) -> Subscription:
    web3 = Web3(Web3.HTTPProvider(rpc_endpoint))
    contract = web3.eth.contract(address=subscription_address, abi=subscription_abi)
    return Subscription(contract=contract, account=account, account_address=account_address)
