"""Export the PRITHVI-Nowcast v7 final system (R2 network + PN-Blend logistic layer) to ONNX.

Source: NetRunnerXD/PRITHVI-AI-Research, branch severe-weather-nowcast,
gpu_bundle/v7/train_v7.py (`Net`, `advect`) and gpu_bundle/v7/score_v7.py (`blend_feats`,
`blend_prob`), frozen choices in results_v7/frozen_v7.json (chosen_run=r2, final=blend).

The network below is a verbatim copy of the research `Net` (mode "v7"); the static
orography/land-sea grid is a registered buffer (adaptive pooling written as its exact fixed-size equivalent for export), so it is baked into the ONNX file.
`FinalSystem` appends the frozen per-lead blend (9 features, logistic) so one ONNX call
returns amount, network probability and the final blended probability for leads 1..12.

    python tools/pn_export_onnx_v7.py --weights /path/r2/best.pt --static static.npy \
        --frozen frozen_v7.json --out models/pn_nowcast_v7.onnx \
        [--verify-bundle /workspace/v7bundle --research /path/gpu_bundle/v7 --n 6]

Inputs (batch 1, float32; masks are the training availability masks, 0 = group masked):
  x   [1,6,320,348]  log1p(mm/h) of the last 6 IMERG hours (q=round(log1p/0.02)·0.02)
  sat [1,7,160,174]  INSAT TIR1/TIR2/WV/cooling (z-scaled) + sid one-hot(2) + cooling mask
  sm  [1]            INSAT mask
  env [1,12,80,87]   GFS f000 env (6) + IFS step-24 env (6), z-scaled ((u8-128)/32)
  em  [1,2]          env masks (GFS, IFS)
  nwp [1,8,80,87]    lead-window rain log1p(mm/h): GFS windows 0-3 h..9-12 h, IFS same
  nm  [1,2]          NWP rain masks (GFS, IFS)
  mo  [1,2,80,87]    Lucas-Kanade motion (0.1° px/h)
  hr  [1,6]          sin/cos hour, sin/cos day-of-year, GFS age/24, IFS age/24
Outputs: amt [1,12,H,W] log1p(mm/h), p_net [1,12,H,W], p_blend [1,12,H,W].
Weights are NOT committed; the .onnx goes to backend/models/ (git-ignored).
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.checkpoint import checkpoint

IN, OUT, QR = 6, 12, 0.02
THR = float(np.log1p(1.0))


# ---------------------------------------------------------------- verbatim research model (train_v7.py)
# Only change: F.adaptive_avg_pool2d is written as its exact equivalent for evenly dividing sizes
# (320x348 -> 80x87 = 4x4 mean; 80x87 -> 80x87 = identity) because the ONNX tracer cannot export
# adaptive pooling after grid_sample. Same maths; parity is checked on real samples below.
def _apool(t, out, inp):
    out = tuple(int(v) for v in out); inp = tuple(int(v) for v in inp)
    if out == inp: return t
    assert inp[0] % out[0] == 0 and inp[1] % out[1] == 0, (inp, out)
    k = (inp[0] // out[0], inp[1] // out[1]); return F.avg_pool2d(t, k, k)

def cb(i, o, s=1, d=1): return nn.Sequential(nn.Conv2d(i, o, 3, s, d, dilation=d), nn.GroupNorm(8, o), nn.GELU())


class Gated(nn.Module):
    def __init__(s, i, o, stride): super().__init__(); s.f = nn.Sequential(cb(i, o, stride), cb(o, o)); s.null = nn.Parameter(torch.zeros(1, o, 1, 1))
    def forward(s, x, m): y = s.f(x); m = m[:, None, None, None].to(y.dtype); return m * y + (1 - m) * s.null.to(y.dtype)


class GRU(nn.Module):
    def __init__(s, i, h): super().__init__(); s.zr = nn.Conv2d(i + h, 2 * h, 3, 1, 1); s.c = nn.Sequential(nn.Conv2d(i + h, h, 3, 1, 2, dilation=2))
    def forward(s, x, h):
        zr = torch.sigmoid(s.zr(torch.cat([x, h], 1))); zg, rg = zr.chunk(2, 1); c = torch.tanh(s.c(torch.cat([x, rg * h], 1))); return (1 - zg) * h + zg * c


def advect(f0, mo, L):
    B, _, H, W = f0.shape; v = F.interpolate(mo, size=(H, W), mode="bilinear", align_corners=False)
    gy, gx = torch.meshgrid(torch.linspace(-1, 1, H, device=f0.device), torch.linspace(-1, 1, W, device=f0.device), indexing="ij")
    base = torch.stack([gx, gy], -1)[None].expand(B, -1, -1, -1); d = torch.stack([v[:, 0] * 2 / (W - 1), v[:, 1] * 2 / (H - 1)], -1)
    out, cur = [], f0
    for _ in range(L): cur = F.grid_sample(cur, base - d, mode="bilinear", padding_mode="zeros", align_corners=True); out.append(cur)
    return out


class Net(nn.Module):
    def __init__(s, static, mode="v7", c1=32, c2=64, c3=128):
        super().__init__(); s.mode = mode; s.register_buffer("stat", static)
        s.e1 = nn.Sequential(cb(IN + 2 + 4, c1), cb(c1, c1)); s.e2 = nn.Sequential(cb(c1, c2, 2), cb(c2, c2)); s.e3 = nn.Sequential(cb(c2, c3, 2), cb(c3, c3, 1, 2))
        s.sat = Gated(7, c2, 1)
        if mode == "r0": s.env = Gated(8, c3, 1); s.nwp = Gated(2, c3, 1); gin = 1 + OUT
        else: s.gfs = Gated(11, c3, 1); s.ifs = Gated(11, c3, 1); gin = 1 + OUT + 4
        s.gru = GRU(gin, c3); s.d2 = nn.Sequential(cb(c3 + c2, c2), cb(c2, c2)); s.d1 = nn.Sequential(cb(c2 + c1 + 1, c1), cb(c1, c1)); s.head = nn.Conv2d(c1, 2, 1)

    def forward(s, x, sat, sm, env, em, nwp, nm, mo, hr):
        B, _, H, W = x.shape; tfe = hr[:, :4, None, None].expand(-1, -1, H, W)
        h1 = s.e1(torch.cat([x, s.stat.expand(B, -1, -1, -1), tfe], 1)); h2 = s.e2(h1)
        h2 = h2 + F.interpolate(s.sat(sat, sm), size=h2.shape[-2:], mode="bilinear", align_corners=False); h3 = s.e3(h2)
        if s.mode == "r0": side = s.env(env, em) + s.nwp(nwp, nm)
        else:
            ag = lambda k: hr[:, 4 + k, None, None, None].expand(-1, 1, *env.shape[-2:])  # noqa: E731
            gm, im = em[:, 0] * nm[:, 0], em[:, 1] * nm[:, 1]
            side = s.gfs(torch.cat([env[:, :6], nwp[:, :4], ag(0)], 1), gm) + s.ifs(torch.cat([env[:, 6:], nwp[:, 4:], ag(1)], 1), im)
            nl = _apool(nwp, h3.shape[-2:], nwp.shape[-2:])
        h3 = h3 + F.interpolate(side, size=h3.shape[-2:], mode="bilinear", align_corners=False)
        adv = advect(x[:, -1:], mo, OUT); hid = h3; amt, lg = [], []
        for L in range(OUT):
            a4 = _apool(adv[L], h3.shape[-2:], (H, W)); le = F.one_hot(torch.full((B,), L, device=x.device), OUT).float()[:, :, None, None].expand(-1, -1, *h3.shape[-2:])
            gi = [a4, le]
            if s.mode == "v7":
                w = L // 3; mg = nm[:, 0, None, None, None].expand(-1, 1, *h3.shape[-2:]); mi = nm[:, 1, None, None, None].expand(-1, 1, *h3.shape[-2:])
                gi += [nl[:, w:w + 1] * mg, nl[:, 4 + w:5 + w] * mi, mg, mi]
            hid = s.gru(torch.cat([g.to(hid.dtype) for g in gi], 1), hid)

            def dec(hd, aL):
                u = F.interpolate(hd, size=h2.shape[-2:], mode="bilinear", align_corners=False); u = s.d2(torch.cat([u, h2.to(u.dtype)], 1))
                u = F.interpolate(u, size=(H, W), mode="bilinear", align_corners=False); u = s.d1(torch.cat([u, h1.to(u.dtype), aL.to(u.dtype)], 1)); return s.head(u)
            o = checkpoint(dec, hid, adv[L], use_reentrant=False) if s.training else dec(hid, adv[L])
            amt.append(F.relu(adv[L][:, 0] + o[:, 0])); lg.append(o[:, 1])
        return torch.stack(amt, 1), torch.stack(lg, 1)


# ---------------------------------------------------------------- frozen PN-Blend (score_v7.blend_feats / blend_prob)
class FinalSystem(nn.Module):
    def __init__(s, net: Net, blend: dict):
        super().__init__(); s.net = net
        W = torch.tensor([blend[str(L)]["w"] for L in range(1, OUT + 1)], dtype=torch.float32)
        B = torch.tensor([blend[str(L)]["b"] for L in range(1, OUT + 1)], dtype=torch.float32)
        MU = torch.tensor([blend[str(L)]["mu"] for L in range(1, OUT + 1)], dtype=torch.float32)
        SD = torch.tensor([blend[str(L)]["sd"] for L in range(1, OUT + 1)], dtype=torch.float32)
        s.register_buffer("bw", W); s.register_buffer("bb", B); s.register_buffer("bmu", MU); s.register_buffer("bsd", SD)

    def forward(s, x, sat, sm, env, em, nwp, nm, mo, hr):
        amt, lg = s.net(x, sat, sm, env, em, nwp, nm, mo, hr)
        pn = torch.sigmoid(lg)
        p = torch.clamp(torch.clamp(torch.round(pn * 250), 0, 250) / 250, 0.002, 0.998)  # research stores p as u8 (p*250)
        pm = torch.clamp(F.max_pool2d(p, 3, 1, 1), 0.002, 0.998)
        last = (x[:, -1:] > THR).float()
        adv = advect(last, mo, OUT)
        rf = (x > THR).float().mean((1, 2, 3))
        up = F.interpolate(nwp, scale_factor=4, mode="nearest")
        lgt = lambda a: torch.log(a / (1 - a))  # noqa: E731
        out = []
        for L in range(OUT):
            w = L // 3
            fe = [lgt(p[:, L]), lgt(pm[:, L]), last[:, 0], (adv[L][:, 0] > 0.5).float(), up[:, w] * nm[:, 0, None, None], up[:, 4 + w] * nm[:, 1, None, None],
                  rf[:, None, None].expand_as(p[:, L]), hr[:, 0, None, None].expand_as(p[:, L]), hr[:, 1, None, None].expand_as(p[:, L])]
            z = s.bb[L] + sum((fe[k] - s.bmu[L, k]) / s.bsd[L, k] * s.bw[L, k] for k in range(9))
            out.append(torch.sigmoid(z))
        return amt, pn, torch.stack(out, 1)


NAMES_IN = ["x", "sat", "sm", "env", "em", "nwp", "nm", "mo", "hr"]
NAMES_OUT = ["amt", "p_net", "p_blend"]


def build(weights: str, static: str, frozen: str) -> FinalSystem:
    st = torch.from_numpy(np.load(static).astype(np.float32))[None].clone(); st[:, 0] /= 2.0  # as infer_v7.py
    net = Net(st, "v7"); net.load_state_dict(torch.load(weights, map_location="cpu", weights_only=True)); net.eval()
    fz = json.load(open(frozen))
    assert fz["chosen_run"] == "r2" and fz["final"] == "blend", fz.get("final")
    m = FinalSystem(net, fz["blend"]); m.eval(); return m



def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--weights", required=True); p.add_argument("--static", required=True); p.add_argument("--frozen", required=True)
    p.add_argument("--out", default="models/pn_nowcast_v7.onnx")
    p.add_argument("--verify-bundle", default=""); p.add_argument("--research", default=""); p.add_argument("--n", type=int, default=6)
    a = p.parse_args()
    torch.set_num_threads(4)
    m = build(a.weights, a.static, a.frozen)
    dummy = (torch.zeros(1, 6, 320, 348), torch.zeros(1, 7, 160, 174), torch.zeros(1), torch.zeros(1, 12, 80, 87), torch.zeros(1, 2),
             torch.zeros(1, 8, 80, 87), torch.zeros(1, 2), torch.zeros(1, 2, 80, 87), torch.zeros(1, 6))
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with torch.no_grad():
        torch.onnx.export(m, dummy, a.out, input_names=NAMES_IN, output_names=NAMES_OUT, opset_version=17, dynamo=False)
    rep = {"onnx": a.out, "bytes": os.path.getsize(a.out)}
    if a.verify_bundle:
        rep["verify"] = verify(a, m)
    print(json.dumps(rep, indent=1))


def verify(a, m: FinalSystem) -> dict:
    """Real test samples: research TV.Net / score_v7.blend_prob (float64 numpy) vs ONNX."""
    import onnxruntime as ort

    sys.path.insert(0, a.research)
    import train_v7 as TV  # research module (exact batch builder)

    Z = TV.load_bundle(a.verify_bundle, mmap="r"); S, T, tt = TV.samples(Z, False)
    ids = S["test"][:: max(1, len(S["test"]) // a.n)][: a.n]
    so = ort.SessionOptions(); so.intra_op_num_threads = 1
    so.enable_cpu_mem_arena = False; so.enable_mem_pattern = False; so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_BASIC  # = app settings
    sess = ort.InferenceSession(a.out, so, providers=["CPUExecutionProvider"])
    fz = json.load(open(a.frozen)); ops = fz["ops"]["blend"]
    base = build(a.weights, a.static, a.frozen)
    ref_net = TV.Net(base.net.stat.clone(), "v7"); ref_net.load_state_dict(base.net.state_dict()); ref_net.eval()
    rows = []
    for i in ids:
        x, y = TV.make_batch(Z, tt, [i], "v7", "cpu")
        with torch.no_grad():
            amt_r, lg_r = ref_net(*x)
        pr = torch.sigmoid(lg_r).numpy()[0]
        o = sess.run(None, {k: v.numpy() for k, v in zip(NAMES_IN, x)})
        # research blend on the research-stored (u8) probabilities
        probs_row = np.clip(np.round(pr * 250), 0, 250).astype(np.uint8)
        pb_ref = np.stack([_blend_prob_ref(TV, Z, tt, i, L, probs_row, fz["blend"][str(L)]) for L in range(1, 13)])
        with torch.no_grad():
            _, _, pb_t = m(*x)  # torch FinalSystem: isolates the blend port from ONNX float error
        pb_t = pb_t.numpy()[0]
        nflip = nflip_t = 0; tot = 0; dcount = 0
        for L in range(12):
            for sc, k in (("0.1", 1), ("0.5", 5)):
                g = ops[sc][str(L + 1)]["csi"]
                a_ = _pool(o[2][0, L], k) >= g; b_ = _pool(pb_ref[L], k) >= g; c_ = _pool(pb_t[L], k) >= g
                nflip += int((a_ != b_).sum()); nflip_t += int((c_ != b_).sum()); tot += a_.size; dcount += abs(int(a_.sum()) - int(b_.sum()))
        rows.append(dict(t=T[i], max_abs_p_net_onnx_vs_torch=float(np.abs(o[1][0] - pr).max()), max_abs_amt=float(np.abs(o[0][0] - amt_r.numpy()[0]).max()),
                         max_abs_p_blend_torchport_vs_research=float(np.abs(pb_t - pb_ref).max()), max_abs_p_blend_onnx_vs_research=float(np.abs(o[2][0] - pb_ref).max()),
                         event_px_flipped_onnx=nflip, event_px_flipped_torchport=nflip_t, event_count_abs_diff=dcount, px_checked=tot))
    return dict(samples=rows, flipped_total=sum(r["event_px_flipped_onnx"] for r in rows), px_total=sum(r["px_checked"] for r in rows))


def _pool(a, k):
    a = np.asarray(a, np.float32)
    if k == 1: return a
    H, W = a.shape; return a[: H // k * k, : W // k * k].reshape(H // k, k, W // k, k).max((1, 3))


def _blend_prob_ref(TV, Z, tt, i, L, probs_row, Wl):
    """verbatim score_v7.blend_feats + blend_prob (numpy, float64)."""
    R = Z["rain"]
    p = np.clip(probs_row[L - 1].astype(np.float32) / 250, 0.002, 0.998); pt = torch.from_numpy(p)
    pm = F.max_pool2d(pt[None, None], 3, 1, 1)[0, 0].numpy().clip(0.002, 0.998)
    last = torch.from_numpy((np.asarray(R[i - 1]).astype(np.float32) * QR > THR).astype(np.float32))[None, None]
    mo = torch.from_numpy(np.asarray(Z["motion"][i]).astype(np.float32))[None]; adv = TV.advect(last, mo, L)[-1][0, 0].numpy()
    w = (L - 1) // 3; nr = np.asarray(Z["nrate"][i]).astype(np.float32) * QR; nok = Z["nrate_ok"][i]
    up = lambda a: np.repeat(np.repeat(a, 4, 0), 4, 1)  # noqa: E731
    g, f_ = up(nr[w]) * float(nok[0]), up(nr[4 + w]) * float(nok[1])
    rf = float((np.asarray(R[i - 6:i]).astype(np.float32) * QR > THR).mean()); h = tt[i].hour
    lg = lambda x: np.log(x / (1 - x))  # noqa: E731
    fe = np.stack([lg(p), lg(pm), last[0, 0].numpy(), (adv > 0.5).astype(np.float32), g, f_, np.full_like(p, rf), np.full_like(p, np.sin(2 * np.pi * h / 24)), np.full_like(p, np.cos(2 * np.pi * h / 24))])
    z = ((fe - np.array(Wl["mu"])[:, None, None]) / np.array(Wl["sd"])[:, None, None] * np.array(Wl["w"])[:, None, None]).sum(0) + Wl["b"]
    return 1 / (1 + np.exp(-z))


if __name__ == "__main__":
    main()
