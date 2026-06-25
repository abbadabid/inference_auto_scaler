import pandas as pd
import matplotlib.pyplot as plt

def load_latency(csv_file):
    df = pd.read_csv(csv_file)
    return df.groupby("second")["latency"].quantile(0.99).reset_index()

def load_replicas(csv_file):
    return pd.read_csv(csv_file)

def load_serverside(csv_file):
    df = pd.read_csv(csv_file)
    df = df[df["p99_latency"].notna()]  # drop failed samples
    return df

yours     = load_latency("custom_autoscaler_results.csv")
hpa70     = load_latency("hpa70_autoscaler_results.csv")
hpa90     = load_latency("hpa90_autoscaler_results.csv")

rep_yours = load_replicas("custom_austoscaler_replicas.csv")
rep_hpa70 = load_replicas("hpa70_autoscaler_replicas.csv")
rep_hpa90 = load_replicas("hpa90_autoscaler_replicas.csv")

ss_yours  = load_serverside("custom_autoscaler_serverside.csv")
ss_hpa70  = load_serverside("hpa70_autoscaler_serverside.csv")
ss_hpa90  = load_serverside("hpa90_autoscaler_serverside.csv")

fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(14, 12), sharex=True)

# ── Top: client-side p99 latency ─────────────────────────────────────────────
ax1.plot(yours["second"], yours["latency"], label="Custom Autoscaler", color="blue")
ax1.plot(hpa70["second"], hpa70["latency"], label="HPA 70%",           color="orange")
ax1.plot(hpa90["second"], hpa90["latency"], label="HPA 90%",           color="green")
ax1.set_ylabel("p99 Latency (s)")
ax1.set_title("Client-side p99 Latency, Server-side p99 Latency, and Replica Count")
ax1.legend()
ax1.grid(True, alpha=0.3)

# ── Middle: server-side p99 latency ──────────────────────────────────────────
ax2.plot(ss_yours["second"], ss_yours["p99_latency"], label="Custom Autoscaler", color="blue")
ax2.plot(ss_hpa70["second"], ss_hpa70["p99_latency"], label="HPA 70%",           color="orange")
ax2.plot(ss_hpa90["second"], ss_hpa90["p99_latency"], label="HPA 90%",           color="green")
ax2.axhline(0.5, color="red", linestyle="--", label="SLO (0.5s)")
ax2.set_ylabel("Server-side p99 Latency (s)")
ax2.legend()
ax2.grid(True, alpha=0.3)

# ── Bottom: replica count ─────────────────────────────────────────────────────
ax3.step(rep_yours["second"], rep_yours["replicas"], label="Custom Autoscaler", color="blue",   where="post")
ax3.step(rep_hpa70["second"], rep_hpa70["replicas"], label="HPA 70%",           color="orange", where="post")
ax3.step(rep_hpa90["second"], rep_hpa90["replicas"], label="HPA 90%",           color="green",  where="post")
ax3.set_ylabel("Number of Replicas (CPU cores)")
ax3.set_xlabel("Time (seconds)")
ax3.legend()
ax3.grid(True, alpha=0.3)
ax3.yaxis.set_major_locator(plt.MaxNLocator(integer=True))

plt.tight_layout()
plt.savefig("comparison.png", dpi=150)
print("Saved comparison.png")
