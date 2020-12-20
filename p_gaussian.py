import numpy as np
from math import exp
import itertools
import random

# https://newton.cx/~peter/2014/03/elementary-gaussian-processes-in-python/ for much of the gaussian code.

class PredictionEngine():
    '''Predicts next recommended investigation point, given previously sampled data.

    pred = prediction_engine()
    pred.append([1,2,3], 4) # Add one four-dimensional data point
    prediction_x = pred.determine_max() # x coordinates at the highest-predicted point, maximizing exploration and exploitation'''

    def __init__(self):
        self.x_known = None
        self.y_known = None

    def append(self, x_values, y_value):
        '''Add x_values (N x 1) and y_value (1 x 1) to the engine'''
        if self.x_known is None:
            self.x_known = np.asarray([x_values])
            self.y_known = np.asarray([y_value])
        else:
            self.x_known = np.append(self.x_known, [x_values], axis=0)
            self.y_known = np.append(self.y_known, [y_value], axis=0)

    def determine_max(self):
        '''Sample within the available space (0 to 1 in each dimension for my case) and return the highest predicted point'''  

        # Determine sample points. Currently samples a random point from the multi-dimensional grid with each dimension having 10 divisions.
        # TODO: Latin Hypercube Sampling would reduce computation, allowing a higher n_sample_points for the same effort.
        n_dimensions = len(self.x_known[0])
        n_sample_points = 10
        samples = [[x/n_sample_points + 0.1*random.random() for x in range(0,n_sample_points)] for _ in range(n_dimensions)]
        prediction_points = list(itertools.product(*samples))

        # Calculate major parameters
        # For the following, N is the number of data points and M is the number of sample points
        # big_r (N x N) is the correlation matrix - correlations between each data point and each data point (again)
        # NOTE: big_r is what the original EGO paper called the "covariance matrix" and the source above calls "cov"
        # NOTE: noise_scale_vector (second argument to calc_big_r) depends on the application. The value I use in this code is arbitrary.
        big_r = self.calc_big_r(self.x_known,
                                1e-9 * np.ones(shape=(len(self.x_known),1)))
        # small_r (N x M) is the correlation array - correlations between each data point and each sample point
        # NOTE: small_r is what the original EGO paper calls the source above's "di_cov"
        small_r = self.calc_small_r(prediction_points)
        # weight_array (N x M) are the weightings given to each data y value, for each sample point
        weight_array = np.dot(np.linalg.inv(big_r), small_r)
        # y_estimates (M x 1) are the predicted y value, for each sample point
        y_estimates = np.dot(weight_array.T, self.y_known)

        # auto-covariance (M x M) - it's a bunch of 1s for math reasons
        # interpolant_variant (M x M) - intermediate step for math reasons
        # interp_u (M x 1) - a prediction of the variance at each sample point, given the distance from nearby data points
        auto_covariance = np.ones(shape=(len(prediction_points), len(prediction_points)))
        interpolant_variance = auto_covariance - np.dot(small_r.T, weight_array)
        interp_u = np.sqrt (np.diag (interpolant_variance))

        # interp_max_pos (1 x 1) is the index of the point which maximizes exploitation (y_estimates) + exploration (interp_u)
        # In more detail, the y_estimates reflect where the highest point is based on the data we have
        #               while interp_u reflects where we might find our model to be wrong.
        interp_max_pos = np.argmax(y_estimates + interp_u)

        return prediction_points[interp_max_pos], y_estimates[interp_max_pos]

    def kernel(self, x_values_1, x_values_2):
        '''Square-exponential kernel for indetermininate number of dimensions.'''
        internal_sum = sum([(a-b)**2 for a,b in zip(x_values_1, x_values_2)])
        # NOTE: This is adapted for multiple dimensions from the following one-dimensional square-exponential kernel:
        #        sqexp_kernel = a * exp(-0.5*(s/r)**2), where a=1 and r=1 in the source linked above.
        #       For other applications than my use of this in Halite, you'd want to retain "r" as a scale between
        #        the dimensions - if one dimension is a lot wider than the others, you'd care less about changes in
        #        that dimension.
        return exp(-0.5*internal_sum)

    def calc_big_r(self, x_known, noise_scale_vector):
        '''Gaussian process covariance matrix: Apply the kernel to the matrix of separations (r[i,j] = x[j] - x[i]) and add noise_scale_vector along the diagonal.'''
        matrix_of_separations = np.asarray([[self.kernel(i,j) for i in x_known] for j in x_known])
        return matrix_of_separations + np.diag (noise_scale_vector)

    def calc_small_r(self, x_predictions):
        '''Covariance array between known x's and interpolation_x's.'''
        return np.asarray([[self.kernel(i,j) for i in x_predictions] for j in self.x_known])

if __name__ == "__main__":
    predictor = PredictionEngine()

    real_func = lambda x,y,z: -(x-0.64567)**2 - (y-0.41745)**2 - (z-0.11)**2
    starter_values = ([0,0,0], [0,1,0.5], [1,0,0.2], [0.9,0.9,0.9])

    for value_set in starter_values:
        predictor.append(value_set, real_func(*value_set))

    for _ in range(20):
        # predict the best x value(s) with the current data
        a, b = predictor.determine_max()
        print ("%s: %s" % (a, b))
        # actually calculate the real value associated with the prediction
        predictor.append(a, real_func(*a))
        # repeat. We know it's "good enough" when the answers converge about some x values.
