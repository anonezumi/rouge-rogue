# this is just some code to try and get a grasp of how the old stats system works, and eventually make a new one that makes much more sense design wise and much less sense in general.

import seaborn as sns
import matplotlib.pyplot as plt
import numpy as np

RAND_RESOLUTION = 10000
SM_RESOLUTION = 1000
u = np.linspace(0, 1, RAND_RESOLUTION)
small_lins = np.linspace(0, 1, SM_RESOLUTION)

#batting = ((1 - u) ** 0.01) * ((1 - u) ** 0.05) * ((u * u) ** 0.35) * ((u * u) ** 0.075) * (u ** 0.02)
#pitching = (u ** 0.5) * (u ** 0.4) * (u ** 0.15) * (u ** 0.1) * (u ** 0.025)
baserunning = [np.mean((s ** 0.5) * ((u * u * u * u) ** 0.1)) for s in small_lins]
#defense = [np.mean(((u * u) ** 0.2) * ((s * u * u) ** 0.1)) for s in small_lins]

# ax = sns.displot(pitching, bins=200)
sns.lineplot(baserunning)

plt.show()