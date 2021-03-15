from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.neighbors import KNeighborsRegressor
from mpl_toolkits import mplot3d; import matplotlib.pyplot as plt

aem_folder = '/home/sudipta/Downloads/aem_sections'
targets = pd.read_csv(Path(aem_folder).joinpath('Albers_cenozoic_interp.txt'))
line = targets[targets['line'] == 3]
line = line.sort_values(by='Y_coor', ascending=False)
line['X_coor_diff'] = line['X_coor'].diff()
line['Y_coor_diff'] = line['Y_coor'].diff()
line['delta'] = np.sqrt(line.X_coor_diff ** 2 + line.Y_coor_diff ** 2)
x_line_origin, y_line_origin = line.X_coor.values[0], line.Y_coor.values[0]
line['delta'] = line['delta'].fillna(value=0.0)

line['d'] = line['delta'].cumsum()
line = line.sort_values(by=['d'], ascending=True)

x_min, x_max = min(line.X_coor.values), max(line.X_coor.values)
y_min, y_max = min(line.Y_coor.values), max(line.Y_coor.values)

# fig = plt.figure()
# ax = plt.axes(projection='3d')
# ax.plot3D(line1.X_coor, line1.Y_coor, line1.AusAEM_DEM - line1.DEPTH, 'gray')
# ax.set_xlabel('x')
# ax.set_ylabel('y')
# ax.set_zlabel('depth')
# plt.show()


# plt.plot(line1.d.values, line1.AusAEM_DEM - line1.DEPTH); plt.show()

# verification y's
y_true = line.AusAEM_DEM - line.DEPTH

data = pd.read_csv(Path(aem_folder).joinpath('Albers_data_AEM_SB.csv'))

dis_tol = 100  # meters, distance tolerance used
# use bbox to select data only for one line
aem_data = data[
    (data.X_coor < x_max + dis_tol) & (data.X_coor > x_min - dis_tol) &
    (data.Y_coor < y_max + dis_tol) & (data.Y_coor > y_min - dis_tol)
]

aem_data = aem_data.sort_values(by='Y_coor', ascending=False)

print(data.shape, aem_data.shape)

# 1. what is tx_height - flight height?

# columns
conductivities = [c for c in data.columns if c.startswith('conduct')]
thickness = [t for t in data.columns if t.startswith('thick')]

coords = ['X_coor', 'Y_coor']
aem_conductivities = aem_data[conductivities]
aem_thickness = aem_data[thickness].cumsum(axis=1)
aem_covariate_cols = ['ceno_euc_a', 'dem_fill', 'Gravity_la', 'national_W', 'relief_ele', 'relief_mrv', 'SagaWET9ce'] \
                     + ['elevation', 'tx_height']

aem_xy_and_other_covs = aem_data[coords + aem_covariate_cols]

categorical = 'relief_mrv'

index = []
covariates_including_xyz = []

final_cols = coords + aem_covariate_cols + ['Z_coor']

for xy, c, t in zip(aem_xy_and_other_covs.head().iterrows(), aem_conductivities.head().iterrows(), aem_thickness.head().iterrows()):
    i, covariates_including_xy_ = xy
    j, cc = c
    k, tt = t
    assert i == j == k
    for ccc, ttt in zip(cc, tt):
        index.append(i)
        covariates_including_xyz_ = covariates_including_xy_.append(
            pd.Series([ttt, ccc], index=['Z_coor', 'conductivity'])
        )
        covariates_including_xyz.append(covariates_including_xyz_)

X = pd.DataFrame(covariates_including_xyz)

y_true_nn = KNeighborsRegressor()


