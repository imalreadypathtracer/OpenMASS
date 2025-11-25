import matplotlib.pyplot as plt
import numpy as np
from scipy.ndimage import maximum_filter, label, center_of_mass
from scipy.optimize import curve_fit
import easygui
from PIL import Image
import tifffile
import time
from numba import jit, njit
from scipy.spatial import cKDTree


@njit
def gaussian_2d(xy, x0, y0, sigma_x, sigma_y, amplitude, offset):
    """
    2D Gaussian function for curve fitting.
    """
    x, y = xy
    return offset + amplitude * np.exp(
        -(((x - x0) ** 2) / (2 * sigma_x ** 2) + ((y - y0) ** 2) / (2 * sigma_y ** 2))
    ).ravel()


def fit_gaussian(coord, image):
    """
    Fit a 2D Gaussian to a subregion of the image around a given coordinate.
    """
    y0, x0 = coord

    # 11x11 region around the peak
    y_min, y_max = max(0, y0 - 5), min(image.shape[0], y0 + 6)
    x_min, x_max = max(0, x0 - 5), min(image.shape[1], x0 + 6)
    sub_image = image[y_min:y_max, x_min:x_max]
    y, x = np.mgrid[y_min:y_max, x_min:x_max]
    x_flat, y_flat = x.ravel(), y.ravel()
    sub_image_flat = sub_image.ravel()
    # crude guess
    amplitude = sub_image.max() - sub_image.min()
    offset = sub_image.min()
    initial_guess = (x0, y0, 1, 1, amplitude, offset)

    try:
        popt, _ = curve_fit(gaussian_2d, (x_flat, y_flat), sub_image_flat, p0=initial_guess, maxfev=200)
        return popt
    except RuntimeError:
        return None  # Return None if the fit fails


def detect_and_fit_gaussian_optimized(image, threshold):
    """
    Detect local maxima and fit 2D Gaussians in a single process.

    Parameters:
        image (numpy.ndarray): 2D image array to process.
        threshold (float): Intensity threshold for detecting peaks.

    Returns:
        List of Gaussian fit parameters for each detected molecule.
    """
    # max filter
    local_max = maximum_filter(image, size=3) == image
    peaks = (image > threshold) & local_max
    labeled_peaks, num_features = label(peaks)
    # centroids
    peak_coords = center_of_mass(image, labeled_peaks, range(1, num_features + 1))
    peak_coords = np.array(peak_coords, dtype=int)

    fit_results = []
    for coord in peak_coords:
        fit_result = fit_gaussian(coord, image)
        if fit_result is not None:
            fit_results.append(fit_result)

    # x, y, sigma_x, sigma_y, amplitude, offset
    return fit_results


def filter_close_points(coords, threshold):
    if len(coords) < 2:
        return set()

    tree = cKDTree(coords)
    pairs = tree.query_pairs(r=threshold)

    to_reject = set()
    for idx1, idx2 in pairs:
        to_reject.add(idx1)
        to_reject.add(idx2)

    return to_reject


def filter_results(fits, imgx, imgy, min_sigma, max_sigma, ecc_thresh, min_dist):
    fits = list(fits)
    filtered_list = []
    for idx, fit in enumerate(fits):
        if 2 < fit[0] < imgy - 3 and 2 < fit[1] < imgx - 3:
            if min_sigma < fit[2] < max_sigma and min_sigma < fit[3] < max_sigma:
                if not (fit[2] / fit[3] < ecc_thresh or fit[3] / fit[2] < ecc_thresh):
                    filtered_list.append(fit)
    coords = [[c[0], c[1]] for c in filtered_list]
    reject_indices = filter_close_points(coords, min_dist)
    final_events = [fit for idx, fit in enumerate(filtered_list) if idx not in reject_indices]
    return final_events


def load_data():
    path = easygui.fileopenbox(msg="Open Mass Photometry '.tiff' file.", filetypes=['*.tiff', '*.tif'], default='N://*.tiff')
    if path:
        raw_tif = Image.open(path)
        print("TIF file shape:", np.shape(raw_tif))
        h, w = np.shape(raw_tif)
        tif_array = np.zeros((h, w, raw_tif.n_frames), dtype='float32')
        for index in range(raw_tif.n_frames):
            raw_tif.seek(index)
            tif_array[:, :, index] = np.array(raw_tif)

        return tif_array.astype(np.float32)


def save_tif(movie):
    path = easygui.filesavebox(msg="Open Mass Photometry '.tiff' file.", filetypes=['*.tiff', '*.tif'], default='N://*.tiff')
    print(movie.shape)
    if path:
        print(np.shape(movie))
        shape = np.shape(movie)
        final_movie = np.zeros(shape=(shape[2], shape[0], shape[1]))
        for idx in range(shape[2]):
            final_movie[idx, :, :] = movie[:, :, idx]
        final_movie = final_movie.astype('float32')
        with tifffile.TiffWriter(path) as tif:
            tif.write(final_movie)


def ratiometric(movie, avg=5):
    shape = np.shape(movie)
    length = shape[2]
    result = np.zeros((shape[0], shape[1], shape[2] - avg * 2 + 1))
    for frame in range(length - avg * 2 + 1):

        win1 = np.zeros((shape[0], shape[1]))
        for add in range(avg):
            win1 = win1 + movie[:, :, frame + add]
        win1 = win1 / avg
        win1 = win1 / np.mean(win1)

        win2 = np.zeros((shape[0], shape[1]))
        for add in range(avg):
            win2 = win2 + movie[:, :, frame + add + avg]
        win2 = win2 / avg
        win2 = win2 / np.mean(win2)

        result[:, :, frame] = win2 / win1 - 1
        if frame % 100 == 0:
            print(f"{round(100 * frame / length, 1)}%")
    return result


if __name__ == '__main__':


    movie = load_data()
    movie = ratiometric(movie[:, :, :500])


    image = movie[:, :, 100:200]
    image = np.abs(np.clip(image, -100, 0))
    image1 = np.max(image, axis=2)
    image2 = np.mean(image, axis=2)
    image = (image1 + image2) / 2
    h, w = np.shape(image)
    plt.imshow(image, cmap='gray')
    plt.show()

    threshold = 0.001  # Adjust as per your image data
    results = detect_and_fit_gaussian_optimized(image, threshold)
    t = time.time()
    results = detect_and_fit_gaussian_optimized(image, threshold)
    results = filter_results(results, w, h, 0.5, 1.5, 0.7, 4)
    print(time.time() - t)
    results = list(results)
    print(len(results))

    coords = [[r[0], r[1]] for r in results]

    plt.imshow(image, cmap='inferno')
    for idx in range(len(coords)):
        # print(coords[idx])
        if 0 < coords[idx][0] < 128 and 0 < coords[idx][1] < 128:
            plt.plot([coords[idx][0], coords[idx][0]], [coords[idx][1], coords[idx][1]], markersize=2, marker='o', color='#007fff')
    plt.show()

    # Print results
    # for fit in results:
    #     print(f"Gaussian Fit Parameters: {fit}")