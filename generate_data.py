"""Generate a synthetic appointment dataset for a fictional outpatient physical therapy clinic.

Every patient, provider, and value is invented. No real patient data is used.
No-show probability is driven by lead time, weekday, payer, reminder status,
visit type, and time of day, so the dashboard surfaces realistic patterns.
"""
import numpy as np, pandas as pd

rng = np.random.default_rng(2026)

PROVIDERS = ["Dr. Rivera, DPT", "Dr. Okafor, DPT", "Dr. Chen, DPT", "Dr. Patel, DPT"]
PAYERS = {"Medicare": .24, "BlueCross BlueShield": .22, "UnitedHealthcare": .13, "Aetna": .10, "Cigna": .07,
          "Medicaid": .12, "Workers' Comp": .06, "Self-pay": .06}
PAYER_RISK = {"Medicare": -0.25, "BlueCross BlueShield": 0.0, "UnitedHealthcare": 0.0, "Aetna": 0.0, "Cigna": 0.05,
              "Medicaid": 0.55, "Workers' Comp": -0.35, "Self-pay": 0.35}
RATE = {"Medicare": 105, "BlueCross BlueShield": 120, "UnitedHealthcare": 115, "Aetna": 118, "Cigna": 116,
        "Medicaid": 72, "Workers' Comp": 135, "Self-pay": 95}
REFERRALS = {"Orthopedic surgeon": .30, "Primary care": .25, "Direct access (self)": .15,
             "Sports medicine": .10, "Chiropractor": .08, "Hospital discharge": .07, "Website / Google": .05}
WEEKDAY_RISK = {0: 0.30, 1: 0.0, 2: -0.10, 3: 0.0, 4: 0.40}
SLOTS = [f"{h:02d}:{m:02d}" for h in range(7, 18) for m in (0, 30)]

n_patients = 1500
PATTERNS = [[0, 2, 4], [1, 3], [0, 3], [1, 4], [2, 4]]
pat = pd.DataFrame({
    "patient_id": [f"PT-{i:05d}" for i in range(1, n_patients + 1)],
    "payer": rng.choice(list(PAYERS), n_patients, p=list(PAYERS.values())),
    "referral_source": rng.choice(list(REFERRALS), n_patients, p=list(REFERRALS.values())),
    "provider": rng.choice(PROVIDERS, n_patients, p=[.3, .27, .23, .2]),
    "start": pd.to_datetime("2025-08-15") + pd.to_timedelta(rng.integers(0, 395, n_patients), "D"),
    "pattern": rng.choice(5, n_patients, p=[.32, .26, .14, .14, .14]),
    "patient_risk": rng.normal(0, 0.45, n_patients),
})

rows = []
for p in pat.itertuples():
    n_visits = int(np.clip(rng.poisson(9), 2, 20))
    d = p.start
    days = PATTERNS[p.pattern]
    for v in range(n_visits):
        while d.weekday() not in days: d += pd.Timedelta(days=1)
        if d > pd.Timestamp("2026-09-30"): break
        visit_type = "Initial evaluation" if v == 0 else ("Discharge" if v == n_visits - 1 else
                     ("Re-evaluation" if v % 8 == 0 else "Follow-up visit"))
        lead = int(rng.integers(5, 21)) if v == 0 else int(np.clip(rng.gamma(2.2, 3.5), 0, 45))
        slot = rng.choice(SLOTS)
        reminder = rng.random() < 0.78
        hour = int(slot[:2])
        logit = (-2.85 + PAYER_RISK[p.payer] + WEEKDAY_RISK[d.weekday()] + 0.045 * lead
                 + (0 if reminder else 0.75) + (0.35 if hour >= 16 else 0) + (-0.2 if hour < 9 else 0)
                 + (0.4 if visit_type == "Initial evaluation" else 0) + p.patient_risk
                 + (0.25 if d.month in (11, 12) else 0))
        p_ns = 1 / (1 + np.exp(-logit))
        r = rng.random()
        if r < p_ns: status = "No-show"
        elif r < p_ns + 0.045: status = "Late cancel"
        elif r < p_ns + 0.10: status = "Cancelled"
        else: status = "Completed"
        charge = RATE[p.payer] * (1.6 if visit_type in ("Initial evaluation", "Re-evaluation") else 1.0)
        rows.append(dict(appointment_date=d.date(), weekday=d.day_name(), time_slot=slot, patient_id=p.patient_id,
                         provider=p.provider, visit_type=visit_type, payer=p.payer, referral_source=p.referral_source,
                         lead_time_days=lead, reminder_sent="Yes" if reminder else "No", status=status,
                         expected_revenue=round(charge, 2)))
        d += pd.Timedelta(days=int(rng.choice([1, 1, 1, 4], p=[.3, .3, .25, .15])))

df = pd.DataFrame(rows).sort_values(["appointment_date", "time_slot"]).reset_index(drop=True)
df.insert(0, "appointment_id", [f"A{i:06d}" for i in range(1, len(df) + 1)])
df["appointment_date"] = pd.to_datetime(df["appointment_date"])
df = df[(df.appointment_date >= "2025-10-01") & (df.appointment_date <= "2026-09-30")]
df.to_csv("synthetic_pt_appointments.csv", index=False)
print(len(df), "appointments")
print(df.status.value_counts(normalize=True).round(3))
print(df.groupby("payer").status.apply(lambda s: (s == "No-show").mean()).round(3))
print(df.groupby("reminder_sent").status.apply(lambda s: (s == "No-show").mean()).round(3))
