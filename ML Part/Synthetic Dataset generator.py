import numpy as np
import pandas as pd
import random

np.random.seed(42)
random.seed(42)

N = 5000
data = []

def generate_sample(force_label=None):
    call_count = np.random.poisson(2)
    call_count = min(call_count, 15)

    is_exported = np.random.choice([0, 1], p=[0.7, 0.3])
    used_in_tests = np.random.choice([0, 1], p=[0.75, 0.25])

    dynamic_call_risk = round(np.random.beta(2, 5), 2)
    cyclomatic_complexity = np.random.randint(1, 15)
    file_depth = np.random.randint(1, 10)

    # Score calculation
    score = 0

    if call_count == 0:
        score += 2
    elif call_count <= 1:
        score += 1

    if is_exported == 0:
        score += 1

    if used_in_tests == 0:
        score += 1

    if dynamic_call_risk < 0.3:
        score += 0.5

    if cyclomatic_complexity < 5:
        score += 0.5

    if file_depth > 5:
        score += 0.5

    prob_dead = 1 / (1 + np.exp(-score))

    # Add noise
    prob_dead += np.random.normal(0, 0.15)
    prob_dead = min(max(prob_dead, 0), 1)

    label = 1 if prob_dead > 0.5 else 0

    # 🔥 FORCE BALANCING
    if force_label is not None:
        if force_label == 1:
            call_count = 0
            is_exported = 0
            used_in_tests = 0
            prob_dead = round(random.uniform(0.7, 0.98), 3)
            label = 1
        else:
            call_count = random.randint(2, 10)
            used_in_tests = 1
            prob_dead = round(random.uniform(0.02, 0.3), 3)
            label = 0

    return [
        call_count,
        is_exported,
        used_in_tests,
        dynamic_call_risk,
        cyclomatic_complexity,
        file_depth,
        prob_dead,
        label
    ]

# Generate balanced dataset
for _ in range(N // 2):
    data.append(generate_sample(force_label=1))  # dead
    data.append(generate_sample(force_label=0))  # not dead

df = pd.DataFrame(data, columns=[
    "call_count",
    "is_exported",
    "used_in_tests",
    "dynamic_call_risk",
    "cyclomatic_complexity",
    "file_depth",
    "dead_code_probability",
    "label"
])

# Shuffle dataset
df = df.sample(frac=1, random_state=42).reset_index(drop=True)

# Save
df.to_csv("dead_code_dataset.csv", index=False)

# Output
print("Dataset Shape:", df.shape)
print("\nClass Distribution:")
print(df["label"].value_counts())
print("\nSample Data:")
print(df.head())