class RestServiceInterface(object):
    def send(self, url, data=None):
        raise NotImplementedError

    def send_ziggy(self, url, ziggy_instance, uuid):
        raise NotImplementedError
