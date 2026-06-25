import pandas as pd
import matplotlib.pyplot as plt

def load_latency(csv_file):
    df = pd.read_csv(csv_file)
    return df.groupby("second")["latency"].quantile(0.99).reset_index()

def load_replicas(csv_file):
    return pd.read_csv(csv_file)

yours = load_latency("custom_results.csv")
hpa70 = load_latency("hpa70_results.csv")
hpa90 = load_latency("hpa90_results.csv")

rep_yours = load_replicas("custom_replicas.csv")
rep_hpa70 = load_replicas("hpa70_replicas.csv")
rep_hpa90 = load_replicas("hpa90_replicas.csv")

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8), sharex=True)

# ── Top: p99 latency ──────────────────────────────────────────────────────────
ax1.plot(yours["second"], yours["latency"], label="Custom Autoscaler", color="blue")
ax1.plot(hpa70["second"], hpa70["latency"], label="HPA 70%",         color="orange")
ax1.plot(hpa90["second"], hpa90["latency"], label="HPA 90%",         color="green")
ax1.axhline(0.5, color="red", linestyle="--", label="SLO (0.5s)")
ax1.set_ylabel("p99 Latency (s)")
ax1.set_title("p99 Latency and Replica Count Comparison")
ax1.legend()
ax1.grid(True, alpha=0.3)

# ── Bottom: replica count ─────────────────────────────────────────────────────
ax2.step(rep_yours["second"], rep_yours["replicas"], label="Custom Autoscaler", color="blue",   where="post")
ax2.step(rep_hpa70["second"], rep_hpa70["replicas"], label="HPA 70%",         color="orange", where="post")
ax2.step(rep_hpa90["second"], rep_hpa90["replicas"], label="HPA 90%",         color="green",  where="post")
ax2.set_ylabel("Number of Replicas (CPU cores)")
ax2.set_xlabel("Time (seconds)")
ax2.legend()
ax2.grid(True, alpha=0.3)
ax2.yaxis.set_major_locator(plt.MaxNLocator(integer=True))

plt.tight_layout()
plt.savefig("comparison.png", dpi=150)
print("Saved comparison.png")
