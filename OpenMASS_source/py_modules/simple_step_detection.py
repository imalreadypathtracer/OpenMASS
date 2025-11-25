import numpy as np
import matplotlib.pyplot as plt
import random
from scipy.signal import medfilt
import ruptures as rpt


def rolling_mean(data, window_size):
    """
    Calculate the rolling mean of a 1D array using numpy.convolve.

    Parameters:
    - data: A 1D numpy array or list of numerical data.
    - window_size: The size of the rolling window.

    Returns:
    - A numpy array containing the rolling mean.
    """
    if window_size < 1:
        raise ValueError("Window size must be at least 1.")
    if len(data) < window_size:
        raise ValueError("Window size must not be larger than the data length.")

    kernel = np.ones(window_size) / window_size
    rolling_mean = np.convolve(data, kernel, mode='valid')

    return rolling_mean


def chung_kennedy_filter(data, lambda_value=10):
    """
    Applies the Chung-Kennedy filter to a noisy time series.

    Parameters:
    - data: A 1D numpy array or list containing the time series data.
    - lambda_value: A smoothing parameter that controls the tradeoff between smoothness and fidelity.

    Returns:
    - filtered_data: A numpy array of the filtered time series.
    """

    data = np.array(data)
    n = len(data)

    # Initialize variables
    filtered_data = np.zeros(n)
    filtered_data[0] = data[0]
    filtered_data[1] = data[1]

    for t in range(2, n):
        predicted = 2 * filtered_data[t - 1] - filtered_data[t - 2]
        filtered_data[t] = (predicted + (data[t] - predicted) / (1 + lambda_value))

    return filtered_data


def find_changepoints_old(time_series, window_size=5, threshold=0.002, min_plateau=5):
    """
    Detects changepoint positions in a noisy time series based on differences in the values.

    Parameters:
    - time_series: A 1D array or list containing the noisy time series data.
    - window_size: The size of the window used for smoothing the data (default=5).
    - threshold: The minimum difference between two consecutive values to consider it a changepoint.

    Returns:
    - changepoints: List of indices where changepoints occur.
    """

    time_series = np.array(time_series)

    if window_size > 1:
        time_series = rolling_mean(time_series, window_size=window_size)

    differences = np.diff(time_series)

    changepoints = np.where(np.abs(differences) > threshold)[0] + 1  # +1 to align with original index
    changepoints = list(changepoints)
    plateaus = []
    for idx in range(1, len(changepoints)):
        if changepoints[idx] - changepoints[idx - 1] > min_plateau:
            plateaus.append([changepoints[idx - 1], changepoints[idx]])

    if len(changepoints) == 0:
        plateaus = [[0, len(time_series) - 1]]
        return [], plateaus

    first, last = [], []
    if changepoints[0] > min_plateau:
        first = [[0, changepoints[0]]]
    if changepoints[-1] < (len(time_series)-1) - min_plateau:
        last = [[changepoints[-1], len(time_series) - 1]]

    if len(first) == 1:
        plateaus = first + plateaus
    if len(last) == 1:
        plateaus = plateaus + last

    return changepoints, plateaus


def find_changepoints(time_series, window_size, threshold=0.001, min_plateau=5):
    data = np.array(time_series)
    if window_size > 1:
        data = rolling_mean(data, window_size=window_size)

    pelt_model = rpt.Pelt(model='l2', min_size=min_plateau).fit(np.array(data, dtype=np.float32))
    cpts = [0] + pelt_model.predict(pen=threshold)[:-1] + [len(data) - 1]

    plateaus = []
    for idx in range(len(cpts) - 1):
        plateaus.append([cpts[idx], cpts[idx + 1]])

    return cpts[1:-1], plateaus



if __name__ == "__main__":

    states = [0.0048, 0.0096, 0.0144, 0.0192, 0.0240]
    state = 0.0096
    data = []
    for i in range(2000):
        if random.random() < 0.01:
            state = states[random.randint(0, 4)]
        v = np.random.normal(loc=state, scale=0.02*np.sqrt(state), size=None)
        data.append(v)


    pelt_model = rpt.Pelt(model='l2', min_size=5).fit(np.array(data, dtype=np.float32))
    cpts = [0] + pelt_model.predict(pen=1)[:-1] + [len(data) - 1]

    print(cpts)

    plateaus = []
    for idx in range(len(cpts) - 1):
        plateaus.append([cpts[idx], cpts[idx + 1]])



    # plt.plot(data)
    # plt.show()
    #
    # data = chung_kennedy_filter(data, lambda_value=2)
    # changepoints, plateaus = find_changepoints(data, window_size=4, threshold=0.0008, min_plateau=8)
    # cps = [0] + changepoints + [len(data)-1]
    #
    # fit = np.zeros(shape=(len(data)))
    # for idx in range(1, len(cps)):
    #     fit[cps[idx-1]:cps[idx]] = np.mean(data[cps[idx-1]:cps[idx]])


    plt.plot(data)

    plat_fit = np.zeros(shape=(len(data)))
    for idx, p in enumerate(plateaus):
        plat_fit[p[0]:p[1]] = np.mean(data[p[0]:p[1]])
        plt.plot([p[0], p[1]], [np.mean(data[p[0]:p[1]]), np.mean(data[p[0]:p[1]])], color='orange')

    # plt.plot(plat_fit)
    plt.show()
