import matplotlib.pyplot as plt
import numpy as np
import cv2
import numba
from numba import jit, njit
from typing import Callable



@jit(parallel=True)
def gauss(x_size, y_size, x0, y0, sigma_x, sigma_y, A, mode="depr", maximum=2):
    gaussian = np.zeros((y_size, x_size, 3))
    for x in numba.prange(x_size):
        for y in numba.prange(y_size):
            num1 = (x - x0)**2
            num2 = (y - y0)**2
            den1 = 2 * (sigma_x**2)
            den2 = 2 * (sigma_y**2)
            if mode == "depr":
                gaussian[y][x][0] = maximum - (A*np.exp(-(num1/den1 + num2/den2)))
                gaussian[y][x][1] = gaussian[y][x][0]
                gaussian[y][x][2] = gaussian[y][x][0]
            elif mode == "protr":
                gaussian[y][x][0] = A*np.exp(-(num1/den1 + num2/den2))
    return gaussian


# old version backup in case new fails
# def ratiometric_median(array: np.ndarray, result: np.ndarray, avg: int, length: int, callback: Callable):
#     shape = np.shape(array)
#     new_array = np.zeros(shape=(shape[0], shape[1], shape[2]+avg*2))
#     new_array[:, :, avg:shape[2]+avg] = array[:, :, :]
#     new_array[:, :, :avg] = array[:, :, :avg]
#     new_array[:, :, shape[2]+avg:] = array[:, :, -avg:]
#     array = new_array
#     # for idx in range(avg):
#     #     array[:, :, idx] = np.copy(array[:, :, avg*2+1+idx])
#     #     array[:, :, idx+length+avg] = np.copy(array[:, :, length+idx])
#     shape = np.shape(array)
#     length = shape[2]
#     for frame in range(avg+1, length - avg - 1):
#         frame_result = get_median(array[:, :, frame - avg:frame + avg], avg, shape)
#         result[:, :, frame-avg-1] = frame_result
#         callback(frame, length, avg)
#     return result


def ratiometric_median(array: np.ndarray, result: np.ndarray, avg: int, length: int, callback: Callable):
    shape = np.shape(array)
    for frame in range(shape[2]):
        zmin = frame - avg
        if zmin < 0:
            zmin = 0
        zmax = frame + avg
        if zmax > length - 1:
            zmax = length - 1
        #print(zmin, zmax)
        median = get_median(array[:, :, zmin:zmax], avg, shape)
        result[:, :, frame] = array[:, :, frame] / median - 1
        status = callback(frame, length, avg)
        if not status:
            break
    return result


def ratiometric_median_old(array: np.ndarray, result: np.ndarray, avg: int, length: int, callback: Callable):
    shape = np.shape(array)
    for frame in range(shape[2]):
        if frame - avg < 0:
            init_index = 0
        else:
            init_index = frame - avg
        section = array[:, :, init_index:frame + avg]
        print(frame, np.shape(section))
        median = get_median(section, avg, shape)
        result[:, :, frame] = array[:, :, frame] / median - 1
        status = callback(frame, length, avg)
        if not status:
            break
    return result


@njit(parallel=True)
def get_median(array: np.ndarray, avg: int, shape: tuple):
    result = np.zeros(shape=shape[:2])
    for x in numba.prange(shape[0]):
        for y in numba.prange(shape[1]):
            median = np.median(array[x, y, :])
            result[x, y] = median
    return result


# old backup
# @njit(parallel=True)
# def get_median(array: np.ndarray, avg: int, shape: tuple):
#     result = np.zeros(shape=shape[:2])
#     for x in numba.prange(shape[0]):
#         for y in numba.prange(shape[1]):
#             median = np.median(array[x, y, :])
#             result[x, y] = array[x, y, avg] / median - 1
#     return result


def low_pass(tif_img, powr, filter=True):
    conv = cv2.filter2D(tif_img, -1, large_filter, borderType=2)
    m = conv.max()
    conv = conv**powr
    conv = conv / conv.max()
    conv = conv * m
    low_pass_result = tif_img - conv
    return low_pass_result


def normal_truncate(matrix):
    for y in range(len(matrix)):
        for x in range(len(matrix[0])):
            if matrix[y][x] > 1:
                matrix[y][x] = 1

    return matrix


def make_valid(grid):
    for y in range(len(grid)):
        for x in range(len(grid[0])):
            try:
                test = int(grid[x][y])
            except ValueError:
                grid[x][y] = 0
    return grid


large_filter = gauss(129, 129, 64, 64, 32, 32, 1, mode="protr")[:, :, 0]
large_filter = large_filter / np.sum(large_filter)

kernel = gauss(7, 7, 3, 3, 1.3, 1.3, 1.1, mode="protr")[:, :, 0] + (np.ones((7, 7)) * 0.0)
kernel = normal_truncate(kernel)


