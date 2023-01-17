import json
import os
import urllib.parse
from urllib.error import URLError
from wildapricotapi import ApiException, WaApiClient

class UnknownUserError(Exception):
    pass
class WildApricotApi(object):
    def __init__(self, api_key):
        self.api = WaApiClient(api_key=api_key)
        self.account = None
        self.connected = False
        self.authenticate()

    def authenticate(self):
        try:
            if not self.api.get_access_token():
                self.api.authenticate_with_apikey()
                accounts = self.api.execute_request("/v2.1/accounts")
                self.account = accounts[0]
                self.connected = True
        except URLError:
            self.connected = False

    def find_contact_by_filter(self, filter):
        """
        example filters:
        "FirstName eq " + str(first_name) + ' AND LastName eq ' + str(last_name)
        "RFID eq " + str(rfid)
        """
        self.authenticate()
        contact = None
        if self.account:
            contacts_url = next(res for res in self.account['Resources'] if res['Name'] == 'Contacts')['Url']
            params = {'$async': 'false', '$filter': filter}

            request_url = contacts_url +  '?' + urllib.parse.urlencode(params)
            try:
                response = self.api.execute_request(request_url)
                if response and response.get('Contacts'):
                    contact = response['Contacts'][0]
                else:
                    raise UnknownUserError("Unknown User")
                self.connected = True
            except URLError:
                self.connected = False
        return contact

    def find_contact_by_name(self, first_name, last_name):
        filter = "FirstName eq " + str(first_name) + ' AND LastName eq ' + str(last_name)
        return self.find_contact_by_filter(filter)

    def find_contact_by_rfid(self, rfid):
        filter = "RFID eq " + str(rfid)
        return self.find_contact_by_filter(filter)

    def get_contact_avatar(self, contact):
        url = None
        avatar = None
        file_name = ""
        for field in contact['FieldValues']:
            if field['FieldName'] == 'Avatar' and field['Value']:
                url = field['Value'].get('Url')
                file_name = field['Value'].get('Id')
                break
        if url:
            try:
                avatar = self.api.execute_request(url + '?asBase64=true', binary=True)
                avatar = {file_name: avatar.decode('ascii')}
            except URLError:
                self.connected = False
        return avatar

    @staticmethod
    def is_active_member(contact):
        for field in contact['FieldValues']:
            if field['FieldName'] == 'Membership status':
                status = field['Value'].get('Value')
        if status in ['Active']:
            return True
        else:
            return False
