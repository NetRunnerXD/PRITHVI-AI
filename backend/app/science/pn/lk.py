"""Dense Lucas-Kanade motion — a minimal vendored copy of pysteps.motion.dense_lucaskanade with the
defaults used to build the v7 research bundle (fd shitomasi buffer_mask=5, idwinterp2d, outliers 3σ/30,
opening 3, decluster 20). Vendored so the app only needs OpenCV + SciPy: importing pysteps costs
~160 MB of RAM, too much next to the model on a small instance. Parity with pysteps is checked in
tests (bit-identical on real bundle hours).

pysteps is © the pysteps developers, BSD 3-Clause licence (https://github.com/pySTEPS/pysteps).
"""

from __future__ import annotations

import numpy as np
from numpy.ma.core import MaskedArray


def _ma(img):
    if not isinstance(img, MaskedArray):
        img = np.ma.masked_invalid(img)
    np.ma.set_fill_value(img, img.min())
    return img


def morph_opening(input_image, thr, n):
    import cv2

    input_image = input_image.copy()
    to_ndarray = False
    if not isinstance(input_image, MaskedArray):
        to_ndarray = True
        input_image = np.ma.masked_invalid(input_image)
    np.ma.set_fill_value(input_image, input_image.min())
    field_bin = np.ndarray.astype(input_image.filled() > thr, "uint8")
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (n, n))
    field_bin_out = cv2.morphologyEx(field_bin, cv2.MORPH_OPEN, kernel)
    mask = field_bin - field_bin_out > 0
    input_image[mask] = np.nanmin(input_image)
    if to_ndarray:
        input_image = np.array(input_image)
    return input_image


def shitomasi(input_image, max_corners=1000, quality_level=0.01, min_distance=10, block_size=5, buffer_mask=5, use_harris=False, k=0.04):
    import cv2

    input_image = _ma(input_image.copy())
    mask = np.ma.getmaskarray(input_image).astype("uint8")
    if buffer_mask > 0:
        mask = cv2.dilate(mask, np.ones((int(buffer_mask), int(buffer_mask)), np.uint8), 1)
        input_image[mask] = np.ma.masked
    im_min = input_image.min(); im_max = input_image.max()
    if im_max - im_min > 1e-08:
        input_image = (input_image.filled() - im_min) / (im_max - im_min) * 255
    else:
        input_image = input_image.filled() - im_min
    input_image = np.ndarray.astype(input_image, "uint8")
    mask = ~mask & 1
    points = cv2.goodFeaturesToTrack(input_image, mask=mask, maxCorners=max_corners, qualityLevel=quality_level, minDistance=min_distance,
                                     blockSize=block_size, useHarrisDetector=use_harris, k=k)
    return np.empty(shape=(0, 2)) if points is None else points[:, 0, :]


def track_features(prvs_image, next_image, points, winsize=(50, 50), nr_levels=3, criteria=(3, 10, 0), flags=0, min_eig_thr=0.0001):
    import cv2

    prvs_img = _ma(prvs_image.copy()); next_img = _ma(next_image.copy()); p0 = np.copy(points)
    im_min = prvs_img.min(); im_max = prvs_img.max()
    prvs_img = (prvs_img.filled() - im_min) / (im_max - im_min) * 255 if im_max - im_min > 1e-08 else prvs_img.filled() - im_min
    im_min = next_img.min(); im_max = next_img.max()
    next_img = (next_img.filled() - im_min) / (im_max - im_min) * 255 if im_max - im_min > 1e-08 else next_img.filled() - im_min
    prvs_img = np.ndarray.astype(prvs_img, "uint8"); next_img = np.ndarray.astype(next_img, "uint8")
    p1, st, __ = cv2.calcOpticalFlowPyrLK(prvs_img, next_img, p0, None, winSize=winsize, maxLevel=nr_levels, criteria=criteria, flags=flags, minEigThreshold=min_eig_thr)
    st = np.atleast_1d(st.squeeze()) == 1
    if np.any(st):
        p1 = p1[st, :]; p0 = p0[st, :]
        return p0, p1 - p0
    return np.empty(shape=(0, 2)), np.empty(shape=(0, 2))


def detect_outliers(input_array, thr, coord, k):
    import scipy.spatial

    input_array = np.copy(input_array)
    nsamples = input_array.shape[0]
    if nsamples < 2:
        return np.zeros(nsamples, dtype=bool)
    coord = np.copy(coord)
    k = np.min((nsamples, k + 1))
    tree = scipy.spatial.cKDTree(coord)
    __, inds = tree.query(coord, k=k)
    outliers = np.empty(shape=0, dtype=bool)
    for i in range(inds.shape[0]):
        thisdata = input_array[i, :]
        neighbours = input_array[inds[i, 1:], :].copy()
        thiszdata = thisdata - np.mean(neighbours, axis=0)
        neighbours = neighbours - np.mean(neighbours, axis=0)
        V = np.cov(neighbours.T)
        try:
            VI = np.linalg.inv(V)
            MD = np.sqrt(np.dot(np.dot(thiszdata, VI), thiszdata.T))
        except np.linalg.LinAlgError:
            MD = 0
        outliers = np.append(outliers, MD > thr)
    return outliers


def decluster(coord, input_array, scale, min_samples=1):
    coord = np.copy(coord); input_array = np.copy(input_array); nvar = input_array.shape[1]
    scale = float(scale)
    coord_ = np.floor(coord / scale)
    ucoord_ = np.unique(coord_, axis=0)
    dinput = np.empty(shape=(0, nvar)); dcoord = np.empty(shape=(0, coord.shape[1]))
    for i in range(ucoord_.shape[0]):
        idx = np.all(coord_ == ucoord_[i, :], axis=1)
        if np.sum(idx) >= min_samples:
            dinput = np.append(dinput, np.median(input_array[idx, :], axis=0)[None, :], axis=0)
            dcoord = np.append(dcoord, np.median(coord[idx, :], axis=0)[None, :], axis=0)
    return dcoord, dinput


def _idw(xy_coord, values, xgrid, ygrid, tree, power=0.5, k=20, dist_offset=0.5):
    nvar = values.shape[1]; npoints = values.shape[0]
    xgridv, ygridv = np.meshgrid(xgrid, ygrid)
    gridv = np.column_stack((xgridv.ravel(), ygridv.ravel()))
    k = int(np.min((k, npoints)))
    dist, inds = tree.query(gridv, k=k)
    if dist.ndim == 1:
        dist = dist[..., None]; inds = inds[..., None]
    x_res = np.gradient(xgrid); y_res = np.gradient(ygrid)
    mean_res = np.mean(np.abs([x_res.mean(), y_res.mean()]))
    dist /= mean_res
    dist += dist_offset
    weights = 1 / np.power(dist, power)
    weights = weights / np.sum(weights, axis=1, keepdims=True)
    out = np.sum(values[inds, :] * weights[..., None], axis=1).reshape(ygrid.size, xgrid.size, nvar)
    return np.moveaxis(out, -1, 0).squeeze()


def idwinterp2d(xy_coord, values, xgrid, ygrid, nchunks=4):
    """pysteps prepare_interpolator(nchunks=4) + idwinterp2d (2x2 grid chunks, one cached KD-tree)."""
    from scipy.spatial import cKDTree

    values = values.copy(); xy_coord = xy_coord.copy(); nv = values.shape[1]; shape = (ygrid.size, xgrid.size)
    if values.shape[0] == 1:
        out = np.ones((nv,) + shape)
        for n, v in enumerate(values[0, ...]):
            out[n, ...] *= v
        return out.squeeze()
    if values.max() == values.min():
        return np.ones((nv,) + shape) * values.ravel()[0]
    nc = int(nchunks ** 0.5)
    sx = [x for x in np.array_split(xgrid, nc) if x.size > 0]; sy = [y for y in np.array_split(ygrid, nc) if y.size > 0]
    tree = cKDTree(xy_coord)
    out = np.zeros((nv,) + shape); ix = 0
    for gx in sx:
        iy = 0
        for gy in sy:
            out[:, iy:iy + gy.size, ix:ix + gx.size] = _idw(xy_coord, values, gx, gy, tree)
            iy += gy.size
        ix += gx.size
    return out.squeeze()


def dense_lucaskanade(input_images, buffer_mask=5, nr_std_outlier=3, k_outlier=30, size_opening=3, decl_scale=20):
    input_images = input_images.copy()
    if input_images.ndim != 3 or input_images.shape[0] < 2:
        raise ValueError("need [n>=2, H, W] frames")
    domain_size = (input_images.shape[1], input_images.shape[2])
    xy = np.empty(shape=(0, 2)); uv = np.empty(shape=(0, 2))
    for n in range(input_images.shape[0] - 1):
        prvs_img = _ma(input_images[n].copy()); next_img = _ma(input_images[n + 1].copy())
        if size_opening > 0:
            prvs_img = morph_opening(prvs_img, prvs_img.min(), size_opening)
            next_img = morph_opening(next_img, next_img.min(), size_opening)
        points = shitomasi(prvs_img, buffer_mask=buffer_mask).astype(np.float32)
        if points.shape[0] == 0:
            continue
        xy_, uv_ = track_features(prvs_img, next_img, points)
        if xy_.shape[0] == 0:
            continue
        xy = np.append(xy, xy_, axis=0); uv = np.append(uv, uv_, axis=0)
    if xy.shape[0] == 0:
        return np.zeros((2,) + domain_size)
    outliers = detect_outliers(uv, nr_std_outlier, xy, k_outlier)
    xy = xy[~outliers, :]; uv = uv[~outliers, :]
    if decl_scale > 1:
        xy, uv = decluster(xy, uv, decl_scale, 1)
    if xy.shape[0] == 0:
        return np.zeros((2,) + domain_size)
    return idwinterp2d(xy, uv, np.arange(domain_size[1]), np.arange(domain_size[0]))
