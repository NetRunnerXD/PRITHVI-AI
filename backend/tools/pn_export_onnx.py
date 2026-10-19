"""Export the research PN-Net (v4 ConvLSTM, PRITHVI-AI-Research branch severe-weather-nowcast,
gpu_bundle/train_nowcast_v4.py) to ONNX for CPU inference with onnxruntime (~15 MB wheel,
no torch at runtime — fits the Render free tier). Run offline where torch is installed:

    python tools/pn_export_onnx.py --weights v4_best.pt --static static.npy --out pn_net_v4.onnx

The architecture below is a verbatim copy of the research `Net`, except the static
orography/land-sea grid is an explicit input instead of a module-level global.
Weights are NOT committed to this repo; set PN_MODEL_PATH to the exported file.
"""

from __future__ import annotations

import argparse
import json
import time

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

IN, OUT, CI = 4, 12, 6


class Cell(nn.Module):
    def __init__(s, c, h):
        super().__init__()
        s.g = nn.Conv2d(c + h, 4 * h, 3, padding=1)

    def forward(s, x, st):
        h, c = st
        i, f, o, g = torch.chunk(s.g(torch.cat([x, h], 1)), 4, 1)
        c = torch.sigmoid(f) * c + torch.sigmoid(i) * torch.tanh(g)
        h = torch.sigmoid(o) * torch.tanh(c)
        return h, c


class Net(nn.Module):
    def __init__(s, h=48):
        super().__init__()
        g = nn.GELU
        s.r = nn.Sequential(nn.Conv2d(3, h, 3, 2, 1), g(), nn.Conv2d(h, h, 3, 2, 1), g())
        s.s = nn.Sequential(nn.Conv2d(6, h // 2, 3, 2, 1), g())
        s.e = nn.Sequential(nn.Conv2d(9, h // 2, 3, 1, 1), g())
        s.n = nn.Sequential(nn.Conv2d(3, h // 2, 3, 1, 1), g())
        s.cell = Cell(2 * h, h)
        s.mix = nn.Conv2d(h + h // 2 + h // 2, 2 * h, 3, 1, 1)
        s.dec = nn.Sequential(nn.ConvTranspose2d(2 * h, h, 4, 2, 1), g(), nn.ConvTranspose2d(h, h, 4, 2, 1), g())
        s.head = nn.Conv2d(h + 2 + IN, 3 * OUT + CI, 3, 1, 1)

    def forward(s, x, sat, env, nwp, stat):
        B, _, H, W = x.shape
        st = stat.expand(B, -1, -1, -1)
        h = c = None
        for t in range(IN):
            fr = s.r(torch.cat([x[:, t : t + 1], st], 1))
            fz = torch.cat([fr, s.s(sat[:, t]), s.e(env[:, t])], 1)
            if h is None:
                h = c = torch.zeros_like(fr)
            h, c = s.cell(fz, (h, c))
        d = s.dec(s.mix(torch.cat([h, s.e(env[:, -1]), s.n(nwp)], 1)))[..., :H, :W]
        o = s.head(torch.cat([d, st, x], 1))
        return F.relu(o[:, :OUT] + x[:, -1:]), o[:, OUT : 2 * OUT], o[:, 2 * OUT : 3 * OUT], o[:, 3 * OUT :]


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--weights", required=True)
    p.add_argument("--static", required=True, help=".npy (2,H,W) orography + land-sea from the training bundle")
    p.add_argument("--out", default="pn_net_v4.onnx")
    a = p.parse_args()
    stat = torch.from_numpy(np.load(a.static).astype(np.float32))[None]
    H, W = stat.shape[-2:]
    net = Net(48)
    net.load_state_dict(torch.load(a.weights, map_location="cpu"))
    net.eval()
    x = torch.zeros(1, IN, H, W)
    sat = torch.zeros(1, IN, 6, H // 2, W // 2)
    env = torch.zeros(1, IN, 9, (H + 3) // 4, (W + 3) // 4)
    nwp = torch.zeros(1, 3, (H + 3) // 4, (W + 3) // 4)
    with torch.no_grad():
        t = time.time()
        ref = net(x, sat, env, nwp, stat)
        torch_ms = (time.time() - t) * 1000
    torch.onnx.export(
        net,
        (x, sat, env, nwp, stat),
        a.out,
        input_names=["rain_log1p", "insat", "env", "nwp", "static"],
        output_names=["rain_amt", "p_rain_logit", "p_ltg_logit", "p_ci_logit"],
        opset_version=17,
        dynamo=False,
    )
    import onnxruntime as ort

    so = ort.SessionOptions()
    so.intra_op_num_threads = 1  # Render free = 0.1 CPU; measure single-thread
    sess = ort.InferenceSession(a.out, so, providers=["CPUExecutionProvider"])
    feed = {"rain_log1p": x.numpy(), "insat": sat.numpy(), "env": env.numpy(), "nwp": nwp.numpy(), "static": stat.numpy()}
    sess.run(None, feed)
    t = time.time()
    for _ in range(3):
        out = sess.run(None, feed)
    ort_ms = (time.time() - t) * 1000 / 3
    err = float(np.max(np.abs(out[0] - ref[0].numpy())))
    import os

    print(json.dumps({"onnx": a.out, "bytes": os.path.getsize(a.out), "torch_ms": round(torch_ms), "ort_ms_1thread": round(ort_ms), "max_abs_diff": err, "grid": [H, W]}))


if __name__ == "__main__":
    main()
