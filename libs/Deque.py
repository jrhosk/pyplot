import numpy as np

from collections import deque

class Deque():
    '''
    Wrapper for collections.deque to return numpy arrays for analysis
    '''

    def __init__(self, array):
        self.deque = deque(array)

    def pop(self):
        return self.deque.pop()

    def popleft(self):
        return self.deque.popleft()

    def append(self, element):
        self.deque.append(element)
        return np.array(self.deque)

    def appendleft(self, element):
        self.deque.appendleft(element)
        return np.array(self.deque)

    def shift(self, element):
        self.deque.popleft()
        self.deque.append(element)

        return np.array(self.deque)

    def to_numpy(self):
        return np.array(self.deque)