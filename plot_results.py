# plot_results.py
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

def load_and_aggregate(csv_file):
    df = pd.read_csv(csv_file)
    return df.groupby("second")["latency"].quantile(0.99).reset_index()

yours  = load_and_aggregate("results.csv")
hpa70  = load_and_aggregate("results_hpa70.csv")
# hpa90  = load_and_aggregate("results_hpa90.csv")

plt.figure(figsize=(12, 5))
plt.plot(yours["second"],  yours["latency"],  label="Your Autoscaler")
plt.plot(hpa70["second"],  hpa70["latency"],  label="HPA 70%")
# plt.plot(hpa90["second"],  hpa90["latency"],  label="HPA 90%")
plt.axhline(0.5, color="red", linestyle="--", label="SLO (0.5s)")
plt.xlabel("Time (seconds)")
plt.ylabel("p99 Latency (s)")
plt.legend()
plt.tight_layout()
plt.savefig("comparison.png", dpi=150)