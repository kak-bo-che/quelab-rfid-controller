import pickle
import logging
from datetime import datetime

class CachedLoginsBase(object):
    def __init__(self):
        self.logger = logging.getLogger()

    def load_cached_login_file(self):
        return []
    def dump_cached_login_file(self):
        self.logger.warn("Cached login file disabled")
        pass
    def check_cached_logins(self, rfid):
        return None
    def update_cached_logins(self, rfid, contact):
        self.logger.warn("Cached login file disabled")
        pass

class CachedLogins(CachedLoginsBase):
    """
    cached login pickle format (rfid, wild_apricot_contact, timestamp)
    """
    def __init__(self, login_path):
        if not login_path:
            raise ValueError("login_path must be a vaild path")
        self.login_path = login_path
        self.cached_logins = self.load_cached_login_file()
        self.logger = logging.getLogger()

    def load_cached_login_file(self):
        logins = []
        try:
            with open(self.login_path, 'rb') as login_file:
                logins = pickle.load(login_file)

        except (TypeError, EOFError, FileNotFoundError):
            # None is not a valid path
            pass
        return logins

    def dump_cached_login_file(self):
        with open(self.login_path, 'wb') as logins:
            pickle.dump(self.cached_logins, logins)
        self.logger.info("Writing to cached login file {}".format(self.login_path))


    def check_cached_logins(self, rfid):
        return next((login[1] for login in self.cached_logins if login[0] == rfid), None)

    def update_cached_logins(self, rfid, contact):
        # remove if rfid already accepted
        self.logger.info("Filter Cached logins")
        self.cached_logins = list(filter(lambda x: x[0] != rfid, self.cached_logins))
        self.cached_logins.insert(0, (rfid, contact, datetime.now()))

        self.cached_logins = self.cached_logins[0:10] # limit to last 10 entries
        self.logger.info("Write login file")

        self.dump_cached_login_file()
