

import shutil
import tempfile

from scipy import linalg, ndimage


import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

from sklearn.datasets import (load_boston,
                              load_iris,
                              load_digits,
                              load_diabetes,
                              load_wine,
                              load_breast_cancer) # Bunch

from sklearn.feature_selection import (SelectKBest,
                                       SelectPercentile,
                                       SelectFromModel,
                                       chi2,
                                       mutual_info_classif,
                                       f_classif,
                                       f_regression,
                                       mutual_info_regression,
                                       VarianceThreshold)

from sklearn.feature_extraction import (FeatureHasher,
                                        grid_to_graph,
                                        DictVectorizer,
                                        hashing,
                                        image,
                                        img_to_graph,
                                        text,
                                        stop_words)

from sklearn.pipeline import (Pipeline,
                              make_pipeline,
                              FeatureUnion,
                              make_union)
#                              clone,
#                              delayed,
#                              sparse,
#                              six,
#                              Bunch, #dict like
#                              Memory,
#                              Parallel)

from sklearn.model_selection import (cross_validate,
                                     cross_val_score,
                                     cross_val_predict,
                                     check_cv,
                                     fit_grid_point,
                                     permutation_test_score,
                                     train_test_split,
                                     TimeSeriesSplit,
                                     validation_curve,
                                     KFold,
                                     StratifiedKFold,
                                     RepeatedKFold,
                                     GroupKFold,
                                     GroupShuffleSplit,
                                     ShuffleSplit,
                                     StratifiedShuffleSplit,
                                     LeaveOneOut,
                                     LeaveOneGroupOut,
                                     LeavePOut,
                                     LeavePGroupsOut,
                                     GridSearchCV,
                                     ParameterGrid,
                                     ParameterSampler,
                                     RandomizedSearchCV)
 
from sklearn.externals.joblib import (Memory,
                                      Parallel,
                                      Logger,
                                      MemorizedResult,
                                      PrintTime,
                                      backports,
                                      cpu_count,
                                      delayed,
                                      disk,
                                      dump,
                                      effective_n_jobs,
                                      format_stack,
                                      func_inspect,
                                      hash,
                                      hashing,
                                      load,
                                      logger,
                                      memory,
                                      my_exceptions,
                                      numpy_pickle,
                                      numpy_pickle_compat,
                                      numpy_pickle_utils,
                                      parallel,
                                      parallel_backend,
                                      pool,
                                      register_parallel_backend)


from sklearn.svm import (SVC, 
                         SVR)


from sklearn.cluster import FeatureAgglomeration
from sklearn.linear_model import BayesianRidge



FeatureAgglomeration?

# #############################################################################
# Generate data
n_samples = 200
size = 40  # image size
roi_size = 15
snr = 5.
np.random.seed(0)
mask = np.ones([size, size], dtype=np.bool)

coef = np.zeros((size, size))
coef[0:roi_size, 0:roi_size] = -1.
coef[-roi_size:, -roi_size:] = 1.

X = np.random.randn(n_samples, size ** 2)
for x in X:  # smooth data
    x[:] = ndimage.gaussian_filter(x.reshape(size, size), sigma=1.0).ravel()
X -= X.mean(axis=0)
X /= X.std(axis=0)

y = np.dot(X, coef.ravel())
noise = np.random.randn(y.shape[0])
noise_coef = (linalg.norm(y, 2) / np.exp(snr / 20.)) / linalg.norm(noise, 2)
y += noise_coef * noise  # add noise

# #############################################################################
# Compute the coefs of a Bayesian Ridge with GridSearch
cv = KFold(2)  # cross-validation generator for model selection
ridge = BayesianRidge()
cachedir = tempfile.mkdtemp()
mem = Memory(cachedir=cachedir, verbose=1)

# Ward agglomeration followed by BayesianRidge
connectivity = grid_to_graph(n_x=size, n_y=size)
ward = FeatureAgglomeration(n_clusters=10, connectivity=connectivity,
                            memory=mem)
clf = Pipeline([('ward', ward), ('ridge', ridge)])
# Select the optimal number of parcels with grid search
clf = GridSearchCV(clf, {'ward__n_clusters': [10, 20, 30]}, n_jobs=1, cv=cv)
clf.fit(X, y)  # set the best parameters
coef_ = clf.best_estimator_.steps[-1][1].coef_
coef_ = clf.best_estimator_.steps[0][1].inverse_transform(coef_)
coef_agglomeration_ = coef_.reshape(size, size)

# Anova univariate feature selection followed by BayesianRidge
f_regression = mem.cache(feature_selection.f_regression)  # caching function
anova = feature_selection.SelectPercentile(f_regression)
clf = Pipeline([('anova', anova), ('ridge', ridge)])
# Select the optimal percentage of features with grid search
clf = GridSearchCV(clf, {'anova__percentile': [5, 10, 20]}, cv=cv)
clf.fit(X, y)  # set the best parameters
coef_ = clf.best_estimator_.steps[-1][1].coef_
coef_ = clf.best_estimator_.steps[0][1].inverse_transform(coef_.reshape(1, -1))
coef_selection_ = coef_.reshape(size, size)

# #############################################################################
# Inverse the transformation to plot the results on an image
plt.close('all')
plt.figure(figsize=(7.3, 2.7))
plt.subplot(1, 3, 1)
plt.imshow(coef, interpolation="nearest", cmap=plt.cm.RdBu_r)
plt.title("True weights")
plt.subplot(1, 3, 2)
plt.imshow(coef_selection_, interpolation="nearest", cmap=plt.cm.RdBu_r)
plt.title("Feature Selection")
plt.subplot(1, 3, 3)
plt.imshow(coef_agglomeration_, interpolation="nearest", cmap=plt.cm.RdBu_r)
plt.title("Feature Agglomeration")
plt.subplots_adjust(0.04, 0.0, 0.98, 0.94, 0.16, 0.26)
plt.show()

# Attempt to remove the temporary cachedir, but don't worry if it fails
shutil.rmtree(cachedir, ignore_errors=True)

