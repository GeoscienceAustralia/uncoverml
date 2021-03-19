import logging
from pathlib import Path
from typing import List
import numpy as np
import pandas as pd
from sklearn.neighbors import KDTree
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.neighbors import KNeighborsRegressor
from sklearn.model_selection import RandomizedSearchCV
from mpl_toolkits import mplot3d; import matplotlib.pyplot as plt

logging.basicConfig(level=logging.INFO)
log = logging.getLogger()

aem_folder = '/home/sudipta/Downloads/aem_sections'
log.info("reading interp data...")
targets = pd.read_csv(Path(aem_folder).joinpath('Albers_cenozoic_interp.txt'))
line = targets[targets['Type'] != 'WITHIN_Cenozoic']
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
# 1 there are two typesof CEN-B lines

# verification y's
# y_true = line.DEPTH
line = line.rename(columns={'DEPTH': 'Z_coor'})
threed_coords = ['X_coor', 'Y_coor', 'Z_coor']
line_required = line[threed_coords]

log.info("reading covariates")
data = pd.read_csv(Path(aem_folder).joinpath('Albers_data_AEM_SB.csv'))

dis_tol = 100  # meters, distance tolerance used
# use bbox to select data only for one line
aem_data = data[
    (data.X_coor < x_max + dis_tol) & (data.X_coor > x_min - dis_tol) &
    (data.Y_coor < y_max + dis_tol) & (data.Y_coor > y_min - dis_tol)
]

aem_data = aem_data.sort_values(by='Y_coor', ascending=False)

log.info(f"Covaraiates data size: {data.shape}, ineterp data size: {line.shape}")

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

# categorical = 'relief_mrv'
covariate_cols_without_xyz = aem_covariate_cols + ['conductivity']

index = []
covariates_including_xyz = []

final_cols = coords + aem_covariate_cols + ['Z_coor']

# build a tree from the interpretation points
tree = KDTree(line_required)
radius = 500


def weighted_target(x: np.ndarray):
    ind, dist = tree.query_radius(x, r=radius, return_distance=True)
    ind, dist = ind[0], dist[0]
    dist += 1e-6  # add just in case of we have a zero distance
    if len(dist):
        df = line_required.iloc[ind]
        weighted_depth = np.sum(df.Z_coor * (1/dist) ** 2) / np.sum((1/dist) ** 2)
        return weighted_depth
    else:
        return None


def convert_to_xy():
    target_depths = []
    for xy, c, t in zip(aem_xy_and_other_covs.iterrows(), aem_conductivities.iterrows(), aem_thickness.iterrows()):
        i, covariates_including_xy_ = xy
        j, cc = c
        k, tt = t
        assert i == j == k
        for ccc, ttt in zip(cc, tt):
            index.append(i)

            covariates_including_xyz_ = covariates_including_xy_.append(
                pd.Series([ttt, ccc], index=['Z_coor', 'conductivity'])
            )
            x_y_z = covariates_including_xyz_[threed_coords].values.reshape(1, -1)

            y = weighted_target(x_y_z)
            if y is not None:
                covariates_including_xyz.append(covariates_including_xyz_)
                target_depths.append(y)
    X = pd.DataFrame(covariates_including_xyz)
    y = pd.Series(target_depths, name='target')
    return {'covariates': X, 'targets': y}

import pickle
if not Path('covariates_targets.data').exists():
    data = convert_to_xy()
    pickle.dump(data, open('covariates_targets.data', 'wb'))
else:
    data = pickle.load(open('covariates_targets.data', 'rb'))

X = data['covariates']
print(X.columns)
X = X[covariate_cols_without_xyz]  # don't use x, y, z values in model
print(X.columns)
y = data['targets']



log.info("assembled covariates and targets")

log.info("tuning model params ....")

rf = GradientBoostingRegressor()


from sklearn.model_selection import cross_val_score, train_test_split
from skopt.space import Real, Integer
from skopt import BayesSearchCV

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.33, random_state=42)

n_features = X.shape[1]

space = {'max_depth': Integer(1, 15),
         'learning_rate': Real(10 ** -5, 10 ** 0, prior="log-uniform"),
         'max_features': Integer(1, n_features),
         'min_samples_split': Integer(2, 100),
         'min_samples_leaf': Integer(1, 100),
         'n_estimators': Integer(20, 200),
}

reg = GradientBoostingRegressor(n_estimators=50, random_state=0)

searchcv = BayesSearchCV(
    reg,
    search_spaces=space,
    n_iter=60,
    cv=3,
    verbose=1000,
    n_points=12,
    n_jobs=4,
)

# callback handler
def on_step(optim_result):
    score = searchcv.best_score_
    print("best score: %s" % score)
    if score >= 0.98:
        print('Interrupting!')
        return True

searchcv.fit(X_train, y_train, callback=on_step)
searchcv.score(X_test, y_test)
import IPython; IPython.embed(); import sys; sys.exit()