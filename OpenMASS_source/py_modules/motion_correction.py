import numpy as np
import matplotlib.pyplot as plt
import numpy.fft as fft
from scipy.signal.windows import hamming
from scipy.signal import iirnotch, filtfilt, sosfiltfilt


def notch_filter(x, index, width, shape):
    # x = x.astype(np.complex128)
    filter_ = 0.5 * np.exp(-((1 / width) * (x - index))**shape)
    filter_base1 = 0.3 * np.exp(-((1 / width*3) * (x - index))**2)
    filter_base2 = 0.13 * np.exp(-((1 / width * 6) * (x - index)) ** 2)
    filter_base3 = 0.07 * np.exp(-((1 / width * 12) * (x - index)) ** 2)
    filter_ = filter_ + filter_base1 + filter_base2 + filter_base3
    filter_ = 1 - filter_
    return filter_


def correct_motion(movie, filter_quality, apodise=False):
    norm1 = np.max(movie)
    shape = np.shape(movie)

    spectrum = fft.fft(movie, axis=2)

    mean_fft_freq = np.mean(np.abs(spectrum), axis=(0, 1))
    half_index = shape[2] // 2
    freq1 = np.argmax(mean_fft_freq[:half_index])
    normalized_frequency1 = 2 * freq1 / shape[2]
    b1, a1 = iirnotch(normalized_frequency1, filter_quality)  # higher quality = smaller notch
    reshaped_signal = movie.reshape(-1, shape[2])
    filtered1 = np.apply_along_axis(lambda signal: filtfilt(b1, a1, signal, irlen=1000), axis=1, arr=reshaped_signal)
    filtered_signal = filtered1.reshape(shape[0], shape[1], shape[2])
    if np.argmax(np.abs(filtered_signal)) > 0.03 and apodise:
        for idx in range(1):
            filtered_signal = supress_ringing(filtered_signal)
    norm2 = np.max(filtered_signal)
    filtered_signal = filtered_signal * (norm1 / norm2)
    return filtered_signal, mean_fft_freq


def supress_ringing(movie):
    ix, iy, iz = np.unravel_index(np.argmax(np.abs(movie)), movie.shape)
    if 21 < iz < movie.shape[2] - 21:
        wavelet = movie[ix, iy, iz-20:iz+20]
        wavelet = wavelet / np.sum(np.abs(wavelet)) * -1
        reshaped_signal = movie.reshape(-1, movie.shape[2])
        filtered = np.apply_along_axis(lambda signal: np.convolve(signal, wavelet, mode='same'), axis=1, arr=reshaped_signal)
        filtered_signal = filtered.reshape(movie.shape[0], movie.shape[1], movie.shape[2])
        return filtered_signal
    else:
        print('Failed to create apodisation function from data due to event proximity to signal edge.')
        return movie


def correct_motion_old(movie, size=20, filter_shape=4):
    norm1 = np.max(movie)
    shape = np.shape(movie)

    spectrum = fft.fft(movie, axis=2)

    mean_fft_freq = np.mean(np.abs(spectrum), axis=(0, 1))
    half_index = shape[2] // 2
    freq1 = np.argmax(mean_fft_freq[:half_index])
    freq2 = np.argmax(mean_fft_freq[half_index:]) + np.shape(mean_fft_freq[:half_index])[0]

    axis = np.arange(shape[2])
    dual_notch = notch_filter(axis, freq1, size, filter_shape) * notch_filter(axis, freq2, size, filter_shape)
    assert np.max(dual_notch) < 1.01 and np.min(dual_notch) > -0.01, "Invalid notch filter shape. function exploded."
    dual_notch = dual_notch[np.newaxis, np.newaxis, :]
    dual_notch = dual_notch.repeat(shape[0], axis=0).repeat(shape[1], axis=1)
    window = hamming(shape[2])
    window = window[np.newaxis, np.newaxis, :]
    window = window.repeat(shape[0], axis=0).repeat(shape[1], axis=1)

    spectrum = spectrum * dual_notch
    spectrum = fft.fftshift(spectrum)
    spectrum = spectrum * window

    processed = np.real(fft.ifft(fft.ifftshift(spectrum)))
    norm2 = np.max(processed)

    processed = processed * (norm1 / norm2)

    # plt.plot(mean_fft_freq)
    # plt.show()
    # plt.plot(dual_notch[0, 0, :])
    # plt.show()
    # plt.plot(spectrum[12, 126, :])
    # plt.show()
    # plt.imshow(processed[:, :, 1085], cmap='gray', vmin=-0.015, vmax=0.015)
    # plt.show()

    return processed

