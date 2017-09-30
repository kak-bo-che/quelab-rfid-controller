import json
import os
import urllib.parse
from wildapricotapi import ApiException, WaApiClient

class WildApricotApi(object):
    def __init__(self, api_key):
        self.api = WaApiClient(api_key=api_key)
        self.api.authenticate_with_apikey()
        accounts = self.api.execute_request("/v2/accounts")
        self.account = accounts[0]

    def find_contact_by_id(self, id):
        contactsUrl = next(res for res in self.account['Resources'] if res['Name'] == 'Contacts')['Url']
        params = {'$async': 'false'}
        request_url = contactsUrl + str(id) +  '?' + urllib.parse.urlencode(params)
        response = self.api.execute_request(request_url)

    def find_contact_by_rfid(self, rfid):
        contact = None
        contactsUrl = next(res for res in self.account['Resources'] if res['Name'] == 'Contacts')['Url']
        params = {'$async': 'false', '$filter': "RFID eq " + str(rfid)}

        request_url = contactsUrl +  '?' + urllib.parse.urlencode(params)
        response = self.api.execute_request(request_url)
        if response:
            contact = response['Contacts'][0]
        return contact
