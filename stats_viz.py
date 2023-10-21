# this is just some code to try and get a grasp of how the old stats system works, and eventually make a new one that makes much more sense design wise and much less sense in general.

import seaborn as sns
import matplotlib.pyplot as plt
import numpy as np

RAND_RESOLUTION = 10000
SM_RESOLUTION = 1000
dist = np.linspace(np.nextafter(0, 1), 1, RAND_RESOLUTION)
sample = np.linspace(-3, 3, SM_RESOLUTION)
# lines = np.linspace(0.1, 0.9, 9)
data = np.zeros((SM_RESOLUTION, 2))

for i in range(SM_RESOLUTION):
    w = sample[i]
    if w < 0:
        w = -w
        mod_dist = np.flip(1 - (1 / ((1 / dist) + w) * (1 + w)))
    else:
        mod_dist = 1 / ((1 / dist) + w) * (1 + w)
    # data[i] = 1 - (np.searchsorted(mod_dist, lines) / RAND_RESOLUTION)
    data[i] = [np.mean(mod_dist), np.std(mod_dist)]

sns.relplot(data=data, kind="line")

plt.show()