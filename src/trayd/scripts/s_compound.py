start = 40_000
avg_return_percent = 150
days_per_return = 365

contribution = 0
contribution_frequency = 30

yrs = 5
num_days = int(365 * yrs)
# um_days = 300

avg_return = avg_return_percent / 100
curr = start
for i in range(num_days):
    if i % days_per_return == 0:
        curr += curr * avg_return

    # print(curr)

    if contribution != 0 and i % contribution == 0:
        curr += contribution

#     if i % 10 == 0:
#         print(f"Day {i}: {curr}")

print()
print(f"START: ${start:.2f}")
print(f"TOTAL: ${curr:.2f}")
print(f"IMPROVE: {((curr - start) / start * 100):.2f}%")
print()
