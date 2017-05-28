'''app.lib.timer'''
import logging
from datetime import datetime

class Timer():

    start_dt = None
    stop_dt = None
    counting = False

    def start(self):

        self.counting = True

        if not self.start_dt:
            self.start_dt = datetime.now()

    def stop(self, to_str=True):

        if self.counting == True:
            self.stop_dt = datetime.now()
            self.counting = False

        if to_str:
            return self.clock(stop=False)

    def restart(self):

        self.start_dt = datetime.now()
        self.stop_dt = None
        self.start()

    def __repr__(self):
        '''Return str duration in sec'''

        return self.clock(stop=False)

    def clock(self, stop=True):
        '''Return str duration in sec w/ stop option'''

        if self.counting and stop:
            self.stop()
            diff = self.stop_dt - self.start_dt
        elif self.counting and not stop:
            diff = datetime.now() - self.start_dt
        elif not self.counting:
            diff = self.stop_dt - self.start_dt

        return '%s.%ss' % (diff.seconds, str(diff.microseconds/1000))

    def __init__(self, start=True):

        if start:
            self.start()
