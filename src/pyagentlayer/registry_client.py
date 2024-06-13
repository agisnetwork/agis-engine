# -*- coding:utf-8 -*-
import logging
import os
from abc import ABC, abstractmethod

import dotenv
from eth_account import Account

from .agent_executor import new_agent_nft
from .models import AgentMetadata
from .utils.ipfs import ParticleIPFSClient, AgentIPFSClient

dotenv.load_dotenv()


class AbstractRegistryClient(ABC):
    @abstractmethod
    def is_owner(self, agent_id):
        return True

    @abstractmethod
    def register(self, metadata: AgentMetadata):
        pass

    @abstractmethod
    def get_agent_meta(self, agent_id):
        pass


class OnChainAgentRegistryClient(AbstractRegistryClient):
    def __init__(self, wallet: Account = None, wallet_address: str = None) -> None:
        self.wallet = wallet
        if self.wallet:
            self.wallet_address = self.wallet.address
        else:
            self.wallet_address = wallet_address

        if os.environ.get('IPFS_PARTICLE_PROJECT_ID') and os.environ.get('IPFS_PARTICLE_SERVER_KEY'):
            logging.debug("using particle ipfs client")
            self.ipfs_client = ParticleIPFSClient(project_id=os.environ.get('IPFS_PARTICLE_PROJECT_ID'),
                                                  project_server_key=os.environ.get('IPFS_PARTICLE_SERVER_KEY'))
        else:
            logging.debug("using agent ipfs client")
            self.ipfs_client = AgentIPFSClient()

        self.agent_nft = new_agent_nft(account=wallet, account_address=wallet_address)
        self.metadata = None

    def is_owner(self, agent_id):
        owner = self.agent_nft.owner_of(agent_id)
        return owner.lower() == self.wallet_address.lower()

    def register(self, metadata: AgentMetadata):
        # build json upload ipfs
        ipfs_cid = self.ipfs_client.upload_json(metadata.to_json())
        logging.info(f"upload agent metadata to ipfs success, ipfs cid: {ipfs_cid}")
        # create new agent
        agent_id = self.agent_nft.safe_mint_sync(ipfs_cid)
        logging.info(f"mint agent id success: {agent_id}")
        return agent_id

    def get_agent_meta(self, agent_id) -> AgentMetadata:
        ipfs_cid = self.agent_nft.token_uri(int(agent_id))
        logging.debug(f"get token uri success, {ipfs_cid}")
        # download from ipfs
        agent_metadata_dict = self.ipfs_client.download_file(ipfs_cid)
        self.metadata = AgentMetadata.from_json(agent_metadata_dict)
        logging.debug(f"get agent metadata success: {agent_metadata_dict}")

        return self.metadata
