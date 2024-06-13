import abc
import base64
import hashlib
import io
import json
import logging
import tempfile
from urllib.parse import urlparse

import requests


def generate_hash(input_string):
    hash_object = hashlib.sha256()
    hash_object.update(input_string.encode('utf-8'))
    hash_value = hash_object.hexdigest()

    return hash_value


class AbsIPFSClient(metaclass=abc.ABCMeta):

    def __init__(self):
        self._headers = {}
        self._endpoint = None

    def upload_file(self, filepath):
        if isinstance(filepath, str) and urlparse(filepath).scheme in ['http', 'https']:
            response = requests.get(filepath)
            if response.status_code == 200:
                files = {'file': (filepath.split('/')[-1], response.content)}
                resp = requests.post(self._endpoint, headers=self._headers, files=files)
                cid = json.loads(resp.content).get('cid')
                logging.debug(f'upload file {filepath} to ipfs success. cid: {cid}')
                return cid
            else:
                logging.error(f'Failed to download file from {filepath}')
        else:
            if (isinstance(filepath, tempfile._TemporaryFileWrapper)
                    or isinstance(filepath, io.IOBase)):
                resp = requests.post(self._endpoint, headers=self._headers, files={'file': filepath})
            else:
                with open(filepath, 'rb') as f:
                    resp = requests.post(self._endpoint, headers=self._headers, files={'file': f})

            assert resp.ok
            res_json = json.loads(resp.content)
            if "error" in res_json:
                logging.error(f'error when upload json to ipfs.')
                raise ValueError(res_json.get("error").get("message"))

            cid = json.loads(resp.content).get('cid')
            logging.debug(f'upload file to ipfs success. cid: {cid}')
            return cid

    def upload_json(self, json_data: dict):
        with tempfile.NamedTemporaryFile(mode="w+") as f:
            f.write(json.dumps(json_data))
            f.seek(0)
            return self.upload_file(f)

    @staticmethod
    def download_file(file_cid):
        resp = requests.get(f'https://quicknode.quicknode-ipfs.com/ipfs/{file_cid}')
        assert resp.ok
        return json.loads(resp.content)


class AgentIPFSClient(AbsIPFSClient):
    def __init__(self):
        super().__init__()
        self._headers = {"X-Api-Key": "c18ebc72ca710ec0rvFVewk5a7MNcb20d"}
        self._endpoint = "https://alpha.agentlayer.xyz/api/ipfs"


class ParticleIPFSClient(AbsIPFSClient):
    def __init__(self, project_id, project_server_key):
        super().__init__()
        self._headers = {"Authorization": "Basic " + base64.b64encode(f"{project_id}:{project_server_key}".encode("utf-8")).decode("utf-8")}
        self._endpoint = "https://rpc.particle.network/ipfs/upload"
