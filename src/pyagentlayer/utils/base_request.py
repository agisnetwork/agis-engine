# -*- coding:utf-8 -*-
import json
from abc import ABC

import requests
from requests.exceptions import HTTPError, ReadTimeout


class BaseRequestClient(ABC):
    def __init__(self) -> None:
        super().__init__()

    def send(self, url, headers, payload):
        response = self.make_request(url, headers, payload)
        if response.ok:
            return response.text
        else:
            raise ValueError(f"call agent failed with message:{response.text} status: {response.status_code}")

    def send_async(self, url, headers, payload):
        response = self.make_request(url, headers, payload, True)
        if response.status_code != 200:
            raise Exception('There is a internet request problem. Please try again later.')

        def get_streaming_answer(data_str):
            try:
                data = json.loads(data_str.replace('data: ', '').strip())
                return data.get('answer', '')
            except Exception as e:
                return ''

        for chunk in response.iter_lines(decode_unicode=True):
            yield chunk

    def make_request(self, url, headers, payload, stream=False):
        try:
            return requests.post(url, headers=headers, json=payload, stream=stream)
        except (HTTPError, ReadTimeout):
            raise Exception('There is a internet request problem. Please try again later.')
