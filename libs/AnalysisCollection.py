import pandas as pd
import numpy as np
import statsmodels.tsa.stattools as sm

class AnalysisCollection():
    def __init__(self):
        pass

    def rolling_average(self, array):
        series = pd.Series(array)
        rolling_avg = series.rolling(10).mean().fillna(0).iloc[-1]
        stdev = series.fillna(0).std()
        return rolling_avg, stdev

    def auto_correlation(self, array):
        temp = np.array(sm.acf(array, fft=True))[-1]
        return temp