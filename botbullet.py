import inspect
import time
import asyncio
import types
import pushbullet
from pushbullet import Pushbullet
from threading import Thread
from pprint import pprint


class IndexedDict(dict):
    '''
    Simple dict but support access as x.y style.
    '''

    def __init__(self, d=None, **kw):
        super(IndexedDict, self).__init__(**kw)
        if d:
            for k, v in d.items():
                self[k] = IndexedDict(v) if isinstance(v, dict) else v

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(
                r"'IndexedDict' object has no attribute '%s'" % key)

    def __setattr__(self, key, value):
        self[key] = value

class BotbulletThread(Thread):
    def __init__(self, alias=None, switch=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.alias = alias
        self.switch = switch

    def stop(self):
        self.switch[0] = False

    def __repr__(self):
        return '<BotbulletThread({}, {})>'.format(self.alias, 'Alive' if self.switch[0] else 'Stopped')

class Botbullet(Pushbullet):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.listen_threads = []

    def get_or_create_device(self, name):
        try:
            return self.get_device(name)
        except pushbullet.InvalidKeyError:
            return self.new_device(name)

    def listen_pushes(self, callback=None, modified_after=None, filter=None, sleep_interval=2, switch=None, log=None):
        def noop(*args):
            pass

        log = log or print
        last_time = modified_after or time.time()
        callback = callback or noop
        # This allows stopping listening from outer scope
        switch = switch or [True]

        log('Pushes listening Start.')
        while True:
            pushes = self.get_pushes(modified_after=last_time)
            if filter:
                pushes = filter(pushes)
            if len(pushes):
                length = len(pushes)
                log('{} pushes received.'.format(length))
                for i in range(length):
                    event_obj = IndexedDict(
                        {'listening': True, 'remain_pushes': length - i - 1, 'sender': self})
                    push = IndexedDict(pushes[i])
                    callback(push, event_obj)
                    if not event_obj['listening']:
                        switch[0] = False  # Escape the listening loop
            if not switch[0]:
                log('Pushes listening end.')
                return
            last_time = time.time()
            time.sleep(sleep_interval)

    def listen_pushes_asynchronously(self, *args, alias=None, **kwargs):
        switch = [True]

        kwargs['switch'] = switch
        thread = BotbulletThread(alias=alias, switch=switch, target=self.listen_pushes, args=args, kwargs=kwargs)

        self.listen_threads.append(thread)
        thread.start()
        return thread

    def stop_listening(self, thread=None):
        if thread:
            if thread.is_alive():
                thread.stop()
            self.listen_threads.remove(thread)
        else:
            for thread in self.listen_threads:
                if thread.is_alive():
                    thread.stop()
            self.listen_threads = []

    def __del__(self):
        self.stop_listening()