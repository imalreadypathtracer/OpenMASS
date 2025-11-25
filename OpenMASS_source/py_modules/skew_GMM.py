import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit
from scipy.stats import norm
import random as rnd
import pickle
from sklearn.cluster import KMeans
from sklearn.metrics import mean_squared_error


def exponential_gaussian(x, amp, mean, stddev, skewness):
    """
    Exponentially weighted Gaussian function

    :param x:
    :param amp:
    :param mean:
    :param stddev:
    :param skewness:
    :return:
    """
    return amp*np.exp(-((x - mean)**2 / (2*stddev**2))) * np.exp(-skewness*(x - mean))


def skew_gaussian(x, amp, mean, stddev, skewness):
    """
    Skew-normal distribution function.
    """
    t = (x - mean) / stddev
    return 2 * amp * norm.pdf(t) * norm.cdf(skewness * t)


def skew_gaussian_mixture(x, *params):
    """
    Mixture of skewed Gaussians.
    """
    num_components = len(params) // 4
    y = np.zeros_like(x)
    for i in range(num_components):
        amp = params[i * 4]
        mean = params[i * 4 + 1]
        stddev = params[i * 4 + 2]
        skewness = params[i * 4 + 3]
        y += skew_gaussian(x, amp, mean, stddev, skewness)
    return y


def sym_gaussian_mixture(x, *params):
    """
        Mixture of symmetric Gaussians.
        """
    num_components = len(params) // 4
    y = np.zeros_like(x)
    for i in range(num_components):
        amp = params[i * 4]
        mean = params[i * 4 + 1]
        stddev = params[i * 4 + 2]
        # skewness = params[i * 4 + 3]
        y += skew_gaussian(x, amp, mean, stddev, 0)
    return y


def estimate_initial_params_kmeans(data, num_components, n_init=5):
    """
    Estimate initial parameters (means and standard deviations) using k-means clustering.

    Parameters:
        data (array-like): The dataset (1D array) to analyze.
        num_components (int): The number of Gaussian components to estimate.
        n_init (int): number of initial random states tried

    Returns:
        initial_means (list): Initial mean values for each component.
        initial_sigmas (list): Initial standard deviation values for each component.
    """

    data = np.asarray(data)
    data_reshaped = data.reshape(-1, 1)

    kmeans = KMeans(n_clusters=num_components, random_state=rnd.randint(1, 10000), n_init=n_init)
    kmeans.fit(data_reshaped)

    initial_means = kmeans.cluster_centers_.flatten()
    labels = kmeans.labels_

    initial_sigmas = [
        np.std(data[labels == cluster_idx]) for cluster_idx in range(num_components)
    ]

    sorted_indices = np.argsort(initial_means)
    initial_means = initial_means[sorted_indices]
    initial_sigmas = np.array(initial_sigmas)[sorted_indices]

    return initial_means.tolist(), initial_sigmas.tolist()


def fit_skewed_gaussian_mixture(data,
                                num_components,
                                bins=100,
                                density=True,
                                plot=True,
                                component_optimizer='aic',
                                component_penalty=0,
                                callback=None,
                                max_iter=10_000,
                                n_init=5,
                                max_components=5,
                                sym=False,
                                ):

    """
    Fits a skewed Gaussian Mixture Model to a dataset.

    Parameters:
        data (array-like): The data to fit.
        num_components (int): Number of skewed Gaussian components in the mixture.
            can be set to 'auto' and will use aic / bic to choose optimal number.
        bins (int or array-like): Number of bins or bin edges for the histogram.
        density (bool): Whether to normalize the histogram to a probability density.
        plot (bool): Whether to plot the histogram and fitted mixture.
        component_optimizer ('aic' or 'bic'): use aic / bic to optimise number of components.
        component_penalty (float): additional regularization penalty added to aic or bic
            to reduce component overfitting.
        callback (callable): callback function during fitting (generally to update UI / progressbar).
        max_iter (int): maximum iterations of the curve fit function.
        n_init (int): number of initial states of random seed of k-means initial guess finder.
        max_components (int): maximum number of components to try and fit during optimisation stage.

    Returns:
        popt (array): Optimal parameters for the skewed Gaussian mixture model.
        pcov (2D array): Covariance matrix of the parameter estimates.
        fit_function (callable): Function to compute the fitted skewed Gaussian mixture.
    """
    print(f"Number of components = {num_components}")
    counts, bin_edges = np.histogram(data, bins=bins, density=density)
    bin_centers = 0.5 * (bin_edges[:-1] + bin_edges[1:])

    if num_components == 'auto':
        opt_aic, opt_bic = find_optimal_components(data, bins=bins, penalty=component_penalty, callback=callback, max_iter=max_iter, n_init=n_init, max_components=max_components, sym=sym)
        if component_optimizer == 'bic':
            num_components = opt_bic
        else:
            num_components = opt_aic
    print(f"Number of components selected by information criterion = {num_components}")

    initial_means, initial_sigmas = estimate_initial_params_kmeans(data, num_components, n_init=n_init)
    print(f"Number of components returned by k-means = {len(initial_means)}")

    initial_guesses = []
    lower_bounds = []
    upper_bounds = []
    for i in range(len(initial_means)):
        amp_guess = max(counts) / num_components
        mean_guess = initial_means[i]
        stddev_guess = initial_sigmas[i]
        skewness_guess = 0.0001  # Start with no skew
        initial_guesses.extend([amp_guess, mean_guess, stddev_guess, skewness_guess])

        lower_bounds.extend([0, 0, mean_guess / 40, -10])
        upper_bounds.extend([np.inf, np.inf, mean_guess / 5, 10])

    if not sym:
        func = skew_gaussian_mixture
    else:
        func = sym_gaussian_mixture
    try:
        popt, pcov = curve_fit(func, bin_centers, counts, p0=initial_guesses, maxfev=max_iter, bounds=(lower_bounds, upper_bounds))
    except ValueError:
        popt, pcov = curve_fit(func, bin_centers, counts, p0=initial_guesses, maxfev=max_iter)

    fitted_curve = func(bin_centers, *popt)

    rmse = np.sqrt(mean_squared_error(counts, fitted_curve))

    def fit_function(x):
        return func(x, *popt)

    if plot:
        plt.hist(data, density=density, bins=bins, label="Data", color="orange", ec="orange", histtype="stepfilled", alpha=0.3)
        x_fit = np.linspace(bin_edges[0], bin_edges[-1], 1000)
        y_fit = fit_function(x_fit)
        plt.plot(x_fit, y_fit, label="Skewed Gaussian Mixture Fit", color="#ffbb22", alpha=1, linewidth=2)

        for i in range(num_components):
            amp = popt[i * 4]
            mean = popt[i * 4 + 1]
            stddev = popt[i * 4 + 2]
            skewness = popt[i * 4 + 3]
            plt.plot(x_fit, skew_gaussian(x_fit, amp, mean, stddev, skewness), color='#ffbb22', alpha=0.6, linewidth=2)

        plt.xlabel("Value")
        plt.ylabel("Density" if density else "Counts")
        plt.legend()
        plt.title("Histogram and Skewed Gaussian Mixture Fit")
        plt.show()

    return popt, pcov, fit_function, rmse


def estimate_skewed_gaussian_mixture(data,
                                     num_components,
                                     bins=100,
                                     density=True,
                                     max_iter=10_000,
                                     n_init=5,
                                     sym=False,
                                     ):
    """
    Fits a skewed Gaussian Mixture Model to a dataset.

    Parameters:
        data (array-like): The data to fit.
        num_components (int): Number of skewed Gaussian components in the mixture.
            can be set to 'auto' and will use aic / bic to choose optimal number.
        bins (int or array-like): Number of bins or bin edges for the histogram.
        density (bool): Whether to normalize the histogram to a probability density.
        plot (bool): Whether to plot the histogram and fitted mixture.
        component_optimizer ('aic' or 'bic'): use aic / bic to optimise number of components.
        component_penalty (float): additional regularization penalty added to aic or bic
            to reduce component overfitting.
        callback (callable): callback function during fitting (generally to update UI / progressbar).
        max_iter (int): maximum iterations of the curve fit function.
        n_init (int): number of initial states of random seed of k-means initial guess finder.
        max_components (int): maximum number of components to try and fit during optimisation stage.

    Returns:
        popt (array): Optimal parameters for the skewed Gaussian mixture model.
        pcov (2D array): Covariance matrix of the parameter estimates.
        fit_function (callable): Function to compute the fitted skewed Gaussian mixture.
    """

    counts, bin_edges = np.histogram(data, bins=bins, density=density)
    bin_centers = 0.5 * (bin_edges[:-1] + bin_edges[1:])

    initial_means, initial_sigmas = estimate_initial_params_kmeans(data, num_components, n_init=n_init)

    initial_guesses = []
    lower_bounds = []
    upper_bounds = []
    for i in range(len(initial_means)):
        amp_guess = max(counts) / num_components
        mean_guess = initial_means[i]
        stddev_guess = initial_sigmas[i]
        skewness_guess = 0.0001  # Start with no skew
        initial_guesses.extend([amp_guess, mean_guess, stddev_guess, skewness_guess])

        lower_bounds.extend([0, 0, mean_guess / 40, -10])
        upper_bounds.extend([np.inf, np.inf, mean_guess / 5, 10])

    if not sym:
        func = skew_gaussian_mixture
    else:
        func = sym_gaussian_mixture
    try:
        popt, pcov = curve_fit(func, bin_centers, counts, p0=initial_guesses, maxfev=max_iter, bounds=(lower_bounds, upper_bounds))
    except ValueError:
        popt, pcov = curve_fit(func, bin_centers, counts, p0=initial_guesses, maxfev=max_iter)

    fitted_curve = func(bin_centers, *popt)

    rmse = np.sqrt(mean_squared_error(counts, fitted_curve))

    def fit_function(x):
        return func(x, *popt)

    return popt, pcov, fit_function, rmse


def log_likelihood(x, *params, sym=False):
    """Calculate the log-likelihood of the skewed Gaussian mixture"""
    num_components = len(params) // 4
    likelihood = np.zeros_like(x)

    for i in range(num_components):
        amp = params[i * 4]
        mean = params[i * 4 + 1]
        stddev = params[i * 4 + 2]
        skewness = params[i * 4 + 3]
        if sym:
            skewness = 0
        likelihood += skew_gaussian(x, amp, mean, stddev, skewness)

    return np.sum(np.log(likelihood + 1e-10))


def calculate_aic_bic(x, data, *params, sym=False):
    """Calculate AIC and BIC manually"""
    n = len(data)
    num_components = len(params) // 4

    ll = log_likelihood(x, *params, sym=sym)

    k = num_components * 4

    aic = 2 * k - 2 * ll
    bic = np.log(n) * k - 2 * ll

    return aic, bic


def find_optimal_components(data, max_components=4, bins=100, penalty=0, callback=None, max_iter=10000, n_init=5, sym=False):
    """Find optimal number of components using AIC and BIC"""
    aic_values = []
    bic_values = []
    x_vals = np.linspace(min(data), max(data), len(data))  # Define x for fitting

    for num_components in range(1, max_components + 1):
        try:
            if callback is not None:
                callback()
            popt, _, _2, _3 = estimate_skewed_gaussian_mixture(data, num_components=num_components, bins=bins, density=False, max_iter=max_iter, n_init=n_init, sym=sym)

            aic, bic = calculate_aic_bic(x_vals, data, sym=sym, *popt)
            aic_values.append(aic + penalty * num_components**2)
            bic_values.append(bic + penalty * num_components**2)

        except Exception as e:
            print(f"Error fitting model for {num_components} components: {e}")
            continue

    # Select the optimal number of components based on AIC and BIC
    optimal_components_aic = np.argmin(aic_values) + 1
    optimal_components_bic = np.argmin(bic_values) + 1

    return optimal_components_aic, optimal_components_bic


def get_stat_moments(param_mean, sigma, alpha):
    """
        Calculates statistical mean, variance / standard deviation of skewed Gaussian

        Parameters:
            param_mean (float): pseudo-mean parameter returned by skewed Gaussian fit.
            sigma (float): sigma parameter returned by skewed Gaussian fit.
            alpha (float): skew parameter returned by skewed Gaussian fit.

        Returns:
            mean (float): true statistical mean of the skewed Gaussian distribution.
            std (float): square root of the variance of the skewed Gaussian fit.
            skew (float): statistical skewness of the skewed Gaussian fit.
        """

    delta = alpha / (np.sqrt(1 + alpha ** 2))
    mean = param_mean + sigma * delta * np.sqrt(2 / np.pi)
    variance = sigma**2 * (1 - (2 * delta**2 / np.pi))
    std = np.sqrt(variance)
    skew = ((4 - np.pi) / 2) * ((delta * np.sqrt(2/np.pi))**3 / (1 - 2*delta**2 / np.pi)**1.5)

    return mean, std, skew


MAX_ITER = 10_000
N_INIT = 5
MAX_FITS = 4




if __name__ == "__main__":
    with open('masses.msf', "rb") as file:
        rawdata = pickle.load(file)

    data = []

    for datum in rawdata:
        if 0 < datum < 1300:
            data.append(datum)

    P_OPT, P_COV, fit_func, rms_error = fit_skewed_gaussian_mixture(data, num_components='auto', bins=120, density=False, component_optimizer='bic', component_penalty=100)
