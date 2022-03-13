import numpy as np
import matplotlib.pyplot as plt
import itertools
from typing import Callable

# https://newton.cx/~peter/2014/03/elementary-gaussian-processes-in-python/

class EGO():
    '''Represents an Efficient Global Optimum predictor.
    Add values with EGO.add_point(y, x).
    Sample a range to predict with EGO.generate_predictions(prediction_xs).'''
    def __init__(self, num_fields:int, kernel:Callable[[float],float], predicted_noise:float, thetas:"tuple[float]"=None):
        '''inputs:
             num_fields: number of dimensions in each point of x.
             kernel: function(r) that provides correlatedness between two points separated by r.
                  example = np.exp(-0.5 * r**2), a square-exponent kernel
             predicted_noise: the amount of variance in the y values, as a fraction of the average.
             thetas: a tuple of floats representing the scale differences between dimensions of x.
                  example = (1, 1000) if x1 is in meters and x2 is in kilometers.
                  Larger thetas mean the difference matters more.
                  If not provided, the assumed value is 1 for each dimension.'''
        self.num_fields = num_fields
        self.kernel = kernel
        self.predicted_noise = predicted_noise

        if thetas is None:
            thetas = tuple(1 for _ in range(num_fields))

        if num_fields > 1:
            # delta_f is the distance between two multi-dimensional points
            #         = sqrt(delta_x1**2 + delta_x2**2 + ...)
            # We also adjust by that dimension's theta. Larger thetas mean the difference matters more.
            def delta_f(x1, x2):
                sum_of_sq = 0
                for i, theta in zip(range(num_fields), thetas):
                    sum_of_sq += ((x1[np.newaxis,:,i] - x2[i,:, np.newaxis]) * theta)**2 
                return np.sqrt(sum_of_sq)
            self.delta_f = delta_f
        else:
            # with only one dimension, we can skip the sqrt and **, since they cancel.
            self.delta_f = lambda x1, x2: x1[np.newaxis,:,0] - x2[0,:, np.newaxis]

        self.x = np.empty((0, num_fields))
        self.y = np.empty((0))

    def add_point(self, y:float, x):
        self.x = np.vstack((self.x, x))
        self.y = np.append(self.y, y)

    def gp_cov(self, x, predicted_noise):
        '''Return the covariance matrix of x and itself, with u added as noise.'''
        # shape of x: len(x), num_fields
        # Matrix of separations: r[i,j] = x[j] - x[i]
        r = self.delta_f(x, np.transpose(x)) # shape: len(x), len(x)
        u = predicted_noise * np.ones_like(x[:,0]) # shape: len(x)
        return self.kernel(r) + np.diag(u)

    def corr_noise(self, cov):
        '''Return a random sampling from the covariance matrix.'''
        uncorr_noise = np.random.normal(size=cov.shape[0])
        return np.dot(np.linalg.cholesky(cov), uncorr_noise)

    def generate_predictions(self, interp_x):
        '''Return estimates of y values and standard deviations for predictions interp_x.
           interp_x must be a numpy array of shape (#, 1),
           which can be done with old_interp_x[:,np.newaxis]'''
        # Generate the covariance matrix of data_x against itself.
        data_cov = self.gp_cov(self.x, self.predicted_noise) # shape: len(x), len(x)

        # Generate the covariance matrix of data_x against the prediction points.
        # Matrix of separations: r[i,j] = x[j] - x[i]
        r = self.delta_f(interp_x, np.transpose(self.x)) # shape: len(x), len(interp_x)
        di_cov = self.kernel(r) # shape: len(x), len(interp_x)
        
        # Determine the weights to apply to data_y points. Apply them.
        cinv = np.linalg.inv(data_cov) # shape: len(x), len(x)
        wt = np.dot(cinv, di_cov) # shape: len(x), len(interp_x)
        average_y = np.average(self.y)
        interp_y = np.dot(wt.T, self.y-average_y) + average_y # shape: len(interp_x)

        # generate the matrix of variances. Take the (matrix) square root to get the (matrix) standard deviation.
        interp_cov = self.kernel(0) - np.dot(di_cov.T, wt) # shape: len(interp_x), len(interp_x)
        #TODO: Is this where the vertical correction would apply?
        std_y = np.std(self.y)
        interp_u = np.sqrt(np.diag(std_y * interp_cov)) # shape: len(interp_x)

        return interp_y, interp_u

def sqexp_kernel(a, s, r):
    '''A square-exponent kernel. Provides a measure of correlatedness of two points separated by r.'''
    return a * np.exp(-0.5 * (r / s)**2)

def himmelblau(x1, x2):
    # Himmelblau's function
    # f(x, y) = (x**2 + y - 11)**2 + (x + y**2 - 7)**2
    # from -5 to 5 for both x and y
    # minimums at (3, 2), (-2.805, 3.131), (-3.779, -3.283), and (3.584, -1.848)
    return (x1**2 + x2 - 11)**2 + (x1 + x2**2 - 7)**2

def demo_2d():
    # Setup
    actual_noise = 0.01
    true_kern = lambda r: sqexp_kernel(1., 1., r)
    true_x = np.linspace(0, 10, 101) # 0, 0.1, 0.2, etc
    true_x = np.round(true_x, 1)

    predicted_noise = 0.005

    ego = EGO(1, true_kern, predicted_noise)

    fig = plt.figure()
    ax = fig.add_subplot(111)

    # The underlying signal -- there's a trend described by a Gaussian process, but no measurement error.
    true_cov = ego.gp_cov(true_x[:,np.newaxis], 1e-9) # note that the last argument is juuuust above zero - no noise.
    true_y = ego.corr_noise(true_cov) # a random sample from the covariance matrix

    # The data points that are actually gatherable, with noise.
    added_noise = np.random.normal(scale = actual_noise * np.ones_like(true_y))
    noisy_y = true_y + added_noise

    dict_func = {x:y for x, y in zip(true_x, noisy_y)}

    # The points we gather data from initially
    for x in (1.5, 5.5, 9.5):
        ego.add_point(dict_func[x], x)

    while True:
        # Our best guess of the underlying signal given the noisy measurements.
        interp_x = np.linspace(0, 10, 101) # The positions we predict at
        interp_x = np.round(interp_x, 1)
        interp_x = interp_x[:,np.newaxis]
        interp_y, interp_u = ego.generate_predictions(interp_x)

        ax.clear()
        ax.plot(ego.x, ego.y, 'o', label='data points')
        ax.plot(interp_x, interp_y, 'r', label='our guess')
        ax.plot(true_x, true_y, 'g', label='true data')
        ax.plot(interp_x, interp_y+interp_u, '--y')
        ax.plot(interp_x, interp_y-interp_u, '--y')
        ax.legend(loc="upper left")

        fig.show()

        max_pos = np.argmax(interp_y+interp_u)
        max_x = interp_x[max_pos, :]

        max_pos = np.argmax(interp_u)
        max_u = interp_x[max_pos, :]

        next_point = float(input(f"What point should be investigated next? (to 1 digit after decimal) Maybe {max_x} or {max_u}: "))
        if next_point == float(-1):
            break
        ego.add_point(dict_func[next_point], next_point)

def demo_3d():
    predicted_noise = 0.005
    true_kern = lambda x: sqexp_kernel(1.0, 1.0, x)
    true_func = lambda x: himmelblau(x[0], x[1])

    fig = plt.figure()
    ax = fig.add_subplot(projection='3d')

    ego = EGO(2, true_kern, predicted_noise)
    for x in ((2.5, 2.5), (-2.5, 2.5), (2.5, -2.5), (-2.5, -2.5)):
        ego.add_point(true_func(x), x)

    one_dim = tuple(range(-50, 50, 5))
    pairs = tuple(itertools.product(one_dim, one_dim))
    interp_x = np.asarray(pairs) / 10 # the positions we predict at

    while True:
        interp_y, interp_u = ego.generate_predictions(interp_x)

        data_points_x1 = tuple(ego.x[:,0])
        data_points_x2 = tuple(ego.x[:,1])
        guess_x1 = tuple(interp_x[:,0])
        guess_x2 = tuple(interp_x[:,1])

        ax.clear()
        ax.scatter(data_points_x1, data_points_x2, ego.y, marker='o', color='g', label='data points')
        ax.scatter(guess_x1, guess_x2, interp_y, marker='.', color = 'r', label='our guess')
        ax.scatter(guess_x1, guess_x2, interp_y+interp_u, marker=',', color='y', label='variance')
        ax.scatter(guess_x1, guess_x2, interp_y-interp_u, marker=',', color='y')

        ax.set_xlabel('x1')
        ax.set_ylabel('x2')
        ax.set_zlabel('y')

        fig.show()

        new_x1 = float(input("Next x1: "))
        new_x2 = float(input("Next x2: "))
        next_x = (new_x1, new_x2)
        next_y = true_func(next_x)
        ego.add_point(next_y, next_x)

if __name__ == '__main__':
    demo_3d()